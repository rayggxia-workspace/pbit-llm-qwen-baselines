"""LLaMA MHA attention on the current finite-memory transaction engine.

All variants use the same banked SRAM and bounded 64-byte scatter DMA.  The
selector is max-of-four subblock means, standardized sigmoid/Bernoulli with
fixed, explicitly supplied bias/temperature; no Qwen calibration is imported.
PV uses one systematic phase per query head and a context-proportional budget.
Ising is an uncharacterized, fully provisioned v4 macro, with online index
readout and a bounded histogram.  Its ideal numerical oracle selects workload
addresses only and does not validate finite-time physical Ising inference.
"""
import copy
import hashlib
import math
from collections import Counter, defaultdict
from pathlib import Path

from attention_reference_v3 import selector, softmax
from ising_macro_v4 import IsingMacro
from memory_schedule_v5 import BankedDigitalDecode, BankedLocalDecode
from pv_stream_v6 import StreamPVDecode, context_samples, systematic_counts
from scatter_memory_v6 import coalesced_bursts, link_access_ranges


MODES = ('dense', 'pv', 'ising', 'screen_exact', 'screen_pv', 'screen_ising')


class LlamaAttentionMixin:
    """Conservative serial tile mapping, shared by digital and stochastic FFN."""

    transfer = StreamPVDecode.transfer
    phase = StreamPVDecode.phase
    prefix_scan = StreamPVDecode.prefix_scan

    def __init__(self, cfg, *args, **kwargs):
        mode = cfg['attention_v3']['mode']
        if mode not in MODES:
            raise ValueError('unknown LLaMA attention mode: ' + mode)
        init = copy.deepcopy(cfg)
        # The historical validator does not recognize the v4 macro mode.  Only
        # its validation mode is changed; this adapter implements every path.
        init['attention_v3']['mode'] = 'dense' if mode == 'dense' else 'pv'
        super().__init__(init, *args, **kwargs)
        self.ac = copy.deepcopy(cfg['attention_v3'])
        self.cfg['attention_v3'] = self.ac
        self.pc = copy.deepcopy(cfg['pv_stream_v6'])
        self.lc = copy.deepcopy(cfg.get('llama_attention', {}))
        if self.group != 1:
            raise ValueError('this adapter targets LLaMA-1 7B MHA (one Q per KV)')
        if self.lc.get('selector', 'max4') != 'max4':
            raise ValueError('only the declared max4 selector is implemented')
        if self.ac.get('calibration_file'):
            raise ValueError('LLaMA adapter must not inherit Qwen calibration')
        if self.lc.get('prefill_prebuilt', False):
            self.ac['summary_initialization'] = 'prefill_prebuilt'
        if (self.cfg['external_memory'].get('backend') != 'dramsys'
                and self.ext.cfg['burst_bytes'] != 64):
            raise ValueError('all comparisons require equal 64-byte bursts')
        self.screen = mode.startswith('screen')
        self.random_attention = mode != 'dense'
        self.pv_phases = defaultdict(float)
        self.pv_tiles, self.pv_stage_rows = [], []
        self.ising_rows = []
        self.ising_macro = None
        if mode in ('ising', 'screen_ising'):
            capacity = self.lc.get('ising_capacity',
                                   cfg['context_tokens'] + cfg['decode_tokens'] - 1)
            self.ising_macro = IsingMacro(self.lc['ising_macro'], capacity)
        if self.screen:
            layout = self.ext.layout
            cursor = math.ceil(layout.total_bytes / 4096) * 4096
            blocks = math.ceil((cfg['context_tokens'] + cfg['decode_tokens']) / 64)
            size = self.kheads * blocks * 4 * self.dim * 4
            for layer in range(self.shape['num_hidden_layers']):
                allocated = math.ceil(size / 4096) * 4096
                layout.regions[f'L{layer}/summary'] = dict(
                    base=cursor, logical_bytes=size, allocated_bytes=allocated)
                cursor += allocated
            layout.total_bytes = cursor
            if hasattr(self.ext, 'capacity') and cursor > self.ext.capacity:
                raise ValueError('summary regions exceed external memory capacity')

    def ranges(self, t, ranges, kind):
        """Pay actual aligned traffic; split into finite descriptor batches."""
        if not ranges:
            return t
        spans = coalesced_bursts(ranges)
        physical = sum(size for _, size in spans)
        self.traffic['attention_' + kind + '_useful_bytes'] += sum(n for _, n in ranges)
        self.traffic['attention_' + kind + '_physical_bytes'] += physical
        limit = self.pc['max_spans_per_descriptor']
        for offset in range(0, len(spans), limit):
            batch = spans[offset:offset + limit]
            start = t
            t = self.transfer(t, 'descriptors', len(batch) * 16, True, 'SG_descriptors')
            t = self.transfer(t, 'descriptors', len(batch) * 16, False, 'SG_descriptor_read')
            t = self.op(t, 'SG_control', vec=len(batch))
            if hasattr(self.ext, 'access_ranges'):
                t = self.ext.access_ranges(t, batch, 'ATT_' + kind)
            else:
                t = link_access_ranges(self.ext, t, batch, 'ATT_' + kind,
                                       pending=self.pc['dma_pending_bursts'],
                                       issue_ns=self.pc['dma_issue_ns'])
            self.record('DRAM_scatter_' + kind, start, t,
                        bytes=sum(n for _, n in batch), ranges=len(batch),
                        resource='external_memory')
        return t

    def _allocate_attention(self, length, sampled):
        block = self.ac['kv_tile_tokens']
        tiles = math.ceil(length / block)
        sizes = [('state', self.qheads * self.dim * 4 + 8192),
                 ('KV', 2 * block * self.kheads * self.vecbytes),
                 ('descriptors', (self.pc['max_spans_per_descriptor']
                                  + self.pc['dma_pending_bursts']) * 16)]
        if self.screen:
            sizes.extend([('summary', self.kheads * math.ceil(length / 64) * 4 * self.dim * 4),
                          ('router', self.qheads * math.ceil(length / 64) * 5)])
        if sampled:
            sizes.extend([('scores', self.qheads * length * 4),
                          ('stats', self.qheads * tiles * 16),
                          ('counts', block * 2 + block * 4 + 64),
                          ('V', block * self.vecbytes)])
        if self.ising_macro:
            sizes.extend([('ising_counts', length * 2), ('ising_index', 4),
                          ('ising_program', math.ceil(self.ising_macro.capacity
                                            * (self.ising_macro.cfg['bias_bits'] + 1) / 8))])
        self.arena = {}
        cursor = 0
        for name, size in sizes:
            cursor = math.ceil(cursor / 64) * 64
            self.arena[name] = (cursor, size)
            cursor += size
        if cursor > self.work_mem.capacity:
            raise ValueError('LLaMA attention exceeds finite banked SRAM capacity')
        self.attn_peak = max(self.attn_peak, cursor)
        self.attn_work_peak = max(self.attn_work_peak, cursor)
        return cursor

    def _route(self, t, length, layer, token):
        rows = []
        if self.screen:
            t, _ = self.summary(t, length, layer)
            blocks, subblocks = math.ceil(length / 64), math.ceil(length / 16)
            t = self.op(t, 'router_proxy', mac=self.qheads * subblocks * self.dim,
                        vec=self.qheads * (subblocks + 12 * blocks),
                        nl=self.qheads * (blocks + 2))
            t = self.transfer(t, 'router', self.qheads * blocks * 4, True,
                              'router_probabilities')
            t = self.transfer(t, 'router', self.qheads * blocks * 4, False,
                              'router_probability_read')
            # On-demand local PRNG; no SRAM array of uniform words.
            t = self.random_words(t, self.qheads * blocks, 'router')
            t = self.sampler(t, self.qheads * blocks, 'router_keep')
            t = self.transfer(t, 'router', self.qheads * blocks, True, 'router_mask',
                              offset=self.qheads * blocks * 4)
            t = self.transfer(t, 'router', self.qheads * blocks, False, 'router_mask_read',
                              offset=self.qheads * blocks * 4)
        for head in range(self.qheads):
            logits = self.source.logits(token, layer, head, length)
            if self.screen:
                bias, temp = self.source.parameters(layer, head)
                indices, info = selector(logits, bias, temp,
                                         self.source.random(token, layer, head, 'router'))
            else:
                indices, info = list(range(length)), {}
            rows.append(dict(head=head, indices=indices,
                             logits=[logits[i] for i in indices], router=info))
        if self.screen:
            t = self.op(t, 'candidate_address_generation',
                        vec=sum(len(row['indices']) for row in rows))
        return t, rows

    def summary(self, t, length, layer):
        """Prefill covers L-1 keys; insert the newest key on EVERY decode call."""
        if (layer not in self.summary_built
                and self.ac['summary_initialization'] == 'cold_build'):
            # Explicit cold construction reads all K and includes the new key.
            return super().summary(t, length, layer)
        self.summary_built.add(layer)
        name = f'L{layer}/summary'
        size = self.kheads * math.ceil(length / 64) * 4 * self.dim * 4
        offset = (((length - 1) // 64) * 4 + ((length - 1) % 64) // 16)
        offset *= self.kheads * self.dim * 4
        update = self.kheads * self.dim * 4
        address = self.ext.layout.address(name, offset, update)
        if (length - 1) % 16:
            t = self.ranges(t, [(address, update)], 'summary_update')
            t = self.transfer(t, 'summary', update, True, 'summary_update_fill')
            t = self.transfer(t, 'summary', update, False, 'summary_update_operand')
        # The just-projected K is resident at the attention boundary.  This
        # consumes its local operand; it is never fetched again from DRAM.
        t = self.transfer(t, 'KV', self.kheads * self.vecbytes, False, 'new_K_summary_operand')
        t = self.op(t, 'summary_update', vec=self.kheads * self.dim)
        t = self.transfer(t, 'summary', update, True, 'summary_updated_sum')
        t = self.transfer(t, 'summary', update, False, 'summary_writeback_operand')
        start = t
        t = self.ext.access(t, update, 'ATT_summary', True, address=address)
        self.record('DRAM_summary_update_write', start, t, address=address,
                    bytes=update, resource='external_memory')
        base = self.ext.layout.address(name, 0, size)
        t = self.ranges(t, [(base, size)], 'summary_read')
        t = self.transfer(t, 'summary', size, True, 'summary_fill')
        t = self.transfer(t, 'summary', size, False, 'summary_operand')
        t = self.op(t, 'summary_means', vec=self.kheads * math.ceil(length / 16) * self.dim,
                    nl=math.ceil(length / 16))
        return t, size

    def _qk(self, t, length, layer, rows, fused):
        block = self.ac['kv_tile_tokens']
        cursors = [0] * self.qheads
        if not fused and not self.ising_macro:
            t = self.transfer(t, 'stats', self.arena['stats'][1], True, 'tile_stats_clear')
        for offset in range(0, length, block):
            selected = [[i for i in row['indices'] if offset <= i < offset + block]
                        for row in rows]
            amount = sum(map(len, selected))
            if not amount:
                continue
            spans = [(self.kv_address(layer, i, head), self.vecbytes)
                     for head, indices in enumerate(selected) for i in indices]
            if fused:
                spans += [(self.kv_address(layer, i, head, True), self.vecbytes)
                          for head, indices in enumerate(selected) for i in indices]
            t = self.ranges(t, spans, 'KV_fused' if fused else 'K')
            size = sum(n for _, n in spans)
            t = self.transfer(t, 'KV', size, True, 'selected_KV_fill')
            t = self.transfer(t, 'KV', size, False, 'selected_KV_operand')
            t = self.op(t, 'QK', mac=amount * self.dim, vec=amount)
            live = sum(bool(indices) for indices in selected)
            if fused:
                t = self.transfer(t, 'state', self.qheads * (self.dim * 4 + 8), False,
                                  'online_accumulator_read')
                t = self.op(t, 'online_softmax', vec=4 * amount + live * (2 * self.dim + 3),
                            nl=amount + live)
                t = self.op(t, 'PV', mac=amount * self.dim)
                t = self.transfer(t, 'state', self.qheads * (self.dim * 4 + 8), True,
                                  'online_accumulator_commit')
            else:
                if not self.ising_macro:
                    t = self.op(t, 'tile_softmax_stats', vec=3 * amount + 3 * live,
                                nl=amount + live)
                for head, indices in enumerate(selected):
                    if not indices:
                        continue
                    t = self.transfer(t, 'scores', len(indices) * 4, True, 'score_stash',
                                      offset=(head * length + cursors[head]) * 4)
                    if not self.ising_macro:
                        t = self.transfer(t, 'stats', 16, True, 'tile_stats',
                                          offset=((offset // block) * self.qheads + head) * 16)
                    cursors[head] += len(indices)
        if fused:
            t = self.op(t, 'online_finalize', vec=self.qheads * self.dim, nl=self.qheads)
        return t

    def _pv_counts(self, t, length, rows, samples, token, layer):
        counts = []
        for row in rows:
            probabilities = softmax(row['logits'])
            phase = self.source.random(token, layer, row['head'], 'pv_v6_systematic').random()
            local = systematic_counts(probabilities, samples, phase)
            counts.append(Counter({row['indices'][i]: count for i, count in local.items()}))
        before = t
        tiles = math.ceil(length / self.ac['kv_tile_tokens'])
        t = self.transfer(t, 'stats', self.arena['stats'][1], False, 'budget_stats')
        t = self.op(t, 'tile_mass_rescale', vec=3 * self.qheads * tiles,
                    nl=self.qheads * (tiles + 1))
        t = self.random_words(t, self.qheads, 'systematic_offsets')
        t = self.prefix_scan(t, 'tile_budget_prefix', tiles, heads=self.qheads)
        t = self.transfer(t, 'stats', self.arena['stats'][1], True, 'budgets_and_phase')
        t = self.phase('budget_and_rng', before, t)
        return t, counts

    def _ising_counts(self, t, length, layer, token, row, samples):
        """One reusable macro; one live output index, no S-word RNG/index buffer."""
        head, n = row['head'], len(row['indices'])
        t = self.transfer(t, 'scores', n * 4, False, 'ising_logits', offset=head * length * 4)
        t = self.op(t, 'ising_bias_encode', vec=2 * n)
        program = self.arena['ising_program'][1]
        t = self.transfer(t, 'ising_program', program, True, 'ising_program_pack')
        t = self.transfer(t, 'ising_program', program, False, 'ising_program_read')
        t = self.transfer(t, 'ising_counts', length * 2, True, 'ising_histogram_clear')
        mem = self.work_mem
        service = (4 * (2 * mem.period + max(mem.spec['read_access_ns'],
                                            mem.spec['write_access_ns']) + mem.cdc_ns)
                   + self.period)
        ids, info = self.ising_macro.request(
            t, row['logits'], samples,
            self.source.random(token, layer, head, 'ising_macro_oracle'),
            (token, layer, head), row['indices'], output_ns_per_index=service)
        self.energy['ATT_Ising_macro_active'] += info['energy_J']
        self.actions['ATT_Ising_macro_calls'] += 1
        self.actions['ATT_Ising_macro_config_bits'] += info['config_bits']
        self.actions['ATT_Ising_macro_samples'] += samples
        last = t
        for j, local in enumerate(ids):
            at = info['first_sample_ns'] + j * info['effective_sample_period_ns']
            at = self.transfer(at, 'ising_index', 4, True, 'ising_index_arrival')
            at = self.transfer(at, 'ising_index', 4, False, 'ising_index_consume')
            address = row['indices'][local] * 2
            at = self.transfer(at, 'ising_counts', 2, False, 'ising_histogram_read', offset=address)
            at = self.op(at, 'ising_histogram_increment', vec=3)
            last = self.transfer(at, 'ising_counts', 2, True, 'ising_histogram_write', offset=address)
        if last > info['end_ns'] + 1e-5:
            raise AssertionError('Ising online output exceeds provisioned backpressure service')
        t = info['end_ns']
        self.record('Ising_macro_stream', info['start_ns'], t,
                    resource='Ising_macro', **{k: v for k, v in info.items()
                                               if k not in ('start_ns', 'end_ns')})
        self.ising_rows.append(dict(**self.coord, head=head, **info))
        return t, Counter(row['indices'][i] for i in ids)

    def _gather_head(self, t, length, layer, row, counts, ising):
        block = self.ac['kv_tile_tokens']
        head = row['head']
        score_cursor = 0
        for offset in range(0, length, block):
            indices = [i for i in row['indices'] if offset <= i < offset + block]
            values = {i: count for i, count in counts.items() if offset <= i < offset + block}
            if not values:
                self.actions['ATT_zero_budget_group_tiles'] += 1
                score_cursor += len(indices)
                continue
            before = t
            if not ising:
                t = self.transfer(t, 'stats', 16, False, 'budget_read',
                                  offset=((offset // block) * self.qheads + head) * 16)
                t = self.transfer(t, 'scores', len(indices) * 4, False, 'score_scan',
                                  offset=(head * length + score_cursor) * 4)
                t = self.prefix_scan(t, 'systematic_count_scan', len(indices))
                t = self.transfer(t, 'counts', len(indices) * 2, True, 'tile_counts')
                t = self.transfer(t, 'counts', len(indices) * 2, False, 'count_union_operand')
            else:
                n = min(block, length - offset)
                t = self.transfer(t, 'ising_counts', n * 2, False, 'ising_histogram_scan',
                                  offset=offset * 2)
            union = sorted(values)
            t = self.op(t, 'union_and_compact', vec=len(indices) + 2 * len(indices))
            t = self.transfer(t, 'counts', len(union) * 4, True, 'union_indices', offset=block * 2)
            t = self.transfer(t, 'counts', len(union) * 4, False, 'union_index_read', offset=block * 2)
            t = self.phase('count_scan_and_route', before, t)
            before = t
            t = self.ranges(t, [(self.kv_address(layer, i, head, True), self.vecbytes)
                                for i in union], 'V_gather')
            t = self.phase('V_DMA', before, t)
            before = t
            t = self.transfer(t, 'V', len(union) * self.vecbytes, True, 'V_union_fill')
            t = self.transfer(t, 'V', len(union) * self.vecbytes, False, 'V_union_operand')
            self.actions['ATT_V_group_union_rows'] += len(union)
            self.actions['ATT_V_broadcast_deliveries'] += len(union)
            self.energy['ATT_V_broadcast'] += (len(union) * self.vecbytes
                                                * self.pc['broadcast_pJ_per_byte'] * 1e-12)
            t = self.transfer(t, 'state', self.dim * 4, False, 'V_accumulator_read',
                              offset=head * self.dim * 4)
            events = sum(values.values())
            t = self.op(t, 'V_accumulate', vec=events * self.dim)
            t = self.transfer(t, 'state', self.dim * 4, True, 'V_accumulator_commit',
                              offset=head * self.dim * 4)
            t = self.phase('V_SRAM_broadcast_and_add', before, t)
            self.pv_tiles.append(dict(**self.coord, kvhead=head, offset=offset,
                                      rows=len(indices), union_rows=len(union), sample_events=events))
            score_cursor += len(indices)
        return t

    def attention(self, ready, length, layer):
        if max(self.weights.slot_free) > ready + 1e-5:
            raise ValueError('weight staging has not released shared SRAM')
        self.attention_length = length
        token = self.attn_calls[layer]
        self.attn_calls[layer] += 1
        self.coord = dict(token=token, layer=layer)
        sampled = self.ac['mode'] not in ('dense', 'screen_exact')
        peak = self._allocate_attention(length, sampled)
        samples = context_samples(length, self.pc) if sampled else 0
        if samples > 65535:
            raise ValueError('16-bit sample-count overflow')
        start = ready
        t, rows = self._route(ready, length, layer, token)
        t = self.transfer(t, 'state', self.qheads * (self.dim * 4 + 8), True,
                          'attention_accumulator_init')
        t = self.phase('route_summary_and_init', ready, t)
        selected = sum(len(row['indices']) for row in rows)
        self.actions['ATT_selected_QK_tokens'] += selected
        self.actions['ATT_possible_QK_tokens'] += self.qheads * length
        before = t
        t = self._qk(t, length, layer, rows, not sampled)
        t = self.phase('score_and_tile_stats', before, t)
        if sampled:
            if not self.ising_macro:
                t, counters = self._pv_counts(t, length, rows, samples, token, layer)
            for row in rows:
                before = t
                if self.ising_macro:
                    t, counts = self._ising_counts(t, length, layer, token, row, samples)
                    t = self.phase('ising_macro_and_online_histogram', before, t)
                else:
                    counts = counters[row['head']]
                if sum(counts.values()) != samples:
                    raise AssertionError('sample budget is not conserved')
                self.actions['ATT_V_sample_events'] += samples
                self.actions['ATT_V_additions'] += samples * self.dim
                self.actions['ATT_V_unique_head_indices'] += len(counts)
                t = self._gather_head(t, length, layer, row, counts, bool(self.ising_macro))
                self.attn_rows.append(dict(**self.coord, head=row['head'],
                                          selected_tokens=len(row['indices']),
                                          unique_V=len(counts), samples=samples,
                                          selected_blocks=row['router'].get('selected_blocks')))
            before_finalize = t
            t = self.op(t, 'sample_mean', vec=self.qheads * self.dim, nl=self.qheads)
        else:
            for row in rows:
                self.attn_rows.append(dict(**self.coord, head=row['head'],
                                          selected_tokens=len(row['indices']), samples=0,
                                          selected_blocks=row['router'].get('selected_blocks')))
            before_finalize = t
        t = self.transfer(t, 'state', self.qheads * self.dim * 2, True, 'attention_output')
        t = self.phase('finalize', before_finalize, t)
        self.pv_stage_rows.append(dict(**self.coord, context=length, samples_per_head=samples,
                                      sample_ratio=samples / length, work_peak_bytes=peak,
                                      selected_QK_tokens=selected))
        self.attn_elapsed += t - start
        self.arena = {}
        return t

    def run(self):
        result = super().run()
        end = sum(result['time_ns'].values())
        if self.ising_macro:
            macro = self.ising_macro.finish(end)
            self.energy['ATT_Ising_macro_idle'] = macro['idle_J']
            result['ising_macro_v4'] = macro
            result['metrics']['parameterized_area_mm2'] += macro['area_mm2']
        result['energy_J'] = dict(self.energy)
        result['metrics']['scenario_mJ_per_token'] = sum(self.energy.values()) / self.cfg['decode_tokens'] * 1000
        result['metrics']['area_budget_feasible'] = (
            result['metrics']['parameterized_area_mm2'] <= self.cfg['area_budget_mm2'])
        result['implementation'] = 'LLaMA MHA adapter: banked SRAM + finite scatter + proportional systematic PV / v4 Ising macro'
        result['llama_attention'] = dict(
            mode=self.ac['mode'], selector='max4; fixed bias/temperature; no model-specific calibration',
            candidate_sharing='MHA: each head owns a distinct K/V tensor; no cross-head union amplification',
            summary_boundary='prefill covers L-1 keys; newest-key summary update charged on every decode, including first',
            budget_rows=self.pv_stage_rows, tiles=self.pv_tiles,
            phase_ms_per_token={k: v / 1e6 / self.cfg['decode_tokens'] for k, v in self.pv_phases.items()},
            ising_rows=self.ising_rows,
            limitations=['conservative serial tiles; no optimal-schedule claim',
                         'digital, PRNG, routing and Ising macro coefficients remain uncharacterized',
                         'numerical trace/oracle drives addresses only; not a new PPL or physical Ising validation',
                         'systematic PV is not the S2ANTA CUDA prop kernel'])
        result['attention_v3']['mapping'] = result['implementation']
        result['attention_v3']['ising'] = 'fully provisioned v4 module; internal RNG counted within macro only; online single-index readout'
        result['attention_v3']['limitations'] = result['llama_attention']['limitations']
        result['source_hashes']['llama7b/attention_adapter.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        return result


class LlamaLocalDecode(LlamaAttentionMixin, BankedLocalDecode):
    pass


class LlamaDigitalDecode(LlamaAttentionMixin, BankedDigitalDecode):
    pass
