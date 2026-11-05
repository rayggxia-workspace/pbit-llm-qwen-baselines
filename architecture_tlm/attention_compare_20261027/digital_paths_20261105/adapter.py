"""Attention-only adapter for Issue236 unified TLM. No FFN configuration edits.

Sampling timing uses checked indices and measured RTL first/end envelopes.
`early`/`late` bound unknown intra-query stream timing; neither is a new RTL trace.
"""
from collections import deque
from types import MethodType
import math
from architecture_tlm.unified_v6.shared_memory import Signal,align_time
from architecture_tlm.digital_baselines_20261104.model import BaselineDecode

SAMPLED={'r8_gf64':'softmax_r8_gf64','r8_bivium':'softmax_r8_bivium',
         'systematic':'softmax_systematic','ising':'ab_both'}

def install(model,mode,samples=None,timing='late'):
    assert mode in ('dense','dense_broadcast','dense_split2','screen_full','screen_broadcast',*SAMPLED)
    assert timing in ('early','late')
    model.attention_path=mode;model.sample_timings=timing;model.sample_input=samples
    model.attention_kind='dense' if mode.startswith('dense') else 'screen_exact'
    model.attention_group=MethodType(attention_group,model)
    model.attention_adapter_contract=dict(mode=mode,timing=timing,SRAM_added=0,
        QK_lanes=512,PV_lanes=512 if mode not in SAMPLED else 0,
        sample_ADD_lanes=512 if mode in SAMPLED else 0,
        score_input='FP32->S12/F4 for sampled paths; converter cost separate',
        scope='module-only replacement; FFN and projection configuration untouched')
    return model

def screen(self,layer,g):
    h=self.h;r=self.att[g];base=self.kv_bases[layer,g];n=self.N
    yield from self._append(layer,g,True)
    yield from h.transfer(self.vector,196608+g*6144+5120,1024,False,'query_feature_scan')
    yield from self.delay(1633.333333,'feature_topk_macro')
    row=self.extra_input['rows'][(layer%3)*8+g]
    dims=row['dimensions'];candidates=row['candidates']
    yield from self.qk_stream(layer,g,[(base+n*256+d*n*2,n*2) for d in dims],'coarse_K')
    yield from h.transfer(r,32768,16384,True,'coarse_scores')
    for k in range(3):yield from h.transfer(r,32768,16384,False,'coarse_score_pass'+str(k+1))
    yield from self.delay(17300,'SparQ_normalize_macro')
    yield from self.delay(8146.666667,'token_topk_macro')
    spans=[(base+t*256,256) for t in candidates]
    yield from h.fetch('Attention'+str(g),spans[0][0],len(candidates)*256,r,0,'selected_K',spans=spans)
    begin=h.now
    yield from self._paced(r,0,len(candidates)*256,32,'selected_K_operand')
    end=begin+(math.ceil(len(candidates)*128*4/64)+4)*10
    if h.now<end:yield from h.delay(end-h.now)
    self.actions['attention_QK_MAC']+=len(candidates)*128*4
    yield from h.transfer(r,16384,2048,True,'selected_scores')

