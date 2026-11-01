"""Observational stall accounting. No new events, queues, or timing rules."""
from collections import Counter,defaultdict
import inspect,math

class SharedAudit:
    def __init__(self,model):
        self.m=model;self.h=model.h;self.phase=None;self.rows=[];self.current=None
    def metric(self,key,value=1):self.current['metrics'][key]+=value
    def span(self,actor,state,start,end):
        if self.current is None:return
        rec=self.current['actors'].setdefault(actor,Counter());rec[state]+=end-start
    def state(self,gen,condition):
        frames=[];g=gen
        while inspect.isgenerator(g):
            frames.append((g.gi_code.co_name,g.gi_frame.f_locals if g.gi_frame else {}));g=g.gi_yieldfrom
        # Classify the most specific source-level operation, not its parent.
        for name,f in reversed(frames):
            if name=='transfer':return 'SRAM:'+f['tag']
            if name=='delay' and 'name' in f:return 'macro:'+f['name']
        root=frames[0][1] if frames else {}
        loaded=root.get('loaded',root.get('state',{}).get('loaded',{}))
        if any(condition is s for s in loaded.values()):return 'wait_weight_ready'
        if any(name=='qk_stream' for name,_ in frames):
            f=next(f for name,f in frames if name=='qk_stream');return 'QK_pipeline:'+f['kind']
        if any(name=='delay' for name,_ in frames):return 'pipeline_tail'
        if gen.gi_code.co_name=='consume':return 'QK_operand_completion'
        if gen.gi_code.co_name=='attention_group':return 'sampler_V_pipeline'
        return 'nested_dependency'
    def trace(self,gen,actor):
        try:condition=next(gen)
        except StopIteration as s:return s.value
        while True:
            start=self.h.now;state=self.state(gen,condition)
            yield condition
            self.span(actor,state,start,self.h.now)
            try:condition=next(gen)
            except StopIteration as s:return s.value
    def install(self):
        m=self.m;h=self.h;mem=h.mem;phase=m.phase;managed=m._managed
        def observed_managed(main,loaders):
            caller=inspect.currentframe().f_back;f=caller.f_locals;name=caller.f_code.co_name
            if name=='worker':actor=('GU' if '.sc_gu.' in main.gi_code.co_qualname else 'NL')+':'+str(f['engine'])
            elif name=='digital_matrix':actor='digital:'+f['name']
            elif name=='qk_stream':actor='QK:'+str(f['g'])+':'+f['kind']
            else:actor='managed:'+name
            return managed(self.trace(main,actor),loaders)
        m._managed=observed_managed
        def observed_phase(name,generators,layer):
            self.phase=(layer,name);start=h.now
            self.current=dict(layer=layer,stage=name,metrics=Counter(),actors={},sram_before=Counter(mem.count),
                              memory_before=Counter(h.count),actions_before=Counter(m.actions),compute_before=Counter(m.compute),kernels_before=Counter(m.kernel_active))
            # Attention groups have top-level scalar macros outside _managed.
            gens=[]
            for i,g in enumerate(generators):
                if g.gi_code.co_name=='attention_group':g=self.trace(g,'Attention:'+str(g.gi_frame.f_locals['g']))
                gens.append(g)
            result=phase(name,gens,layer);r=self.current;r['elapsed_ns']=h.now-start
            for field,counter in [('sram',mem.count),('memory',h.count),('actions',m.actions),('compute',m.compute),('kernels',m.kernel_active)]:
                key=field+'_before';before=r.pop(key);r[field+'_delta']={k:v-before[k] for k,v in counter.items() if v-before[k]}
            r['actors']={a:dict(v) for a,v in r['actors'].items()};r['metrics']=dict(r['metrics']);self.rows.append(r);self.current=None
            return result
        m.phase=observed_phase
        submit=mem.submit
        def observed_submit(region,offset,size,write,tag,callback):
            start=h.now;words=math.ceil((offset%mem.word+size)/mem.word)
            per=min(len(region.banks),mem.fabric_words)
            ideal=math.ceil((start-1e-9)/mem.period)*mem.period+(math.ceil(words/per)-1)*mem.period+mem.access_ns
            if h.common_period_ns:ideal=math.ceil((ideal-1e-9)/h.common_period_ns)*h.common_period_ns
            row=self.current
            def completed():
                if row is not None:
                    c=row['metrics'];c['transfer_count:'+tag]+=1;c['transfer_latency_ns:'+tag]+=h.now-start
                    c['transfer_excess_over_isolated_ns:'+tag]+=max(0,h.now-ideal)
                callback()
            return submit(region,offset,size,write,tag,completed)
        mem.submit=observed_submit
        tick=mem._tick
        def observed_tick():
            before=mem.count['read_words']+mem.count['write_words'];tick()
            granted=mem.count['read_words']+mem.count['write_words']-before
            if self.current is not None:
                self.metric('sram_ticks',1);self.metric('sram_granted_words',granted)
                self.metric('fabric_full_with_queue_cycles',int(granted==mem.fabric_words and bool(mem.queue)))
        mem._tick=observed_tick
        dma=h.dma
        def observed_dma(owner,address,size,region,offset,kind,callback,write=False,spans=None):
            start=h.now;row=self.current
            def completed():
                if row is not None:row['metrics']['descriptor_count:'+kind]+=1;row['metrics']['descriptor_latency_ns:'+kind]+=h.now-start
                callback()
            return dma(owner,address,size,region,offset,kind,completed,write,spans)
        h.dma=observed_dma
        step=h.backend.step;sent={}
        def observed_step(until,requests=()):
            start=h.now;n=len(h.pending)+len(requests);queued=bool(h.active_owners)
            for req in requests:sent[req['id']]=(start,self.current)
            state=self.current
            if state is not None:
                c=state['metrics'];c['issued_bytes']+=64*len(requests)
                for req in requests:c['channel_bytes:'+str((req['address']>>6)&7)]+=64
            credit_full=n>=h.credit;reserved_full=h.return_occupied+n*64>=h.response_bytes
            result=step(until,requests);dt=result['now_ns']-start
            if state is not None:
                c=state['metrics'];c['outstanding_integral_request_ns']+=n*dt
                c['with_outstanding_ns']+=dt*bool(n);c['no_DDR_demand_ns']+=dt*(not n and not queued)
                c['queued_and_credit_full_ns']+=dt*(queued and credit_full)
                c['queued_and_response_reserved_full_ns']+=dt*(queued and reserved_full)
                c['queued_injection_pacing_ns']+=min(dt,max(0,h.issue_at-start))*(queued and not credit_full and not reserved_full)
            for reply in result['responses']:
                began,row=sent.pop(reply['id']);lat=reply['done_ns']-began
                if row is not None:
                    c=row['metrics'];c['request_count']+=1;c['request_RTT_sum_ns']+=lat;c['request_RTT_max_ns']=max(c['request_RTT_max_ns'],lat)
            return result
        h.backend.step=observed_step
        return self
    def report(self):
        return dict(scope='driver-blocking states and interface observations, not physical MAC toggles',phases=self.rows,
                    overlap_rule='Per-core state durations partition that core driver; parent Attention and child QK must not be added. Endpoint-full times can overlap; SRAM latency sums are not wall time.')
