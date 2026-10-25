"""Full batch-one decode graph using a common resource and memory contract.

The behavioral logits select transactions; this is not model inference. Regular
kernels are bounded latency models. Parallel samplers reuse the frozen v5 FSMs.
"""
import copy
import hashlib
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TLM = HERE.parent
sys.path.insert(0, str(TLM))
from attention_reference_v3 import TraceSource, softmax, selector, categorical, ising_random_scan
from screen_ising_tlm_v4 import budget_blocks
from winner_hold_tlm_v5 import WinnerHoldSampler
from corrected_rejection_tlm_v5 import CorrectedRejectionSampler
from sram_cacti_calibration_v1 import macro_lookup
from .core import Ledger, Scheduler, Arena, SRAM, DRAM, AddressMap, LocalRandomService, ceildiv, sha
from .rng_integrated import IntegratedRandomService, selector_parameters
from .ffn_latest import LatestFFN, validate as validate_latest
from .tile_pipeline import TilePipeline


MODES = ('exact', 'pv', 'screen_exact', 'screen_pv', 'screen_rejection', 'screen_winner', 'screen_serial_ising')


def stable_rng(*args):
    data = ':'.join(str(a) for a in args).encode('utf-8')
    return random.Random(int.from_bytes(hashlib.sha256(data).digest()[:8], 'little'))


