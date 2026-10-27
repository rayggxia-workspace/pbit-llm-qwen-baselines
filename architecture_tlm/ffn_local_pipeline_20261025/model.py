"""Two finite local weight banks, one SC compute/counter/restore pipeline.

Next-bank programming overlaps only within the same output/window, where
current restore makes no shared-SRAM accesses. Boundary work keeps original
SRAM priority. This intentionally conservative schedule cannot issue a future
prefill ahead of an earlier-ready partial write. Ordinary operators unchanged.
"""
import hashlib
import json
import math
from collections import Counter
from ..unified_v6.ffn_locality import LocalityFFN
from ..unified_v6.ffn_latest import batch_cycles
from ..unified_v6.core import ceildiv


class LocalPipelineFFN(LocalityFFN):
    def __init__(self, owner):
        super().__init__(owner)
        self.opt=owner.c.get('local_pipeline',{})
        self.overlap=self.opt.get('overlap',True)
        self.bypass=self.opt.get('weight_bypass',False)
        self.cross_window_program=self.opt.get('cross_window_program',False)
        c=owner.c['sram'];supply=min(c['fabric_GBs'],c['banks']*c['word_bytes']*c['clock_hz']/1e9)
        if not self.bypass and self.f['local_weight_load_bytes_per_cycle']/owner.period<supply:
            raise ValueError('shared receiver requires explicit SRAM throttling; no implicit FIFO')
        self.bank_tickets=[None,None];self.bank_generation=[0,0]
        self.response_ticket=None;self.serial=0;self.active_bank=None;self.receipts=[];self.stats=Counter()
        self.order_hash=hashlib.sha256();self.logical_frames=hashlib.sha256()
        bank=self.local['weight_hold_bytes'];coef=self.local['tile_coefficient_and_exponent_bits']//8
        self.local.update(weight_hold_bytes=2*bank,local_weight_banks=2,
            additional_weight_bank_bytes=bank,
            tile_coefficient_and_exponent_bits=2*coef*8,
            additional_coefficient_bank_bytes=coef,
            dma_prefetch_buffer_bytes=bank+coef)
        self.bank_capacity=bank;self.coef_capacity=coef

    def issue_local(self,ready,name,job):
        kw,stop,j,n,k,kg,off,size,co,lt=job
        if self.response_ticket is not None:raise AssertionError('DMA response buffer still occupied')
        bank=self.serial%2;self.serial+=1
        if self.bank_tickets[bank] is not None:raise AssertionError('local bank overwritten')
        if size>self.bank_capacity or lt*4>self.coef_capacity:raise AssertionError('finite bank overflow')
        self.bank_generation[bank]+=1
        o=self.o;slot=o.slot_serial%2;o.slot_serial+=1
        ready=max(ready,o.slot_free[slot])
        wdone=o.dram.tensor(ready,name,off,size)
        # Same single DMA actor, bounded response buffers. Coefficients remain
        # tagged per bank; never replace the active bank's coefficient copy.
        cdone=o.dram.tensor(wdone,name,o.matrix_info[name]['bytes']+co,lt*4,kind='weight_scales')
        ticket=dict(id=self.serial,bank=bank,generation=self.bank_generation[bank],
            slot=slot,name=name,job=job,bytes=size,coefficient_bytes=lt*4,
            issue_ns=ready,weight_dma_done_ns=wdone,coefficient_dma_done_ns=cdone)
        self.bank_tickets[bank]=ticket;self.response_ticket=ticket
        self.stats['issued']+=1;self.stats['weight_load_bytes']+=size;self.stats['coefficient_load_bytes']+=lt*4
        self.stats['max_live_banks']=max(self.stats['max_live_banks'],sum(x is not None for x in self.bank_tickets))
        o.e.action('SC_DMA_response_buffer_write_byte',size+lt*4,'weight_interface')
        return ticket

    def program(self,ready,ticket):
        o=self.o;f=self.f;bank=ticket['bank'];size=ticket['bytes'];slot=ticket['slot'];nc=ticket['coefficient_bytes']
        if self.bank_tickets[bank] is not ticket:raise AssertionError('stale bank generation')
        start=max(ready,ticket['weight_dma_done_ns'])
        if not self.bypass:
            start=o.mem.transfer(start,o.slots[slot],size,True,'weight_fill')
            # Shared read and receiver are a single transfer. Reserve both
            # sides for its duration; other bank may be computing concurrently.
            resources=['sram_fabric','sc_local_program_bus','sc_weight_bank:'+str(bank)]+[
                'sram_bank:'+str(b) for b in range(o.c['sram']['banks'])]
            start=max([start]+[o.s.free[x] for x in resources])
            read_done=o.mem.transfer(start,o.slots[slot],size,False,'weight_consume')
        else:
            start=max(start,o.s.free['sc_local_program_bus'],o.s.free['sc_weight_bank:'+str(bank)])
            read_done=start
            o.e.action('SC_shared_SRAM_bypass_weight_byte',size,'weight_interface')
        duration=max(read_done-start,ceildiv(size,f['local_weight_load_bytes_per_cycle'])*o.period)+o.period
        end=o.s.reserve('SC_local_weight_program',start,duration,
            ('sc_local_program_bus','sc_weight_bank:'+str(bank)),o.period,bank=bank)
        ticket.update(program_start_ns=end-duration,program_done_ns=end)
        o.e.action('SC_local_weight_program_byte',size,'weight_interface')
        coef_ready=max(end,ticket['coefficient_dma_done_ns'])
        if not self.bypass:
            coef_ready=o.mem.transfer(coef_ready,o.ffn_coefficient_scratch,nc,True,'weight_scales')
            coef_ready=o.mem.transfer(coef_ready,o.ffn_coefficient_scratch,nc,False,'weight_scales')
        else:
            coef_ready=o.s.reserve('SC_local_coefficient_program',coef_ready,
                ceildiv(nc,4)*o.period,('sc_local_program_bus',),o.period)
            o.e.action('SC_shared_SRAM_bypass_coefficient_byte',nc,'weight_interface')
        o.e.action('SC_local_coefficient_bank_write_byte',nc,'weight_interface')
        o.e.action('SC_DMA_response_buffer_read_byte',size+nc,'weight_interface')
        o.slot_free[slot]=coef_ready
        ticket['ready_ns']=coef_ready
        if self.response_ticket is not ticket:raise AssertionError('response ownership')
        self.response_ticket=None
        self.stats['programmed']+=1
        return coef_ready

    def execute(self,t,n,kg,kind,first):
        o=self.o;f=self.f;T=64 if kind=='gu' else f['nonlinear_samples'];B=4 if kind=='gu' else 7
        t=self.context(t,kind,kg,first)
        batches=ceildiv(kg,self.c['source_groups'])
        ii=batches*(1 if kind=='gu' else 2)
        # R1/64: calibrated against actual v6 array service 74/137 cycles.
        cycles=1+(T-1)*ii+8+2+(
            (batches-1)*2 if kind=='down' else 0)
        start=t
        t=o.s.reserve('SC_locality_'+kind,t,cycles*o.period,
            ['sc:'+str(i) for i in range(ceildiv(n,self.c['tile']))]+
            ['sc_weight_bank:'+str(self.active_bank),'locality_stream'],o.period,
            samples=T,K64_groups=kg,source_groups=self.c['source_groups'],II=ii)
        self.locality_counts['physical_waves']+=1
        self.locality_counts['logical_64_tiles']+=n//64*kg
        self.locality_counts['sample_cycles']+=cycles
        trials=n*64*kg*T
        o.metadata['SC_64x64_tiles']+=n//64*kg
        o.metadata['SC_product_trials']+=trials
        o.metadata['SC_accepted_stream_samples']+=T*kg
        o.metadata['SC_4bucket_tiles' if kind=='gu' else 'SC_7bucket_tiles']+=n//64*kg
        o.e.action('SC_W8_magnitude_AND',trials*7,'SC_compute')
        o.e.action('SC_product_sign_XOR',trials,'SC_compute')
        o.e.action('SC_weighted_bitplane_compress_bit_work',n*kg*B*7*120*T,'SC_compute')
        o.e.action('SC_signed_temporal_accumulate',n*kg*B*T,'SC_compute')
        o.e.action('SC_bucket_route',trials,'SC_compute')
        o.e.action('locality_R8_word_demand',kg*T*(1 if kind=='gu' else 192),'FFN_locality')
        o.e.action('locality_endpoint_update',kg*T*(1 if kind=='gu' else 10),'FFN_locality')
        o.e.action('locality_live_code_read_bit',kg*64*(16 if kind=='gu' else 32),'FFN_locality')
        if kind=='down':
            o.e.action('AND_threeway_comparison',kg*192*T,'SC_nonlinear')
            o.e.action('AND_two_input_gate',kg*128*T,'SC_nonlinear')
        return start,t

    def matrix_local(self,t,layer,kind):
        o=self.o;f=self.f;name='L%d/'%layer+('gu' if kind=='gu' else 'down')
        info=o.matrix_info[name];K=info['inp']//64;O=info['out'];width=f['engines']*self.c['tile']
        R=min(K,self.c['retain_k64_groups']);B=4 if kind=='gu' else 7
        cb=128 if kind=='gu' else 256;base=o.locality_x_codes if kind=='gu' else o.z
        jobs=[];off=co=0
        for kw in range(0,K,R):
            stop=min(K,kw+R)
            for j in range(0,O,width):
                n=min(width,O-j)
                for k in range(kw,stop,self.q):
                    kg=min(self.q,stop-k);size=n*kg*64;lt=n//64*kg
                    jobs.append((kw,stop,j,n,k,kg,off,size,co,lt));off+=size;co+=lt*4
        if off!=info['bytes'] or co!=info['scale_bytes']:raise AssertionError('weight coverage')
        ticket=None;prev_kw=None
        for index,job in enumerate(jobs):
            kw,stop,j,n,k,kg,off,size,co,lt=job
            if kw!=prev_kw:
                t=o.mem.transfer(t,base+kw*cb,(stop-kw)*cb,False,'locality_code_window')
                o.e.action('locality_code_window_write_bit',(stop-kw)*cb*8,'FFN_locality');prev_kw=kw
            if k==kw:
                if kw:t=o.mem.transfer(t,o.matrix_output+j*8,n*8,False,'SC_wide_partial')
                else:t=o.s.reserve('locality_partial_clear',t,o.period,('locality_accumulator',),o.period)
            if ticket is None:ticket=self.issue_local(t,name,job)
            before=t
            if 'ready_ns' not in ticket:self.program(t,ticket)
            t=max(t,ticket['ready_ns']);self.stats['exposed_supply_wait_ns']+=t-before
            self.active_bank=ticket['bank']
            start,end=self.execute(t,n,kg,kind,j==0)
            ticket.update(compute_start_ns=start,compute_done_ns=end)
            order=[name,kw,j,k,kg,n];self.order_hash.update(json.dumps(order,separators=(',',':')).encode()+b'\n')
            # Logical frame IDs and replay order are independent of physical
            # schedule. Actual endpoint is still a bounded timing macro.
            self.logical_frames.update(json.dumps([name,k,kg,j==0],separators=(',',':')).encode()+b'\n')
            next_ticket=None
            if index+1<len(jobs):
                nxt=jobs[index+1];next_ticket=self.issue_local(start,name,nxt)
                if self.overlap and ((nxt[0]==kw and nxt[2]==j) or self.cross_window_program):
                    self.program(start,next_ticket)
                    self.stats['early_programs']+=1
                    if nxt[0]!=kw or nxt[2]!=j:self.stats['cross_window_early_programs']+=1
                    self.stats['program_compute_overlap_ns']+=max(0.,min(end,next_ticket['program_done_ns'])-max(start,next_ticket['program_start_ns']))
                else:self.stats['boundary_or_disabled_deferred_programs']+=1
            t=end
            for g in range(kg):
                t=self.macro(t,'SC_bucket_shift_reduce',n*B,f.get('bucket_reduce_lanes',64),3)
                t=self.macro(t,'SC_coefficient16_restore',n,f['restore_lanes'],f['restore_latency'])
                t=o.s.reserve('locality_accumulator_update',t,
                    batch_cycles(n,f['accumulate_lanes'],f['accumulate_latency'])*o.period,
                    ('locality_accumulator',),o.period)
                o.e.action('locality_partial_register_update_bit',n*64,'FFN_locality')
                if k+g:o.e.action('SC_cross_tile_add64',n,'FFN_macro')
            if k+kg==stop:
                t=o.mem.transfer(t,o.matrix_output+j*8,n*8,True,'SC_wide_partial')
                self.locality_counts['partial_write_bytes']+=n*8
                if kw:self.locality_counts['partial_read_bytes']+=n*8
            ticket['retire_ns']=t
            if ticket['compute_start_ns']+1e-6<ticket['ready_ns'] or t<end:raise AssertionError('ticket dependency')
            self.bank_tickets[ticket['bank']]=None
            self.stats['retired']+=1;self.locality_counts['weight_bytes']+=size
            if len(self.receipts)<o.c['trace_event_limit']:self.receipts.append(dict(ticket))
            ticket=next_ticket
        if ticket or self.response_ticket or any(self.bank_tickets):raise AssertionError('pipeline not drained')
        self.locality_counts['completed_matrices']+=1
        return t

    def report(self):
        r=super().report()
        r['local_pipeline']=dict(config=self.opt,counts=dict(self.stats),records=self.receipts,
            records_truncated=self.stats['retired']>len(self.receipts),
            bank_capacity_bytes=self.bank_capacity,coefficient_bank_bytes=self.coef_capacity,
            max_weight_response_bytes=self.bank_capacity,max_coefficient_response_bytes=self.coef_capacity,
            logical_job_order_sha256=self.order_hash.hexdigest(),logical_frame_order_sha256=self.logical_frames.hexdigest(),
            contract=('two local weight/coefficient banks; one SC/counter/restore pipeline; next inactive bank may preprogram across output/input windows' if self.cross_window_program else 'two local weight/coefficient banks; one SC/counter/restore pipeline; preprogram only within output window; boundary SRAM priority preserved'),
            energy_J=None,area_mm2=None,actual_endpoint_executed=False,
            seed_note='same logical frame sequence; wall-clock reseed epoch may differ, no bitwise endpoint equivalence claim')
        return r
