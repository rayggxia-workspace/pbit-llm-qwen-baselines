"""Blocked systematic PV, GQA-union reads, proportional context budgets.

Inspired by S2ANTA (2605.01910v2), NOT a reproduction of its CUDA kernels.
Uses a single global systematic phase per head, preserving exact S and the
unbiased systematic estimator. Tile budgets come from that global phase;
they do NOT use the paper prop kernel's largest-remainder integer allocation.
All timing/energy coefficients outside calibrated SRAM remain scenarios.
"""
import bisect
from collections import Counter, defaultdict
import hashlib
import math
import heapq
from functools import lru_cache
from pathlib import Path
from attention_reference_v3 import softmax, cdf
from memory_schedule_v5 import BankedLocalDecode, BankedDigitalDecode
from scatter_memory_v6 import coalesced_bursts, link_access_ranges


def context_samples(length, cfg):
    if length < 1:
        raise ValueError('empty context')
    if cfg.get('fixed_samples') is not None:
        samples = cfg['fixed_samples']
        if not isinstance(samples, int) or samples < 1:
            raise ValueError('invalid fixed sample budget')
        return samples
    raw = length * cfg['sample_ratio']
    if raw <= 0:
        raise ValueError('invalid sample ratio')
    return max(cfg['minimum_samples'], min(cfg['maximum_samples'],
               2 ** math.floor(math.log2(raw))))


def systematic_counts(probabilities, samples, offset):
    """Reference only: count the ordered thresholds (m+offset)/S.

    The timed hardware performs a block prefix/count scan; Python bisect here
    is not charged as, or claimed to implement, binary-search hardware.
    """
    if samples < 1 or not 0 <= offset < 1:
        raise ValueError('invalid systematic sampler')
    cumulative = cdf(probabilities)
    return Counter(bisect.bisect_right(cumulative, (i + offset) / samples)
                   for i in range(samples))


@lru_cache(maxsize=128)
def prefix_schedule(n, heads, lanes):
    """List-schedule independent Brent-Kung scans on a FIXED ALU lane budget.

    Two pre-scale operations and phase-add/floor/count-difference are charged
    per input. All dependencies are explicit. Interleave heads to use idle ALU
    lanes during the narrower tree levels; no separate prefix ASIC is assumed.
    """
    dependencies = []
    def node(*parents):
        identity = len(dependencies)
        dependencies.append([p for p in parents if p is not None])
        return identity
    def add(left, right):
        if left is None:
            return right
        if right is None:
            return left
        return node(left, right)
    padded = 2 ** math.ceil(math.log2(max(1, n)))
    for _ in range(heads):
        values = [node(node()) for i in range(n)] + [None] * (padded - n)
        stride = 1
        while stride < padded:
            for i in range(2 * stride - 1, padded, 2 * stride):
                values[i] = add(values[i - stride], values[i])
            stride *= 2
        stride = padded // 4
        while stride:
            for i in range(3 * stride - 1, padded, 2 * stride):
                values[i] = add(values[i - stride], values[i])
            stride //= 2
        floors = [node(node(values[i])) for i in range(n)]
        for i, value in enumerate(floors):
            node(value, floors[i - 1] if i else None)
    children = [[] for _ in dependencies]
    for i, parents in enumerate(dependencies):
        for parent in parents:
            children[parent].append(i)
    priority = [1] * len(dependencies)
    for i in reversed(range(len(dependencies))):
        if children[i]:
            priority[i] += max(priority[child] for child in children[i])
    pending = [len(parents) for parents in dependencies]
    ready = [(-priority[i], i) for i, degree in enumerate(pending) if not degree]
    heapq.heapify(ready)
    cycles = completed = 0
    while ready:
        issued = [heapq.heappop(ready)[1] for _ in range(min(lanes, len(ready)))]
        completed += len(issued)
        cycles += 1
        for i in issued:
            for child in children[i]:
                pending[child] -= 1
                if not pending[child]:
                    heapq.heappush(ready, (-priority[child], child))
    assert completed == len(dependencies)
    return cycles, completed


