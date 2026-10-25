"""Fixed-scale W8 / joint-stratified three-stream AND -> Wd schedule.

Timing/resource model, not an inference implementation. The new integer GU
restoration is an explicit, unvalidated numerical macro; never inherits PPL.
No general FP32 nonlinearity, z tensor, or z SNG exists on this path.
"""
import math
from collections import Counter
from .core import ceildiv


def defaults():
    return dict(algorithm='fixed4_and_direct', samples=64, strata=64, bins=4,
        nonlinear_samples=64, joint_strata=[4,2,4], weight_bits=8,
        x_scale_offsets=[0,2,4,6], gu_scale_offsets=[1,3,5,7],
        engines=8, sample_II_cycles=1, startup_cycles=1, drain_cycles=8,
        encoder_lanes=64, encoder_latency=3, encoder_II=1,
        field_lanes=64, field_latency=2, lut_lanes=16, lut_latency=1,
        restore_lanes=16, restore_latency=6, restore_II=1,
        accumulate_lanes=32, accumulate_latency=2,
        bf16_lanes=16, bf16_latency=3,
        local_weight_bytes=8*4096, local_weight_load_bytes_per_cycle=256,
        weight_feed='resident_macro', weight_schedule='legacy', prefetch_across_input_groups=False,
        counter_pipeline_bits_per_lane=512, wide_bits=64, coefficient_bits=16,
        rng_nl=dict(words_per_cycle=192, response_latency=2, stream_II=2,
            command_cycles=2, state_bits_per_endpoint=177, words_per_endpoint=20,
            seed_word_bits=32, seed_word_interval_cycles=100, warmup_cycles=5,
            reseed_interval_cycles=100000000),
        numeric_status='GU fixed-point coefficient/rounding macro pending bit-exact validation; no inherited PPL')


def batch_cycles(count, lanes, latency, ii=1):
    if count <= 0:return 0
    if min(lanes,latency,ii)<1:raise ValueError('positive macro parameters required')
    return (ceildiv(count,lanes)-1)*ii+latency


def signed_width(bound):
    return 1+int(bound).bit_length()


