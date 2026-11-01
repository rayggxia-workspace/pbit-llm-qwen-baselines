"""Opt-in whole-shape shared-memory frontend for unified_v6, Issue227.

No weights or activations are numerically evaluated. Matrix shapes, addresses,
finite operand banks, dependencies and library SRAM events are executed. The
stochastic compute actors use measured100MHz service contracts and explicit
unvalidated cross-K/format macros. Attention uses address/event inputs, never
a constant113us service. This does not establish PPL or physical timing.
"""
from collections import Counter,deque
from pathlib import Path
import argparse,hashlib,json,math,time
from .shared_memory import SharedMemory,AnalyticDRAM,DRAMSysAsync,dram_energy,align_time,Signal,when_any
from .shared_clock import SharedClock,PROFILES


MODEL=dict(hidden=2560,ffn=9728,layers=36,q_heads=32,kv_heads=8,head_dim=128,vocab=151936)


class AddressSpace:
    def __init__(self):self.next=65536;self.regions={}
    def alloc(self,name,size):
        if name in self.regions:raise ValueError('duplicate external tensor')
        base=math.ceil(self.next/4096)*4096;self.regions[name]=(base,size);self.next=base+size;return base


def spans_tile(base,out_start,outputs,k,input_size,inputs,element):
    return [(base+(out_start+j)*input_size*element+k*element,inputs*element) for j in range(outputs)]