def stratified_thresholds(T, K, rng):
    """Same K equal strata, T/K replacement draws/stratum as numerical FFN."""
    if T < 1 or K < 1 or K > 256 or 256 % K or T % K:
        raise ValueError('invalid T/K')
    width = 256//K
    return [k*width+rng.randrange(width) for k in range(K) for _ in range(T//K)]


def bucket_code(values, bins):
    """Small functional oracle: no channel permutation, q/256 + true-one flag."""
    if not values or bins < 1 or any(not math.isfinite(x) for x in values):
        raise ValueError('invalid amplitudes')
    maximum = max(abs(x) for x in values)
    if maximum:
        mantissa, exponent = math.frexp(maximum)
        top = math.ldexp(1., exponent-1 if mantissa == .5 else exponent)
    else:
        top = 1.
    out = []
    for value in values:
        b = 0
        while b+1 < bins and abs(value) <= top/(4.**(b+1)):
            b += 1
        scale = top/(4.**b)
        q = min(255, max(0, round(abs(value)*256/scale)))
        out.append(dict(bin=b, scale=scale, q=q, one=abs(value) >= scale, sign=-1 if value < 0 else 1))
    return out


def bitplane_reference(weights, codes, thresholds, bins):
    """Exact signed-W8/sign-input bin/bit-plane counts, then scale restoration."""
    if len(weights) != len(codes) or not thresholds or any(type(w) is not int or not -128 <= w <= 127 for w in weights):
        raise ValueError('signed W8 required')
    counts = [[[0]*8 for _ in range(2)] for _ in range(bins)]
    for w, c in zip(weights, codes):
        for r in thresholds:
            if c['one'] or r < c['q']:
                sign = 0 if c['sign'] > 0 else 1
                for p in range(8):
                    counts[c['bin']][sign][p] += ((w & 255) >> p) & 1
    value = 0.
    for b in range(bins):
        signed = sum((1 if p < 7 else -1)*(1 << p)*(counts[b][0][p]-counts[b][1][p]) for p in range(8))
        scale = next((c['scale'] for c in codes if c['bin'] == b), 0.)
        value += signed*scale/len(thresholds)
    return value


class FullDecode:
    def __init__(self, config, shape):
        self.c, self.m = copy.deepcopy(config), copy.deepcopy(shape)
        c, m = self.c, self.m
        self.period = 1e9/c['core_hz']
        self.s, self.e = Scheduler(c['trace_event_limit']), Ledger(c['prices_pJ'])
        if c['attention']['mode'] not in MODES or c['ffn']['mode'] not in ('bf16', 'w8', 'sc'):
            raise ValueError('unknown operator mode')
        f = c['ffn']
        self.latest_ffn = f['mode']=='sc' and f.get('algorithm')=='fixed4_and_direct'
        if self.latest_ffn:
            validate_latest(f,m['hidden_size'],m['intermediate_size'],c['weight_chunk_bytes'])
        if f['samples'] % f['strata'] or 256 % f['strata'] or not 1 <= f['strata'] <= 256:
            raise ValueError('invalid stratification')
        if f['mode'] == 'sc' and (m['hidden_size'] % 64 or m['intermediate_size'] % 64):
            raise ValueError('current exact SC mapping needs full 64-lane groups')
        if m['hidden_size'] % m['num_attention_heads'] or m['num_attention_heads'] % m['num_key_value_heads']:
            raise ValueError('invalid head geometry')
        self.h, self.F, self.H, self.KH = [m[k] for k in ('hidden_size', 'intermediate_size', 'num_attention_heads', 'num_key_value_heads')]
        self.d = m.get('head_dim',self.h//self.H)
        self.q_width = self.H*self.d
        self.group = self.H//self.KH
        calibration_path = TLM/c['sram']['calibration']
        calibration = json.loads(calibration_path.read_text(encoding='utf-8'))
        spec = macro_lookup(calibration, c['sram']['macro_depth'], c['sram']['word_bytes']*8, c['sram']['corner'], c['sram']['clock_hz'])
        self.mem = SRAM(c['sram'], spec, self.s, self.e)
        self.calibration_sha = sha(calibration_path)
        self.arena = Arena(c['sram']['capacity_bytes'])
        chunk = c['weight_chunk_bytes']
        self.slots = [self.arena.allocate('weight_ping', chunk), self.arena.allocate('weight_pong', chunk)]
        self.slot_free, self.slot_serial = [0., 0.], 0
        self.activation = self.arena.allocate('normalized_activation_and_attention_output', max(65536, self.h*8))
        self.matrix_output = self.arena.allocate('matrix_output_and_wide_partials', max(65536, self.F*(16 if self.latest_ffn else 8)))
        self.z = self.arena.allocate('nonlinear_P8_sign_exponent_codes' if self.latest_ffn else 'SwiGLU_z_FP32', max(65536, self.F*4))
        if self.latest_ffn:
            self.fixed_scale_table=self.arena.allocate('frozen_FFN_scale_tables',4*(self.h//64)+8*(self.F//64))
            self.ffn_coefficient_scratch=self.arena.allocate('FFN_tile_coefficients',f['engines']*4)
        self.residual = self.arena.allocate('live_BF16_residual', self.h*2)
        self.encoded = self.arena.allocate('one_shared_encoded_input_group', 64*2)
        L = c['context_tokens']+c['decode_tokens']
        max_samples = max(1, math.ceil(L*c['attention']['sample_ratio']), c['attention']['minimum_samples'])
        if c['attention']['samples'] is not None:
            max_samples = c['attention']['samples']
        if c['attention']['mode']=='screen_winner':
            max_samples *= c['attention']['winner_update_multiplier']
        self.max_retained_samples = max_samples
        # One KV-head group at a time. No all-head maps/summaries resident.
        self.summary_base = self.arena.allocate('one_KV_group_summary', ceildiv(L, 16)*self.d*4)
        mode = c['attention']['mode']
        screen, sampled = mode.startswith('screen_'), mode not in ('exact','screen_exact')
        candidates = min(L, c['attention']['candidate_blocks']*64)
        self.row_capacity = candidates if screen and c['attention']['selection']=='fixed_budget' else L
        max_scores = self.row_capacity*self.group
        self.attn_work = self.arena.allocate('one_KV_group_logits',max(16,max_scores*4 if sampled else 16))
        self.map_base = self.arena.allocate('candidate_maps',max(16,max_scores*4 if screen else 16))
        self.hist_base = self.arena.allocate('one_head_histogram',max(16,self.row_capacity*4 if sampled else 16))
        needs_index = mode in ('screen_winner','screen_rejection','screen_serial_ising')
        self.indices_base = self.arena.allocate('sampler_output_indices_word_stride',max(16,max_samples*16 if needs_index else 16))
        worklist_bytes = min(max_samples,self.row_capacity)*self.group*8 if sampled else 16
        self.worklist_base = self.arena.allocate('GQA_sorted_V_worklists',max(16,worklist_bytes))
        self.kv_buffer = self.arena.allocate('K_V_tile', c['attention']['tile_tokens']*self.d*4)
        self.mem.regions = self.arena.regions
        self.integrated_rng=c['random'].get('backend','local_prng_interface')=='integrated_service'
        if self.latest_ffn and self.integrated_rng and f['weight_feed']=='sram_reread':
            raise ValueError('reread schedule currently requires local_prng_interface; actual per-sample source handshake pending')
        if c['random'].get('backend','local_prng_interface') not in ('local_prng_interface','integrated_service'):
            raise ValueError('unknown random backend')
        self.rng = (IntegratedRandomService(c['random'],self.s,self.e,self.period,
                    ffn=f['mode'],mode=mode,group=self.group,context=c['context_tokens']+c['decode_tokens']-1,
                    candidates=self.row_capacity,seed=c['seed'])
                    if self.integrated_rng else LocalRandomService(c['random'], self.s, self.e, self.period))
        self.layout = self.make_layout()
        self.dram = DRAM(c['dram'], self.layout, self.s, self.e)
        policy=c.get('schedule_policy','legacy')
        if policy not in ('legacy','shared_tiles'):raise ValueError('unknown schedule policy')
        self.tile_pipeline=TilePipeline(self) if policy=='shared_tiles' else None
        self.digital_activation_peak=0;self.digital_partial_peak=0
        if c.get('digital_w8_restore','legacy_row') not in ('legacy_row','block64'):
            raise ValueError('unknown W8 scale restoration contract')
        a = c['attention']
        tc = dict(seed=c['seed'], fixture_logit_std=a['synthetic_logit_std'],
            selector_bias=a['selector_bias'], selector_temperature=a['selector_temperature'],
            trace_file=a.get('trace_file'), calibration_file=a.get('selector_calibration'))
        self.source = TraceSource(tc, m)
        self.samplers = {}
        for name, cls in [('screen_rejection', CorrectedRejectionSampler), ('screen_winner', WinnerHoldSampler)]:
            options = copy.deepcopy(c['sampler_v5'])
            options['clock_ns'] = self.period
            if self.integrated_rng:options['external_source_programming']=True
            self.samplers[name] = cls(options, max(1, candidates))
        self.phases, self.attn_rows = [], []
        self.sampler_audit = []
        self.attn_stats = Counter()
        self.frame = 0
        self.metadata = Counter()
        self.ffn_latest=LatestFFN(self) if self.latest_ffn else None

    def make_layout(self):
        a = AddressMap()
        a.allocate('lm_head', self.m['vocab_size']*self.h*2)
        if not self.m.get('tie_word_embeddings', False):
            a.allocate('embedding', self.m['vocab_size']*self.h*2)
        a.allocate('final_norm', self.h*2)
        bpw = 2 if self.c['ffn']['mode'] == 'bf16' else 1
        self.matrix_info = {}
        for layer in range(self.m['num_hidden_layers']):
            a.allocate('L%d/norms' % layer, 4*self.h)
            if self.latest_ffn:
                a.allocate('L%d/ffn_fixed_scales'%layer,4*(self.h//64)+8*(self.F//64))
            if self.m.get('qk_norm',False):a.allocate('L%d/qk_norm'%layer,4*self.d)
            for suffix, inp, out, width in [('qkv', self.h, self.q_width+2*self.KH*self.d, 2),
                    ('o', self.q_width, self.h, 2), ('gu', self.h, 2*self.F, bpw), ('down', self.F, self.h, bpw)]:
                name = 'L%d/%s' % (layer, suffix)
                payload = inp*out*width
                scales = ceildiv(inp,64)*ceildiv(out,64)*4 if width == 1 else 0
                self.matrix_info[name] = dict(inp=inp, out=out, width=width, bytes=payload, scale_bytes=scales)
                a.allocate(name, payload+scales)
        self.matrix_info['lm_head'] = dict(inp=self.h, out=self.m['vocab_size'], width=2,
                                          bytes=self.h*self.m['vocab_size']*2, scale_bytes=0)
        total = self.c['context_tokens']+self.c['decode_tokens']
        for layer in range(self.m['num_hidden_layers']):
            a.allocate('L%d/K' % layer, total*self.KH*self.d*2)
            a.allocate('L%d/V' % layer, total*self.KH*self.d*2)
            a.allocate('L%d/summary' % layer, self.KH*ceildiv(total,16)*self.d*4)
        return a

    def vec(self, t, name, ops=0, nonlinear=0, read=0, write=0, energy_unit='vector_op', read_address=None, write_address=None):
        if read:
            t = self.mem.transfer(t, self.activation if read_address is None else read_address, read, False, name+'_input')
        duration = (ceildiv(ops, self.c['vector_lanes'])+ceildiv(nonlinear, self.c['nonlinear_lanes']))*self.period
        t = self.s.reserve(name, t, duration, ('vector',), self.period, vector_ops=ops, nonlinear_ops=nonlinear)
        self.e.action(energy_unit, ops, 'digital')
        self.e.action('nonlinear_op', nonlinear, 'digital')
        if write:
            t = self.mem.transfer(t, self.activation if write_address is None else write_address, write, True, name+'_output')
        return t

    def residual_add(self, t, normalize=False):
        t = self.mem.transfer(t, self.residual, self.h*2, False, 'residual_operand')
        t = self.vec(t, 'BF16_residual', self.h, read=self.h*2, write=self.h*2,
                     read_address=self.matrix_output, write_address=self.activation)
        t = self.mem.transfer(t, self.residual, self.h*2, True, 'residual_commit')
        if normalize:
            t = self.vec(t, 'RMSNorm', 5*self.h, 1, read=self.h*2, write=self.h*2)
        return t

    def mac(self, t, name, count, fp32=False):
        cycles = self.c['mac_startup_cycles']+ceildiv(count, self.c['macs_per_cycle'])
        t = self.s.reserve(name, t, cycles*self.period, ('mac',), self.period, macs=count)
        self.e.action('fp32_mac' if fp32 else 'bf16_mac', count, 'digital')
        return t

    def weight(self, t, name, offset, size):
        if size > self.c['weight_chunk_bytes']:
            raise ValueError('weight transfer exceeds ping-pong slot')
        slot = self.slot_serial % 2
        self.slot_serial += 1
        t = max(t, self.slot_free[slot])
        t = self.dram.tensor(t, name, offset, size)
        t = self.mem.transfer(t, self.slots[slot], size, True, 'weight_fill')
        t = self.mem.transfer(t, self.slots[slot], size, False, 'weight_consume')
        return t, slot

    def digital_w8_restore(self,t,n,inp):
        if self.c.get('digital_w8_restore','legacy_row')=='legacy_row':
            return self.vec(t,'W8_scale_apply',n,energy_unit='weight_scale_op')
        # Every K64 x O64 weight block has an independent scale. A single
        # post-dot scale is not equivalent. MAC emits separate FP32 partials;
        # local buffer writes are absorbed in the explicit macro output rate.
        groups=ceildiv(inp,64);values=n*groups
        self.digital_partial_peak=max(self.digital_partial_peak,values*4)
        self.e.action('digital_block_partial_write_byte',values*4,'digital_local_storage')
        self.e.action('digital_block_partial_read_byte',values*4,'digital_local_storage')
        t=self.vec(t,'W8_block_scale_apply',values,energy_unit='weight_scale_op')
        return self.vec(t,'W8_block_reduce_FP32',n*(groups-1))

    def matrix(self, t, name):
        if self.tile_pipeline is not None:return self.matrix_shared(t,name)
        info = self.matrix_info[name]
        inp, out = info['inp'], info['out']
        # Row-complete chunks keep streaming output/argmax bounded.
        row_bytes = inp*info['width']
        digital_chunk=self.c.get('digital_weight_chunk_bytes',self.c['weight_chunk_bytes'])
        if digital_chunk<row_bytes or digital_chunk>self.c['weight_chunk_bytes']:
            raise ValueError('digital matrix row chunk outside staging slot')
        rows = max(1, digital_chunk//row_bytes)
        input_width = 4 if name.endswith('/down') and info['width']==1 else 2
        input_base = self.z if name.endswith('/down') else self.activation
        t = self.mem.transfer(t, input_base, inp*input_width, False, 'matrix_activation')
        prefetch, current = t, t
        for first in range(0, out, rows):
            n = min(rows, out-first)
            loaded, slot = self.weight(prefetch, name, first*row_bytes, n*row_bytes)
            if info['width'] == 1:
                # Same offline W8 scale metadata as SC, no online weight conversion.
                scale_first = (first//64)*ceildiv(inp,64)*4
                count = (ceildiv(first+n,64)-first//64)*ceildiv(inp,64)*4
                loaded = self.dram.tensor(loaded, name, info['bytes']+scale_first, count, kind='weight_scales')
                loaded = self.mem.transfer(loaded, self.slots[slot], count, True, 'weight_scales')
                loaded = self.mem.transfer(loaded, self.slots[slot], count, False, 'weight_scales')
            start = max(current, loaded, self.s.free['mac'])
            current = self.mac(start, 'matrix_'+name.split('/')[-1], inp*n)
            self.slot_free[slot] = current
            if info['width'] == 1:
                current = self.digital_w8_restore(current,n,inp)
            output_width = 4 if info['width']==1 or name=='lm_head' else 2
            if output_width==2:
                current = self.vec(current, 'matrix_FP32_to_BF16', n, energy_unit='FP32_to_BF16')
            output_address = self.matrix_output+(0 if name=='lm_head' else first*output_width)
            current = self.mem.transfer(current, output_address, n*output_width, True, 'matrix_result')
            if name == 'lm_head':
                current = self.vec(current, 'stream_argmax', n, read=n*4, read_address=self.matrix_output)
            prefetch = start if self.c['double_buffer'] else current
        return current

    def matrix_shared(self,t,name):
        """Digital operator on the same DMA-ticket lifecycle used by SC.

        Local operands have explicit bounded capacity. Next DMA is issued at
        current compute start; its shared-SRAM fill waits until retirement.
        Thus FIFO SRAM scheduling cannot push current output behind future fill.
        """
        info=self.matrix_info[name];inp,out=info['inp'],info['out']
        row_bytes=inp*info['width'];chunk=self.c.get('digital_weight_chunk_bytes',self.c['weight_chunk_bytes'])
        if chunk<row_bytes or chunk>self.c['weight_chunk_bytes']:
            raise ValueError('digital matrix row chunk outside staging slot')
        rows=chunk//row_bytes;pipe=self.tile_pipeline
        input_width=4 if name.endswith('/down') and info['width']==1 else 2
        input_base=self.z if name.endswith('/down') else self.activation
        t=self.mem.transfer(t,input_base,inp*input_width,False,'matrix_activation')
        self.digital_activation_peak=max(self.digital_activation_peak,inp*input_width)
        self.e.action('digital_local_activation_write_byte',inp*input_width,'digital_local_storage')
        first=0;n=min(rows,out)
        ticket=pipe.issue(t,name,0,n*row_bytes,'digital',first=0,n=n)
        while first<out:
            current_ticket=ticket;n=current_ticket['n']
            loaded,slot=pipe.fill(t,current_ticket)
            loaded=self.mem.transfer(loaded,self.slots[slot],n*row_bytes,False,'weight_consume')
            self.e.action('digital_local_operand_write_byte',n*row_bytes,'digital_local_storage')
            if info['width']==1:
                scale_first=(first//64)*ceildiv(inp,64)*4
                count=(ceildiv(first+n,64)-first//64)*ceildiv(inp,64)*4
                loaded=self.dram.tensor(loaded,name,info['bytes']+scale_first,count,kind='weight_scales')
                loaded=self.mem.transfer(loaded,self.slots[slot],count,True,'weight_scales')
                loaded=self.mem.transfer(loaded,self.slots[slot],count,False,'weight_scales')
            start=max(t,loaded,self.s.free['mac']);end=self.mac(start,'matrix_'+name.split('/')[-1],inp*n)
            pipe.compute(current_ticket,start,end)
            self.e.action('digital_local_operand_read_byte',n*row_bytes,'digital_local_storage')
            self.e.action('digital_local_activation_read_byte',inp*n*input_width,'digital_local_storage')
            nxt=first+n
            if nxt<out and self.c['double_buffer']:
                ticket=pipe.issue(start,name,nxt*row_bytes,min(rows,out-nxt)*row_bytes,'digital',first=nxt,n=min(rows,out-nxt))
            t=end
            if info['width']==1:t=self.digital_w8_restore(t,n,inp)
            output_width=4 if info['width']==1 or name=='lm_head' else 2
            if output_width==2:t=self.vec(t,'matrix_FP32_to_BF16',n,energy_unit='FP32_to_BF16')
            address=self.matrix_output+(0 if name=='lm_head' else first*output_width)
            t=self.mem.transfer(t,address,n*output_width,True,'matrix_result')
            if name=='lm_head':t=self.vec(t,'stream_argmax',n,read=n*4,read_address=self.matrix_output)
            pipe.retire(current_ticket,t)
            if nxt<out and not self.c['double_buffer']:
                ticket=pipe.issue(t,name,nxt*row_bytes,min(rows,out-nxt)*row_bytes,'digital',first=nxt,n=min(rows,out-nxt))
            first=nxt
        return t

    def matrix_sc(self, t, name):
        info = self.matrix_info[name]
        inp, out = info['inp'], info['out']
        f = self.c['ffn']
        T, K, B, E = [f[k] for k in ('samples', 'strata', 'bins', 'engines')]
        groups = out//64
        # Input-group-major: reuse/replay the SAME x sequence for every output.
        # This mapping intentionally retains a barrier before SwiGLU.
        for k in range(inp//64):
            input_width = 4 if name.endswith('/down') else 2
            input_base = self.z if name.endswith('/down') else self.activation
            t = self.mem.transfer(t, input_base+k*64*input_width, 64*input_width, False, 'sc_activation')
            t = self.vec(t, 'dynamic_PoT_encode', 64*6+63, energy_unit='SC_encode_op')
            self.metadata[('FP32' if input_width==4 else 'BF16')+'_to_probability8_values'] += 64
            self.metadata['input_bin_select_values'] += 64
            self.metadata['group_absmax_calls'] += 1
            t = self.mem.transfer(t, self.encoded, 64*2, True, 'encoded_group')
            frame = (name, k, self.frame)
            self.frame += 1
            prefetch = t
            for j in range(0, groups, E):
                n = min(E, groups-j)
                data = n*4096
                loaded, slot = self.weight(prefetch, name, (k*groups+j)*4096, data)
                scale_n = n*4
                loaded = self.dram.tensor(loaded, name, info['bytes']+(k*groups+j)*4, scale_n, kind='weight_scales')
                loaded = self.mem.transfer(loaded, self.slots[slot], scale_n, True, 'weight_scales')
                loaded = self.mem.transfer(loaded, self.slots[slot], scale_n, False, 'weight_scales')
                if self.integrated_rng:
                    begin=self.rng.prepare_ffn(max(t,loaded),frame,j>0)
                else:
                    begin = self.rng.request('ffn', max(t, loaded), T, 8-int(math.log2(K)), 1,
                        'shared64_stratified', frame, replay=(j>0))
                resources = ['sc:'+str(i) for i in range(n)]
                start = max([begin]+[self.s.free[r] for r in resources])
                # B bins in parallel; exact bit-plane counts. No B*T serial pass.
                duration = (f['startup_cycles']+T*f['sample_II_cycles']+f['drain_cycles'])*self.period
                if self.integrated_rng:
                    consumed=self.rng.stream_ffn(start+f['startup_cycles']*self.period,T,K,f['sample_II_cycles'])
                    duration=max(duration,consumed-start)
                t = self.s.reserve('SC_'+name.split('/')[-1], start, duration, resources, self.period,
                    tiles=n, samples=T, strata=K, bins=B, stationary_weight_bytes=data)
                self.slot_free[slot] = t
                trials = n*64*64*T
                self.e.action('SC_weight_bit_gate', trials*8*2, 'SC_compute')
                self.e.action('SC_bin_route', trials, 'SC_compute')
                self.e.action('SC_counter_update', n*64*8*2*B*T, 'SC_compute')
                # Binary popcount tree: 32 one-bit adds,16 two-bit adds,...
                # six input-bit positions at root. Nodes and bit work differ.
                self.e.action('SC_reduction_bit_work', n*64*8*2*B*120*T, 'SC_compute')
                self.metadata['SC_popcount_tree_nodes'] += n*64*8*2*B*63*T
                self.e.action('SC_resident_weight_feed_cycle', n*T, 'weight_interface')
                self.metadata['SC_64x64_tiles'] += n
                self.metadata['SC_product_trials'] += trials
                self.metadata['SC_counter_peak_bits'] = max(self.metadata['SC_counter_peak_bits'],
                    E*64*8*2*B*math.ceil(math.log2(64*T+1)))
                prefetch = start if self.c['double_buffer'] else t
                # Restore signed bit planes and B scales before cross-k addition.
                t = self.vec(t, 'SC_bin_restore', n*64*B*(8*2+2), energy_unit='SC_restore_op')
                self.metadata['weight_scale_multiplies'] += n*64*B
                self.metadata['restored_FP32_partials'] += n*64
                partial = n*64*4
                if k:
                    t = self.mem.transfer(t, self.matrix_output+j*64*4, partial, False, 'SC_partial')
                t = self.mem.transfer(t, self.matrix_output+j*64*4, partial, True, 'SC_partial')
            if self.integrated_rng:t=self.rng.release_ffn(t)
        return t

    def kv_ranges(self, layer, kv, ids, value=False):
        name = 'L%d/%s' % (layer, 'V' if value else 'K')
        return [(self.layout.address(name, (i*self.KH+kv)*self.d*2, self.d*2), self.d*2) for i in ids]

    def route(self, t, token, layer, kv, length):
        a = self.c['attention']
        screen = a['mode'].startswith('screen_')
        blocks = ceildiv(length, 64)
        heads = list(range(kv*self.group, (kv+1)*self.group))
        if screen:
            # Warm, persistent summaries reside in DRAM; only one KV group lives
            # in SRAM. Update current token's 16-token sub-summary, every call.
            subs = ceildiv(length,16)
            offset = (kv*ceildiv(self.c['context_tokens']+self.c['decode_tokens'],16)+(length-1)//16)*self.d*4
            name = 'L%d/summary' % layer
            if (length-1)%16:
                t = self.dram.tensor(t, name, offset, self.d*4, kind='summary_update')
            t = self.vec(t, 'summary_update', self.d)
            t = self.dram.tensor(t, name, offset, self.d*4, True, 'summary_update')
            off = kv*ceildiv(self.c['context_tokens']+self.c['decode_tokens'],16)*self.d*4
            size = subs*self.d*4
            t = self.dram.tensor(t, name, off, size, kind='summary_read')
            t = self.mem.transfer(t, self.summary_base, size, True, 'summary_fill')
            t = self.mem.transfer(t, self.summary_base, size, False, 'summary_operand')
            t = self.vec(t, 'summary_mean', subs*self.d, nonlinear=subs)
            t = self.mac(t, 'screen_Q_summary', len(heads)*subs*self.d)
            t = self.vec(t, 'screen_max4_normalize_sigmoid', len(heads)*blocks*12,
                len(heads)*(2 if self.integrated_rng else blocks+2))
            if not self.integrated_rng:
                t = self.rng.request('selector', t, 1, 8, len(heads)*blocks, 'independent_block_keep', (token,layer,kv))
                self.e.action('selector_compare', len(heads)*blocks, 'screening')
        source_info=[]
        if screen and self.integrated_rng:
            for h in heads:
                logits=self.source.logits(token,layer,h,length)
                bias,temperature=self.source.parameters(layer,h)
                source_info.append(selector_parameters(logits,bias,temperature))
            keep,t=self.rng.selector(t,source_info)
        rows = []
        for h in heads:
            logits = self.source.logits(token, layer, h, length)
            ids = list(range(length))
            if screen:
                bias, temperature = self.source.parameters(layer, h)
                if self.integrated_rng:
                    info=source_info[h-heads[0]]
                    base=(h-heads[0])*blocks
                    info['selected_blocks']=[i for i,b in enumerate(keep[base:base+blocks]) if b]
                else:
                    _, info = selector(logits, bias, temperature,
                        self.source.random(token, layer, h, 'selector'))
                if a['selection'] == 'fixed_budget':
                    chosen = budget_blocks(info['block_scores'], info['selected_blocks'], a['candidate_blocks'])
                elif a['selection'] == 'variable':
                    chosen = info['selected_blocks']
                else:
                    raise ValueError('unknown candidate selection')
                ids = [i for b in chosen for i in range(b*64,min(length,(b+1)*64))]
            rows.append(dict(head=h, ids=ids, logits=[logits[i] for i in ids]))
        if screen and a['selection'] == 'fixed_budget':
            levels = (blocks-1).bit_length()
            comparisons = (1 << levels)//2*levels*(levels+1)//2
            t = self.vec(t, 'fixed_candidate_budget_repair', comparisons*len(heads))
            self.e.action('budget_compare_exchange', comparisons*len(heads), 'screening')
        if screen:
            n = sum(len(r['ids']) for r in rows)
            t = self.mem.transfer(t, self.map_base, n*4, True, 'candidate_maps')
            self.e.action('candidate_compact', n, 'screening')
        return t, rows

    def qk(self, t, layer, kv, rows, fused):
        a = self.c['attention']
        sets = [set(r['ids']) for r in rows]
        written = [0]*len(rows)
        union = sorted(set().union(*sets))
        self.attn_stats['QK_logical_positions'] += sum(len(s) for s in sets)
        self.attn_stats['K_unique_group_positions'] += len(union)
        for offset in range(0,len(union),a['tile_tokens']):
            ids = union[offset:offset+a['tile_tokens']]
            ranges = self.kv_ranges(layer, kv, ids)
            if fused:
                ranges += self.kv_ranges(layer, kv, ids, True)
            loaded = self.dram.ranges(t, ranges, False, 'KV_fused' if fused else 'K_selected')
            size = len(ids)*self.d*2*(2 if fused else 1)
            t = self.mem.transfer(loaded, self.kv_buffer, size, True, 'KV_fill')
            t = self.mem.transfer(t, self.kv_buffer, size, False, 'KV_operand')
            active = sum(sum(i in s for i in ids) for s in sets)
            t = self.mac(t, 'attention_QK', active*self.d)
            t = self.vec(t, 'attention_score_scale', active)
            if fused:
                t = self.vec(t, 'online_softmax', 5*active+len(rows)*(2*self.d+3), active+len(rows))
                t = self.mac(t, 'attention_PV_exact', active*self.d, fp32=True)
                self.attn_stats['V_unique_group_positions'] += len(ids)
            else:
                for rh, chosen in enumerate(sets):
                    count = sum(i in chosen for i in ids)
                    if count:
                        address = self.attn_work+(rh*self.row_capacity+written[rh])*4
                        t = self.mem.transfer(t,address,count*4,True,'compact_logits')
                        written[rh] += count
        if fused:
            t = self.vec(t, 'online_normalize', len(rows)*self.d, len(rows))
        return t

    def sample_row(self, t, token, layer, row, samples):
        a = self.c['attention']
        n = len(row['ids'])
        score_address = self.attn_work+(row['head']%self.group)*self.row_capacity*4
        t = self.mem.transfer(t, score_address, n*4, False, 'score_input')
        name = a['mode']
        rng = self.source.random(token,layer,row['head'],'V_samples')
        if name in ('pv', 'screen_pv'):
            t = self.vec(t, 'accurate_softmax', n*5, n+1)
            t = self.mem.transfer(t, score_address, n*4, True, 'probabilities')
            t = self.vec(t, 'CDF_prefix', n)
            # One systematic offset. Counts per CDF interval avoid S binary
            # searches; all multiplicities survive deduplication.
            if self.integrated_rng:
                uniform,t=self.rng.systematic(t)
            else:
                t = self.rng.request('pv', t, 1, 32, 1, 'systematic_PV_offset', (token,layer,row['head']))
                uniform=rng.random()
            p = softmax(row['logits'])
            u = uniform/samples
            out, total, j = [], p[0], 0
            for i in range(samples):
                q = u+i/samples
                while total <= q and j+1 < n:
                    j += 1
                    total += p[j]
                out.append(j)
            t = self.vec(t, 'systematic_CDF_counts', 2*n+samples)
            t = self.mem.transfer(t, score_address, n*4, False, 'CDF_scan')
            return t, out
        if name == 'screen_serial_ising':
            out, details = ising_random_scan(row['logits'], samples, a['serial_burn'], a['serial_spacing'], rng)
            attempts = details['attempts']
            t = self.rng.request('serial_ising', t, attempts, 32, 1, 'serial_heatbath', (token,layer,row['head']))
            before_busy = self.s.by_stage['serial_ising']
            t = self.s.reserve('serial_ising', t, attempts*a['serial_cycles_per_attempt']*self.period,
                               ('sampler',), self.period, attempts=attempts)
            # Read the reservation actually made above, not a second timing model.
            service_ns = self.s.by_stage['serial_ising']-before_busy
            self.sampler_audit.append(dict(token=token, layer=layer, head=row['head'],
                sampler='serial_random_scan', audit_scope='attempt-service macro; output transfer is separate',
                start_ns=t-service_ns, end_ns=t, elapsed_cycles=service_ns/self.period,
                clock_ns=self.period, valid_candidates=n, base_sample_budget=samples,
                requested_samples=samples, outputs=len(out), attempts=attempts,
                flips=details['flips'], proposal_frames=None, algorithm_updates=None,
                rejected_multi=None, rejected_empty=None,
                source_lane_work=dict(uniform_words=attempts, uniform_word_bits=32),
                stage_cycles=dict(serial_ising=service_ns/self.period),
                stage_calls=dict(serial_ising=1)))
            self.e.action('serial_ising_attempt', attempts, 'sampler')
            self.attn_stats['serial_attempts'] += attempts
            t = self.mem.transfer(t,self.indices_base,len(out)*16,True,'serial_sample_indices')
            return t, out
        module = self.samplers[name]
        retained = samples*a['winner_update_multiplier'] if name == 'screen_winner' else samples
        if not self.integrated_rng:
            t = self.rng.request('parallel_sampler', t, 0, 1, n, 'biased_source_setup', (token,layer,row['head']))
        # Explicit conservative stream sink: one index occupies one SRAM word,
        # whole source+FSM request owns sampler and common SRAM fabric. This
        # counts output backpressure without inventing a hidden address FIFO.
        resources = ['sampler', 'sram_fabric']+['sram_bank:'+str(i) for i in range(self.c['sram']['banks'])]
        ready = max([t]+[self.s.free[r] for r in resources])
        output_ns = self.mem.period+self.mem.spec['write_access_ns']+self.c['sram']['cdc_ns']
        out, receipt = module.request(ready, row['logits'], retained, rng,
            (token,layer,row['head']), row['ids'], output_ns_per_index=output_ns,
            **({'source':self.rng} if self.integrated_rng else {}))
        activity = receipt['actions']
        # Keep every serviced head, even when detailed events/addresses are
        # disabled or truncated. Values are copied from the original receipt.
        self.sampler_audit.append(dict(token=token, layer=layer, head=row['head'],
            sampler=receipt['sampler'], audit_scope='configured blocking sampler FSM including output transfer',
            start_ns=receipt['start_ns'], configured_ns=receipt['configured_ns'],
            first_sample_ns=receipt['first_sample_ns'], end_ns=receipt['end_ns'],
            elapsed_cycles=receipt['elapsed_cycles'], clock_ns=receipt['clock_ns'],
            valid_candidates=receipt['valid_candidates'], base_sample_budget=samples,
            requested_samples=receipt['requested_samples'], outputs=receipt['samples'],
            proposal_frames=activity.get('proposal_frames',0),
            algorithm_updates=activity.get('algorithm_updates'),
            rejected_multi=activity.get('rejected_multi',0),
            rejected_empty=activity.get('rejected_empty',0),
            source_lane_work={key:activity.get(key,0) for key in
                ('biased_bit_draws','fair_bit_draws','source_slot_cycles','timed_source_service_cycles')},
            stage_cycles=dict(receipt['stage_cycles']), stage_calls=dict(receipt['stage_calls'])))
        start, end = receipt['start_ns'], receipt['end_ns']
        t = self.s.reserve('parallel_'+name, start, end-start, resources, self.period,
            frames=receipt['actions'].get('proposal_frames',0), outputs=len(out))
        if abs(t-end) > 1e-6:
            raise AssertionError('sampler resource schedule disagrees with FSM')
        self.mem.traffic['write_logical_bytes'] += len(out)*4
        self.mem.traffic['write_physical_bytes'] += len(out)*self.mem.word
        self.mem.traffic['write_words'] += len(out)
        self.e.action('sram_write', len(out), 'SRAM_internal', self.mem.spec['write_internal_pJ'])
        if not self.integrated_rng:
            self.rng.embedded('parallel_sampler', receipt['actions'], receipt['actions'].get('source_slot_cycles',0))
        for action, count in receipt['actions'].items():
            if action not in ('biased_bit_draws','fair_bit_draws','source_slot_cycles','delegated_drive_bits','timed_source_service_cycles'):
                self.e.action('sampler_'+action, count, 'sampler')
        # A local digital PRNG p-bit backend still needs a response conversion
        # and comparators. They are pending costs, not free sigmoid operations.
        if not self.integrated_rng:
            response_updates = n*(1+receipt['actions'].get('offset_changes',0))
            self.e.action('local_sigmoid_response_encode', response_updates, 'random_frontend')
            self.e.action('local_probability_compare', receipt['actions'].get('biased_bit_draws',0), 'random_frontend')
        self.attn_stats['sampler_proposal_frames'] += receipt['actions'].get('proposal_frames',0)
        self.attn_stats['sampler_outputs'] += len(out)
        self.attn_stats['sampler_rejected'] += receipt['actions'].get('rejected_multi',0)+receipt['actions'].get('rejected_empty',0)
        if self.integrated_rng:
            # CPU simulation memory only: aggregate ledgers and bounded row
            # receipts suffice; no need to retain every full query history.
            module.requests.clear()
        return t, out

    def sampled_attention(self, t, token, layer, kv, rows, samples):
        per_head = []
        total_samples = 0
        for row in rows:
            t, out = self.sample_row(t, token, layer, row, samples)
            counts = Counter(row['ids'][i] for i in out)
            per_head.append(counts)
            total_samples += len(out)
            # Explicit scan/histogram/remap, with repeated addresses retained as
            # counts. Index scratch is not a random-number stream buffer.
            if self.c['attention']['mode'] not in ('pv','screen_pv'):
                t = self.mem.transfer(t,self.hist_base,len(row['ids'])*4,True,'histogram_clear')
                t = self.mem.transfer(t,self.indices_base,len(out)*16,False,'sample_indices')
                t = self.mem.serial_histogram(t,self.hist_base,out,self.period)
                t = self.mem.transfer(t,self.hist_base,len(row['ids'])*4,False,'histogram_scan')
            t = self.vec(t, 'sample_histogram_remap', len(row['ids'])+len(counts))
            if self.c['attention']['mode'].startswith('screen_'):
                t = self.mem.transfer(t,self.map_base,len(counts)*4,False,'index_remap')
            local_offset = (row['head']%self.group)*min(self.max_retained_samples,self.row_capacity)*8
            t = self.mem.transfer(t, self.worklist_base+local_offset, max(8, len(counts)*8), True, 'V_worklist')
            if len(self.attn_rows) < self.c['row_receipt_limit']:
                self.attn_rows.append(dict(token=token, layer=layer, head=row['head'], candidates=len(row['ids']),
                    outputs=len(out), unique_V=len(counts), sampled_address_sha256=hashlib.sha256(json.dumps(out).encode()).hexdigest()))
        union = sorted(set().union(*(set(c) for c in per_head)))
        entries = sum(len(c) for c in per_head)
        t = self.mem.transfer(t,self.worklist_base,entries*8,False,'GQA_worklist_merge')
        t = self.vec(t,'GQA_sorted_union',entries*max(1,self.group.bit_length()))
        self.attn_stats['V_unique_group_positions'] += len(union)
        self.attn_stats['V_sample_events'] += total_samples
        # Union once per KV group, broadcast to every interested Q head.
        for start in range(0,len(union),self.c['dram']['max_pending']):
            ids = union[start:start+self.c['dram']['max_pending']]
            t = self.dram.ranges(t,self.kv_ranges(layer,kv,ids,True),False,'V_sparse_union')
            size = len(ids)*self.d*2
            t = self.mem.transfer(t,self.kv_buffer,size,True,'V_fill')
            t = self.mem.transfer(t,self.kv_buffer,size,False,'V_broadcast')
            additions = sum(sum(c[i] for i in ids) for c in per_head)*self.d
            t = self.vec(t,'V_repeated_add',additions)
            self.e.action('V_selection_add',additions,'attention_PV')
        return self.vec(t,'sample_average',len(rows)*self.d,len(rows))

    def attention(self,t,token,layer,length):
        a = self.c['attention']
        samples = a['samples'] if a['samples'] is not None else max(a['minimum_samples'],math.ceil(length*a['sample_ratio']))
        self.attn_stats['possible_QK_positions'] += self.H*length
        self.attn_stats['possible_K_group_positions'] += self.KH*length
        self.attn_stats['possible_V_group_positions'] += self.KH*length
        for kv in range(self.KH):
            t,rows = self.route(t,token,layer,kv,length)
            fused = a['mode'] in ('exact','screen_exact')
            t = self.qk(t,layer,kv,rows,fused)
            if not fused:
                t = self.sampled_attention(t,token,layer,kv,rows,samples)
        return self.mem.transfer(t,self.activation,self.q_width*2,True,'attention_output')

    def phase(self,name,token,layer,ready,fn):
        end = fn(ready)
        if end+1e-6 < ready:
            raise AssertionError('phase time reversed')
        self.phases.append(dict(name=name,token=token,layer=layer,start_ns=ready,end_ns=end))
        return end

    def run(self):
        c,m = self.c,self.m
        t,token_times = 0.,[]
        for token in range(c['decode_tokens']):
            begin = t
            # Match historical TLM: context is total attention length including
            # the current query. Initially context-1 prior KV tokens exist.
            length = c['context_tokens']+token
            embed = 'lm_head' if m.get('tie_word_embeddings',False) else 'embedding'
            t = self.phase('embedding',token,None,t,lambda z:self.dram.tensor(z,embed,7*self.h*2,self.h*2,kind='embedding'))
            t = self.mem.transfer(t,self.activation,self.h*2,True,'embedding')
            t = self.mem.transfer(t,self.residual,self.h*2,True,'initial_residual')
            for layer in range(m['num_hidden_layers']):
                t = self.dram.tensor(t,'L%d/norms'%layer,0,self.h*4,kind='norm_weights')
                t = self.phase('attention_norm',token,layer,t,lambda z:self.vec(z,'RMSNorm',5*self.h,1,read=self.h*2,write=self.h*2))
                t = self.phase('QKV_projection',token,layer,t,lambda z:self.matrix(z,'L%d/qkv'%layer))
                if m.get('qk_norm',False):
                    t=self.dram.tensor(t,'L%d/qk_norm'%layer,0,4*self.d,kind='norm_weights')
                    t=self.phase('QK_head_norm',token,layer,t,lambda z:self.vec(z,'QK_RMSNorm',5*(self.q_width+self.KH*self.d),self.H+self.KH,
                        read=(self.q_width+self.KH*self.d)*2,write=(self.q_width+self.KH*self.d)*2,
                        read_address=self.matrix_output,write_address=self.matrix_output))
                bias = self.q_width+2*self.KH*self.d if m.get('attention_bias',False) else 0
                qkv_bytes = (self.q_width+2*self.KH*self.d)*2
                t = self.phase('RoPE_bias_KV_append',token,layer,t,lambda z:self.vec(z,'RoPE_bias',3*(self.q_width+self.KH*self.d)+bias,
                    read=qkv_bytes,write=qkv_bytes,read_address=self.matrix_output,write_address=self.matrix_output))
                for kind in ('K','V'):
                    off = self.q_width*2+(self.KH*self.d*2 if kind=='V' else 0)
                    t = self.mem.transfer(t,self.matrix_output+off,self.KH*self.d*2,False,'KV_append_operand')
                    t = self.dram.tensor(t,'L%d/%s'%(layer,kind),(length-1)*self.KH*self.d*2,self.KH*self.d*2,True,'KV_append')
                t = self.phase('attention_core',token,layer,t,lambda z:self.attention(z,token,layer,length))
                t = self.phase('O_projection',token,layer,t,lambda z:self.matrix(z,'L%d/o'%layer))
                t = self.phase('residual_and_ffn_norm',token,layer,t,lambda z:self.residual_add(z,True))
                if self.latest_ffn:
                    t=self.phase('FFN_gate_up',token,layer,t,lambda z:self.ffn_latest.gate_up(z,layer))
                    t=self.phase('FFN_nonlinear_encoding',token,layer,t,self.ffn_latest.encode_nonlinear)
                    t=self.phase('FFN_AND_direct_down',token,layer,t,lambda z:self.ffn_latest.down(z,layer))
                    t=self.phase('ffn_output_conversion',token,layer,t,self.ffn_latest.final)
                else:
                    matrix_fn = self.matrix_sc if c['ffn']['mode']=='sc' else self.matrix
                    t = self.phase('FFN_gate_up',token,layer,t,lambda z:matrix_fn(z,'L%d/gu'%layer))
                    sw_width = 2 if c['ffn']['mode']=='bf16' else 4
                    t = self.phase('FFN_SwiGLU',token,layer,t,lambda z:self.vec(z,'SwiGLU_'+('BF16' if sw_width==2 else 'FP32'),2*self.F,self.F,
                        read=2*sw_width*self.F,write=sw_width*self.F,read_address=self.matrix_output,write_address=self.z))
                    t = self.phase('FFN_down',token,layer,t,lambda z:matrix_fn(z,'L%d/down'%layer))
                if c['ffn']['mode']!='bf16' and not self.latest_ffn:
                    t = self.phase('ffn_output_conversion',token,layer,t,lambda z:self.vec(z,'FP32_to_BF16',self.h,read=self.h*4,write=self.h*2,
                        read_address=self.matrix_output,write_address=self.matrix_output,energy_unit='FP32_to_BF16'))
                t = self.phase('ffn_residual',token,layer,t,lambda z:self.residual_add(z))
            t = self.dram.tensor(t,'final_norm',0,self.h*2,kind='norm_weights')
            t = self.phase('final_norm',token,None,t,lambda z:self.vec(z,'final_RMSNorm',5*self.h,1))
            t = self.phase('lm_head_and_argmax',token,None,t,lambda z:self.matrix(z,'lm_head'))
            token_times.append(t-begin)
        if abs(self.s.end()-t)>1e-6:
            raise AssertionError('unretired asynchronous resource at token end')
        if self.tile_pipeline is not None and (self.tile_pipeline.pending is not None or self.tile_pipeline.active is not None):
            raise AssertionError('unretired tile at token end')
        random_report=self.rng.finish(t) if self.integrated_rng else self.rng.report()
        dram = self.dram.finish(t)
        memory = self.mem.report(t)
        for state in ('digital_idle_ns','sc_idle_ns','control_interconnect_ns'):
            self.e.action(state,t,'standby')
        totals = Counter()
        for p in self.phases:
            totals[p['name']] += p['end_ns']-p['start_ns']
        # Non-phase traffic (norm weights, KV appends, final norm weights) is
        # explicitly reported so phase totals never pretend to equal full time.
        totals['other_explicit_memory'] = t-sum(totals.values())
        if totals['other_explicit_memory'] < -1e-6:
            raise AssertionError('phase accounting overlap')
        return dict(schema_version=6,model=m,config=c,
            scope='batch1 full decoder decode + embedding/final norm/lm_head/greedy selection; prior context already exists; no prefill/TTFT',
            implementation='bounded tile/resource event TLM; NOT full-chip cycle-accurate simulation',
            metrics=dict(TPOT_ms=sum(token_times)/len(token_times)/1e6,token_ms=[x/1e6 for x in token_times],
                tokens_per_second=len(token_times)/(t*1e-9),elapsed_ns=t,
                priced_subtotal_mJ_per_token=sum(self.e.energy.values())/len(token_times)*1000,
                full_physical_energy_J=None,full_physical_area_mm2=None,quality_reference_ppl=None),
            energy_J=dict(self.e.energy),unpriced_actions=dict(self.e.missing),actions=dict(self.e.actions),
            phase_ns=dict(totals),phases=self.phases,resource_busy_ns=dict(self.s.busy),
            wait_ns=dict(self.s.wait),events=self.s.events,event_count=self.s.count,
            stage_busy_ns=dict(self.s.by_stage),sampler_audit=self.sampler_audit,
            trace_truncated=self.s.count>len(self.s.events),random_interface=random_report,
            SRAM={**memory,'layout':self.arena.regions,'reserved_peak_bytes':self.arena.peak},
            DRAM=dram,attention_activity=dict(self.attn_stats),row_receipts=self.attn_rows,
            FFN_activity=dict(self.metadata),input_provenance=self.source.provenance,
            FFN_contract=self.ffn_latest.report() if self.latest_ffn else {'contract':'legacy_FP32_SwiGLU'},
            sampler_local_state={name:dict(buffer_bits=s.buffer_bits,biased_lanes=s.biased_capacity,
                fair_lanes=s.fair_capacity) for name,s in self.samplers.items() if name==c['attention']['mode']},
            tile_pipeline=self.tile_pipeline.report() if self.tile_pipeline is not None else {'contract':'legacy'},
            digital_operand_contract=dict(schedule=c.get('schedule_policy','legacy'),
                operand_capacity_bytes=self.tile_pipeline.digital_capacity if self.tile_pipeline else None,
                activation_peak_bytes=self.digital_activation_peak if self.tile_pipeline else None,
                W8_restore=c.get('digital_w8_restore','legacy_row'),
                FP32_block_partial_peak_bytes=self.digital_partial_peak,
                partial_write_bytes_per_cycle=ceildiv(c['macs_per_cycle'],64)*4,
                partial_read_bytes_per_cycle=c['vector_lanes']*4,
                block_boundary='K64 partial output supported continuously; no extra per-block startup assumed',
                local_weight_read_bytes_per_cycle=c['macs_per_cycle']*2,
                timing='local operand throughput absorbed in configured MAC rate; not STA calibrated',
                area_mm2=None,energy_J=None),
            calibration_sha256=self.calibration_sha,
            limitations=['regular arithmetic timing is configured, not calibrated whole-core timing',
                'SC B4/short-stream counter/scale-restoration power and area not characterized',
                'stationary weight tile interface is an unverified macro contract, not free DFF replacement',
                ('FFN input-group-major gu/encoding/AND-direct-down barriers; not optimality claim'
                 if self.latest_ffn else 'FFN input-group-major gu/SwiGLU/down barriers; not optimality claim'),
                'one KV group at a time; no head/group parallelism inferred from array size',
                ('actual finite Issue95 backend with q/256 response; complete random PPA still incomplete'
                 if self.integrated_rng else 'local source interface assumes enough lanes; backend pending'),
                'parallel sampling sink owns SRAM fabric for complete FSM; conservative blocking mapping',
                'SRAM blocking descriptors and DRAM bounded windows, no arbitrary multi-DMA reorder',
                'warm K summaries live in DRAM; context prefill/build cost excluded, steady updates included',
                'all published timing/traffic cases synthetic unless complete user logit trace supplied',
                'no new PPL, GPU performance, RTL/PT or silicon measurements'])
