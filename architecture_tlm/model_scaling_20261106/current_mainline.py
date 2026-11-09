"""Model shape adapter around the existing current100/250 host actors.

No new DRAM/SRAM timing kernel. Preserve finite ordinary FIFO, early refill,
the measured shared FFN frame service, and sampled-PV producer/consumer.
"""
from pathlib import Path
from types import MethodType
from collections import Counter
import hashlib,importlib.util,inspect,json,math,sys,types

ceildiv=lambda a,b:(a+b-1)//b
load=lambda p:json.loads(Path(p).read_bytes())
def mod(name,path,package=False):
    if package and not path.exists():
        m=types.ModuleType(name);m.__path__=[str(path.parent)];sys.modules[name]=m;return m
    s=importlib.util.spec_from_file_location(name,path,submodule_search_locations=[str(path.parent)] if package else None)
    m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def environment(snapshot,runtime,deps,clock):
    host=snapshot/'host';boot=mod('cross_current_boot',host/'architecture_tlm/sram1216_20261106/250MHz/bootstrap.py')
    identity=boot.bootstrap(runtime,deps,snapshot/'owner_front')
    import architecture_tlm
    architecture_tlm.__path__[:0]=[str(host/'architecture_tlm'),str(snapshot/'modules/architecture_tlm')]
    if clock==100:
        mod('architecture_tlm.sram1216_20261106',host/'architecture_tlm/sram1216_20261106/__init__.py',True)
        owner=mod('cross_current_owner100',snapshot/'modules/architecture_tlm/attention_resource_compaction_20261107/__init__.py',True)
        owner=mod('cross_current_owner100.model',snapshot/'modules/architecture_tlm/attention_resource_compaction_20261107/model.py')
        from architecture_tlm.module_refresh_20261107.host100 import make_model
        factory=lambda backend,**kw:make_model(backend,owner_install=owner.install,attention_source=snapshot/'owner_front',**kw)
    else:
        from whole250.model import make_model
        factory=make_model
    import whole250.ffn_actor
    return factory,identity

def vector_decoder(meta):
    def address(offset,size):
        if offset>=196608:
            g,inside=divmod(offset-196608,6144)
            if g<8 and inside>=5120 and inside+size<=6144:return 49152+g*1024+inside-5120
        if 131072<=offset and offset+size<=131072+8192:return 32768+offset-131072
        if 65536<=offset and offset+size<=65536+meta+1024:return offset
        if 0<=offset and offset+size<=32768:return offset
        raise ValueError(('unmapped cross-model vector',offset,size,meta))
    return address

def bind_wrapped_vector_decoder(submit,decoder):
    """Reach the real compact-SRAM function beneath the100MHz QK wrapper."""
    pending=[submit];seen=set();bound={}
    while pending:
        item=pending.pop();fn=getattr(item,'__func__',item)
        if id(fn) in seen:continue
        seen.add(id(fn))
        if not hasattr(fn,'__code__'):continue
        g=fn.__globals__
        if 'vector_address' in fn.__code__.co_names and callable(g.get('vector_address')):
            g['vector_address']=decoder;bound[id(g)]=g.get('__name__','unknown')
        for cell in fn.__closure__ or ():
            value=cell.cell_contents
            if hasattr(getattr(value,'__func__',value),'__code__'):pending.append(value)
    assert len(bound)==1,('expected one compact vector decoder',bound)
    return list(bound.values())