class StreamPVMixin:
    def __init__(self, cfg, *args, **kwargs):
        super().__init__(cfg, *args, **kwargs)
        self.pc = cfg['pv_stream_v6']
        if self.ac['mode'] not in ('dense', 'pv'):
            raise ValueError('v6 currently implements dense and PV; screening/Ising unchanged in v5')
        if self.cfg['external_memory'].get('backend') != 'dramsys' and self.ext.cfg['burst_bytes'] != 64:
            raise ValueError('use equal 64B bursts for v6 dense and PV')
        self.pv_phases = defaultdict(float)
        self.pv_tiles = []
        self.pv_stage_rows = []

    def ranges(self, t, ranges, kind):
        if not ranges:
            return t
        spans = coalesced_bursts(ranges)
        physical = sum(n for _, n in spans)
        self.traffic['attention_' + kind + '_useful_bytes'] += sum(n for _, n in ranges)
        self.traffic['attention_' + kind + '_physical_bytes'] += physical
        start = t
        # One bounded tile descriptor. The backend issues up to 32 real bursts
        # concurrently, instead of draining at every disjoint address run.
        if len(spans) > self.pc['max_spans_per_descriptor']:
            raise ValueError('scatter descriptor exceeds provisioned span buffer')
        if 'descriptors' in self.arena:
            t = self.transfer(t, 'descriptors', len(spans) * 16, True, 'SG_descriptors')
            t = self.transfer(t, 'descriptors', len(spans) * 16, False, 'SG_descriptor_read')
        else:
            # Dense uses the existing state region's 8KiB controller allowance.
            base, capacity = self.arena['state']
            address = base + self.qheads * self.dim * 4
            size = len(spans) * 16
            if address + size > base + capacity:
                raise ValueError('dense descriptor workspace overflow')
            t = self.work_mem.transfer(t, address, size, True, 'SG_descriptors')
            t = self.work_mem.transfer(t, address, size, False, 'SG_descriptor_read')
            self.traffic['attention_scratch_write_bytes'] += size
            self.traffic['attention_scratch_read_bytes'] += size
        t = self.op(t, 'SG_control', vec=len(spans))
        if hasattr(self.ext, 'access_ranges'):
            t = self.ext.access_ranges(t, spans, 'ATT_' + kind)
        else:
            t = link_access_ranges(self.ext, t, spans, 'ATT_' + kind,
                                   pending=self.pc['dma_pending_bursts'],
                                   issue_ns=self.pc['dma_issue_ns'])
        return self.record('DRAM_scatter_' + kind, start, t, bytes=physical,
                           ranges=len(spans), resource='external_memory')

    def transfer(self, t, region, size, write, tag, offset=0):
        base, capacity = self.arena[region]
        if offset + size > capacity:
            raise ValueError('v6 bounded scratch region overflow: ' + region)
        if not size:
            return t
        t = self.work_mem.transfer(t, base + offset, size, write, tag)
        self.traffic['attention_scratch_' + ('write' if write else 'read') + '_bytes'] += size
        return t

    def phase(self, name, start, end):
        self.pv_phases[name] += end - start
        return end

    def prefix_scan(self, t, name, n, heads=1):
        lanes = self.cfg['digital']['vector_ops_per_cycle']
        cycles, operations = prefix_schedule(n, heads, lanes)
        t = self.op(t, name, vec=operations)
        extra = cycles - math.ceil(operations / lanes)
        t += extra * self.period
        self.digital_free = t
        self.actions['ATT_prefix_dependency_cycles'] += extra
        return t

    def attention(self, ready, length, layer):
        if self.ac['mode'] == 'dense':
            return super().attention(ready, length, layer)
        if max(self.weights.slot_free) > ready + 1e-5:
            raise ValueError('weight staging has not released shared SRAM')
        self.attention_length = length
        token = self.attn_calls[layer]
        self.attn_calls[layer] += 1
        self.coord = dict(token=token, layer=layer)
        block = self.ac['kv_tile_tokens']
        tiles = math.ceil(length / block)
        samples = context_samples(length, self.pc)
        if samples > 65535:
            raise ValueError('16-bit sample count overflow')
        # Disjoint regions, finite count/V buffers. No uniform-word SRAM.
        sizes = [('state', self.qheads * self.dim * 4 + 8192),
                 ('KV', 2 * block * self.kheads * self.vecbytes),
                 ('scores', self.qheads * length * 4),
                 ('stats', self.qheads * tiles * 16),
                 ('counts', self.group * block * 2 + block * 4 + 64),
                 ('V', block * self.vecbytes),
                 ('descriptors', self.pc['max_spans_per_descriptor'] * 16 +
                  self.pc['dma_pending_bursts'] * 16)]
        self.arena = {}
        cursor = 0
        for name, size in sizes:
            cursor = math.ceil(cursor / 64) * 64
            self.arena[name] = (cursor, size)
            cursor += size
        self.attn_peak = max(self.attn_peak, cursor)
        self.attn_work_peak = max(self.attn_work_peak, cursor)
        if cursor > self.work_mem.capacity:
            raise ValueError('v6 working set exceeds SRAM')
        start = ready
        t = ready
        counts = []
        # Numerical fixture/oracle, not additional hardware dense computation.
        for head in range(self.qheads):
            probabilities = softmax(self.source.logits(token, layer, head, length))
            offset = self.source.random(token, layer, head, 'pv_v6_systematic').random()
            counts.append(systematic_counts(probabilities, samples, offset))
        possible = self.qheads * length
        self.actions['ATT_selected_QK_tokens'] += possible
        self.actions['ATT_possible_QK_tokens'] += possible
        # Pass 1: K only, complete QK, per-tile exponents/statistics, no V prefetch.
        before = t
        for offset in range(0, length, block):
            n = min(block, length - offset)
            spans = [(self.kv_address(layer, i, 0), self.kheads * self.vecbytes)
                     for i in range(offset, offset + n)]
            t = self.ranges(t, spans, 'K')
            size = n * self.kheads * self.vecbytes
            t = self.transfer(t, 'KV', size, True, 'K_tile_fill')
            t = self.transfer(t, 'KV', size, False, 'K_tile_operand')
            amount = n * self.qheads
            t = self.op(t, 'QK', mac=amount * self.dim, vec=amount)
            t = self.op(t, 'tile_softmax_stats', vec=3 * amount + 3 * self.qheads,
                        nl=amount + self.qheads)
            t = self.transfer(t, 'scores', amount * 4, True, 'score_stash',
                              offset=offset * self.qheads * 4)
            t = self.transfer(t, 'stats', self.qheads * 16, True, 'tile_stats',
                              offset=(offset // block) * self.qheads * 16)
        t = self.phase('score_and_tile_stats', before, t)
        # Global tile mass scan yields exact integer budgets from each head's
        # single systematic phase. Counts sum to S, not rounded S per tile.
        before = t
        t = self.transfer(t, 'stats', self.qheads * tiles * 16, False, 'budget_stats')
        t = self.op(t, 'tile_mass_rescale', vec=3 * self.qheads * tiles,
                    nl=self.qheads * (tiles + 1))
        t = self.random_words(t, self.qheads, 'systematic_offsets')
        t = self.prefix_scan(t, 'tile_budget_prefix', tiles, heads=self.qheads)
        t = self.transfer(t, 'stats', self.qheads * tiles * 16, True, 'budgets_and_phase')
        t = self.phase('budget_and_rng', before, t)
        self.actions['ATT_V_sample_events'] += self.qheads * samples
        self.actions['ATT_V_additions'] += self.qheads * samples * self.dim
        self.actions['ATT_V_unique_head_indices'] += sum(map(len, counts))
        # Pass 2: by KV group then tile. Read each union V row once, broadcast
        # to participating heads, retain repeated additions for multiplicities.
        for kvhead in range(self.kheads):
            heads = range(kvhead * self.group, (kvhead + 1) * self.group)
            for offset in range(0, length, block):
                n = min(block, length - offset)
                per_head = [{i: c for i, c in counts[h].items() if offset <= i < offset + n}
                            for h in heads]
                live = [j for j, values in enumerate(per_head) if values]
                if not live:
                    self.actions['ATT_zero_budget_group_tiles'] += 1
                    continue
                before = t
                t = self.transfer(t, 'stats', self.group * 16, False, 'budget_read',
                                  offset=((offset // block) * self.qheads + kvhead * self.group) * 16)
                # Packed tile-major score data, grouped head-major within tile.
                t = self.transfer(t, 'scores', self.group * n * 4, False, 'score_scan',
                                  offset=offset * self.qheads * 4 + kvhead * self.group * n * 4)
                t = self.prefix_scan(t, 'systematic_count_scan', n, heads=len(live))
                # Inactive heads are masked; counts are a bounded local tile,
                # not an L-sized histogram or S random-number buffer.
                count_bytes = self.group * n * 2
                t = self.transfer(t, 'counts', count_bytes, True, 'tile_counts')
                t = self.transfer(t, 'counts', count_bytes, False, 'count_union_operand')
                union = sorted(set().union(*per_head))
                t = self.op(t, 'union_and_compact', vec=self.group * n + 2 * n)
                t = self.transfer(t, 'counts', len(union) * 4, True, 'union_indices',
                                  offset=self.group * block * 2)
                t = self.transfer(t, 'counts', len(union) * 4, False, 'union_index_read',
                                  offset=self.group * block * 2)
                t = self.phase('count_scan_and_route', before, t)
                before = t
                t = self.ranges(t, [(self.kv_address(layer, i, kvhead, True), self.vecbytes)
                                    for i in union], 'V_gather')
                t = self.phase('V_DMA', before, t)
                before = t
                t = self.transfer(t, 'V', len(union) * self.vecbytes, True, 'V_union_fill')
                t = self.transfer(t, 'V', len(union) * self.vecbytes, False, 'V_union_operand')
                self.actions['ATT_V_group_union_rows'] += len(union)
                deliveries = sum(map(len, per_head))
                self.actions['ATT_V_broadcast_deliveries'] += deliveries
                self.energy['ATT_V_broadcast'] += deliveries * self.vecbytes * self.pc['broadcast_pJ_per_byte'] * 1e-12
                # Fixed vector ALU throughput: deliberately retain v5's 64
                # additions/cycle, rather than quietly assume a faster unit.
                additions = sum(sum(values.values()) for values in per_head) * self.dim
                t = self.op(t, 'V_accumulate', vec=additions)
                t = self.phase('V_SRAM_broadcast_and_add', before, t)
                self.pv_tiles.append(dict(**self.coord, kvhead=kvhead, offset=offset,
                                          rows=n, union_rows=len(union),
                                          sample_events=additions // self.dim))
        before = t
        t = self.op(t, 'sample_mean', vec=self.qheads * self.dim, nl=self.qheads)
        t = self.transfer(t, 'state', self.qheads * self.dim * 2, True, 'attention_output')
        t = self.phase('finalize', before, t)
        for head, counter in enumerate(counts):
            self.attn_rows.append(dict(**self.coord, head=head, selected_tokens=length,
                                      unique_V=len(counter), samples=samples))
        self.pv_stage_rows.append(dict(**self.coord, context=length, samples_per_head=samples,
                                      sample_ratio=samples / length, work_peak_bytes=cursor))
        self.attn_elapsed += t - start
        self.arena = {}
        return t

    def run(self):
        result = super().run()
        result['pv_stream_v6'] = dict(
            config=self.pc, budget_rows=self.pv_stage_rows,
            phase_ms_per_token={k: v / 1e6 / self.cfg['decode_tokens'] for k, v in self.pv_phases.items()},
            estimator='global systematic phase; tile counts sum exactly to S; not paper prop largest-remainder budgets',
            scatter='finite burst queue; real addresses; one descriptor per bounded tile',
            quality='synthetic logits; no new PPL claim',
            limitations=['prefix/routing are parameterized ALU work, not synthesized RTL',
                         'serial tile stages retained; no free all-tile concurrency or ideal DMA/compute overlap',
                         'PRNG precision, accumulation order and real-Qwen quality need separate validation'])
        result['implementation'] = 'v6 blocked systematic PV + GQA union + bounded scatter; inherited full FFN'
        result['attention_v3']['mapping'] = 'v6 tiled systematic/GQA union' if self.ac['mode'] == 'pv' else 'dense GQA with same scatter backend'
        result['memory_v5']['limitations'] = [
            'SRAM blocking descriptors retained; CDC paid once per bulk transaction',
            'digital/RNG/routing costs provisional; SRAM calibrated; synthetic attention',
            'one systematic offset/head, not buffered uniform arrays',
            'SC resident-weight interface unchanged; not newly validated hardware']
        for name in ('pv_stream_v6.py', 'scatter_memory_v6.py'):
            result['source_hashes'][name] = hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
        return result


class StreamPVDecode(StreamPVMixin, BankedLocalDecode):
    pass


class StreamDigitalDecode(StreamPVMixin, BankedDigitalDecode):
    pass
