"""Finite shared QK service, explicit selected-K transpose and bank swizzle."""
from collections import deque
import math

def word16_address(dimension,token8):
    """Bijection of1024 words; XOR low bank bits with higher row bits."""
    word=dimension*8+token8
    return word ^ ((word>>4)&15)

def word32_address(dimension,context):
    lo=word16_address(dimension,context*2)
    hi=word16_address(dimension,context*2+1)
    assert lo//2==hi//2
    return (lo//2)*32,bool(lo&1)

def local_delay(model,ns,name):
    from architecture_tlm.unified_v6.shared_memory import Signal,align_time
    h=model.h;period=model.compute_period_ns;done=Signal()
    end=align_time(h.now,period)+ns;model.compute[name]+=end-h.now
    h.later(end,done.set);yield done

class Pool:
    def __init__(self,model,lanes):
        self.model=model;self.slots=lanes//64;self.active=set();self.waiters=deque();self.rows=[]
    def acquire(self,g,kind):
        assert self.model.pool_phase=='attention'
        ticket=object();self.waiters.append(ticket);begin=self.model.h.now
        yield lambda:self.waiters[0] is ticket and len(self.active)<self.slots
        self.waiters.popleft();assert g not in self.active;self.active.add(g)
        row=dict(group=g,kind=kind,wait_ns=self.model.h.now-begin,start_ns=self.model.h.now,lanes=64,active_groups=len(self.active))
        self.rows.append(row);return row
    def release(self,g,row):
        assert g in self.active;self.active.remove(g);row['end_ns']=self.model.h.now

def stream_words(model,g,offsets,kind):
    """Four32B credits including in-flight; ordered issue, four FMA16 contexts."""
    from architecture_tlm.unified_v6.shared_memory import Signal,align_time
    h=model.h;period=model.compute_period_ns;r=model.att[g]
    state=dict(read=0,issued=0,credits=0,ready=set(),scheduled=False);done=Signal();last=[h.now]
    audit=dict(group=g,kind=kind,words=len(offsets),max_words=0,scalar_MAC=0,start_ns=h.now)
    model.resource_audit['QK_words'].append(audit)
    def fill():
        while state['credits']<4 and state['read']<len(offsets):
            j=state['read'];state['read']+=1;state['credits']+=1
            audit['max_words']=max(audit['max_words'],state['credits'])
            def arrived(j=j):state['ready'].add(j);dispatch()
            h.mem.submit(r,offsets[j],32,False,kind+'_operand',arrived)
    def dispatch():
        j=state['issued']
        if state['scheduled'] or j not in state['ready']:return
        state['scheduled']=True;t=align_time(max(h.now,last[0]),period)
        def issue():
            model.actions['attention_QK_MAC']+=64;audit['scalar_MAC']+=64
            state['ready'].remove(j);state['credits']-=1;state['issued']+=1;state['scheduled']=False;last[0]=h.now+period
            if state['issued']==len(offsets):
                assert state['credits']==0
                h.later(h.now+4*period,done.set)
            else:fill();dispatch()
        h.later(t,issue)
    fill();yield done
    assert audit['scalar_MAC']==len(offsets)*64
    audit['end_ns']=h.now

def coarse(model,layer,g,dims):
    from architecture_tlm.unified_v6.shared_memory import Signal
    h=model.h;r=model.att[g];base=model.kv_bases[layer,g];n=model.N
    assert n%64==0 and len(dims)==32
    ready=[Signal() for _ in range(n//64)];pending={}
    def load(k):
        spans=[(base+n*256+d*n*2+k*128,128) for d in dims]
        yield from h.fetch('Attention'+str(g),spans[0][0],4096,r,(k%2)*8192,'coarse_K',spans=spans)
        ready[k].set()
    def compute():
        for k in range(n//64):
            yield ready[k];lease=yield from model.qk_pool.acquire(g,'coarse')
            yield from stream_words(model,g,[(k%2)*8192+j*32 for j in range(128)],'coarse_K')
            model.qk_pool.release(g,lease)
            if k+2<n//64:pending[k+2]=load(k+2)
    pending[0]=load(0);pending[1]=load(1)
    yield from model._managed(compute(),pending)

def transpose(model,g):
    """2KiB staging, sixteen finite store credits, actual SRAM read/write costs."""
    from architecture_tlm.unified_v6.shared_memory import Signal
    h=model.h;r=model.att[g]
    for chunk8 in range(8):
        yield from h.transfer(r,chunk8*2048,2048,False,'selected_K_transpose_read')
        done=Signal();state=dict(next=0,inflight=0,completed=0)
        def pump():
            while state['inflight']<16 and state['next']<128:
                d=state['next'];state['next']+=1;state['inflight']+=1
                def written():
                    state['inflight']-=1;state['completed']+=1
                    if state['completed']==128:done.set()
                    else:pump()
                h.mem.submit(r,16384+word16_address(d,chunk8)*16,16,True,'selected_K_transpose_write',written)
        pump();yield done
    model.actions['selected_K_reorder_read_bytes']+=16384
    model.actions['selected_K_reorder_write_bytes']+=16384

def selected(model,layer,g,candidates):
    from architecture_tlm.unified_v6.shared_memory import Signal
    h=model.h;r=model.att[g];base=model.kv_bases[layer,g]
    assert len(candidates)==128
    ready=[Signal(),Signal()];pending={}
    def load(k):
        spans=[(base+t*256,256) for t in candidates[k*64:(k+1)*64]]
        yield from h.fetch('Attention'+str(g),spans[0][0],16384,r,0,'selected_K',spans=spans)
        ready[k].set()
    def compute():
        for k in range(2):
            yield ready[k];yield from model.transpose_call(model,g)
            if k==0:pending[1]=load(1) # raw slot free; transposed slot remains live
            lease=yield from model.qk_pool.acquire(g,'selected')
            offsets=[16384+word32_address(d,c)[0] for d in range(128) for c in range(4)]
            yield from stream_words(model,g,offsets,'selected_K')
            model.qk_pool.release(g,lease)
    pending[0]=load(0);yield from model._managed(compute(),pending)

def screen(self,layer,g):
    h=self.h;r=self.att[g];period=self.compute_period_ns
    yield from self._append(layer,g,True) # append transpose stays at validated host100
    yield from h.transfer(self.vector,196608+g*6144+5120,1024,False,'query_feature_scan')
    yield from local_delay(self,math.ceil(163.333333)*period,'feature_topk_macro')
    row=self.extra_input['rows'][(layer%3)*8+g]
    yield from coarse(self,layer,g,row['dimensions'])
    yield from h.transfer(r,32768,16384,True,'coarse_scores')
    for k in range(3):yield from h.transfer(r,32768,16384,False,'coarse_score_pass'+str(k+1))
    yield from local_delay(self,1730*period,'SparQ_normalize_macro')
    yield from local_delay(self,math.ceil(814.666667)*period,'token_topk_macro')
    yield from selected(self,layer,g,row['candidates'])
    yield from h.transfer(r,16384,2048,True,'selected_scores')