def sampled(self,layer,g):
    h=self.h;region=self.att[g];base=self.kv_bases[layer,g];n=self.N
    yield from screen(self,layer,g)
    candidates=self.extra_input['rows'][(layer%3)*8+g]['candidates']
    self.actions['sampler_queries']+=4
    yield from h.transfer(region,16384,2048,False,'sampler_score_input')
    # Four scalar converters are pipelined with the existing32-cycle load.
    # One extra latency cycle is a provisional interface, not measured STA.
    yield from self.delay(10,'FP32_to_S12_pipeline_tail_proxy')
    self.actions['FP32_to_S12']+=512
    top=SAMPLED[self.attention_path];events=[];offset=0
    for head in range(4):
        q=self.sample_input['samples'][f'{top}/{self.seed}/{g}/{layer%3*4+head}']
        indices=q['indices'];assert len(indices)==q['hits']
        # Late: complete query then serialize every contribution. Early: first
        # observed output then one index/cycle. The actual bounded interface
        # below applies backpressure; query duration is never less than RTL.
        first=q['cycles'] if self.sample_timings=='late' else q['first']
        for j,index in enumerate(indices):events.append((offset+max(0,first+j)*10,head,index,1))
        offset+=max(q['cycles']+1,max(0,first)+len(indices)+1)*10
    self.actions['samples']+=len(events)
    self.actions['sample_output_BF16']+=512
    queues=[deque() for _ in range(4)];busy=[False]*4;cache={}
    producer={'index':0,'shift':0.,'held':False};consumed=[0]*4
    feedback=[[0.]*8 for _ in range(4)];head_issue=[h.now]*4
    last_result=[h.now];start=h.now
    def consume(head):
        if busy[head] or not queues[head]:return
        index=queues[head][0]
        if cache.get(index)!='valid':return
        queues[head].popleft();busy[head]=True
        origin=max(h.now,head_issue[head]-10);left=[8]
        def returned(j):
            begin=align_time(max(h.now,head_issue[head],feedback[head][j]),10)
            head_issue[head]=begin+10;feedback[head][j]=begin+70
            last_result[0]=max(last_result[0],begin+70)
            self.actions['PV_ADD']+=16;left[0]-=1
            if left[0]==0:
                def complete():
                    busy[head]=False;consumed[head]+=1
                    if producer['held']:producer['held']=False;h.later(h.now,produce)
                    consume(head)
                h.later(max(h.now,head_issue[head]-10),complete)
        for j in range(8):
            h.later(origin+j*10,h.mem.submit,region,65536+index*256+j*32,32,False,
                    'sample_V_operand',lambda j=j:returned(j))
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
        queues[head].append(index)
        if index not in cache:
            cache[index]='pending';self.actions['unique_V']+=1
            h.dma('Attention'+str(g),base+2*n*256+candidates[index]*256,256,region,
                  65536+index*256,'sample_V',lambda i=index:fetched(i))
        else:self.actions['V_fetch_reuse']+=1
        consume(head)
        if producer['index']<len(events):
            h.later(max(h.now,start+events[producer['index']][0]+producer['shift']),produce)
    if events:h.later(start+events[0][0],produce)
    yield lambda:sum(consumed)==len(events)
    # Includes a zero-hit query and RNG rounds after its last hit.
    finish=max(last_result[0],start+offset+producer['shift'])
    if h.now<finish:yield from h.delay(finish-h.now)
    assert len(cache)<=128 and not any(queues) and not any(busy)
    self.actions['sample_queue_peak_capacity']=128
    yield from self.delay(160,'sample_normalize_BF16_macro')
    yield from h.transfer(region,122880,1024,True,'attention_output')

