"""Real BeatSRAM events, 1 KiB scratch and 128 B transpose staging per KV group.

No data values are buffered by this timing actor. Ready metadata represents
only the two declared SRAM slots. A 32 B SRAM response is captured by the
existing FMA operand register and broadcast to four Q slices. Four feedback
contexts are retained; sequential FMA order differs from a grouped reduction.
"""
from types import MethodType
from architecture_tlm.unified_v6.shared_memory import Signal, BeatSRAM, align_time

PERIOD = 10
SCRATCH = 49152  # In the existing64KiB Attention region, away from live objects.


def install(model, feedback_cycles=4, operand_credits=4):
    if model.h.now or model.mac_lanes != 640 or model.N != 2048:
        raise ValueError('install on the selected 100MHz/640/2K host before work')
    if feedback_cycles < 1 or operand_credits not in (1,4):
        raise ValueError('positive FMA feedback latency')
    if model.resource_contract['independent_QK_lanes'] != 0:
        raise ValueError('install the shared QK candidate first')
    capacities={r.size for r in model.att}
    if capacities not in ({65536},{49152}):raise ValueError('unsupported QK scratch layout')
    # SelectedK0..32KiB and scores32..34KiB are disjoint from34..35KiB
    # scratch; coarse scores have been consumed before selected transposition.
    scratch=34816 if capacities=={49152} else SCRATCH
    assert scratch+1024<=min(capacities)
    model.qk_supply_audit=[]
    model.qk_supply_active=set()
    model.qk_supply_contract=dict(clock_MHz=100, SRAM_clock_MHz=100,
        feedback_cycles=feedback_cycles, feedback_basis='FMA16/C4 existing L4 contract; not new RTL',
        groups=8, lanes_per_group=64, transpose_SRAM_bytes_per_group=1024,
        transpose_register_bytes_per_group=128, operand_capture='existing FMA input register',
        coarse_operand_credits=operand_credits,
        coarse_operand_FIFO_bytes_per_group=128 if operand_credits==4 else 0,
        SRAM_capacity_added=0, scratch_offset=scratch, ports='existing16B/1RW physical banks',
        default_changed=False, new_PPA=False, new_PPL=False,
        scope='bounded transaction timing; no numerical data stored in simulator')
    model.resource_contract.update(QK_transpose_SRAM_bytes=8192,
        QK_transpose_staging_register_bytes=1024,
        QK_coarse_operand_FIFO_bytes=1024 if operand_credits==4 else 0,
        QK_real_bank_supply=True,QK_new_route_PPA='macro proxy, not integrated synthesis')
    phase={'name':None}
    previous_phase=model.phase
    def run_phase(self,name,generators,layer):
        assert not self.qk_supply_active and phase['name'] is None
        phase['name']=name
        try:return previous_phase(name,generators,layer)
        finally:
            assert not self.qk_supply_active
            phase['name']=None
    model.phase=MethodType(run_phase,model)
    original_submit=model.h.mem.submit
    # These are explicit PHYSICAL offsets in the compact region. Existing
    # semantic translation does not know the newly introduced scratch role.
    def submit(region, offset, size, write, tag, callback):
        if tag.startswith('qksupply_'):
            assert region in model.att and 0 <= offset and offset+size <= region.size
            return BeatSRAM.submit(model.h.mem,region,offset,size,write,tag,callback)
        return original_submit(region,offset,size,write,tag,callback)
    model.h.mem.submit=submit

    def begin(g,kind):
        assert phase['name']=='attention' and g not in model.qk_supply_active
        model.qk_supply_active.add(g)
        assert len(model.qk_supply_active)*64 <= model.mac_lanes
        row=dict(group=g,kind=kind,start_ns=model.h.now,vectors=0,
            feedback_wait_ns=0,operand_read_wait_ns=0,ready_wait_ns=0,
            transpose_read_bytes=0,transpose_write_bytes=0,operand_read_bytes=0,
            max_ready_tiles=0,bank_layout='host existing word interleave; no free swizzle')
        model.qk_supply_audit.append(row)
        model.resource_audit['QK_leases'].append(row)
        return row

    def end(g,row):
        model.qk_supply_active.remove(g)
        row.update(end_ns=model.h.now,duration_ns=model.h.now-row['start_ns'],
            ideal_issue_cycles=row['vectors'],scalar_MAC=row['vectors']*64)

    def issue(self,r,offset,context,feedback,stats):
        h=self.h
        start=h.now
        yield from h.transfer(r,offset,32,False,'qksupply_K_operand')
        stats['operand_read_wait_ns']+=h.now-start
        # Fetch first, then wait on feedback. One vector is held at the input,
        # rather than needlessly serializing SRAM access after feedback wait.
        t=align_time(max(h.now,feedback[context]),PERIOD)
        if t>h.now:
            stats['feedback_wait_ns']+=t-h.now
            yield from h.delay(t-h.now)
        # Synchronous SRAM response is accepted by the existing input register.
        feedback[context]=h.now+feedback_cycles*PERIOD
        self.actions['attention_QK_MAC']+=64
        stats['vectors']+=1;stats['operand_read_bytes']+=32

    def stream(self,r,offsets,feedback,stats):
        """Four32B coarse operand slots, including outstanding requests."""
        h=self.h;done=Signal();state=dict(read=0,issued=0,live=0,ready=set(),scheduled=False)
        next_issue=[h.now];last=[h.now]
        def fill():
            while state['live']<4 and state['read']<len(offsets):
                j=state['read'];state['read']+=1;state['live']+=1
                stats['max_operand_credits']=max(stats.get('max_operand_credits',0),state['live'])
                def arrived(j=j):state['ready'].add(j);dispatch()
                h.mem.submit(r,offsets[j],32,False,'qksupply_K_operand',arrived)
        def dispatch():
            j=state['issued']
            if state['scheduled'] or j not in state['ready']:return
            c=j%4;state['scheduled']=True
            t=align_time(max(h.now,next_issue[0],feedback[c]),PERIOD)
            stats['feedback_wait_ns']+=max(0,t-max(h.now,next_issue[0]))
            def accept():
                state['live']-=1;state['ready'].remove(j);state['issued']+=1;state['scheduled']=False
                feedback[c]=h.now+feedback_cycles*PERIOD;next_issue[0]=h.now+PERIOD;last[0]=feedback[c]
                self.actions['attention_QK_MAC']+=64;stats['vectors']+=1;stats['operand_read_bytes']+=32
                if state['issued']==len(offsets):
                    assert state['live']==0
                    h.later(max(feedback),done.set)
                else:fill();dispatch()
            h.later(t,accept)
        start=h.now;fill();yield done
        stats['coarse_stream_elapsed_ns']=stats.get('coarse_stream_elapsed_ns',0)+h.now-start

    def coarse(self,layer,g,spans,kind):
        """Read the SAME external multiset in64-token/all32-dimension blocks.

        This completes one64-token group with four live contexts before reuse;
        it does not retain2048 partial sums in invisible context registers.
        Existing two8KiB allocations hold two4KiB source blocks.
        """
        assert kind=='coarse_K' and len(spans)==32
        h=self.h;r=self.att[g];stats=begin(g,'coarse')
        ready=[Signal() for _ in range(self.N//64)];pending={}
        def load(k):
            s=[(address+k*128,128) for address,n in spans]
            assert all(n==self.N*2 for _,n in spans)
            yield from h.fetch('Attention'+str(g),s[0][0],4096,r,k%2*8192,'coarse_K',spans=s)
            ready[k].set()
        def consume():
            for k in range(len(ready)):
                yield ready[k]
                feedback=[h.now]*4
                if operand_credits==4:
                    yield from stream(self,r,[k%2*8192+j*32 for j in range(128)],feedback,stats)
                else:
                    for d in range(32):
                        for c in range(4):
                            yield from issue(self,r,k%2*8192+(d*4+c)*32,c,feedback,stats)
                finish=max(feedback)
                if h.now<finish:yield from h.delay(finish-h.now)
                if k+2<len(ready):pending[k+2]=load(k+2)
        pending[0]=load(0);pending[1]=load(1)
        yield from self._managed(consume(),pending)
        end(g,stats)
    model.qk_stream=MethodType(coarse,model)

    def selected(self,layer,g,candidates):
        """One32KiB raw source, two512B transposed tiles, one128B microtile.

        Producer and consumer overlap. Consumer may interleave the two ready
        tiles, but cannot issue a context before its preceding result returns.
        Scratch is released only after its last read has completed.
        """
        h=self.h;r=self.att[g];stats=begin(g,'selected')
        slots=[None,None]
        for batch in range(2):
            items=[(d0,c) for d0 in range(0,128,16) for c in range(4)]
            feedback=[h.now]*4;next_dimension=[0]*4
            def producer():
                for index,(d0,c) in enumerate(items):
                    slot=index%2
                    yield lambda slot=slot:slots[slot] is None
                    state=dict(context=c,d0=d0,next=0,ready=False)
                    slots[slot]=state
                    token0=batch*64+c*16
                    # A single8x8 microtile at a time,128B physical staging.
                    for rr in (0,8):
                        for cc in (0,8):
                            done=[Signal() for _ in range(8)]
                            for i in range(8):
                                off=(token0+rr+i)*256+(d0+cc)*2
                                h.mem.submit(r,off,16,False,'qksupply_transpose_source',done[i].set)
                            yield lambda:all(s() for s in done)
                            stats['transpose_read_bytes']+=128
                            writes=[Signal() for _ in range(8)]
                            for j in range(8):
                                off=scratch+slot*512+(cc+j)*32+rr*2
                                h.mem.submit(r,off,16,True,'qksupply_transpose_store',writes[j].set)
                            yield lambda:all(s() for s in writes)
                            stats['transpose_write_bytes']+=128
                    state['ready']=True
                    stats['max_ready_tiles']=max(stats['max_ready_tiles'],sum(s is not None for s in slots))
            def consumer():
                completed=0
                while completed<len(items):
                    start=h.now
                    def available():
                        return any(s and s['ready'] and s['d0']+s['next']==next_dimension[s['context']] for s in slots)
                    yield available
                    stats['ready_wait_ns']+=h.now-start
                    choices=[(max(h.now,feedback[s['context']]),i,s) for i,s in enumerate(slots)
                        if s and s['ready'] and s['d0']+s['next']==next_dimension[s['context']]]
                    _,slot,state=min(choices,key=lambda v:(v[0],v[1]))
                    c=state['context'];j=state['next']
                    yield from issue(self,r,scratch+slot*512+j*32,c,feedback,stats)
                    state['next']+=1;next_dimension[c]+=1
                    if state['next']==16:slots[slot]=None;completed+=1
                assert next_dimension==[128]*4 and not any(slots)
            yield from self._parallel([producer(),consumer()])
            finish=max(feedback)
            if h.now<finish:yield from h.delay(finish-h.now)
        end(g,stats)

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
        yield from selected(self,layer,g,candidates)
        yield from h.transfer(r,16384,2048,True,'selected_scores')
    model.compact_screen=MethodType(screen,model)
    parent=model.run
    def run(self):
        result=parent();assert not self.qk_supply_active
        result['qk_supply_contract']=dict(self.qk_supply_contract)
        result['qk_supply_audit']=self.qk_supply_audit
        result['attention_candidate_integration']['real_bank_supply_events_modeled']=True
        result['attention_candidate_integration']['supply_validation_scope']='transaction model and synthetic layout; not integrated RTL'
        return result
    model.run=MethodType(run,model)
    return model