class SharedDecode:
    def __init__(self,hub,*,layers=36,context=2048,ffn='sc',gu=16,nl=256,
                 staging=False,seed=17,attention_input=None,fullpv=False,include_lm=True,
                 hidden=2560,ffn_size=9728,q_heads=32,kv_heads=8,head_dim=128,vocab=151936,cross_prefetch=True,progress=None,
                 clock_profile='chip100'):
        if ffn not in ('sc','w8','bf16'):raise ValueError('FFN mode')
        if min(hidden,ffn_size)%64 or context%32:raise ValueError('full64 channels and32token layout blocks required')
        self.h=hub;self.model=dict(MODEL,hidden=hidden,ffn=ffn_size,layers=layers,
            q_heads=q_heads,kv_heads=kv_heads,head_dim=head_dim,vocab=vocab)
        if q_heads//kv_heads!=4 or q_heads%kv_heads or head_dim!=128:raise ValueError('four query heads per KV/d128 contract')
        self.N=context;self.ffn_mode=ffn;self.gu=gu;self.nl=nl;self.staging=staging
        self.seed=seed;self.fullpv=fullpv;self.include_lm=include_lm
        self.cross_prefetch=cross_prefetch;self.progress=progress;self.prefetched=set();self.prefetched_gu=set();self.metadata_prefetched=set()
        self.a=AddressSpace();self.actions=Counter();self.phases=[];self.compute=Counter();self.kernel_active=Counter()
        self.clock=SharedClock(clock_profile)
        if self.clock.synchronous:
            if hub.now or hub.descriptors or hub.mem.queue:raise ValueError('set chip clock before execution')
            if abs(hub.mem.period-self.clock.period_ns)>1e-8 or abs(hub.issue_period-self.clock.period_ns)>1e-8:
                raise ValueError('chip100 SRAM/DMA front clock mismatch')
            hub.common_period_ns=self.clock.period_ns
        self.unpriced=Counter();self.mac_hz=self.clock.mac_hz;self.mac_lanes=2048
        self.vector_hz=100000000;self.extra_input=attention_input;self.numeric_quality=False
        # Physical banks0..255 serve weights/local vectors.256..511 give eight
        # groups32 physical128-bit banks, i.e.16 logical256-bit1RW banks each.
        m=hub.mem;self.weight=[m.region('operand_ping',131072,range(0,128)),m.region('operand_pong',131072,range(128,256))]
        self.cim_weight=[m.region('CIM_ping',131072,range(0,128)),m.region('CIM_pong',131072,range(128,256))]
        self.stage=[m.region('staging_ping',131072,range(0,128)),m.region('staging_pong',131072,range(128,256))] if staging else None
        self.cim_stage=[m.region('CIM_staging_ping',131072,range(0,128)),m.region('CIM_staging_pong',131072,range(128,256))] if staging else None
        self.vector=m.region('activations_and_codes',262144,range(0,64))
        norm_size=math.ceil((layers*(4*hidden+512)+hidden*2)/64)*64
        self.norm_weights=m.region('resident_norm_weights',norm_size,range(0,64))
        self.att=[m.region('Attention_KVgroup'+str(g),131072,range(256+32*g,288+32*g)) for g in range(kv_heads)]
        self.time_actors={};self.work_digest=hashlib.sha256()
        self.weight_bases={};self.kv_bases={}
        for layer in range(layers):
            d=hidden;f=ffn_size;q=q_heads*head_dim;kv=kv_heads*head_dim
            for name,o,inp,eb in [('QKV',q+2*kv,d,2),('O',d,q,2),
                                   ('g',f,d,1 if ffn!='bf16' else 2),('u',f,d,1 if ffn!='bf16' else 2),
                                   ('down',d,f,1 if ffn!='bf16' else 2)]:
                self.weight_bases[layer,name]=self.a.alloc(f'L{layer}/{name}',o*inp*eb)
            self.weight_bases[layer,'metadata']=self.a.alloc(f'L{layer}/scales',32768)
            for g in range(kv_heads):self.kv_bases[layer,g]=self.a.alloc(f'L{layer}/KV{g}',3*context*256)
        self.lm_base=self.a.alloc('lm_head',vocab*hidden*2)
    def phase(self,name,generators,layer):
        start=self.h.now;values=self.h.execute(generators)
        row=dict(layer=layer,stage=name,start_ns=start,end_ns=self.h.now,duration_ns=self.h.now-start)
        if self.clock.synchronous:
            if abs(self.h.now/self.clock.period_ns-round(self.h.now/self.clock.period_ns))>1e-5:raise ValueError('off-edge chip completion')
            row['chip_cycles']=round((self.h.now-start)/self.clock.period_ns)
        self.phases.append(row)
        if self.progress:self.progress(self.phases[-1])
        return values
    def delay(self,ns,name):
        ns=self.clock.service_ns(name,ns)
        self.compute[name]+=ns;yield from self.h.delay(ns)
    def copy(self,src,src_offset,dst,dst_offset,size,tag):
        # Four64B elastic copy slots, not an unaccounted whole-tile buffer.
        done=Signal();state={'next':0,'complete':0}
        def launch():
            if state['next']>=size:return
            off=state['next'];n=min(64,size-off);state['next']+=n
            def read():
                def written():
                    state['complete']+=n
                    if state['complete']==size:done.set()
                    launch()
                self.h.mem.submit(dst,dst_offset+off,n,True,tag+'_write',written)
            self.h.mem.submit(src,src_offset+off,n,False,tag+'_read',read)
        for _ in range(4):launch()
        self.unpriced['copy_elastic_256B_engines'] = 1
        yield done
    def load(self,owner,spans,slot,offset,tag):
        pool=self.cim_weight if tag in ('GU_weights','down_weights') else self.weight
        stages=self.cim_stage if tag in ('GU_weights','down_weights') else self.stage
        total=sum(n for _,n in spans);dst=stages[slot] if self.staging else pool[slot]
        yield from self.h.fetch(owner,spans[0][0],total,dst,offset,tag,spans=spans)
        if self.staging:yield from self.copy(dst,offset,pool[slot],offset,total,'staging_to_operand')
    def matrix_tasks(self,layer,name,outputs,inputs,element=2):
        base=self.lm_base if name=='lm_head' else self.weight_bases[layer,name]
        tasks=[]
        for o in range(0,outputs,64):
            nout=min(64,outputs-o)
            for k in range(0,inputs,1024):
                n=min(1024,inputs-k)
                spans=spans_tile(base,o,nout,k,inputs,n,element)
                tasks.append((spans,nout*n,o,nout,k+n==inputs))
        return tasks
    def prefetch_matrix(self,layer,name,outputs,inputs,element=2):
        tasks=self.matrix_tasks(layer,name,outputs,inputs,element)
        def first(ix):
            yield from self.load('ordinary',tasks[ix][0],ix,0,name+'_weights')
            self.prefetched.add((layer,name,ix))
        yield from self._parallel([first(ix) for ix in range(min(2,len(tasks)))])
    def prefetch_gu(self,layer):
        d=self.model['hidden'];f=self.model['ffn']
        def first(engine,k):
            spans=spans_tile(self.weight_bases[layer,'g'],engine*64,64,k*64,d,64,1)
            spans+=spans_tile(self.weight_bases[layer,'u'],engine*64,64,k*64,d,64,1)
            yield from self.load('GU'+str(engine),spans,k%2,engine*8192,'GU_weights')
            self.prefetched_gu.add((layer,engine,engine,k))
        yield from self._parallel([first(e,k) for e in range(min(self.gu,f//64)) for k in range(min(2,d//64))])
    def digital_matrix(self,layer,name,outputs,inputs,element=2):
        tasks=self.matrix_tasks(layer,name,outputs,inputs,element)
        state={'loaded':{},'next':0}
        loaders={}
        def loader(ix,slot):
            spans,work,_,_,_=tasks[ix]
            if (layer,name,ix) in self.prefetched:
                self.prefetched.remove((layer,name,ix));self.actions['ordinary_prefetch_hits']+=1
            else:yield from self.load('ordinary',spans,slot,0,name+'_weights')
            state['loaded'].setdefault(ix,Signal()).set()
        def driver():
            source=98304 if name=='down' else 0
            yield from self.h.transfer(self.vector,source,inputs*2,False,name+'_activation_to_local')
            for ix,(spans,work,out0,nout,last_k) in enumerate(tasks):
                slot=ix%2
                if ix==0:loaders[0]=loader(0,0);loaders[1]=loader(1,1) if len(tasks)>1 else None
                # Nested finite loaders are advanced by the same global hub.
                yield state['loaded'].setdefault(ix,Signal())
                start=self.h.now;nbytes=sum(n for _,n in spans)
                yield from self.h.transfer(self.weight[slot],0,nbytes,False,name+'_operand')
                compute_end=start+(math.ceil(work/self.mac_lanes)+2)*self.clock.mac_period_ns
                if self.h.now<compute_end:yield from self.h.delay(compute_end-self.h.now)
                self.actions['digital_'+('BF16' if element==2 else 'W8')+'_MAC']+=work
                self.compute['ordinary_MAC_ideal_ns']+=math.ceil(work/self.mac_lanes)/self.mac_hz*1e9
                self.work_digest.update(f'{name}/{layer}/{ix}/{work}/{nbytes}'.encode())
                state['loaded'].pop(ix)
                if last_k:
                    if name=='lm_head':
                        yield from self.delay(14,'streaming_argmax_macro')
                        self.actions['argmax_compares']+=nout
                    else:
                        dest={'g':32768,'u':65536}.get(name,0)
                        yield from self.delay(math.ceil(nout/64)*10+30,'matrix_output_quant_macro')
                        yield from self.h.transfer(self.vector,dest+out0*2,nout*2,True,name+'_output')
                nxt=ix+2
                if nxt<len(tasks):loaders[nxt]=loader(nxt,slot)
            # FP32 partial accumulator/PoT restoration are explicit macro state.
            self.unpriced['digital_FP32_partial_register_bytes_peak']=max(self.unpriced['digital_FP32_partial_register_bytes_peak'],64*4)
            self.unpriced['digital_activation_hold_bytes_peak']=max(self.unpriced['digital_activation_hold_bytes_peak'],inputs*2)
        yield from self._managed(driver(),loaders)
    def sc_gu(self,layer):
        d=self.model['hidden'];f=self.model['ffn'];groups=deque(range(f//64))
        # Full x probability codes live in bounded SRAM; local per-core input
        # holding and source checkpoint implementation remain explicit unknowns.
        yield from self.h.transfer(self.vector,0,d*2,False,'x_encode_input')
        yield from self.delay(math.ceil(d/64)*30,'x_P8_encoding_macro')
        yield from self.h.transfer(self.vector,0,math.ceil((d//64)*80/64)*64,True,'x_codes_store')
        def worker(engine):
            while groups:
                out=groups.popleft();pending={};loaded={k:Signal() for k in range(d//64)}
                def load(k):
                    slot=k%2;off=engine*8192
                    key=(layer,engine,out,k)
                    if key in self.prefetched_gu:
                        self.prefetched_gu.remove(key);self.actions['GU_prefetch_hits']+=1
                    else:
                        spans=spans_tile(self.weight_bases[layer,'g'],out*64,64,k*64,d,64,1)
                        spans+=spans_tile(self.weight_bases[layer,'u'],out*64,64,k*64,d,64,1)
                        yield from self.load('GU'+str(engine),spans,slot,off,'GU_weights')
                    yield from self.h.transfer(self.vector,65536+(out*(d//64)+k)*2,2,False,'GU_weight_scale_metadata')
                    loaded[k].set()
                def compute():
                    for k in range(d//64):
                        yield loaded[k]
                        slot=k%2
                        yield from self.h.transfer(self.vector,k*80,80,False,'GU_x_codes')
                        yield from self.delay(660,'GU100MHz_core')
                        self.kernel_active['GU_frames']+=1;self.actions['GU_logical_R8_ports']+=4096
                        # Cross-K exponent alignment and128 INT64 updates; not
                        # included in the measured GU frame. Existing32-lane,
                        # latency2 macro; chip100 uses5 whole100MHz cycles.
                        yield from self.delay(10,'GU_crossK_align_add_macro')
                        self.actions['crossK_updates']+=128
                        if k+2<d//64:pending[k+2]=load(k+2)
                    yield from self.delay(8,'GU_fixed8_quant_macro')
                    yield from self.h.transfer(self.vector,8192+out*128,128,True,'GU_quantized_output')
                pending[0]=load(0)
                if d//64>1:pending[1]=load(1)
                yield from self._managed(compute(),pending)
        self.unpriced['GU_crossK_INT64_register_bytes']=self.gu*128*8
        self.unpriced['GU_input_hold_bytes']=self.gu*80
        yield from self._parallel([worker(e) for e in range(self.gu)])
    def sc_down(self,layer):
        d=self.model['hidden'];f=self.model['ffn'];groups=deque(range(d//8))
        def worker(engine):
            while groups:
                out=groups.popleft();pending={};loaded={k:Signal() for k in range(f//64)}
                def load(k):
                    spans=spans_tile(self.weight_bases[layer,'down'],out*8,8,k*64,f,64,1)
                    yield from self.load('NL'+str(engine),spans,k%2,engine*512,'down_weights')
                    yield from self.h.transfer(self.vector,65536+2*(f//64)*(d//64)+(out//8)*(f//64)+k,1,False,'Wd_weight_scale_metadata')
                    loaded[k].set()
                def compute():
                    for k in range(f//64):
                        yield loaded[k]
                        yield from self.h.transfer(self.vector,8192+k*128,128,False,'NL_gu_codes')
                        yield from self.delay(660,'NL100MHz_core')
                        self.kernel_active['NL_frames']+=1;self.actions['NL_logical_R8_ports']+=12288
                        yield from self.delay(4,'down_crossK_align_add_macro');self.actions['crossK_updates']+=8
                        if k+2<f//64:pending[k+2]=load(k+2)
                    yield from self.delay(6,'final_BF16_macro')
                    yield from self.h.transfer(self.vector,out*16,16,True,'FFN_BF16_output')
                pending[0]=load(0)
                if f//64>1:pending[1]=load(1)
                yield from self._managed(compute(),pending)
        self.unpriced['NL_crossK_INT64_register_bytes']=self.nl*8*8
        self.unpriced['NL_input_hold_bytes']=self.nl*128
        yield from self._parallel([worker(e) for e in range(self.nl)])
    def _managed(self,main,loaders):
        condition=next(main);active={}
        while True:
            changed=True
            while changed:
                changed=False
                for key,gen in list(loaders.items()):
                    if gen is not None and key not in active:
                        try:active[key]=[gen,next(gen)]
                        except StopIteration:loaders.pop(key,None)
                        changed=True
                for key,(gen,cond) in list(active.items()):
                    if cond():
                        try:active[key][1]=next(gen)
                        except StopIteration:del active[key];loaders.pop(key,None)
                        changed=True
                if condition():
                    try:condition=next(main)
                    except StopIteration:return
                    changed=True
            yield when_any([condition]+[cond for _,cond in active.values()])
    def _parallel(self,generators):
        active=[]
        for gen in generators:
            try:active.append([gen,next(gen)])
            except StopIteration:pass
        while active:
            changed=True
            while changed:
                changed=False
                for item in list(active):
                    gen,cond=item
                    if cond():
                        try:item[1]=next(gen)
                        except StopIteration:active.remove(item)
                        changed=True
            if active:yield when_any([cond for _,cond in active])
    def qk_stream(self,layer,g,spans,kind):
        # Two8KiB K slots within the128KiB per-group SRAM region.
        bursts=[a+o for a,n in spans for o in range(0,n,64)]
        chunks=[bursts[i:i+128] for i in range(0,len(bursts),128)]
        pending={};loaded={k:Signal() for k in range(len(chunks))};region=self.att[g]
        def load(k):
            s=[(a,64) for a in chunks[k]]
            yield from self.h.fetch('Attention'+str(g),s[0][0],len(s)*64,region,k%2*8192,kind,spans=s)
            loaded[k].set()
        def consume():
            for k,block in enumerate(chunks):
                yield loaded[k]
                start=self.h.now;left=[len(block)*2];done=Signal();last=[start]
                def read_done():
                    left[0]-=1;last[0]=max(last[0],self.h.now)
                    if left[0]==0:done.set()
                # One32B operand word per10ns for64 reused QK MACs.
                for j in range(len(block)*2):
                    self.h.later(start+j*10,self.h.mem.submit,region,k%2*8192+j*32,32,False,kind+'_operand',read_done)
                yield done
                end=max(start+len(block)*20+140,last[0]+140)
                if end>self.h.now:yield from self.h.delay(end-self.h.now)
                self.actions['attention_QK_MAC']+=len(block)*32*4
                if k+2<len(chunks):pending[k+2]=load(k+2)
        if chunks:
            pending[0]=load(0)
            if len(chunks)>1:pending[1]=load(1)
            yield from self._managed(consume(),pending)
    def attention_group(self,layer,g):
        h=self.h;region=self.att[g];base=self.kv_bases[layer,g];n=self.N
        # One complete32token K block is maintained at this boundary. Physical
        # scratch is per active group, reused across all layers, never36 copies.
        qvals=self.model['q_heads']*128;kvvals=self.model['kv_heads']*128
        yield from h.transfer(self.vector,qvals*2+g*256,256,False,'K_append_source')
        yield from h.transfer(self.vector,(qvals+kvvals)*2+g*256,256,False,'V_append_source')
        query_bytes=(self.model['q_heads']//self.model['kv_heads'])*256
        yield from h.transfer(self.vector,g*query_bytes,query_bytes,False,'Q_to_attention')
        yield from h.transfer(region,24576,query_bytes,True,'Q_local_fill')
        qwidth=self.model['q_heads']*256;kvwidth=self.model['kv_heads']*256
        yield from h.transfer(self.vector,qwidth+g*256,256,False,'K_append_input')
        yield from h.transfer(region,114688,256,True,'K_append_source')
        yield from h.fetch('Attention'+str(g),base+(n-1)*256,256,region,114688,'K_append',write=True)
        yield from h.transfer(self.vector,qwidth+kvwidth+g*256,256,False,'V_append_input')
        yield from h.transfer(region,114688,256,True,'V_append_source')
        yield from h.fetch('Attention'+str(g),base+2*n*256+(n-1)*256,256,region,114688,'V_append',write=True)
        yield from h.fetch('Attention'+str(g),base+(n-32)*256,8192,region,114688,'K_block_for_transpose')
        yield from h.transfer(region,114688,8192,False,'K_transpose_read')
        yield from self.delay(2560,'K_transpose_macro')
        yield from h.transfer(region,114688,8192,True,'K_transpose_write')
        spans=[(base+n*256+d*n*2+(n-32)*2,64) for d in range(128)]
        yield from h.fetch('Attention'+str(g),spans[0][0],8192,region,114688,'K_feature_append',write=True,spans=spans)
        yield from h.transfer(region,24576,512,False,'query_feature_scan')
        yield from self.delay(1633.333333,'feature_topk_macro')
        dims=[(self.seed+g*7+j*3)%128 for j in range(32)]
        candidates=[(j*(n//128)+g*3)%n for j in range(128)]
        if self.extra_input:
            rows=self.extra_input['rows'];row=rows[(layer%3)*self.model['kv_heads']+g]
            dims=row['dimensions'];candidates=row['candidates']
        coarse=[(base+n*256+d*n*2,n*2) for d in dims]
        yield from self.qk_stream(layer,g,coarse,'coarse_K')
        yield from h.transfer(region,32768,16384,True,'coarse_scores')
        # Preserve library SRAM words for three score passes and shared-head
        # normalization; local compute is an existing macro, not new RTL.
        yield from h.transfer(region,32768,16384,False,'coarse_score_pass1')
        yield from h.transfer(region,32768,16384,False,'coarse_score_pass2')
        yield from h.transfer(region,32768,16384,False,'coarse_score_pass3')
        yield from self.delay(17300,'SparQ_normalize_macro')
        yield from self.delay(8146.666667,'token_topk_macro')
        yield from self.qk_stream(layer,g,[(base+t*256,256) for t in candidates],'selected_K')
        yield from h.transfer(region,16384,2048,True,'selected_scores')
        if self.fullpv:
            yield from self.delay(6640,'digital_softmax_macro')
            #128V, reused across four query heads, one load per candidate.
            yield from self.qk_stream(layer,g,[(base+2*n*256+t*256,256) for t in candidates],'full_V')
            self.actions['attention_PV_MAC']+=128*128*4
            return
        self.actions['sampler_queries']+=4;self.actions['samples']+=256
        yield from h.transfer(region,16384,2048,False,'sampler_score_input')
        queries=None
        if self.extra_input:queries=self.extra_input['queries'][str(self.seed)][g][layer%3*4:layer%3*4+4]
        events=[];offset=0.
        for head in range(4):
            q=queries[head] if queries else None
            if q:
                edge=lambda t:align_time(t,self.clock.period_ns) if self.clock.synchronous else t
                events.extend((offset+edge(t),head,index,count) for t,index,count in q['events'])
                offset+=edge(q['duration_ns'])+10
            else:
                events.extend((offset+700+j*10,head,(self.seed+head*19+j*7)%128,1) for j in range(64));offset+=1460
        queues=[deque() for _ in range(4)];busy=[False]*4;cache={};producer={'index':0,'shift':0.,'held':False};consumed=[0]*4
        feedback=[[0.]*8 for _ in range(4)];head_issue=[h.now]*4;last_result=[h.now];start=h.now
        def consume(head):
            if busy[head] or not queues[head]:return
            index=queues[head][0]
            if cache.get(index)!='valid':return
            queues[head].popleft();busy[head]=True;origin=max(h.now,head_issue[head]-10);left=[8]
            def returned(j):
                begin=align_time(max(h.now,head_issue[head],feedback[head][j]),10)
                head_issue[head]=begin+10;feedback[head][j]=begin+70;last_result[0]=max(last_result[0],begin+70)
                self.actions['PV_ADD']+=16;left[0]-=1
                if left[0]==0:
                    def complete():
                        busy[head]=False;consumed[head]+=1
                        if producer['held']:producer['held']=False;h.later(h.now,produce)
                        consume(head)
                    h.later(max(h.now,head_issue[head]-10),complete)
            for j in range(8):h.later(origin+j*10,h.mem.submit,region,65536+index*256+j*32,32,False,'sample_V_operand',lambda j=j:returned(j))
        def fetched(index):
            cache[index]='valid'
            for head in range(4):consume(head)
        def produce():
            pos=producer['index']
            if pos==len(events):return
            relative,head,index,count=events[pos];due=start+relative+producer['shift']
            if h.now+1e-6<due:h.later(due,produce);return
            if sum(map(len,queues))+count>128:producer['held']=True;return
            producer['shift']+=max(0,h.now-due);producer['index']+=1
            for _ in range(count):queues[head].append(index)
            if index not in cache:
                cache[index]='pending';self.actions['unique_V']+=1
                h.dma('Attention'+str(g),base+2*n*256+candidates[index]*256,256,region,65536+index*256,'sample_V',lambda i=index:fetched(i))
            else:self.actions['V_fetch_reuse']+=1
            consume(head)
            if producer['index']<len(events):h.later(max(h.now,start+events[producer['index']][0]+producer['shift']),produce)
        h.later(start+events[0][0],produce)
        yield lambda:sum(consumed)==256
        if h.now<last_result[0]:yield from h.delay(last_result[0]-h.now)
        yield from self.delay(160,'sample_normalize_BF16_macro')
        yield from h.transfer(region,122880,1024,True,'attention_output')
    def norm(self,layer,which):
        d=self.model['hidden'];stride=4*d+512;offset=layer*stride+(2*d if which=='ffn' else 0)
        if which=='final':offset=self.model['layers']*stride
        yield from self.h.transfer(self.vector,0,d*2,False,'norm_activation')
        yield from self.h.transfer(self.norm_weights,offset,d*2,False,'norm_gamma')
        yield from self.delay(math.ceil(d/64)*10+30,'RMSNorm_macro')
        yield from self.h.transfer(self.vector,0,d*2,True,'norm_output')
    def rope(self):
        count=(self.model['q_heads']+self.model['kv_heads'])*128*2
        yield from self.h.transfer(self.vector,0,count,False,'QK_norm_rope_input')
        yield from self.delay(1600,'RoPE_headnorm_macro')
        yield from self.h.transfer(self.vector,0,count,True,'QK_norm_rope_output')
    def residual(self):
        n=self.model['hidden']*2
        yield from self.h.transfer(self.vector,0,n,False,'residual_branch')
        yield from self.h.transfer(self.vector,131072,n,False,'residual_skip')
        yield from self.delay(math.ceil(n/128)*10+30,'residual_add_macro')
        yield from self.h.transfer(self.vector,0,n,True,'residual_output')
    def gather_attention(self):
        for g in range(self.model['kv_heads']):
            yield from self.copy(self.att[g],122880,self.vector,g*1024,1024,'attention_gather')
    def swiglu(self):
        n=self.model['ffn']*2
        yield from self.h.transfer(self.vector,32768,n,False,'digital_g')
        yield from self.h.transfer(self.vector,65536,n,False,'digital_u')
        yield from self.delay(math.ceil(self.model['ffn']/16)*10+30,'digital_SwiGLU_macro')
        yield from self.h.transfer(self.vector,98304,n,True,'digital_z')
    def run(self):
        d=self.model['hidden'];f=self.model['ffn'];q=self.model['q_heads']*128;kv=self.model['kv_heads']*128
        self.phase('embedding',[self.h.fetch('embedding',self.lm_base+(self.seed%self.model['vocab'])*d*2,d*2,self.vector,0,'embedding')],-1)
        for layer in range(self.model['layers']):
            self.phase('save_attention_residual',[self.copy(self.vector,0,self.vector,131072,d*2,'save_residual')],layer)
            self.phase('norm', [self.norm(layer,'attention')],layer)
            self.phase('QKV',[self.digital_matrix(layer,'QKV',q+2*kv,d)],layer)
            self.phase('RoPE_headnorm',[self.rope()],layer)
            attention_jobs=[self.attention_group(layer,g) for g in range(self.model['kv_heads'])]
            if self.cross_prefetch:attention_jobs.append(self.prefetch_matrix(layer,'O',d,q))
            self.phase('attention',attention_jobs,layer)
            self.phase('attention_gather',[self.gather_attention()],layer)
            o_jobs=[self.digital_matrix(layer,'O',d,q)]
            if self.cross_prefetch and self.ffn_mode=='sc':o_jobs.append(self.prefetch_gu(layer))
            self.phase('O',o_jobs,layer)
            self.phase('attention_residual',[self.residual()],layer)
            self.phase('save_ffn_residual',[self.copy(self.vector,0,self.vector,131072,d*2,'save_residual')],layer)
            self.phase('ffn_norm',[self.norm(layer,'ffn')],layer)
            if self.ffn_mode=='sc':
                # All scale metadata is loaded once per layer; no per-frame
                # DRAM reload of the same calibration table.
                self.phase('metadata',[self.h.fetch('FFN_metadata',self.weight_bases[layer,'metadata'],32768,self.vector,65536,'FFN_scale_metadata')],layer)
                self.phase('GU',[self.sc_gu(layer)],layer)
                down_jobs=[self.sc_down(layer)]
                if self.cross_prefetch:
                    if layer+1<self.model['layers']:down_jobs.append(self.prefetch_matrix(layer+1,'QKV',q+2*kv,d))
                    elif self.include_lm:down_jobs.append(self.prefetch_matrix(0,'lm_head',self.model['vocab'],d))
                self.phase('NL_Wd',down_jobs,layer)
            else:
                eb=1 if self.ffn_mode=='w8' else 2
                self.phase('GU_g',[self.digital_matrix(layer,'g',f,d,eb)],layer)
                self.phase('GU_u',[self.digital_matrix(layer,'u',f,d,eb)],layer)
                self.phase('digital_SwiGLU',[self.swiglu()],layer)
                self.phase('Wd',[self.digital_matrix(layer,'down',d,f,eb)],layer)
            self.phase('residual',[self.residual()],layer)
        if self.include_lm:
            self.phase('final_norm',[self.norm(0,'final')],-1)
            self.phase('lm_head',[self.digital_matrix(0,'lm_head',self.model['vocab'],d)],-1)
        return dict(model=self.model,context=self.N,ffn=self.ffn_mode,seed=self.seed,
            phases=self.phases,actions=dict(self.actions),kernel_active=dict(self.kernel_active),
            compute_macro_busy_sum_ns=dict(self.compute),unpriced_state_and_actions=dict(self.unpriced),
            external_tensor_bytes=self.a.next,work_spec_sha256=self.work_digest.hexdigest(),
            numeric_model_executed=False,model_quality_verified=False,clock_contract=self.clock.report(),
            macro_evidence='GU/NL100MHz measured frames; digital array/crossK/normalization remain explicit operator contracts; selected profile determines cycles/time')


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--backend',choices=['analytic','dramsys'],default='dramsys')
    p.add_argument('--binary');p.add_argument('--dram-config');p.add_argument('--input',type=Path)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--layers',type=int,default=36)
    p.add_argument('--ffn',choices=['sc','w8','bf16'],default='sc');p.add_argument('--seed',type=int,default=17)
    p.add_argument('--clock-profile',choices=PROFILES,default='chip100')
    p.add_argument('--issue',type=int,default=8);p.add_argument('--credit',type=int,default=64)
    p.add_argument('--quantum',type=int,default=16)
    p.add_argument('--return-banks',type=int,default=128)
    p.add_argument('--serial',action='store_true');p.add_argument('--staging',action='store_true')
    p.add_argument('--response-bypass',action='store_true');p.add_argument('--no-lm',action='store_true')
    p.add_argument('--no-cross-prefetch',action='store_true')
    p.add_argument('--gu',type=int,default=16);p.add_argument('--nl',type=int,default=256)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);start=time.time()
    backend=DRAMSysAsync(a.binary,a.dram_config,a.credit,a.out/'dramsys.stderr.log') if a.backend=='dramsys' else AnalyticDRAM()
    hub=SharedMemory(backend,credit=a.credit,issue_per_cycle=a.issue,descriptor_serial=a.serial,response_buffered=not a.response_bypass,owner_quantum=a.quantum,return_banks=a.return_banks)
    try:
        model=SharedDecode(hub,layers=a.layers,ffn=a.ffn,gu=a.gu,nl=a.nl,staging=a.staging,seed=a.seed,include_lm=not a.no_lm,
            attention_input=json.loads(a.input.read_bytes()) if a.input else None,cross_prefetch=not a.no_cross_prefetch,clock_profile=a.clock_profile,
            progress=lambda row:print('PHASE '+json.dumps(row),flush=True))
        result=model.run();result['memory']=hub.report();result['DRAM']=dram_energy(backend.finish(hub.now))
        result.update(status='completed',backend=a.backend,wall_seconds=time.time()-start,arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
            input_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest() if a.input else None,
            simulated_ms=hub.now*1e-6,complete_chip_energy_J=None,
            scope='whole configured layer/weight/address workload on ONE memory timeline; no numerical inference or physical timing signoff')
        if model.clock.synchronous:result['simulated_chip_cycles']=round(hub.now/model.clock.period_ns)
        (a.out/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps(dict(status='completed',simulated_ms=result['simulated_ms'],wall_seconds=result['wall_seconds'],DRAM=result['DRAM'],SRAM_mJ=result['memory']['SRAM']['dynamic_mJ']+result['memory']['SRAM']['leakage_mJ'])))
    finally:backend.close()


if __name__=='__main__':main()
