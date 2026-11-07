"""Cross-model CPU integration on the existing bank/credit event kernel.

This is an explicit, initially serialized phase schedule, not a rescaling of
old Qwen results. Four-query Attention slots are padded for 3/1-query models;
physical work and useful work are separately reported. No model payloads.
"""
from pathlib import Path
from collections import Counter
import argparse, hashlib, importlib.util, json, math, sys, time, types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ceildiv = lambda a,b: (a+b-1)//b
load = lambda p: json.loads(Path(p).read_bytes())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return m


def libraries(root):
    # Supplied, version-pinned modules; never fetch a new uncontrolled simulator.
    sys.path.insert(0,str(root))
    from architecture_tlm.attention_digital_small_20261107 import adapter as attention
    from architecture_tlm.attention_digital_small_20261107 import profile as attention_price
    from architecture_tlm.ffn_digital_contract_20261107 import adapter as ffn
    from architecture_tlm.ffn_digital_contract_20261107.async_adapter import run_ffn
    mem=module('shape_host_memory',root/'base/architecture_tlm/unified_v6/shared_memory.py')
    return attention,attention_price,ffn,run_ffn,mem


def allocation(root,clock,scheme):
    from architecture_tlm.attention_digital_small_20261107.profile import profile
    from architecture_tlm.ffn_digital_contract_20261107.adapter import make_profile
    t=load(HERE.parent/'equal_area_100_250_20261107/TARGETS.json')['versions'][str(clock)]
    if scheme=='SC_ising':
        return dict(target=t,lanes=640 if clock==100 else 256,slices=40 if clock==100 else 16,
                    area55_mm2=t['target_area55_mm2'],status=t['target_status'])
    p=make_profile(clock,'BF16' if scheme=='BF16_dense' else 'W8')
    ap=profile(clock,'screen_full' if scheme=='W8_screen' else 'dense',8)
    components={}
    for c in t['digital_host_fixed_components']+p['fixed_components']+p['shared_components']+ap['fixed_components']:
        name=c['resource_id'];area=c['area55_mm2']
        if name in components and components[name]!=area:raise ValueError('conflicting area '+name)
        components[name]=area
    fixed=sum(components.values());unit=p['pool']['area55_mm2_per_slice']
    slices=max(n for n in p['legal_pool_slices'] if fixed+n*unit<=t['target_area55_mm2'])
    return dict(target=t,slices=slices,lanes=16*slices,components=components,
                area55_mm2=fixed+slices*unit,area_gap_percent=100*((fixed+slices*unit)/t['target_area55_mm2']-1),
                status='legal_total_area_not_exceeding_target',ffn_profile=p)


