from collections import deque
from .qk_layout import local_delay
def pv_consumer(model, region, queues, busy, cache, consumed, producer, produce,
                feedback, head_issue, last_result, lanes, audit):
    """One independent consumer/head; two 32B read credits, including in-flight.

    No data values in TLM. Credit/ordering, scalar-operation and byte ledgers
    are explicit. Buffer storage and selectors require separate PPA.
    """
    from architecture_tlm.unified_v6.shared_memory import align_time
    h=model.h;period=model.compute_period_ns
    def consume(head):
        if busy[head] or not queues[head]:return
        index=queues[head][0]
        if cache.get(index)!='valid':return
        queues[head].popleft();busy[head]=True
        state={'read':0,'issued':0,'credits':0,'ready':{},'scheduled':False}
        def fill():
            while state['credits']<2 and state['read']<8:
                j=state['read'];state['read']+=1;state['credits']+=1
                audit['max_words_per_head']=max(audit['max_words_per_head'],state['credits'])
                def arrived(j=j):
                    state['ready'][j]=True
                    dispatch()
                h.mem.submit(region,65536+index*256+j*32,32,False,'sample_V_operand',arrived)
        def dispatch():
            j=state['issued']
            if state['scheduled'] or j not in state['ready']:return
            state['scheduled']=True
            begin=align_time(max(h.now,head_issue[head]),period)
            # Each word covers sixteen consecutive dimensions. Fixed splitting
            # preserves the sample order of additions for each dimension.
            for sub in range(16//lanes):
                chunk=j*(16//lanes)+sub
                t=max(begin+sub*period,feedback[head][chunk])
                t=align_time(t,period)
                def issue(chunk=chunk,t=t):
                    assert t>=feedback[head][chunk]
                    feedback[head][chunk]=t+7*period
                    last_result[0]=max(last_result[0],t+7*period)
                    model.actions['PV_ADD']+=lanes
                    audit['scalar_adds']+=lanes
                    if hasattr(model,'pv_issue_probe'):model.pv_issue_probe(head,index,chunk,lanes,t)
                h.later(t,issue)
            end=t
            head_issue[head]=end+period
            def release():
                state['credits']-=1;del state['ready'][j]
                state['issued']+=1;state['scheduled']=False
                if state['issued']==8:
                    assert state['credits']==0 and not state['ready']
                    busy[head]=False;consumed[head]+=1
                    if producer['held']:
                        producer['held']=False;h.later(h.now,produce)
                    consume(head)
                else:
                    fill();dispatch()
            h.later(end,release)
        fill()
    return consume


def sampled_small(self,layer,g):
    from architecture_tlm.digital_fair_20261105.joint_handoff.attention import adapter as old
    period=self.compute_period_ns;h=self.h;region=self.att[g];base=self.kv_bases[layer,g];n=self.N
    yield from self.compact_screen(layer,g)
    candidates=self.extra_input['rows'][(layer%3)*8+g]['candidates']
    self.actions['sampler_queries']+=4
    yield from h.transfer(region,16384,2048,False,'sampler_score_input')
    yield from local_delay(self,period,'FP32_to_S12_pipeline_tail_proxy')
    lease=yield from self.sampler_pool.acquire(g,'sampler')
    self.actions['FP32_to_S12']+=512
    top=old.SAMPLED[self.attention_path];events=[];offset=0
    for head in range(4):
        q=self.sample_input['samples']['%s/%d/%d/%d'%(top,self.seed,g,layer%3*4+head)]
        indices=q['indices'];assert len(indices)==q['hits']
        first=q['cycles'] if self.sample_timings=='late' else q['first']
        for j,index in enumerate(indices):events.append((offset+max(0,first+j)*period,head,index,1))
        offset+=max(q['cycles']+1,max(0,first)+len(indices)+1)*period
    self.actions['samples']+=len(events);self.actions['sample_output_BF16']+=512
    queues=[deque() for _ in range(4)];busy=[False]*4;cache={}
    producer={'index':0,'shift':0.,'held':False};consumed=[0]*4
    feedback=[[0.]*(128//self.pv_lanes) for _ in range(4)];head_issue=[h.now]*4
    last_result=[h.now];start=h.now
    audit=dict(layer=layer,group=g,lanes_per_head=self.pv_lanes,max_words_per_head=0,scalar_adds=0)
    self.resource_audit['PV'].append(audit)
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
        if producer['index']==len(events):
            h.later(max(h.now,start+offset+producer['shift']),lambda:self.sampler_pool.release(g,lease))
        if producer['index']<len(events):
            h.later(max(h.now,start+events[producer['index']][0]+producer['shift']),produce)
    consume=pv_consumer(self,region,queues,busy,cache,consumed,producer,produce,
                       feedback,head_issue,last_result,self.pv_lanes,audit)
    if events:h.later(start+events[0][0],produce)
    else:h.later(start+offset,lambda:self.sampler_pool.release(g,lease))
    yield lambda:sum(consumed)==len(events)
    finish=max(last_result[0],start+offset+producer['shift'])
    if h.now<finish:yield from h.delay(finish-h.now)
    assert len(cache)<=128 and not any(queues) and not any(busy)
    assert audit['scalar_adds']==len(events)*128
    audit.update(sample_count=len(events),duration_ns=h.now-start,
                 backpressure_shift_ns=producer['shift'])
    self.actions['sample_queue_peak_capacity']=128
    yield from local_delay(self,16*period,'sample_normalize_BF16_macro')
    yield from h.transfer(region,122880,1024,True,'attention_output')