def broadcast(self,layer,g,part=None):
    """Same64FMA/group,16/head; one V tile read serves four heads.

    All four probability vectors are available before broadcasting. This may
    lose front/PV overlap; retain original path as a control, not assume a win.
    256B V hold and2KiB ping/pong weights/group are explicitly priced local state.
    """
    h=self.h;r=self.att[g];base=self.kv_bases[layer,g];n=self.N
    split=part is not None;tile=64 if split else 128;lanes=32 if split else 64
    soff=(part or 0)*65536;vbase=2*tile*256
    is_screen=self.attention_kind=='screen_exact'
    if is_screen:
        # Share identical screening and selected K computation with sampled.
        yield from screen(self,layer,g)
        candidates=self.extra_input['rows'][(layer%3)*8+g]['candidates']
    else:
        if not split:yield from self._append(layer,g,False)
        candidates=list(range(part*n//2,(part+1)*n//2)) if split else list(range(n))
    chunks=[candidates[i:i+tile] for i in range(0,len(candidates),tile)]
    ready=[Signal() for _ in chunks];scores=[Signal() for _ in chunks];free=[Signal() for _ in chunks]
    weights=[Signal() for _ in chunks]
    scratch=196608+g*6144+(part or 0)*2048
    def loader(slot):
        for i in range(slot,len(chunks),2):
            tokens=chunks[i]
            def fetch(v):
                spans=[(base+(2*n if v else 0)*256+t*256,256) for t in tokens]
                yield from h.fetch('Attention'+str(g),spans[0][0],len(tokens)*256,r,
                      soff+(vbase if v else 0)+slot*tile*256,'digital_V' if v else 'digital_K',spans=spans)
            yield from self._parallel([fetch(True)] if is_screen else [fetch(False),fetch(True)])
            ready[i].set();yield free[i]
    def qk():
        if not is_screen:yield from h.transfer(self.vector,196608+g*6144+5120,1024,False,'digital_Q_operand_hold')
        for i,tokens in enumerate(chunks):
            yield ready[i]
            if not is_screen:
                begin=h.now
                yield from self._paced(r,soff+i%2*tile*256,len(tokens)*256,lanes//2,'digital_K_operand')
                end=begin+(math.ceil(len(tokens)*128*4/lanes)+4)*10
                if h.now<end:yield from h.delay(end-h.now)
                self.actions['attention_QK_MAC']+=len(tokens)*128*4
            yield from h.transfer(self.vector,scratch+i%2*tile*16,len(tokens)*16,True,'digital_scores')
            scores[i].set()
    def front():
        for i,tokens in enumerate(chunks):
            yield scores[i];count=len(tokens)
            for head in range(4):
                begin=h.now
                for k in range(2):yield from h.transfer(self.vector,scratch+i%2*tile*16+head*count*4,count*4,False,'digital_score_pass')
                end=begin+math.ceil(count/(2 if split else 4))*40
                if h.now<end:yield from h.delay(end-h.now)
                self.actions['softmax_FP32_ADD']+=2*count;self.actions['softmax_EXP']+=count
                # Two local1KiB weight slots preserve front/PV overlap.
                self.actions['broadcast_probability_hold_writes']+=count
            weights[i].set()
    def pv():
        for i,tokens in enumerate(chunks):
            yield weights[i];count=len(tokens)
            if 0<i<=min(3,len(chunks)-1):
                for head in range(4):
                    yield from self.delay(1330,'online_rescale_FP32_macro')
                    self.actions['softmax_FP32_MUL']+=129;self.actions['softmax_EXP']+=1
                    self.actions['online_rescale_blocks']+=1
            begin=h.now
            yield from self._paced(r,soff+vbase+i%2*tile*256,count*256,lanes//2,'broadcast_V_operand')
            end=begin+(count*128*4//lanes+2)*10
            if h.now<end:yield from h.delay(end-h.now)
            self.actions['attention_PV_MAC']+=count*128*4
            self.actions['attention_PV_partial_updates']+=count*128*4
            self.actions['softmax_FP32_ADD']+=4;free[i].set()
        if split:return
        yield from self.delay(4*1590,'online_reciprocal_output_macro')
        self.actions['softmax_RECIP_SEED']+=4
        self.actions['softmax_FP32_MUL']+=4*(128+6);self.actions['softmax_FP32_ADD']+=16
        self.actions['attention_output_BF16']+=512
        yield from h.transfer(r,122880,1024,True,'attention_output')
    yield from self._parallel([loader(s) for s in range(min(2,len(chunks)))]+[qk(),front(),pv()])

def attention_group(self,layer,g):
    if self.attention_path in SAMPLED:yield from sampled(self,layer,g)
    elif self.attention_path=='dense_split2':
        yield from self._append(layer,g,False)
        yield from self._parallel([broadcast(self,layer,g,p) for p in range(2)])
        # Stable merge: common max, two exp scale factors, scaled denominator
        # and numerator sums, then one final normalization. Same64 PV lanes;
        # two state contexts and merge arithmetic are charged separately.
        self.actions['softmax_EXP']+=8
        self.actions['softmax_FP32_MUL']+=4*(258+134)
        self.actions['softmax_FP32_ADD']+=4*(129+6)
        self.actions['softmax_RECIP_SEED']+=4
        self.actions['attention_output_BF16']+=512
        self.actions['split_merge_groups']+=1
        yield from self.delay(4*(1330+1290+1590),'split_merge_and_normalize_proxy')
        yield from self.h.transfer(self.att[g],122880,1024,True,'attention_output')
    elif self.attention_path.endswith('_broadcast'):yield from broadcast(self,layer,g)
    else:yield from BaselineDecode.attention_group(self,layer,g)
