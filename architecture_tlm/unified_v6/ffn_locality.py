"""Opt-in K64-preserving FFN output-window locality experiment.

128x128 means four independent 64x64 quadrants, NOT a new K128 scale or
shared128 random sequence. New context-bank ports are bounded timing macros;
this is not a physical implementation of the Issue95 endpoint.
"""
import math
from collections import Counter
from .core import ceildiv
from .ffn_latest import LatestFFN, batch_cycles


def configure(cfg, *, tile=64, engines=8, retain=8, source_groups=1):
    if tile not in (64,128) or min(engines,retain,source_groups)<1:
        raise ValueError('positive geometry/window; tile 64 or 128')
    f=cfg['ffn']
    f.update(engines=engines,local_weight_bytes=engines*tile*tile,
        locality=dict(tile=tile,retain_k64_groups=retain,source_groups=source_groups,
            context_word_bits=32,context_command_cycles=2,
            logical_group=64,accumulator_bits=64))
    cfg['digital_weight_chunk_bytes']=cfg.get('digital_weight_chunk_bytes',cfg['weight_chunk_bytes'])
    cfg['weight_chunk_bytes']=max(cfg['weight_chunk_bytes'],engines*tile*tile)
    return cfg


class LocalityFFN(LatestFFN):
    def __init__(self,o):
        super().__init__(o)
        self.c=self.f['locality'];self.q=self.c['tile']//64
        if self.c['logical_group']!=64 or self.c['accumulator_bits']!=64:
            raise ValueError('preserve existing K64 scales and wide accumulator')
        if self.c['retain_k64_groups']%self.q:
            raise ValueError('window must contain complete physical input groups')
        self.locality_counts=Counter();self.last_seed={}
        self.local.pop('temporal_counter_bits');self.local.pop('reduction_pipeline_bits')
        r=min(self.c['retain_k64_groups'],max(o.h,o.F)//64)
        lanes=self.f['engines']*self.c['tile']
        quadrants=self.f['engines']*self.q*self.q
        self.local.update(weight_hold_bytes=self.f['engines']*self.c['tile']**2,
            temporal_counter_bits=quadrants*64*7*self.counter_bits,
            reduction_pipeline_bits=quadrants*64*self.f['counter_pipeline_bits_per_lane'],
            tile_coefficient_and_exponent_bits=quadrants*32,
            resident_output_partial_bits=lanes*64,
            local_input_code_window_bits=r*64*32,
            input_context_bank_bits=r*32,
            nonlinear_context_bank_bits=r*10*177,
            source_parallel_groups=self.c['source_groups'],
            independent_nonlinear_live_state_bits=self.c['source_groups']*10*177,
            independent_input_live_state_bits=self.c['source_groups']*32,
            dma_prefetch_buffer_bytes=self.f['engines']*self.c['tile']**2)

    def context(self,t,kind,n,new):
        bits=32 if kind=='gu' else 177
        groups=self.c['source_groups']
        now=math.ceil(t/self.o.period)
        if new and (kind not in self.last_seed or
                now-self.last_seed[kind]>=self.f['rng_nl']['reseed_interval_cycles']):
            beats=(1 if kind=='gu' else 60)*groups
            t=self.o.s.reserve('locality_rng_seed_'+kind,t,(beats*100+5)*self.o.period,
                ('locality_seed',),self.o.period)
            self.locality_counts['seed_beats']+=beats
            self.o.e.action('locality_seed_beat',beats,'FFN_locality')
            self.last_seed[kind]=math.ceil(t/self.o.period)
        # Ten NL endpoint contexts move concurrently through ten 32-bit local
        # ports; source_groups limits independent K64 groups, not output columns.
        cycles=ceildiv(n,groups)*(ceildiv(bits,self.c['context_word_bits'])+
                                     self.c['context_command_cycles'])
        t=self.o.s.reserve('locality_context_'+('save' if new else 'restore'),t,
            cycles*self.o.period,('locality_context_port',),self.o.period)
        endpoint_count=1 if kind=='gu' else 10
        self.o.e.action('locality_context_move_bit',n*bits*endpoint_count,'FFN_locality')
        self.locality_counts['new_contexts' if new else 'replayed_contexts']+=n
        return t

    def issue(self,t,name,offset,size,meta):
        if self.o.tile_pipeline is None:
            raise ValueError('locality requires shared finite tile pipeline')
        return self.o.tile_pipeline.issue(t,name,offset,size,'sc',**meta)

    def fill(self,t,ticket,name,coef_offset,logical_tiles):
        o=self.o;f=self.f
        bw=min(o.c['sram']['fabric_GBs'],o.c['sram']['banks']*o.c['sram']['word_bytes']*o.c['sram']['clock_hz']/1e9)
        if f['local_weight_load_bytes_per_cycle']/o.period < bw:
            raise ValueError('local receiver requires explicit SRAM throttling')
        t,slot=o.tile_pipeline.fill(t,ticket)
        resources=['sram_fabric','sc_weight_local_port']+[
            'sram_bank:'+str(b) for b in range(o.c['sram']['banks'])]
        start=max([t]+[o.s.free[r] for r in resources])
        done=o.mem.transfer(start,o.slots[slot],ticket['bytes'],False,'weight_consume')
        duration=max(done-start,ceildiv(ticket['bytes'],f['local_weight_load_bytes_per_cycle'])*o.period)+o.period
        t=o.s.reserve('SC_local_weight_program',start,duration,('sc_weight_local_port',),o.period)
        o.e.action('SC_local_weight_program_byte',ticket['bytes'],'weight_interface')
        n=logical_tiles*4
        t=o.dram.tensor(t,name,o.matrix_info[name]['bytes']+coef_offset,n,kind='weight_scales')
        t=o.mem.transfer(t,o.ffn_coefficient_scratch,n,True,'weight_scales')
        t=o.mem.transfer(t,o.ffn_coefficient_scratch,n,False,'weight_scales')
        return t,slot

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
            ['sc_weight_local_port','locality_stream'],o.period,
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
        code_bytes=128 if kind=='gu' else 256
        code_base=o.locality_x_codes if kind=='gu' else o.z
        # Offline retiled layout follows this schedule. Every logical K64/O64
        # weight block is fetched exactly once, with its own scale coefficient.
        offset=coef_offset=0
        for kw in range(0,K,R):
            stop=min(K,kw+R)
            t=o.mem.transfer(t,code_base+kw*code_bytes,(stop-kw)*code_bytes,False,'locality_code_window')
            o.e.action('locality_code_window_write_bit',(stop-kw)*code_bytes*8,'FFN_locality')
            jobs=[]
            for j in range(0,O,width):
                n=min(width,O-j)
                for k in range(kw,stop,self.q):
                    kg=min(self.q,stop-k);size=n*kg*64;lt=n//64*kg
                    jobs.append((j,n,k,kg,offset,size,coef_offset,lt));offset+=size;coef_offset+=lt*4
            ticket=None
            for index,(j,n,k,kg,off,size,co,lt) in enumerate(jobs):
                if k==kw:
                    if kw:
                        t=o.mem.transfer(t,o.matrix_output+j*8,n*8,False,'SC_wide_partial')
                    else:
                        t=o.s.reserve('locality_partial_clear',t,o.period,('locality_accumulator',),o.period)
                if ticket is None:ticket=self.issue(t,name,off,size,dict(k=k,j=j,n=n))
                t,slot=self.fill(t,ticket,name,co,lt)
                start,end=self.execute(t,n,kg,kind,j==0)
                o.tile_pipeline.compute(ticket,start,end)
                next_ticket=None
                if index+1<len(jobs):
                    jj,nn,kk,kkg,oo,ss,cc,ll=jobs[index+1]
                    next_ticket=self.issue(start,name,oo,ss,dict(k=kk,j=jj,n=nn))
                t=end
                # Preserve per-K64 restoration and ascending K rounding order.
                for g in range(kg):
                    t=self.macro(t,'SC_bucket_shift_reduce',n*B,64,3)
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
                o.tile_pipeline.retire(ticket,t);ticket=next_ticket
                self.locality_counts['weight_bytes']+=size
        if offset!=info['bytes'] or coef_offset!=info['scale_bytes']:
            raise AssertionError('retiled logical weight coverage mismatch')
        self.locality_counts['completed_matrices']+=1
        return t

    def gate_up(self,t,layer):
        o=self.o;f=self.f;t=self.metadata(t,layer)
        for k in range(o.h//64):
            t=o.mem.transfer(t,o.activation+k*128,128,False,'SC_BF16_x')
            t=o.mem.transfer(t,o.fixed_scale_table+2*k,2,False,'SC_fixed_x_scale')
            t=self.macro(t,'SC_fixed4_P8_encode',64,f['encoder_lanes'],f['encoder_latency'])
            t=o.mem.transfer(t,o.locality_x_codes+k*128,128,True,'locality_x_code_store')
            o.metadata['fixed_x_encoded_values']+=64
        return self.matrix_local(t,layer,'gu')

    def down(self,t,layer):return self.matrix_local(t,layer,'down')

    def report(self):
        result=super().report()
        result.update(locality_config=self.c,locality_counts=dict(self.locality_counts),
            random_candidate_status='bounded context-bank macro; not actual Issue95 FFN endpoint execution',
            retile_status='offline K64 blocks reordered; coefficients remain per original K64/O64 block',
            numerical_status='local integer reduction order validated separately; full GU compiler and PPL remain pending')
        result['nonlinear_random']=dict(kind='locality_bounded_context_macro',actual_endpoint_executed=False,
            random_stream_SRAM_bytes=0,area_mm2=None,energy_J=None,
            context_bank_in_local_state=True)
        return result