def validate(f, h, hidden, chunk):
    if f['samples']!=64 or f['strata']!=64 or f['bins']!=4 or f['weight_bits']!=8:
        raise ValueError('latest certified schedule contract is W8/B4/xT64K64')
    if f['nonlinear_samples'] not in (32,64,128) or f['joint_strata']!=[4,2,4]:
        raise ValueError('joint32 strata require nonlinear T32/64/128')
    if f['x_scale_offsets']!=[0,2,4,6] or f['gu_scale_offsets']!=[1,3,5,7]:
        raise ValueError('scale offsets must match pinned numerical contract')
    if min(h,hidden)%64 or h%64 or hidden%64:raise ValueError('full64 tiles required')
    if f['weight_feed'] not in ('resident_macro','sram_reread'):
        raise ValueError('unknown weight feed')
    for k in ('engines','local_weight_load_bytes_per_cycle','sample_II_cycles',
              'encoder_lanes','restore_lanes','accumulate_lanes','bf16_lanes'):
        if not isinstance(f[k],int) or f[k]<1:raise ValueError('positive integer '+k)
    wave=min(f['engines'],max(2*hidden//64,h//64))*4096
    if wave>chunk:raise ValueError('weight wave exceeds ping/pong slot')
    if f['weight_feed']=='resident_macro' and f['local_weight_bytes']<wave:
        raise ValueError('parallel tile contract requires full-wave local weight capacity')
    if f.get('weight_schedule','legacy') not in ('legacy','dma_prefetch'):
        raise ValueError('unknown weight schedule')
    # Guard uses maximum allowed alignment, coeff and all input channels.
    gu_bound=h*64*127*((1<<16)-1)*(1<<6)
    down_bound=hidden*f['nonlinear_samples']*127*((1<<16)-1)*(1<<14)
    if f['wide_bits']<max(signed_width(gu_bound),signed_width(down_bound)):
        raise ValueError('wide partial accumulator cannot hold conservative bound')


class JointRandomMacro:
    """Separate request port for independent per-lane/axis words, NOT shared64.

    This new consumer has a finite macro producer, not the old verified
    Issue95 endpoint evaluator. It shares the core clock and records state,
    seed traffic, startup/reseed/replay and bandwidth. Bits never enter SRAM.
    It is deliberately exposed separately from the unchanged Attention RNG.
    """
    def __init__(self, owner):
        self.o=owner;self.c=owner.c['ffn']['rng_nl'];self.count=Counter()
        self.saved=None;self.last_seed=None
        self.endpoints=ceildiv(self.c['words_per_cycle'],self.c['words_per_endpoint'])
        if min(self.c['words_per_cycle'],self.c['stream_II'],self.c['response_latency'])<1:
            raise ValueError('finite nonlinear random throughput required')

    def setup(self,t,frame,replay):
        c=self.c;o=self.o
        cycle=math.ceil(t/o.period)
        if not replay:
            if self.saved is not None:raise ValueError('release joint frame before SAVE')
            if self.last_seed is None or cycle-self.last_seed>=c['reseed_interval_cycles']:
                beats=self.endpoints*ceildiv(c['state_bits_per_endpoint'],c['seed_word_bits'])
                delay=beats*c['seed_word_interval_cycles']+c['warmup_cycles']
                t=o.s.reserve('AND_rng_seed_and_warmup',t,delay*o.period,
                    ('rng_nl_seed_port',),o.period,seed_beats=beats)
                self.last_seed=math.ceil(t/o.period);self.count['seed_beats']+=beats
                self.count['warmup_endpoint_cycles']+=self.endpoints*c['warmup_cycles']
                o.e.action('AND_rng_seed_beat',beats,'random_new_macro')
                o.e.action('AND_rng_warmup_endpoint_cycle',self.endpoints*c['warmup_cycles'],'random_new_macro')
            self.saved=frame;self.count['save']+=1
        else:
            if self.saved!=frame:raise ValueError('all Wd columns must replay the same events')
            self.count['restore']+=1
        o.e.action('AND_rng_restore' if replay else 'AND_rng_save',self.endpoints,'random_new_macro')
        return o.s.reserve('AND_rng_restore' if replay else 'AND_rng_save',t,
            c['command_cycles']*o.period,('rng_nl_control',),o.period)

    def stream_cycles(self,T):
        # Three R8 words per channel; 4/2/4 high-bit cell IDs are deterministic.
        batches=ceildiv(192,self.c['words_per_cycle'])
        ii=batches*self.c['stream_II']
        self.count['streams']+=1;self.count['samples']+=T
        self.count['R8_words']+=192*T;self.count['useful_random_low_bits']+=1216*T
        self.count['joint_cell_visits']+=T;self.count['producer_batches']+=batches*T
        generated=batches*self.endpoints*self.c['words_per_endpoint']*T
        self.count['native_generated_R8_words']+=generated
        self.count['discarded_R8_words']+=generated-192*T
        self.o.e.action('AND_rng_native_endpoint_update',batches*self.endpoints*T,'random_new_macro')
        # Demand statistic only; charge native endpoint updates, not both.
        self.o.e.action('AND_rng_R8_word_demand',192*T,'random_new_macro',0.)
        self.o.e.action('AND_threeway_comparison',192*T,'SC_nonlinear')
        self.o.e.action('AND_two_input_gate',128*T,'SC_nonlinear')
        return ii,self.c['response_latency']+(batches-1)*self.c['stream_II']

    def release(self,t):
        if self.saved is None:raise ValueError('joint frame absent')
        self.saved=None;self.count['release']+=1
        self.o.e.action('AND_rng_release',self.endpoints,'random_new_macro')
        return self.o.s.reserve('AND_rng_release',t,self.c['command_cycles']*self.o.period,
            ('rng_nl_control',),self.o.period)

    def report(self):
        return dict(kind='finite_local_independent_R8_macro',actual_endpoint_executed=False,
            counts=dict(self.count),config=self.c,clock_hz=self.o.c['core_hz'],
            endpoint_count=self.endpoints,
            live_and_saved_PRNG_state_bits=2*self.endpoints*self.c['state_bits_per_endpoint'],
            partial_response_register_bits=192*8 if self.c['words_per_cycle']<192 else 0,
            random_stream_SRAM_bytes=0,probability_storage='one live encoded64 group, charged separately',
            area_mm2=None,energy_J=None,
            replay='same saved frame for every Wd output wave; reseed only between frames',
            limitations=['independent per-lane/axis outputs are a statistical interface requirement',
                'new nonlinear endpoint mapping/seed-port implementation and PPA not validated',
                'separate finite seed service macro; shared global seed arbitration not connected',
                'not an unlimited-rate source and not the existing shared64 input source'])


class LatestFFN:
    def __init__(self,o):
        self.o=o;self.f=o.c['ffn'];self.rng=JointRandomMacro(o)
        f=self.f;T=max(64,f['nonlinear_samples'])
        # Per-bin signed sum of weighted bit-plane compression, then time add.
        self.pipeline=Counter();self.wave_records=[];self.wave_serial=0
        self.slot_generation=[0,0];self.pending_ticket=None;self.last_restore=0.
        self.counter_bits=signed_width(64*127*T)
        self.local=dict(weight_hold_bytes=f['local_weight_bytes'] if f['weight_feed']=='resident_macro' else 0,
            dma_prefetch_buffer_bytes=(min(f['engines'],max(2*o.F//64,o.h//64))*4096
                if f.get('weight_schedule')=='dma_prefetch' else 0),
            weight_response_buffer_bytes=2*o.c['sram']['banks']*o.c['sram']['word_bytes'],
            tile_coefficient_and_exponent_bits=f['engines']*32,
            output_group_exponent_bits=16*(2*o.F//64+o.h//64),
            temporal_counter_bits=f['engines']*64*7*self.counter_bits,
            reduction_pipeline_bits=f['engines']*64*f['counter_pipeline_bits_per_lane'],
            input_probability_state_bits=64*16,nonlinear_probability_state_bits=64*32,
            sigmoid_ROM_bits=256*9*f['lut_lanes'],
            full_area_mm2=None,full_energy_J=None)

    def macro(self,t,name,count,lanes,latency,ii=1):
        o=self.o
        cycles=batch_cycles(count,lanes,latency,ii)
        o.e.action(name,count,'FFN_macro')
        return o.s.reserve(name,t,cycles*o.period,('ffn_'+name,),o.period,
            values=count,latency_cycles=latency,lanes=lanes,initiation_interval=ii,
            evidence='assumed pipelined macro; no matching STA')

    def metadata(self,t,layer):
        o=self.o
        size=4*(o.h//64)+8*(o.F//64)
        t=o.dram.tensor(t,'L%d/ffn_fixed_scales'%layer,0,size,kind='ffn_fixed_scale_table')
        t=o.mem.transfer(t,o.fixed_scale_table,size,True,'ffn_fixed_scale_table')
        # Common GU/down output exponents are compiler metadata, not implicit FP32.
        exp_size=2*(2*o.F//64+o.h//64)
        return o.mem.transfer(t,o.fixed_scale_table+size-exp_size,exp_size,False,'SC_output_exponents_to_local')

    def load_wave(self,ready,name,k,j,n):
        o=self.o;info=o.matrix_info[name];groups=info['out']//64
        slot=o.slot_serial%2;o.slot_serial+=1;ready=max(ready,o.slot_free[slot])
        loaded=o.dram.tensor(ready,name,(k*groups+j)*4096,n*4096)
        loaded=o.mem.transfer(loaded,o.slots[slot],n*4096,True,'weight_fill')
        if self.f['weight_feed']=='resident_macro':
            # Stream the SRAM response into the local full-width tile. Bounded
            # two-bank-beat elasticity, with a receiver at least as wide/fast
            # as the producer. Do not materialize a hidden whole-wave FIFO.
            bw=min(o.c['sram']['fabric_GBs'],o.c['sram']['banks']*o.c['sram']['word_bytes']*o.c['sram']['clock_hz']/1e9)
            if self.f['local_weight_load_bytes_per_cycle']/o.period < bw:
                raise ValueError('local weight receiver slower than SRAM: explicit throttling backend required')
            resources=['sram_fabric']+['sram_bank:'+str(b) for b in range(o.c['sram']['banks'])]
            start=max([loaded]+[o.s.free[r] for r in resources])
            done=o.mem.transfer(loaded,o.slots[slot],n*4096,False,'weight_consume')
            duration=max(done-start,ceildiv(n*4096,self.f['local_weight_load_bytes_per_cycle'])*o.period)+o.period
            loaded=o.s.reserve('SC_local_weight_program',start,duration,('sc_weight_local_port',),o.period,bytes=n*4096)
            o.e.action('SC_local_weight_program_byte',n*4096,'weight_interface')
        loaded=o.dram.tensor(loaded,name,info['bytes']+(k*groups+j)*4,n*4,kind='weight_scales')
        loaded=o.mem.transfer(loaded,o.ffn_coefficient_scratch,n*4,True,'weight_scales')
        loaded=o.mem.transfer(loaded,o.ffn_coefficient_scratch,n*4,False,'weight_scales')
        return loaded,slot

    def prefetch_wave(self,ready,name,k,j,n):
        """One bounded DMA-completion buffer. SRAM fill is deliberately deferred.

        This conservative macro overlaps DRAM with the preceding compute, but
        does not pretend that returned data can wait without physical storage.
        No second local full-width weight macro is assumed.
        """
        if self.pending_ticket is not None:
            raise ValueError('prefetch queue full: consume the outstanding wave first')
        o=self.o;info=o.matrix_info[name];groups=info['out']//64
        slot=o.slot_serial%2;o.slot_serial+=1
        ready=max(ready,o.slot_free[slot]);self.slot_generation[slot]+=1
        self.wave_serial+=1
        loaded=o.dram.tensor(ready,name,(k*groups+j)*4096,n*4096)
        ticket=dict(wave_id=self.wave_serial,name=name,k=k,j=j,n=n,slot=slot,
            generation=self.slot_generation[slot],issue_ns=ready,dram_done_ns=loaded)
        self.pending_ticket=ticket
        self.pipeline['waves']+=1;self.pipeline['prefetch_bytes']+=n*4096
        o.e.action('SC_DMA_response_buffer_write_byte',n*4096,'weight_interface')
        return ticket

    def load_prefetched_wave(self,ready,ticket):
        if self.pending_ticket is not ticket:
            raise ValueError('stale or unowned weight ticket')
        o=self.o;name=ticket['name'];n=ticket['n'];slot=ticket['slot']
        info=o.matrix_info[name];groups=info['out']//64
        if ticket['generation']!=self.slot_generation[slot]:raise ValueError('stale slot generation')
        loaded=max(ready,ticket['dram_done_ns'],o.slot_free[slot],self.last_restore)
        loaded=o.mem.transfer(loaded,o.slots[slot],n*4096,True,'weight_fill')
        ticket['fill_done_ns']=loaded
        o.e.action('SC_DMA_response_buffer_read_byte',n*4096,'weight_interface')
        self.pending_ticket=None
        if self.f['weight_feed']=='resident_macro':
            bw=min(o.c['sram']['fabric_GBs'],o.c['sram']['banks']*o.c['sram']['word_bytes']*o.c['sram']['clock_hz']/1e9)
            if self.f['local_weight_load_bytes_per_cycle']/o.period < bw:
                raise ValueError('local weight receiver slower than SRAM: explicit throttling backend required')
            resources=['sram_fabric','sc_weight_local_port']+['sram_bank:'+str(b) for b in range(o.c['sram']['banks'])]
            start=max([loaded]+[o.s.free[r] for r in resources])
            done=o.mem.transfer(start,o.slots[slot],n*4096,False,'weight_consume')
            duration=max(done-start,ceildiv(n*4096,self.f['local_weight_load_bytes_per_cycle'])*o.period)+o.period
            loaded=o.s.reserve('SC_local_weight_program',start,duration,('sc_weight_local_port',),o.period,
                bytes=n*4096,wave_id=ticket['wave_id'],slot=slot,generation=ticket['generation'])
            ticket['program_start_ns']=start;ticket['program_done_ns']=loaded
            o.e.action('SC_local_weight_program_byte',n*4096,'weight_interface')
        # Single coefficient storage is only reused after previous restoration.
        loaded=o.dram.tensor(loaded,name,info['bytes']+(ticket['k']*groups+ticket['j'])*4,n*4,kind='weight_scales')
        loaded=o.mem.transfer(loaded,o.ffn_coefficient_scratch,n*4,True,'weight_scales')
        loaded=o.mem.transfer(loaded,o.ffn_coefficient_scratch,n*4,False,'weight_scales')
        ticket['coeff_done_ns']=loaded
        return loaded,slot

    def array(self,t,name,n,T,B,slot,nl=False):
        o=self.o;f=self.f
        resources=['sc:'+str(i) for i in range(n)]
        if f.get('weight_schedule')=='dma_prefetch' and f['weight_feed']=='resident_macro':
            resources.append('sc_weight_local_port')
        t=max([t]+[o.s.free[r] for r in resources])
        ii=f['sample_II_cycles'];front=0
        if nl:
            rngii,front=self.rng.stream_cycles(T);ii=max(ii,rngii)
            resources+=['rng_nl_stream','AND_comparator_array']
        # Both branches explicitly supply finite bandwidth. Reread is a slow,
        # conservative schedule, not an II=1 claim from a narrow SRAM.
        if f['weight_feed']=='sram_reread':
            for _ in range(T):
                t=o.mem.transfer(t,o.slots[slot],n*4096,False,'SC_weight_sample_reread')
                t=o.s.reserve('SC_'+name+'_sample',t,ii*o.period,resources,o.period)
            cycles=f['startup_cycles']+f['drain_cycles']+front
        else:
            cycles=f['startup_cycles']+(T-1)*ii+f['drain_cycles']+front
        end=o.s.reserve('SC_'+name,t,cycles*o.period,resources,o.period,
            tiles=n,samples=T,bins=B,II=ii,weight_feed=f['weight_feed'])
        if not nl and o.integrated_rng:
            consumed=o.rng.stream_ffn(t+f['startup_cycles']*o.period,T,64,ii)
            # True source stalls extend the resource reservation, never disappear.
            drained=consumed+f['drain_cycles']*o.period
            if drained>end:
                end=o.s.reserve('SC_'+name+'_source_backpressure',end,drained-end,
                                resources,o.period)
        o.slot_free[slot]=end
        trials=n*4096*T
        o.e.action('SC_W8_magnitude_AND',trials*7,'SC_compute')
        o.e.action('SC_product_sign_XOR',trials,'SC_compute')
        o.e.action('SC_weighted_bitplane_compress_bit_work',n*64*B*7*120*T,'SC_compute')
        o.e.action('SC_signed_temporal_accumulate',n*64*B*T,'SC_compute')
        o.e.action('SC_bucket_route',trials,'SC_compute')
        o.e.action('SC_local_weight_feed_cycle',n*T,'weight_interface')
        o.metadata['SC_64x64_tiles']+=n;o.metadata['SC_product_trials']+=trials
        o.metadata['SC_accepted_stream_samples']+=T
        o.metadata['SC_7bucket_tiles' if nl else 'SC_4bucket_tiles']+=n
        return end

    def restore(self,t,n,buckets,k,j):
        o=self.o;f=self.f;values=n*64
        t=self.macro(t,'SC_bucket_shift_reduce',values*buckets,64,3)
        t=self.macro(t,'SC_coefficient16_restore',values,f['restore_lanes'],f['restore_latency'],f['restore_II'])
        size=values*8;addr=o.matrix_output+j*64*8
        if k:
            t=o.mem.transfer(t,addr,size,False,'SC_wide_partial')
            t=self.macro(t,'SC_cross_tile_add64',values,f['accumulate_lanes'],f['accumulate_latency'])
        t=o.mem.transfer(t,addr,size,True,'SC_wide_partial')
        o.metadata['wide_partial_values']+=values
        self.last_restore=t
        return t

    def prefetched_group(self,t,name,k,groups,E,frame,nl=False):
        o=self.o;f=self.f
        ticket=self.pending_ticket
        if ticket is None:ticket=self.prefetch_wave(t,name,k,0,min(E,groups))
        elif (ticket['name'],ticket['k'],ticket['j'])!=(name,k,0):
            raise ValueError('prefetch belongs to another input group')
        for j in range(0,groups,E):
            n=min(E,groups-j);current=ticket
            loaded,slot=self.load_prefetched_wave(t,current)
            begin=max(t,loaded)
            if nl:begin=self.rng.setup(begin,frame,j>0)
            elif o.integrated_rng:begin=o.rng.prepare_ffn(begin,frame,j>0)
            else:begin=o.rng.request('ffn',begin,64,2,1,'shared64_stratified',frame,replay=j>0)
            current['array_start_ns']=begin
            end=self.array(begin,'AND_direct_Wd' if nl else 'gate_up',n,
                f['nonlinear_samples'] if nl else 64,7 if nl else 4,slot,nl=nl)
            current['array_done_ns']=end
            # Only DRAM is submitted early: no future SRAM reservation can
            # push current restoration out of a usable gap in the FIFO model.
            if o.c['double_buffer']:
                if j+E<groups:
                    ticket=self.prefetch_wave(begin,name,k,j+E,min(E,groups-j-E))
                    self.pipeline['prefetch_during_previous_array']+=int(ticket['issue_ns']<end)
                elif f.get('prefetch_across_input_groups',False) and k+1<o.matrix_info[name]['inp']//64:
                    # Weight addresses do not depend on the next input code.
                    # Keep only a DMA ticket: neither its coefficients nor its
                    # local weights may overwrite this group's live state.
                    self.prefetch_wave(begin,name,k+1,0,min(E,groups))
                    self.pipeline['cross_input_group_prefetches']+=1
                    self.pipeline['prefetch_during_previous_array']+=int(self.pending_ticket['issue_ns']<end)
            t=self.restore(end,n,7 if nl else 4,k,j)
            current['restore_done_ns']=t
            if len(self.wave_records)<o.c['trace_event_limit']:self.wave_records.append(dict(current))
            if j+E<groups and not o.c['double_buffer']:
                ticket=self.prefetch_wave(t,name,k,j+E,min(E,groups-j-E))
        return t

    def gate_up(self,t,layer):
        o=self.o;f=self.f;name='L%d/gu'%layer;groups=2*o.F//64;E=f['engines']
        t=self.metadata(t,layer)
        for k in range(o.h//64):
            t=o.mem.transfer(t,o.activation+k*128,128,False,'SC_BF16_x')
            t=o.mem.transfer(t,o.fixed_scale_table+2*k,2,False,'SC_fixed_x_scale')
            t=self.macro(t,'SC_fixed4_P8_encode',64,f['encoder_lanes'],f['encoder_latency'],f['encoder_II'])
            o.metadata['fixed_x_encoded_values']+=64
            t=o.mem.transfer(t,o.encoded,128,True,'SC_x_code')
            t=o.mem.transfer(t,o.encoded,128,False,'SC_x_code_to_local')
            frame=('latest_gu',layer,k,o.frame);o.frame+=1;prefetch=t
            if f.get('weight_schedule')=='dma_prefetch':
                t=self.prefetched_group(t,name,k,groups,E,frame)
                if o.integrated_rng:t=o.rng.release_ffn(t)
                continue
            for j in range(0,groups,E):
                n=min(E,groups-j);loaded,slot=self.load_wave(prefetch,name,k,j,n)
                begin=max(t,loaded)
                if o.integrated_rng:begin=o.rng.prepare_ffn(begin,frame,j>0)
                else:begin=o.rng.request('ffn',begin,64,2,1,'shared64_stratified',frame,replay=j>0)
                t=self.array(begin,'gate_up',n,64,4,slot)
                # Conservatively permit prefetch only after array completion.
                prefetch=t if o.c['double_buffer'] else None
                t=self.restore(t,n,4,k,j)
                if prefetch is None:prefetch=t
            if o.integrated_rng:t=o.rng.release_ffn(t)
        return t

    def encode_nonlinear(self,t):
        o=self.o;f=self.f
        for k in range(o.F//64):
            t=o.mem.transfer(t,o.matrix_output+k*512,512,False,'SC_g_wide')
            t=o.mem.transfer(t,o.matrix_output+(o.F+k*64)*8,512,False,'SC_u_wide')
            t=o.mem.transfer(t,o.fixed_scale_table+2*(o.h//64)+4*k,4,False,'SC_fixed_gu_scale')
            t=self.macro(t,'SC_fixed4_GU_P8_encode',128,f['encoder_lanes'],f['encoder_latency'],f['encoder_II'])
            t=self.macro(t,'SC_true_g_signed8',64,f['field_lanes'],f['field_latency'])
            t=self.macro(t,'SC_sigmoid_ROM9',64,f['lut_lanes'],f['lut_latency'])
            t=self.macro(t,'SC_sign_and_exponent_sum',64,64,1)
            t=o.mem.transfer(t,o.z+k*256,256,True,'SC_joint_codes')
        o.metadata['fixed_gu_encoded_values']+=2*o.F
        o.metadata['online_absmax_calls']+=0
        return t

    def down(self,t,layer):
        o=self.o;f=self.f;name='L%d/down'%layer;E=f['engines'];groups=o.h//64
        for k in range(o.F//64):
            t=o.mem.transfer(t,o.z+k*256,256,False,'SC_joint_codes_to_local')
            frame=('latest_down',layer,k,o.frame);o.frame+=1;prefetch=t
            if f.get('weight_schedule')=='dma_prefetch':
                t=self.prefetched_group(t,name,k,groups,E,frame,nl=True)
                t=self.rng.release(t)
                continue
            for j in range(0,groups,E):
                n=min(E,groups-j);loaded,slot=self.load_wave(prefetch,name,k,j,n)
                begin=self.rng.setup(max(t,loaded),frame,j>0)
                t=self.array(begin,'AND_direct_Wd',n,f['nonlinear_samples'],7,slot,nl=True)
                prefetch=t if o.c['double_buffer'] else None
                t=self.restore(t,n,7,k,j)
                if prefetch is None:prefetch=t
            t=self.rng.release(t)
        return t

    def final(self,t):
        o=self.o;f=self.f
        t=o.mem.transfer(t,o.matrix_output,o.h*8,False,'SC_final_wide')
        t=self.macro(t,'SC_wide_RNE_BF16',o.h,f['bf16_lanes'],f['bf16_latency'])
        return o.mem.transfer(t,o.matrix_output,o.h*2,True,'SC_final_BF16')

    def report(self):
        return dict(contract='fixed4_and_direct',numerical_status=self.f['numeric_status'],
            integer_bound_condition='offline compiler must fold tile scales into unsigned16 coefficient and output-group common exponent; compiler/rounding equivalence pending',
            local_state=self.local,nonlinear_random=self.rng.report(),
            weight_pipeline=dict(schedule=self.f.get('weight_schedule','legacy'),counts=dict(self.pipeline),
                records=self.wave_records,pending=self.pending_ticket is not None,
                overlap='next DMA only, optionally across input groups; SRAM fill/program after previous restore; one local weight bank',
                buffer='one explicit full-wave DMA response macro; unknown PPA'),
            unknown_macro_ppa=['fixed4 encoders','GU fixed-point restore/rounding','signed8 field/ROM',
                'weighted compressor and 4/7 bucket counters','local weight interface','direct AND fanout',
                'coefficient multiplier / wide accumulators / BF16 RNE','nonlinear local RNG'],
            scale_policy='offline frozen x/g/u tables; no token absmax; channel order unchanged',
            weight_policy='fixed sign+magnitude W8, one packed byte per weight; offline tables',
            stream_policy='no z materialization; same event replayed for all Wd output waves',
            gu_width_bound=signed_width(self.o.h*64*127*65535*(1<<6)),
            down_width_bound=signed_width(self.o.F*self.f['nonlinear_samples']*127*65535*(1<<14)))