def rebuild(model,shape,logical_layers,scheme):
    """Hardware remains fixed; new external tensor sizes and live-object map."""
    from architecture_tlm.unified_v6.shared_decode import AddressSpace
    m=model;H,F,Q,KV,D,V=[shape[k] for k in ('hidden','ffn','q_heads','kv_heads','head_dim','vocab')]
    assert H%128==0 and F%64==0 and D==128 and KV%8==0 and Q%KV==0
    m.model=dict(shape,layers=logical_layers);m.cross_qpg=Q//KV;m.cross_scheme=scheme
    m.cross_has_qknorm=(shape['hidden']==2560);m.a=AddressSpace();m.weight_bases={};m.kv_bases={}
    m.cross_kv_bases={};meta=3*(H//64)*(F//64);m.cross_meta=ceildiv(max(meta,32768),4096)*4096
    m.cross_gu_scale=20000 if meta<=20000 else ceildiv(meta,64)*64
    assert 65536+m.cross_gu_scale+F//64<=m.vector.size
    for l in range(logical_layers):
        for name,o,k,wb in [('QKV',(Q+2*KV)*D,H,2),('O',H,Q*D,2),('g',F,H,2 if scheme=='BF16_dense' else 1),
            ('u',F,H,2 if scheme=='BF16_dense' else 1),('down',H,F,2 if scheme=='BF16_dense' else 1)]:
            m.weight_bases[l,name]=m.a.alloc('L%d/%s'%(l,name),o*k*wb)
        m.weight_bases[l,'metadata']=m.a.alloc('L%d/scales'%l,m.cross_meta)
        for g in range(KV):m.cross_kv_bases[l,g]=m.a.alloc('L%d/KV%d'%(l,g),3*m.N*256)
    m.lm_base=m.a.alloc('lm_head',V*H*2)
    n=m.norm_store;n.d=H;n.layers=logical_layers;n.stride=4*H+(512 if m.cross_has_qknorm else 0)
    assert n.stride<=16384
    n.logical_bytes=n.layers*n.stride+2*H;n.external=m.a.alloc('normalization_weights',n.logical_bytes)
    if scheme=='SC_ising':
        # The existing decoder is retained, with wider metadata/residual bounds.
        m.h.mem.submit.__globals__['vector_address']=vector_decoder(m.cross_meta)
        if m.cross_clock==100 and H>2560:
            m.cross_decoder_bindings=bind_wrapped_vector_decoder(m.h.mem.submit,vector_decoder(m.cross_meta))
    else:
        # Digital module uses physical local offsets. Reuse the exact same
        # banks/ports, bypass only the SC semantic address decoder.
        raw=type(m.h.mem).submit.__get__(m.h.mem);address=vector_decoder(m.cross_meta)
        def submit(region,offset,size,write,tag,callback):
            if region is m.vector:offset=address(offset,size)
            if offset<0 or offset+size>region.size:raise ValueError('digital physical SRAM overflow '+tag)
            return raw(region,offset,size,write,tag,callback)
        m.h.mem.submit=submit
    def rope(self):
        layer=self.norm_active_layer
        if self.cross_has_qknorm:yield from n.headnorm(layer)
        else:n.slots[layer%2]['uses'].add('qk') # no such parameter in this model
        count=(Q+KV)*D*2
        yield from self.h.transfer(self.vector,0,count,False,'QK_norm_rope_input')
        cycles=ceildiv((Q+KV)*160,40)
        yield from self.delay(cycles*10,'RoPE_headnorm_macro')
        yield from self.h.transfer(self.vector,0,count,True,'QK_norm_rope_output')
    m.rope=MethodType(rope,m)
    def append(self,l,g,screen):
        # Logical KV group is distinct from its reused physical worker slot.
        # Query padding stays local; never read another logical head as padding.
        h=self.h;r=self.att[g];base=self.kv_bases[l,g];logical=self.cross_wave_start+g
        qbytes=Q*256;kvbytes=KV*256
        for label,source,target in [('K',qbytes+logical*256,base),('V',qbytes+kvbytes+logical*256,base+2*self.N*256)]:
            yield from h.transfer(self.vector,source,256,False,label+'_append_input')
            yield from h.transfer(r,114688,256,True,label+'_append_source')
            yield from h.fetch('Attention'+str(g),target+(self.N-1)*256,256,r,114688,label+'_append',write=True)
        yield from h.transfer(self.vector,logical*self.cross_qpg*256,self.cross_qpg*256,False,'Q_to_attention')
        yield from h.transfer(self.vector,196608+g*6144+5120,1024,True,'Q_local_fill')
        if screen:
            yield from h.fetch('Attention'+str(g),base+(self.N-32)*256,8192,r,114688,'K_block_for_transpose')
            yield from h.transfer(r,114688,8192,False,'K_transpose_read')
            yield from self.delay(2560,'K_transpose_macro')
            yield from h.transfer(r,114688,8192,True,'K_transpose_write')
            spans=[(base+self.N*256+d*self.N*2+(self.N-32)*2,64) for d in range(128)]
            yield from h.fetch('Attention'+str(g),spans[0][0],8192,r,114688,'K_feature_append',write=True,spans=spans)
    m._append=MethodType(append,m)
    # Reuse current shared actor, changing only model-dependent metadata base
    # and its frequency parameter. Explicit replacement receipts are frozen.
    source=inspect.getsource(sys.modules['whole250.ffn_actor'])
    source=source.replace('core_contract(250)','core_contract(CLOCK)')
    source=source.replace('65536+20000','65536+self.cross_gu_scale')
    source=source.replace('align_time(h.now,4)','align_time(h.now,PERIOD)').replace('ports[port]=begin+16','ports[port]=begin+4*PERIOD')
    env=dict(CLOCK=m.cross_clock,PERIOD=1000/m.cross_clock)
    exec(compile(source,'<current_shared_actor_shape_binding>','exec'),env)
    m._common_stage=MethodType(env['common_stage'],m)
    from architecture_tlm.attention_supply_front_20261107 import pv_stream
    src=inspect.getsource(pv_stream)
    src=src.replace("for head in range(4)]","for head in range(self.cross_qpg)]")
    src=src.replace("self.actions['sampler_queries']+=4","self.actions['sampler_queries']+=self.cross_qpg")
    src=src.replace("self.actions['sample_output_BF16']+=512","self.actions['sample_output_BF16']+=self.cross_qpg*128")
    src=src.replace("yield from h.transfer(r,122880,1024,True,'attention_output')","yield from h.transfer(r,122880,self.cross_qpg*256,True,'attention_output')")
    env=dict(pv_stream.__dict__);exec(compile(src,'<current_PV_active_heads>','exec'),env)
    m.attention_group=MethodType(env['sampled_explicit'],m)
    return m

def digital_install(m,snapshot,shape,clock,scheme):
    """Delivered digital modules, actual shared pool and finite FIFO supply."""
    from architecture_tlm.attention_digital_small_20261107 import adapter as A
    from architecture_tlm.ffn_digital_contract_20261107 import adapter as F
    from architecture_tlm.ffn_digital_contract_20261107.async_adapter import run_ffn,SharedPoolPort
    old=mod('cross_old_shape_glue',snapshot/'glue/execution.py')
    old.HERE=snapshot/'glue'
    target=load(snapshot/'architecture_tlm/equal_area_100_250_20261107/TARGETS.json')['versions'][str(clock)]
    path='BF16' if scheme=='BF16_dense' else 'W8'
    from architecture_tlm.attention_digital_small_20261107.profile import profile
    gu_units=32 if clock==100 and path=='W8' else 16
    fp=F.make_profile(clock,path,gu_units=gu_units);ap=profile(clock,'screen_full' if scheme=='W8_screen' else 'dense',8)
    components={}
    for c in target['digital_host_fixed_components']+fp['fixed_components']+fp['shared_components']+ap['fixed_components']:
        v=c['area55_mm2']
        if c['resource_id']=='host_projection_FIFO':v=16384*.0000483721875
        if c['resource_id'] in components:assert components[c['resource_id']]==v
        components[c['resource_id']]=v
    unit=fp['pool']['area55_mm2_per_slice'];fixed=sum(components.values())
    fifo_capacity=lambda n:ceildiv(max(16384,n*256+256),1024)*1024
    payload_area=lambda n:fifo_capacity(n)*.0000483721875
    fixed_without_fifo=fixed-components['host_projection_FIFO']
    slices=max(n for n in fp['legal_pool_slices'] if fixed_without_fifo+payload_area(n)+n*unit<=target['target_area55_mm2'])
    fifo_bytes=fifo_capacity(slices);components['host_projection_FIFO']=payload_area(slices);fixed=sum(components.values())
    fp=F.make_profile(clock,path,slices,gu_units=gu_units);fp['source_layout']='offline_packet_packed'
    fp['integer_DMA_K64_blocks']=4
    m.cross_allocation=dict(target_area55_mm2=target['target_area55_mm2'],components=components,slices=slices,lanes=slices*16,
        area55_mm2=fixed+slices*unit,area_gap_percent=100*((fixed+slices*unit)/target['target_area55_mm2']-1),
        projection_FIFO_payload_bytes=fifo_bytes,projection_weight_slot_bytes=131072)
    m.cross_pool=A.SharedPool(m.h,slices*16)
    m.resource_contract.update(scheme=scheme,FFN_shared_cores=0,common_FFN_cores=0,
        GU_samples=0,Wd_samples=0,ordinary_FMA_lanes=slices*16,independent_QK_lanes=0,
        sampler_cores=0,PV_ADD_lanes=0,FFN_integer_GU_units=gu_units if path=='W8' else 0,
        FFN_nonlinear_units=fp['NL_units'],digital_Attention_slots=8,
        canonical_shared_pool='ordinary_BF16_FMA_pool',SC_hardware_charged=False,
        SRAM_roles='same physical capacity;CIM-bank regions reused as ordinary SRAM',
        routing_base='SC constructor only supplies common memory;digital actors andarea ledger authoritative')
    # Ordinary matrices reuse the existing two128KiB CIM-bank regions when
    # digital FFN is inactive. The64/160KiB original ordinary slots are not
    # claimed as extra capacity or extra arrays. DigitalFFN follows O retirement.
    m.cross_projection_weights=m.cim_weight
    m._pool=MethodType(lambda self,l,n:self.cross_projection_weights,m)
    from architecture_tlm.attention_supply_front_20261107 import ordinary_pool,finite_supply
    src=inspect.getsource(ordinary_pool)
    src=src.replace("lanes not in (128,192,256,320,384,448,512,640)","(lanes%64!=0 or lanes>2048)")
    src=src.replace('output_tile=lanes//k_parallel*4','output_tile=min(lanes//k_parallel*4,131072//(k_parallel*16*2))')
    env=dict(ordinary_pool.__dict__);exec(compile(src,'<current_digital_projection_pool>','exec'),env)
    kp=8 if clock==100 else 4;env['install'](m,slices*16,kp,True,1000/clock,4,True)
    assert m.ordinary_pool_contract['FIFO_payload_bytes']<=fifo_bytes
    m.ordinary_pool_contract['allocated_FIFO_payload_bytes']=fifo_bytes
    m.ordinary_pool_contract['weight_slot_capacity_bytes']=131072
    from architecture_tlm.digital_baselines_20261104.model import BaselineDecode
    m.reduction_cycles=lambda outputs,leaves=kp:BaselineDecode.reduction_cycles(outputs,leaves,fp['reduction_units'])
    projection=m.digital_matrix
    def shared_projection(self,l,name,rows,k,element=2):
        lease=yield from self.cross_pool.acquire('projection:'+name,slices*16)
        try:yield from projection(l,name,rows,k,element)
        finally:self.cross_pool.release(lease)
    m.digital_matrix=MethodType(shared_projection,m)
    # Expand only the word-reuse factor for INT8 readout:16 stored codes per
    # physical16B word, rather than8 BF16 values. Each word is consumed4 times.
    src=inspect.getsource(finite_supply.consume_tile)
    src=src.replace('credits=8,on_last=None','credits=8,weight_B=2,on_last=None')
    src=src.replace('bundle=8//kp','bundle=(16//weight_B)//kp')
    src=src.replace('term*kp//8','term*kp//(16//weight_B)')
    env=dict(finite_supply.__dict__);exec(compile(src,'<current_INT8_word_reuse>','exec'),env);consume_tile=env['consume_tile']
    class Facade:
        h=m.h;attlib=A;mem=sys.modules['architecture_tlm.unified_v6.shared_memory'];pool=m.cross_pool
        ffn_layout=lambda self,H,F:old.Host.ffn_layout(self,H,F)
        layer_id=0;weight_base=0;mac=Counter()
        scratch=m.cim_weight[0]
    facade=Facade();facade.clock=clock;facade.period=1000/clock;facade.model=shape
    class Port(old.MatrixPort):
        def load(self,slot,q):
            if not q['integer']:
                return (yield from super().load(slot,q))
            assert slot not in self.busy;self.busy[slot]=q;done=self.host.mem.Signal()
            self.a['DRAM_weight_bytes']+=q['source_bytes'];base=self.l['objects']['weight'+str(slot)]['offset']
            pending=[0]
            def operands_ready():
                pending[0]-=1
                if pending[0]==0:done.set()
            def landed():
                offset=q['k']*10//8;xo=self.l['objects']['x']['offset']+offset;xb=q['ks']*10//8
                jobs=[(m.cim_weight[0],base,q['packed_bytes'],'digital_integer_weight_FIFO'),
                    (m.cim_weight[xo//131072],xo%131072,xb,'digital_integer_x_FIFO')]
                H,Fb=ceildiv(self.p['hidden'],64),ceildiv(self.p['intermediate'],64)
                prefix=0 if q['role']=='Wg' else Fb*H
                for out in range(q['row']//64,ceildiv(q['row']+q['rows'],64)):
                    for kb in range(q['k']//64,ceildiv(q['k']+q['ks'],64)):
                        address=self.l['objects']['scales']['offset']+prefix+out*H+kb
                        jobs.append((m.cim_weight[address//131072],address%131072,1,'digital_integer_scale_FIFO'))
                pending[0]=len(jobs)
                for region,off,n,tag in jobs:self.h.mem.submit(region,off,n,False,tag,operands_ready)
            self.h.dma('digital_weights',self.host.weight_base+q['source_spans'][0][0],q['source_bytes'],m.cim_weight[0],base,
                'digital_weights',landed,spans=[(self.host.weight_base+a,n) for a,n in q['source_spans']])
            if False:yield
            return done
        def nonlinear(self,count):
            pending=[];index=0;period=1000/clock;units=self.p['NL_units'];F=self.p['intermediate']
            while index<count or pending:
                before=self.h.now
                if pending and pending[0][0]<=self.h.now+1e-7:
                    _,first,n=pending.pop(0)
                    yield from self.memory('z',first*2,n*2,True,'digital_nonlinear_z')
                if index<count and len(pending)<5:
                    n=min(units,count-index)
                    yield from A.parallel([self.memory('gu',index*4,n*4,tag='digital_nonlinear_g'),
                        self.memory('gu',F*4+index*4,n*4,tag='digital_nonlinear_u')])
                    pending.append((self.h.now+5*period,index,n));index+=n;self.a['SwiGLU']+=n
                if self.h.now<before+period:yield from self.h.delay(before+period-self.h.now)
                if (index==count or len(pending)==5) and pending and self.h.now<pending[0][0]:
                    yield from self.h.delay(pending[0][0]-self.h.now)
            self.a['nonlinear_pipeline_slots_peak']=5
        def end(self):
            assert not self.busy
            if False:yield
            return dict(actions=dict(self.a))
        def begin(self,p,l):
            self.p=p;self.l=facade.ffn_layout(p['hidden'],p['intermediate']);self.context=[self.h.now]*4
            yield from self.h.transfer(m.vector,0,p['hidden']*2,False,'digital_FFN_input_source')
            yield from self.memory('x',0,p['hidden']*2,True,'digital_x_input')
            if p['path']=='W8':yield from self.delay(4+ceildiv(p['hidden'],32));self.a['host_input_quantize_elements']+=p['hidden']
        def memory(self,key,offset,size,write=False,tag='digital_operand'):
            o=self.l['objects'][key];assert offset>=0 and offset+size<=o['bytes']
            address=o['offset']+offset
            while size:
                region=m.cim_weight[address//131072];inside=address%131072;n=min(size,131072-inside)
                yield from self.h.transfer(region,inside,n,write,tag);address+=n;size-=n
        def metadata(self,count):
            self.a['DRAM_metadata_bytes']+=count
            yield from self.h.fetch('digital_meta',m.weight_bases[facade.layer_id,'metadata'],count,m.cim_weight[1],
                self.l['objects']['scales']['offset']-131072 if self.l['objects']['scales']['offset']>=131072 else self.l['objects']['scales']['offset'],'digital_metadata')
        def consume(self,slot,q):
            p=self.p;role=q['role'];self.host.mac[role]+=q['rows']*q['ks'];self.a['MAC']+=q['rows']*q['ks']
            if p['path']=='W8' and not q['integer']:
                H,Fb=ceildiv(p['hidden'],64),ceildiv(p['intermediate'],64);prefix=0 if role=='Wg' else Fb*H if role=='Wu' else 2*Fb*H
                for out in range(q['row']//64,ceildiv(q['row']+q['rows'],64)):
                    for kb in range(q['k']//64,ceildiv(q['k']+q['ks'],64)):
                        yield from self.memory('scales',prefix+out*ceildiv(q['K'],64)+kb,1,tag='digital_PoT_metadata')
            if q['integer']:
                # Finite two-packet operand FIFO is filled after DMA landing,
                # overlapping the previous packet's one-cycle DOT operation.
                assert 2*(q['packed_bytes']+q['ks']*10//8)<=fifo_bytes
                assert q['ks']%64==0
                yield from self.delay(q['ks']//64+(4 if q['last'] else 0));self.a['A9W8_DOT64']+=q['rows']*(q['ks']//64)
                self.a['input_FIFO_capture_bytes']+=q['packed_bytes']+q['ks']*10//8
            else:
                yield from self.memory('z' if role=='Wd' else 'x',q['k']*2,q['ks']*2,tag='digital_activation_packet')
                self.a['input_FIFO_capture_bytes']+=q['ks']*2
                region=m.cim_weight[0]
                base=self.l['objects']['weight'+str(slot)]['offset']
                # Region view translates offsets into the existing physical
                # region; no allocation and no additional ports.
                class View:
                    def __init__(self):self.size=q['packed_bytes'];self.base=region.base+base;self.name=region.name;self.banks=region.banks
                view=View()
                original=self.h.mem.submit
                def submit(r,off,n,w,tag,cb):return original(region,base+off,n,w,tag,cb) if r is view else original(r,off,n,w,tag,cb)
                self.h.mem.submit=submit
                try:row=yield from consume_tile(m,view,q['rows'],q['ks'],p['lanes'],4,1000/clock,4,weight_B=q['weight_B'],word_interleaved=True)
                finally:self.h.mem.submit=original
                self.a['W8_BF16_FMA' if p['path']=='W8' else 'BF16_FMA']+=q['rows']*q['ks']
                self.a['input_FIFO_capture_bytes']+=row['read_words']*16
                if q['last']:
                    yield from self.delay(3+ceildiv(q['rows']*3,p['reduction_units']));self.a['FP32_reduce_ADD']+=q['rows']*3
            if q['last']:
                key='y' if role=='Wd' else 'gu';width=2 if role=='Wd' else 4
                off=(p['intermediate']*4 if role=='Wu' else 0)+q['row']*width
                yield from self.memory(key,off,q['rows']*width,True,'digital_matrix_output')
    def packed_transactions(profile,role,n,k,base):
        pending=None;members=0
        for q in F.packets(profile,role,n,k,base):
            if not q['integer']:
                assert pending is None;yield q;continue
            if pending is not None and (q['row']!=pending['row'] or members==4):
                yield pending;pending=None;members=0
            if pending is None:pending=dict(q);members=1
            else:
                assert pending['k']+pending['ks']==q['k']
                assert len(q['source_spans'])==len(pending['source_spans'])==1
                assert pending['source_spans'][0][0]+pending['source_bytes']==q['source_spans'][0][0]
                pending['ks']+=q['ks'];pending['packed_bytes']+=q['packed_bytes'];pending['source_bytes']+=q['source_bytes']
                pending['source_spans']=[(pending['source_spans'][0][0],pending['source_bytes'])];pending['last']=q['last'];members+=1
        if pending is not None:yield pending
    env=dict(run_ffn.__globals__);env['packets']=packed_transactions
    exec(compile(inspect.getsource(run_ffn),'<four_K64_integer_DMA_packet>','exec'),env);run_packed=env['run_ffn']
    port=Port(facade);wrapped=SharedPoolPort(port,m.cross_pool);m.cross_digital_results=[]
    def ffn(self,l):
        facade.layer_id=l;facade.weight_base=m.weight_bases[l,'g'];port.a=Counter();port.busy={}
        r=yield from run_packed(fp,wrapped,shape['hidden'],shape['ffn'])
        self.cross_digital_results.append(dict(profile=fp,result=r,actions=dict(port.a)))
        yield from self.copy(m.cim_weight[facade.ffn_layout(shape['hidden'],shape['ffn'])['objects']['y']['offset']//131072],
            facade.ffn_layout(shape['hidden'],shape['ffn'])['objects']['y']['offset']%131072,self.vector,0,shape['hidden']*2,'digital_FFN_output')
    m.cross_digital_ffn=MethodType(ffn,m)
    m.cross_attention_results=[]
    def attention(self,l,g):
        mode='screen_full' if scheme=='W8_screen' else 'dense'
        actor=A.Attention(self.h,m.cross_pool,m.att,A.Config(clock,mode,8,2048,rescale='trace'))
        row=dict(self.extra_input['rows'][(l%3)*8+g],base=self.kv_bases[l,g])
        row['max_changes']=row['screen_full_max_changes' if mode=='screen_full' else 'dense_max_changes']
        logical=self.cross_wave_start+g;Q,KV=self.model['q_heads'],self.model['kv_heads']
        yield from A.parallel([self.h.transfer(self.vector,logical*self.cross_qpg*256,self.cross_qpg*256,False,'digital_Q_input_source'),
            self.h.transfer(self.vector,Q*256+logical*256,256,False,'digital_K_input_source'),
            self.h.transfer(self.vector,(Q+KV)*256+logical*256,256,False,'digital_V_input_source')])
        yield from actor.group(g,g,row)
        self.cross_attention_results.append(dict(actions=dict(actor.actions),audit=actor.audit,configuration=actor.c.__dict__ if hasattr(actor,'c') else dict(clock_MHz=clock,mode=mode,concurrent_groups=8)))
    m.attention_group=MethodType(attention,m)
    return m

def full_run(m,fixture,layers,include_head,progress):
    H,F,Q,KV,D=[m.model[k] for k in ('hidden','ffn','q_heads','kv_heads','head_dim')]
    q=Q*D;kv=KV*D;clock=m.cross_clock
    def phase(name,jobs,l):
        value=m.phase(name,jobs,l);progress(name,l,m.h.now);return value
    phase('embedding',[m.h.fetch('embedding',m.lm_base+(m.seed%m.model['vocab'])*H*2,H*2,m.vector,0,'embedding')],-1)
    for l in range(layers):
        phase('save_attention_residual',[m.copy(m.vector,0,m.vector,131072,H*2,'save_residual')],l)
        phase('norm',[m.norm(l,'attention')],l)
        phase('QKV',[m.digital_matrix(l,'QKV',q+2*kv,H)],l)
        phase('RoPE_headnorm',[m.rope()],l)
        for start in range(0,KV,8):
            m.cross_wave_start=start
            for g in range(8):m.kv_bases[l,g]=m.cross_kv_bases[l,start+g]
            m.extra_input={'rows':[dict(fixture[l%3][start+g]) for _ in range(3) for g in range(8)]}
            jobs=[m.attention_group(l,g) for g in range(8)]
            if start==0 and m.cross_prefetch:jobs.append(m.prefetch_matrix(l,'O',H,q))
            phase('attention',jobs,l)
            def gather():
                for g in range(8):
                    source=122880 if m.cross_scheme=='SC_ising' else 40960
                    tag='attention_gather' if m.cross_scheme=='SC_ising' else 'digital_attention_gather'
                    yield from m.copy(m.att[g],source,m.vector,(start+g)*m.cross_qpg*256,m.cross_qpg*256,tag)
            phase('attention_gather',[gather()],l)
        jobs=[m.digital_matrix(l,'O',H,q)]
        if m.cross_scheme=='SC_ising' and m.cross_prefetch:jobs.append(m.prefetch_gu(l))
        phase('O',jobs,l);phase('attention_residual',[m.residual()],l)
        phase('save_ffn_residual',[m.copy(m.vector,0,m.vector,131072,H*2,'save_residual')],l)
        phase('ffn_norm',[m.norm(l,'ffn')],l)
        if m.cross_scheme=='SC_ising':
            phase('metadata',[m.h.fetch('FFN_metadata',m.weight_bases[l,'metadata'],m.cross_meta,m.vector,65536,'FFN_scale_metadata')],l)
            phase('GU',[m.sc_gu(l)],l);jobs=[m.sc_down(l)]
            if m.cross_prefetch:
                if l+1<layers:jobs.append(m.prefetch_matrix(l+1,'QKV',q+2*kv,H))
                elif include_head:jobs.append(m.prefetch_matrix(0,'lm_head',m.model['vocab'],H))
            phase('NL_Wd',jobs,l)
        else:phase('digital_FFN',[m.cross_digital_ffn(l)],l)
        phase('residual',[m.residual()],l)
    if include_head:
        phase('final_norm',[m.norm(0,'final')],-1)
        phase('lm_head',[m.digital_matrix(0,'lm_head',m.model['vocab'],H)],-1)
    return m