class MatrixPort:
    """Bind the delivered generator FFN to native DMA and physical SRAM.

    Operand reads really arbitrate; C4 states persist across K packets. This
    first integration deliberately waits for each operand packet, with no
    unpriced whole-tile DFF cache. More aggressive supply overlap is separate.
    """
    def __init__(self,host):self.host=host;self.h=host.h;self.a=Counter();self.busy={};self.context=[0.]*4
    def delay(self,n):return self.h.delay(n*self.host.period)
    def begin(self,p,l):
        self.p=p;self.l=self.host.ffn_layout(p['hidden'],p['intermediate']);self.context=[self.h.now]*4
        assert self.l['total_bytes']<=self.host.scratch.size
        yield from self.h.transfer(self.host.scratch,self.l['objects']['x']['offset'],p['hidden']*2,True,'digital_x_input')
        if p['path']=='W8':
            yield from self.delay(4+ceildiv(p['hidden'],32));self.a['host_input_quantize_elements']+=p['hidden']
    def memory(self,key,offset,size,write=False,tag='digital_operand'):
        obj=self.l['objects'][key]
        if offset<0 or offset+size>obj['bytes']:raise ValueError('object overflow '+key)
        return self.h.transfer(self.host.scratch,obj['offset']+offset,size,write,tag)
    def metadata(self,count):
        self.a['DRAM_metadata_bytes']+=count
        yield from self.h.fetch('digital_meta',0x700000000+self.host.layer_id*65536,count,self.host.scratch,
                               self.l['objects']['scales']['offset'],'digital_metadata')
    def load(self,slot,q):
        if slot in self.busy:raise ValueError('live weight slot overwrite')
        self.busy[slot]=q;done=self.host.mem.Signal()
        self.h.dma('digital_weights',self.host.weight_base+q['source_spans'][0][0],q['source_bytes'],
                   self.host.scratch,self.l['objects']['weight'+str(slot)]['offset'],'digital_weights',done.set,
                   spans=[(self.host.weight_base+a,n) for a,n in q['source_spans']])
        self.a['DRAM_weight_bytes']+=q['source_bytes']
        if False:yield
        return done
    def wait(self,ticket):yield ticket
    def release(self,slot):
        del self.busy[slot]
        if False:yield
    def consume(self,slot,q):
        p=self.p;perctx=4*p['pool_slices'];role=q['role'];self.host.mac[role]+=q['rows']*q['ks']
        self.a['MAC']+=q['rows']*q['ks']
        if p['path']=='W8':
            H,F=ceildiv(p['hidden'],64),ceildiv(p['intermediate'],64)
            prefix=0 if role=='Wg' else F*H if role=='Wu' else 2*F*H
            for out in range(q['row']//64,ceildiv(q['row']+q['rows'],64)):
                for kb in range(q['k']//64,ceildiv(q['k']+q['ks'],64)):
                    yield from self.memory('scales',prefix+out*ceildiv(q['K'],64)+kb,1,tag='digital_PoT_metadata')
        if q['integer']:
            yield from self.memory('weight'+str(slot),0,q['packed_bytes'])
            yield from self.memory('x',q['k']*10//8,80)
            yield from self.delay(1+(4 if q['last'] else 0));self.a['A9W8_DOT64']+=q['rows']
        else:
            lease=yield from self.host.pool.acquire('matrix:'+role,self.host.pool.lanes)
            perword=16//q['weight_B']
            for step in range(ceildiv(q['ks'],4)):
                for ctx in range(4):
                    nr=min(perctx,max(0,q['rows']-ctx*perctx))
                    if not nr:continue
                    if self.context[ctx]>self.h.now:yield from self.h.delay(self.context[ctx]-self.h.now)
                    off=(step*4//perword)*q['rows']*16+ctx*perctx*16
                    yield from self.host.attlib.parallel([
                        self.memory('weight'+str(slot),off,nr*16),
                        self.memory('z' if role=='Wd' else 'x',(q['k']+step*4)*2,8)])
                    self.context[ctx]=self.h.now+4*self.host.period
                    yield from self.delay(1)
                    key='W8_BF16_FMA' if p['path']=='W8' else 'BF16_FMA'
                    self.a[key]+=nr*min(4,q['ks']-4*step)
            if q['last']:
                yield from self.delay(3+ceildiv(q['rows']*3,p['reduction_units']))
                self.a['FP32_reduce_ADD']+=q['rows']*3
            self.host.pool.release(lease)
        if q['last']:
            key='y' if role=='Wd' else 'gu';width=2 if role=='Wd' else 4
            off=(p['intermediate']*4 if role=='Wu' else 0)+q['row']*width
            yield from self.memory(key,off,q['rows']*width,True,'digital_matrix_output')
    def nonlinear(self,count):
        # Five-stage measured pipeline, bounded blocks of NL_units, SRAM R/W.
        for start in range(0,count,self.p['NL_units']):
            n=min(self.p['NL_units'],count-start)
            yield from self.host.attlib.parallel([self.memory('gu',start*4,n*4),self.memory('gu',(count+start)*4,n*4)])
            yield from self.delay(5)
            yield from self.memory('z',start*2,n*2,True,'digital_nonlinear_z')
            self.a['SwiGLU']+=n
    def end(self):
        assert not self.busy
        yield from self.memory('y',0,self.p['hidden']*2,False,'digital_FFN_handoff')
        return dict(actions=dict(self.a))


class Host:
    def __init__(self,root,model,clock,scheme,backend,seed=17):
        self.root=root;self.model=model;self.clock=clock;self.scheme=scheme;self.seed=seed
        self.period=1000/clock;self.attlib,self.attprice,self.ffnlib,self.run_ffn,self.mem=libraries(root)
        self.resource=allocation(root,clock,scheme);self.mac=Counter();self.phases=[]
        t=self.resource['target'];n=t['SRAM_banks'];front=n-96
        self.h=self.mem.SharedMemory(backend,credit=256,response_bytes=16384,issue_per_cycle=24,
            issue_period_ns=self.period,response_buffered=False,return_banks=4,
            memory_config=dict(capacity=t['SRAM_KiB']*1024,banks=n,clock_hz=clock*1e6,
                fabric_GBs=512.,read_pJ=10.0527 if clock==100 else 12.0293,write_pJ=13.9599 if clock==100 else 16.2931))
        self.h.common_period_ns=self.period
        # Direct-return DMA uses 16KiB DFF holding already priced, not SRAM.
        self.h.mem.regions.clear();self.h.mem.top=0;self.h.mem.bank_allocated=[0]*n
        cursor=[0]
        def reg(name,size):
            # Rotate the starting bank across objects; otherwise independent
            # ceil rounding falsely overfills a full-capacity front partition.
            order=tuple(range(front));shift=cursor[0]%front;order=order[shift:]+order[:shift]
            result=self.h.mem.region(name,size,order);cursor[0]+=ceildiv(size,16);return result
        self.vector=reg('vectors',131072);self.norm=reg('norm_double',32768)
        self.scratch=reg('FFN_weight_or_digital_scratch',262144)
        self.state=reg('crossK_state',98304)
        self.ordinary=reg('ordinary_operands',163840 if clock==100 else 65536)
        self.attregions=[self.h.mem.region('Attention'+str(g),49152,range(front+g*12,front+(g+1)*12)) for g in range(8)]
        self.pool=self.attlib.SharedPool(self.h,self.resource['lanes'])
        self.weight_base=0x100000;self.layer_id=0;self.layer_stride=0x20000000;self.port=MatrixPort(self)
        self.reference=load(root/'inputs/SAMPLES.json')['samples']
        self.ffn_profiles=[];self.att_actors=[];self.SC_stats=[]
    def ffn_layout(self,H,F):
        # Scale metadata uses original64x64 indexing; no hardcoded20/32KiB limit.
        sizes=[('weight0',32768),('weight1',32768),('x',ceildiv(H*2,4096)*4096),
               ('gu',ceildiv(F*8,4096)*4096),('z',ceildiv(F*2,4096)*4096),
               ('scales',ceildiv(3*(H//64)*(F//64),4096)*4096),('y',ceildiv(H*2,4096)*4096)]
        objects={};cur=0
        for name,size in sizes:objects[name]=dict(offset=cur,bytes=size);cur+=size
        if cur>262144:raise ValueError('digital scratch exceeds existing256KiB')
        return dict(objects=objects,total_bytes=cur)
    def phase(self,name,gen,layer):
        t=self.h.now;self.attlib.drive(self.h,gen)
        self.phases.append(dict(layer=layer,name=name,start_ns=t,end_ns=self.h.now,ns=self.h.now-t))
    def matrix(self,role,rows,k):
        p=self.ffnlib.make_profile(self.clock,'BF16',self.resource['slices'])
        p.update(hidden=k,intermediate=max(p['matrix_mapping']['output_tile'],k));self.port.p=p;self.port.l=self.ffn_layout(k,p['intermediate'])
        self.port.context=[self.h.now]*4
        # Matrices larger than GU scratch (lm_head) stream output blocks, not a
        # full vocabulary vector resident in SRAM. No full logits cache here.
        base=0
        for row in range(0,rows,p['matrix_mapping']['output_tile']):
            nr=min(rows-row,p['matrix_mapping']['output_tile'])
            for q in self.ffnlib.packets(p,'Wd',nr,k,base):
                q['row']=0;q['last']=False
                ticket=yield from self.port.load(0,q);yield ticket
                yield from self.port.consume(0,q);yield from self.port.release(0)
            yield from self.h.delay((4+ceildiv(nr*3,32))*self.period)
            yield from self.h.transfer(self.vector,0,nr*2,True,role+'_output')
            base+=nr*k*2
        self.mac[role]+=rows*k
        self.weight_base+=ceildiv(rows*k*2,4096)*4096
    def digital_ffn(self):
        H,F=self.model['hidden'],self.model['ffn'];path='BF16' if self.scheme=='BF16_dense' else 'W8'
        p=self.ffnlib.make_profile(self.clock,path,self.resource['slices'])
        self.port.a=Counter();result=yield from self.run_ffn(p,self.port,H,F)
        self.ffn_profiles.append(dict(profile=p,result=result));self.weight_base+=ceildiv(H*F*(6 if path=='BF16' else 3),4096)*4096
    def sc_ffn(self):
        # Existing output-batched common actor, instance-local symbol binding.
        source=self.root/'architecture_tlm/sc_actor_source.py'
        raw=source.read_text();raw=raw.replace('from architecture_tlm.unified_v6.shared_memory import Signal,align_time','Signal=MEM.Signal\nalign_time=MEM.align_time')
        for old,new in [('align_time(h.now,4)','align_time(h.now,PERIOD)'),('ports[port]=begin+16','ports[port]=begin+4*PERIOD'),("stats['sample_core_ns']+=(samples+2)*4","stats['sample_core_ns']+=(samples+2)*PERIOD"),('65536+20000','65536+META')]:
            assert old in raw,old;raw=raw.replace(old,new)
        env=dict(MEM=self.mem,PERIOD=self.period,META=ceildiv(3*(self.model['hidden']//64)*(self.model['ffn']//64),64)*64)
        exec(compile(raw,str(source),'exec'),env)
        m=types.SimpleNamespace(h=self.h,model=self.model,common_cores=6 if self.clock==100 else 3,
            output_batch=96,state_ports=2,state_port_free=[self.h.now]*2,common_prefetched=set(),common_stats=[],
            vector=self.vector,common_state=self.state,actions=Counter(),kernel_active=Counter(),_parallel=self.attlib.parallel)
        F=self.model['ffn']//64;H=self.model['hidden']//64
        def tiles(mode):
            outs,blocks=(F,H) if mode=='GU' else (H//2,F)
            if mode=='Wd':return [(o,k) for k in range(blocks) for o in range(outs)],outs,blocks
            count=ceildiv(outs,96);small,extra=divmod(outs,count);alltiles=[];start=0
            for b in range(count):
                size=small+(b<extra);alltiles.extend((o,k) for k in range(blocks) for o in range(start,start+size));start+=size
            return alltiles,outs,blocks
        ordered={mode:{ok:i for i,ok in enumerate(tiles(mode)[0])} for mode in ('GU','Wd')}
        def spans(layer,mode,out,k):return [(self.weight_base+(0 if mode=='GU' else 2*F*H*4096)+ordered[mode][out,k]*8192,8192)]
        def transfer(owner,spans_,slot,off,tag):
            yield from self.h.fetch(owner,spans_[0][0],8192,self.scratch,slot*131072+off,tag,spans=spans_)
        def delay(ns,tag):
            cycles=ns/10
            if tag=='GU_fixed8_quant_macro':cycles=4
            elif tag=='final_BF16_macro':cycles=3
            yield from self.h.delay(cycles*self.period)
        m._tiles=tiles;m._weight_spans=spans;m.load=transfer;m.delay=delay
        meta=3*F*H
        yield from self.h.fetch('scmeta',self.weight_base+3*F*H*4096,meta,self.vector,65536,'SC_metadata')
        yield from self.h.transfer(self.vector,0,self.model['hidden']*2,True,'SC_input')
        yield from self.h.delay((4+H)*self.period)
        yield from env['common_stage'](m,0,'GU');yield from env['common_stage'](m,0,'Wd')
        self.SC_stats.append(dict(stages=m.common_stats,actions=dict(m.actions),frames=dict(m.kernel_active)))
        assert m.actions['SC_equivalent_MAC']==3*self.model['hidden']*self.model['ffn']
        self.weight_base+=ceildiv(3*self.model['hidden']*self.model['ffn']+meta,4096)*4096
    def attention(self,rows,layer):
        # Slots remain4Q even for1/3Q groups: explicit padding, no phantom
        # speedup from changing hardware. Logical KV groups schedule in waves.
        mode='screen_full' if self.scheme in ('W8_screen','SC_ising') else 'dense'
        actor=self.attlib.Attention(self.h,self.pool,self.attregions,self.attlib.Config(self.clock,mode,8,2048,rescale='trace'))
        before=self.h.now
        if self.scheme=='SC_ising':
            for start in range(0,len(rows),8):
                yield from self.attlib.parallel([self.prob_group(actor,w,g,rows[g],layer) for w,g in enumerate(range(start,min(start+8,len(rows))))])
        else:
            for start in range(0,len(rows),8):
                yield from self.attlib.parallel([actor.group(w,g,rows[g]) for w,g in enumerate(range(start,min(start+8,len(rows))))])
        self.att_actors.append(dict(time_ns=self.h.now-before,actions=dict(actor.actions),audit=actor.audit,
                                   padded_heads=4*self.model['kv_heads'],useful_heads=self.model['q_heads']))
    def prob_group(self,a,w,g,row,layer):
        h=self.h;r=a.regions[w];n=2048;ids=row['candidates'];base=row['base']
        yield from a.append(r,base,True);yield from h.transfer(r,a.QUERY,1024,True,'Q_arrival')
        # r32 on this first cross-model mapping, also at250; report difference
        # from current r16 preset rather than silently changing the trace.
        yield from a.coarse(r,base,g,row['dimensions'])
        for b in range(4):
            spans=[(base+t*256,256) for t in ids[b*32:(b+1)*32]]
            yield from h.fetch('selectedK'+str(g),spans[0][0],8192,r,a.K[b%2],'selected_K',spans=spans)
            yield from a.transpose(r,b%2)
            yield from h.transfer(r,a.QUERY,1024,False,'selected_query_load')
            for cluster in range(2):
                packets=[(a.SCRATCH+self.attlib.packed_word(cluster*4+c,d),c) for d in range(32) for c in range(4)]
                lease=yield from self.pool.acquire('selected_QK',64);yield from a.delay(16)
                yield from a.stream(r,packets,'exact_QK','selected',lease);self.pool.release(lease)
                a.actions['fpadd']+=192;yield from a.delay(68)
                yield from h.transfer(r,a.STATE+b*512+cluster*256,256,True,'selected_scores')
        qpg=self.model['q_heads']//self.model['kv_heads'];traces=[]
        for head in range(qpg):
            key='ab_both/%d/%d/%d'%(self.seed,g%8,(layer%3)*4+head)
            traces.append(self.reference[key])
        # Wide max/sub/gap u8/P8 frontend: explicit macro, not scalarS12 input.
        yield from h.transfer(r,a.STATE,2048,False,'wide_score_front_read')
        yield from a.delay(12+ceildiv(qpg*128,4))
        latency=max(t['cycles']-t['front'] for t in traces)
        yield from a.delay(latency)
        a.actions['sampler_cycles']+=sum(t['cycles']-t['front'] for t in traces)
        a.actions['sampler_hits']+=sum(t['hits'] for t in traces)
        a.actions['sampler_samples']+=64*qpg
        unique=sorted({ids[i] for t in traces for i in t['indices']});cache={v:j for j,v in enumerate(unique)}
        spans=[(base+2*n*256+v*256,256) for v in unique]
        yield from h.fetch('sampleV'+str(g),spans[0][0],len(unique)*256,r,0,'sample_V',spans=spans)
        lanes=128 if self.clock==100 else 64
        for t in traces:
            for i in t['indices']:
                yield from h.transfer(r,cache[ids[i]]*256,256,False,'sample_V_operand')
                yield from a.delay(ceildiv(128,lanes))
            yield from a.delay(4)
        a.actions['sample_ADD']+=qpg*64*128;a.actions['unique_V']+=len(unique);a.actions['completed_groups']+=1
        yield from h.transfer(r,a.STATE,qpg*256,True,'sample_output')


def run(args):
    root=args.runtime.resolve();sys.path.insert(0,str(root));libraries(root)
    models=load(HERE/'CURRENT_WORKLOAD_PLAN.json')['models'];m=models[args.model]['shape']
    back=module('shape_native_backend',root/'base/architecture_tlm/digital_baselines_20261104/backend.py')
    if args.native:
        profile=next(p for p in load(root/'base/profiles/PROFILES.json') if p['name']=='derived8533')
        assert sha(root/'base/profiles/derived8533.yaml')==profile['sha256']
        backend=back.RamulatorBackend(root/'base/liblpbridge.so',root/'base/profiles/derived8533.yaml',profile['period_ns'],256)
    else:
        mem=libraries(root)[-1];backend=mem.AnalyticDRAM(latency_ns=60,bandwidth_GBs=136.4606)
    h=Host(root,m,args.clock,args.scheme,backend,args.seed)
    fixture=load(root/'inputs/SHAPE_FIXTURES.json')[args.model]
    layers=m['layers'] if args.layers==0 else args.layers
    started=time.time()
    if args.component=='FFN':
        h.phase('FFN',h.sc_ffn() if args.scheme=='SC_ising' else h.digital_ffn(),0)
        nohead=h.h.now;layers=1
    elif args.component=='Attention':
        rows=[dict(r,base=0x800000000+g*0x400000,max_changes=r['screen_full_max_changes' if args.scheme in ('W8_screen','SC_ising') else 'dense_max_changes']) for g,r in enumerate(fixture)]
        h.phase('Attention',h.attention(rows,0),0);nohead=h.h.now;layers=1
    else:
        full_run(h,args,m,fixture,layers)
        nohead=next((p['start_ns'] for p in h.phases if p['name']=='lm_head'),h.h.now)
    assert not h.pool.live and not h.pool.queue and not h.h.pending and not h.h.descriptors and not h.h.mem.queue
    result=dict(status='completed',scope='cross_model_initial_integration_not_original_preset',component=args.component,model=args.model,shape=m,clock_MHz=args.clock,scheme=args.scheme,
        layers_executed=layers,seed=args.seed,time_ms=h.h.now/1e6,time_without_head_ms=nohead/1e6,
        phases=h.phases,resource=h.resource,matrix_work=dict(h.mac),SC=h.SC_stats,digital_FFN=h.ffn_profiles,Attention=h.att_actors,
        SRAM=h.h.mem.report(h.h.now),DMA=dict(h.h.count),by_kind={k:dict(v) for k,v in h.h.by_kind.items()},backend=backend.finish(h.h.now),
        input_fixture_sha256=sha(root/'inputs/SHAPE_FIXTURES.json'),reference_sampler_sha256=sha(root/'inputs/SAMPLES.json'),
        limitations=['synthetic/reference traces,not actual text/model PPL','fixed4Q slot padding explicitly retained',
        'phase-serial first mapping,no cross-layer prefetch','Attention r32 also at250,not current r16 preset',
        'PV producer/consumer first mapping serialized;no claim current optimized latency',
        '250 shortT FFN PPA pending;no failed price accepted','norm/RoPE/residual latency macros;no free FP32 ideal arithmetic'])
    result['wall_seconds']=time.time()-started
    args.out.mkdir(parents=True,exist_ok=False)
    for name,value in [('RESULT.json',result),('VALIDATION.json',dict(status='PASS',queues_drained=True,native=args.native,layers=layers))]:
        (args.out/name).write_bytes((json.dumps(value,indent=2)+'\n').encode())
    (args.out/'SEAL.json').write_bytes((json.dumps(dict(files_sha256={p.name:sha(p) for p in args.out.iterdir()}),indent=2)+'\n').encode())


def full_run(h,args,m,fixture,layers):
    h.phase('embedding',h.h.fetch('embedding',0x80000000000,m['hidden']*2,h.vector,0,'embedding'),-1)
    for l in range(layers):
        h.layer_id=l;h.weight_base=0x100000+l*h.layer_stride
        h.phase('norm_and_RoPE_macro',h.h.delay((4+ceildiv(m['hidden'],32)+ceildiv(m['q_heads']*128,32))*h.period),l)
        h.phase('QKV',h.matrix('QKV',(m['q_heads']+2*m['kv_heads'])*128,m['hidden']),l)
        rows=[dict(r,base=0x800000000+l*0x10000000+g*0x400000,
                   max_changes=r['screen_full_max_changes' if args.scheme in ('W8_screen','SC_ising') else 'dense_max_changes']) for g,r in enumerate(fixture)]
        h.phase('Attention',h.attention(rows,l),l)
        h.phase('O',h.matrix('O',m['hidden'],m['q_heads']*128),l)
        h.phase('FFN',h.sc_ffn() if args.scheme=='SC_ising' else h.digital_ffn(),l)
        h.phase('residual_macro',h.h.delay((4+ceildiv(m['hidden'],32))*h.period),l)
        print(json.dumps(dict(layer=l,time_ms=h.h.now/1e6)),flush=True)
    h.weight_base=0x600000000
    if not args.skip_head:h.phase('lm_head',h.matrix('lm_head',m['vocab'],m['hidden']),layers)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--model',choices=('qwen3_4b','llama32_3b','deepseek_7b'),required=True)
    p.add_argument('--scheme',choices=('SC_ising','BF16_dense','W8_dense','W8_screen'),required=True)
    p.add_argument('--clock',type=int,choices=(100,250),required=True);p.add_argument('--seed',type=int,default=17)
    p.add_argument('--layers',type=int,default=1);p.add_argument('--native',action='store_true');p.add_argument('--skip-head',action='store_true')
    p.add_argument('--component',choices=('full','FFN','Attention'),default='full')
    p.add_argument('--out',type=Path,required=True);run(p.parse_args())
