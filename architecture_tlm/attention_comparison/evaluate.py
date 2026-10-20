"""Conditional blocking full-Attention TLM; no model inference or physical PPA.

Reuse current router, GQA unions, Ising service and V gather algorithm. The
bounded DMA batches share one link; pending32 does not implement PV-v6 union
broadcast or overlap different gather descriptors. All non-SRAM PPA is a proxy.
"""
import argparse
import copy
import csv
import hashlib
import itertools
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
from attention_tlm_v3 import AttentionDigitalDecode
from screen_ising_tlm_v4 import ScreenIsingDigital
from system_decode import External

DEFAULT_BATCH = Path(__file__).with_name('comparison_config.json')
DEPENDENCIES = [
    'attention_comparison/evaluate.py', 'attention_comparison/test_evaluate.py',
    'attention_comparison/comparison_config.json',
    'attention_tlm_v3.py', 'attention_reference_v3.py', 'screen_ising_tlm_v4.py',
    'ising_macro_v4.py', 'system_decode.py', 'system_decode_local_shared_v2.py',
    'rng_local_shared_v2.py', 'rng_hierarchy.py', 'dramsys_backend.py',
    'configs/system_decode_default.json', 'configs/model_config.json',
    'configs/attention_v3.json', 'configs/screen_ising_v4.json',
    'configs/rng_hierarchy_v1.json', 'configs/attention_max4_c2048.json',
    'configs/attention_max4_c8192.json',
    'results/sram_calibration_v1_20261016/exact_macro_table.csv']
SCOPE = '24-layer Qwen2.5-0.5B B1 decode: normalized-input QKV, bias/RoPE, KV append, QK/normalization/V, Wo; excludes RMSNorm/residual/FFN/lm_head/prefill'


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical_case(case):
    case = dict(case)
    if case['mode'] == 'digital_dense':
        case['selection'] = 'none'
    elif case['mode'] == 'screen_exact':
        case['selection'] = 'variable'
    return case


class BatchExternal(External):
    """One blocking descriptor, finite in-flight64B bursts, batch drain barrier."""
    def __init__(self, cfg, energy, traffic, layout, pending):
        super().__init__(cfg, energy, traffic)
        self.layout, self.pending = layout, pending
        self.batch_count = self.burst_count = 0
        self.latency_sum_ns = self.barrier_ns = self.wire_ns = 0.

    def access(self, ready, size, kind, write, address=None):
        if address is None or address < 0 or size <= 0:
            raise ValueError('actual positive addressed DMA required')
        first, last = address // 64, math.ceil((address + size) / 64)
        return self.access_bursts(ready, [i * 64 for i in range(first, last)], kind, write, size)

    def access_bursts(self, ready, addresses, kind, write, logical):
        addresses = sorted(set(addresses))
        if any(a < 0 or a % 64 for a in addresses):
            raise ValueError('64-byte aligned physical bursts required')
        direction = 'write' if write else 'read'
        self.traffic[f'external_{kind}_{direction}_logical_bytes'] += logical
        self.traffic[f'external_{kind}_{direction}_burst_bytes'] += len(addresses) * 64
        self.traffic[f'external_{kind}_{direction}_requests'] += 1
        self.energy['external_' + kind] += len(addresses) * 64 * self.cfg[direction + '_pJ_per_byte'] * 1e-12
        t = ready
        for start in range(0, len(addresses), self.pending):
            batch = addresses[start:start + self.pending]
            done = t
            for _ in batch:
                # The wire is occupied only by bytes, while requests remain in flight.
                self.link.free = max(t, self.link.free) + 64 / self.link.rate
                done = max(done, self.link.free + self.link.latency)
            t = done
            self.batch_count += 1
            self.barrier_ns += self.link.latency
        self.burst_count += len(addresses)
        self.latency_sum_ns += len(addresses) * self.link.latency
        self.wire_ns += len(addresses) * 64 / self.link.rate
        return t


def sram_spec():
    with (ROOT / DEPENDENCIES[-1]).open(encoding='utf-8-sig', newline='') as f:
        row = next(r for r in csv.DictReader(f) if r['id'] == 'E' and r['corner'] == 'SS')
    return {k: v if k in ('id', 'corner') else float(v) for k, v in row.items()}


class ModuleMixin:
    def prepare(self, case, spec):
        self.case, self.spec = case, spec
        self.ext = BatchExternal(self.cfg['external_memory'], self.energy, self.traffic,
                                 self.ext.layout, case['max_pending'])
        self.stage = 'initialization'
        self.phases, self.event_counts, self.event_ns = [], defaultdict(int), defaultdict(float)
        self.SRAM_read_words = self.SRAM_write_words = 0
        self.sample_index_digest = hashlib.sha256()
        if hasattr(self, 'macro'):
            request = self.macro.request
            def audited_request(*args, **kwargs):
                # Four4B indices pack into a16B host word. For period>=1ns
                # every word drains before the next fills; final flush is1ns.
                kwargs['output_ns_per_index'] = 1.0
                ids, service = request(*args, **kwargs)
                self.sample_index_digest.update(json.dumps(ids, separators=(',', ':')).encode() + b'\n')
                return ids, service
            self.macro.request = audited_request

    def op(self, t, name, mac=0, vec=0, nl=0):
        t = super().op(t, name, mac=mac, vec=vec, nl=nl)
        if name == 'PV' and mac:
            # Separate price, even though both placeholder coefficients are2pJ.
            self.energy['ATT_MAC'] -= mac * self.cfg['digital']['mac_pJ'] * 1e-12
            self.energy['ATT_PV_FP32_proxy'] += mac * self.cfg['digital']['FP32_PV_proxy_pJ'] * 1e-12
        return t

    def record(self, name, start, end, **fields):
        if hasattr(self, 'event_counts'):
            self.event_counts[name] += 1
            self.event_ns[name] += end - start
            if name == 'Ising_output_stream':
                words = math.ceil(fields['write_bytes'] / 16)
                self.SRAM_write_words += words
                # Old adapter charges logical bytes; pay a complete tail word.
                tail_words = words - fields['write_bytes'] / 16
                self.energy['ATT_scratch'] += tail_words * self.spec['write_internal_pJ'] * 1e-12
        return super().record(name, start, end, **fields)

    def scratch(self, t, read=0, write=0, kind='buffer'):
        if min(read, write) < 0:
            raise ValueError('negative SRAM transaction')
        rd, wr = math.ceil(read / 16), math.ceil(write / 16)
        start = max(t, self.attn_port.free)
        end = self.attn_port.transfer(t, (rd + wr) * 16) if rd + wr else t
        self.SRAM_read_words += rd
        self.SRAM_write_words += wr
        self.energy['ATT_scratch'] += (rd * self.spec['read_internal_pJ'] + wr * self.spec['write_internal_pJ']) * 1e-12
        self.traffic['attention_scratch_read_bytes'] += read
        self.traffic['attention_scratch_write_bytes'] += write
        return self.record('scratch_' + kind, start, end, read_bytes=read, write_bytes=write, resource='shared_SRAM')

    def ranges(self, t, ranges, kind):
        lines = set()
        for address, size in ranges:
            lines.update(range(address // 64, math.ceil((address + size) / 64)))
        useful = sum(n for _, n in ranges)
        self.traffic['attention_' + kind + '_useful_bytes'] += useful
        self.traffic['attention_' + kind + '_physical_bytes'] += len(lines) * 64
        start = t
        if lines:
            t = self.ext.access_bursts(t, [line * 64 for line in lines], 'ATT_' + kind, False, useful)
        return self.record('DRAM_' + kind, start, t, bytes=len(lines) * 64, resource='external_memory')

    def summary(self, t, length, layer):
        # Same summary algebra/layout as AttentionMixin.summary, with explicit
        # SRAM staging added around DMA and the first warm token update fixed.
        blocks = math.ceil(length / 64)
        size = self.kheads * blocks * 4 * self.dim * 4
        name = f'L{layer}/summary'
        new = layer not in self.summary_built
        if new and self.case['summary'] == 'cold':
            for offset in range(0, length, self.ac['kv_tile_tokens']):
                indices = range(offset, min(length, offset + self.ac['kv_tile_tokens']))
                ranges = [(self.kv_address(layer, i, head), self.vecbytes)
                          for i in indices for head in range(self.kheads)]
                t = self.ranges(t, ranges, 'summary_build_K')
                n = len(ranges) * self.dim
                t = self.scratch(t, write=n * 2, kind='summary_input_fill')
                t = self.scratch(t, read=n * 2, kind='summary_input_operand')
                t = self.op(t, 'summary_build', vec=n)
            t = self.scratch(t, write=size, kind='summary_build_result')
            t = self.scratch(t, read=size, kind='summary_build_writeback')
            start = t
            t = self.ext.access(t, size, 'ATT_summary', True, self.ext.layout.address(name, 0, size))
            self.record('DRAM_summary_initial_write', start, t, resource='external_memory')
        else:
            offset = (((length - 1) // 64) * 4 + ((length - 1) % 64) // 16) * self.kheads * self.dim * 4
            n = self.kheads * self.dim * 4
            address = self.ext.layout.address(name, offset, n)
            if (length - 1) % 16:
                t = self.ranges(t, [(address, n)], 'summary_update')
                t = self.scratch(t, write=n, kind='summary_old_sum_fill')
                t = self.scratch(t, read=n, kind='summary_old_sum_operand')
            t = self.scratch(t, read=self.kheads * self.dim * 2, kind='summary_new_K_operand')
            t = self.op(t, 'summary_update', vec=self.kheads * self.dim)
            t = self.scratch(t, write=n, kind='summary_update_result')
            t = self.scratch(t, read=n, kind='summary_update_writeback')
            start = t
            t = self.ext.access(t, n, 'ATT_summary', True, address)
            self.record('DRAM_summary_update_write', start, t, resource='external_memory')
        self.summary_built.add(layer)
        t = self.ranges(t, [(self.ext.layout.address(name, 0, size), size)], 'summary_read')
        t = self.scratch(t, write=size, kind='summary_fill')
        t = self.scratch(t, read=size, kind='summary_operand')
        t = self.op(t, 'summary_means', vec=self.kheads * math.ceil(length / 16) * self.dim,
                    nl=math.ceil(length / 16))
        return t, size

    def digital_matrix(self, name, inp, out, ready, bytes_per_weight=2):
        if bytes_per_weight != 2:
            raise ValueError('common QKV/Wo projections are BF16 weights')
        t = self.scratch(ready, read=inp * 2, kind='projection_input')
        total = inp * out * 2
        for offset in range(0, total, 32768):
            size = min(32768, total - offset)
            address = self.ext.layout.address(name, offset, size)
            t = self.ext.access(t, size, 'projection_weights', False, address)
            t = self.scratch(t, write=size, kind='projection_weight_fill')
            t = self.scratch(t, read=size, kind='projection_weight_operand')
            t = self.op(t, 'projection', mac=size // 2)
        self.actions['projection_weight_bytes'] += total
        return self.scratch(t, write=out * 2, kind='projection_output')

    def phase(self, name, t, function):
        before = sum(self.energy.values())
        start = t
        self.stage = name
        t = function(t)
        self.phases.append(dict(name=name, start_ns=start, end_ns=t,
                                elapsed_ns=t - start, attributed_dynamic_J=sum(self.energy.values()) - before))
        return t

    def module_run(self):
        h = self.shape['hidden_size']
        kd = self.kheads * self.dim
        length = self.cfg['context_tokens']
        cursor = 0.
        for layer in range(self.shape['num_hidden_layers']):
            self.coord = dict(token=0, layer=layer)
            cursor = self.phase('QKV_projection', cursor, lambda t: self.digital_matrix(f'L{layer}/qkv', h, h + 2 * kd, t))
            def rope(t):
                t = self.scratch(t, read=(h + 2 * kd) * 2 + self.dim * 4,
                                 write=(h + 2 * kd) * 2, kind='QKV_bias_RoPE_interface')
                return self.op(t, 'QKV_bias_RoPE', vec=(h + 2 * kd) + 3 * (h + kd))
            cursor = self.phase('bias_RoPE', cursor, rope)
            def append(t):
                t = self.scratch(t, read=2 * kd * 2, kind='KV_append_operand')
                address = self.ext.layout.address(f'L{layer}/KV', (length - 1) * self.ext.layout.kv_token_bytes, 2 * kd * 2)
                return self.ext.access(t, 2 * kd * 2, 'KV_append', True, address)
            cursor = self.phase('KV_append', cursor, append)
            cursor = self.phase('Attention_core', cursor, lambda t: self.attention(t, length, layer))
            cursor = self.phase('Wo_projection', cursor, lambda t: self.digital_matrix(f'L{layer}/Wo', h, h, t))
        return self.finish_module(cursor)

    def finish_module(self, end):
        seconds = end * 1e-9
        root_report = None
        if self.attn_root:
            root_report = self.attn_root.finish(end)
            for name, value in root_report['energy_J'].items():
                self.energy['ATT_root_' + name] += value
        macro_report = self.macro.finish(end) if hasattr(self, 'macro') else None
        if macro_report:
            self.energy['ATT_Ising_macro_idle'] += macro_report['idle_J']
        if self.screen:
            self.energy['ATT_leaf_idle'] += (self.ac['rng_idle_W'] + self.ac['sampler_idle_W']) * seconds
        self.energy['digital_idle'] += self.cfg['digital']['idle_W'] * seconds
        self.energy['control_interconnect'] += self.cfg['control_interconnect_W'] * seconds
        self.energy['external_background'] += self.cfg['external_memory']['background_W'] * seconds
        # Exact old-core live-buffer count plus explicit common interfaces;
        # projections reuse this pool only after the core has completed.
        output_padding = (16 + (-4 * self.case['samples']) % 16) if macro_report else 0
        peak = max(self.attn_work_peak + 8192 + output_padding, 32768 + 8192)
        groups = math.ceil(peak / 65536)
        macros = groups * 16
        capacity = groups * 65536
        self.energy['SRAM_CEoff_leakage'] += macros * self.spec['ce_off_leakage_W'] * seconds
        area = macros * self.spec['area_mm2'] + self.cfg['digital']['area_mm2']
        if self.screen:
            area += self.ac['rng_area_mm2'] + self.ac['sampler_area_mm2']
        if root_report:
            area += root_report['area_mm2']
        if macro_report:
            area += macro_report['area_mm2']
        core_ns = sum(p['elapsed_ns'] for p in self.phases if p['name'] == 'Attention_core')
        total = sum(self.energy.values())
        phases = []
        for name in dict.fromkeys(p['name'] for p in self.phases):
            members = [p for p in self.phases if p['name'] == name]
            ns = sum(p['elapsed_ns'] for p in members)
            joules = sum(p['attributed_dynamic_J'] for p in members)
            phases.append(dict(name=name, elapsed_ms=ns / 1e6, attributed_dynamic_J=joules,
                               mean_attributed_dynamic_W=joules / (ns * 1e-9)))
        row_hash = digest(json.dumps(self.attn_rows, sort_keys=True, separators=(',', ':')).encode())
        selected = [r['selected_tokens'] for r in self.attn_rows]
        return dict(case=self.case, scope=SCOPE, layers=self.shape['num_hidden_layers'],
            timing=dict(full_module_ms=end / 1e6, Attention_core_ms=core_ns / 1e6,
                        phase_sum_ms=sum(p['elapsed_ns'] for p in self.phases) / 1e6), phases=phases,
            proxy=dict(status='UNCHARACTERIZED conditional scenario, not physical PPA',
                       energy_J=total, mean_power_W=total / seconds, area_mm2=area,
                       energy_ledger_J=dict(self.energy), unassigned_shared_idle_and_root_J=total - sum(p['attributed_dynamic_J'] for p in self.phases)),
            physical_PPA=dict(energy_J=None, area_mm2=None, power_W=None, complete=False),
            allocation=dict(peak_live_bytes=peak, original_core_peak_bytes=self.attn_work_peak,
                            output_packing_register_and_tail_bytes=output_padding,
                            allocated_bytes=capacity, E_macros=macros,
                            bank_lanes=16, capacity_macros_per_lane=groups,
                            SRAM_macro_only_area_mm2=macros * self.spec['area_mm2'],
                            note='capacity multiples do not increase bandwidth; phases reuse pool; wrapper/STA unverified'),
            known_SRAM_internal=dict(read_words=self.SRAM_read_words, write_words=self.SRAM_write_words,
                dynamic_J=(self.SRAM_read_words * self.spec['read_internal_pJ'] + self.SRAM_write_words * self.spec['write_internal_pJ']) * 1e-12,
                macro=self.spec, excludes='Q-load/wrapper/CDC/clock and undisclosed register traffic'),
            DRAM=dict(bursts=self.ext.burst_count, finite_batches=self.ext.batch_count,
                wire_ns=self.ext.wire_ns, sum_per_request_80ns=self.ext.latency_sum_ns,
                serialized_batch_barrier_ns=self.ext.barrier_ns,
                status='NEW conditional scheduling assumption, not inherited old Link behavior or measured controller',
                note='pending1 is diagnostic; primary comparisons use pending32; batch drains; no cross-gather reordering or PV-v6 union broadcast'),
            actions=dict(self.actions), traffic=dict(self.traffic), macro=macro_report,
            root_random=root_report, event_counts=dict(self.event_counts), event_elapsed_ns=dict(self.event_ns),
            workload=dict(kind=self.source.provenance, selected_min=min(selected),
                selected_max=max(selected), mean_candidates=sum(selected) / len(selected),
                logical_QK_fraction=self.actions['ATT_selected_QK_tokens'] / self.actions['ATT_possible_QK_tokens'],
                raw_rows_sha256=row_hash, raw_rows_retained=False,
                ordered_local_sample_indices_sha256=self.sample_index_digest.hexdigest() if macro_report else None),
            configuration=dict(digital=self.cfg['digital'], external=self.cfg['external_memory'],
                attention=self.ac, screen_ising=getattr(self, 'v4', None),
                SRAM_word_bytes=16, SRAM_aggregate_fabric_GBs=16,
                projection_chunk_bytes=32768, RNG_cost_status=self.cfg['rng_hierarchy']['cost_status'],
                index_output='host16B packing register,4 indices/word, tail word flushed1ns; period>=1ns; register PPA uncharacterized'),
            precision=dict(QKV_KV_output='BF16', QK_scores_probability_sum_PV='FP32 mathematical contract',
                PV_cost='2pJ/op independent uncharacterized FP32-probability-times-V proxy; not characterized BF16 FMA',
                sigmoid_exp_reciprocal='16 nonlinear ops/cycle and10pJ/op proxies; not bit-true RTL'),
            validation=dict(PPL=None, model_inference=False, silicon_measured=False,
                phase_closed=math.isclose(sum(p['elapsed_ns'] for p in self.phases), end, rel_tol=1e-12),
                no_FFN_lm_head=not any(k.startswith('sc_') for k in self.actions),
                allocated_capacity_fits=capacity >= peak),
            limitations=['old-core bulk datapath operand activity and digital1mm2/2pJ MAC/1pJ vector/10pJ nonlinear are placeholders',
                'inherited online bulk vector counts are conservative (about one extra vector/logit vs Issue36 itemized ledger); not an optimized per-operation digital circuit',
                '64pJ/DRAM byte and background power are proxies, no DRAMSys/PHY/device power model',
                'one shared16GB/s SRAM fabric, word-rounded16B transfers; no per-bank arbitration/STA/CDC physical validation',
                'Ising idealIID oracle only creates addresses; no bias quantization/mixing/correlation/PPL validation',
                'warm summary prefix build charged to prefill; this new token update and summary reads are charged',
                'RoPE coefficients assumed resident with per-layer read; generation/table area uncharacterized',
                'end-to-end denotes full Attention module only; no complete decoder TPOT claim'])


class DigitalModule(ModuleMixin, AttentionDigitalDecode):
    pass


class IsingModule(ModuleMixin, ScreenIsingDigital):
    pass


def build(case, layers=None):
    case = canonical_case(case)
    if case['mode'] not in ('digital_dense', 'screen_exact', 'screen_ising'):
        raise ValueError('unknown mode')
    if case['summary'] not in ('cold', 'warm') or case['max_pending'] not in (1, 32):
        raise ValueError('summary or pending contract')
    if not 1 <= case['context'] <= 32768 or case['samples'] < 1 or not math.isfinite(case['period']) or case['period'] < 1:
        raise ValueError('context/samples/period')
    cfg, shape = read('configs/system_decode_default.json'), read('configs/model_config.json')
    if layers is not None:
        shape['num_hidden_layers'] = layers
    cfg.update(context_tokens=case['context'], decode_tokens=1, frequency_hz=100000000, sc_engines=0)
    cfg['scratchpad'].update(capacity_MiB=2, bandwidth_GBs=16)
    cfg['digital']['FP32_PV_proxy_pJ'] = 2
    cfg['weight_macro']['cache_MiB'] = 1 / 16  # Inherited object unused; no weight-cache requests.
    cfg['external_memory'].update(bandwidth_GBs=16, latency_ns=80, burst_bytes=64)
    cfg['rng_hierarchy'] = read('configs/rng_hierarchy_v1.json')
    cfg['attention_v3'] = read('configs/attention_v3.json')
    a = cfg['attention_v3']
    a.update(mode='dense' if case['mode'] == 'digital_dense' else 'screen_exact',
             samples=case['samples'], seed=case['seed'], kv_tile_tokens=64,
             summary_initialization='prefill_prebuilt' if case['summary'] == 'warm' else 'cold_build',
             record_transactions=False)
    calibration = ROOT / f"configs/attention_max4_c{case['context']}.json"
    a['calibration_file'] = str(calibration) if calibration.exists() else None
    spec = sram_spec()
    if max(spec['read_cycle_ns'], spec['write_cycle_ns']) > 10:
        raise ValueError('E/SS period-only100MHz eligibility failed')
    cfg['scratchpad'].update(read_pJ_per_byte=spec['read_internal_pJ'] / 16,
                            write_pJ_per_byte=spec['write_internal_pJ'] / 16)
    if case['mode'] == 'screen_ising':
        v = cfg['screen_ising_v4'] = read('configs/screen_ising_v4.json')
        v.update(selection=case['selection'], samples=case['samples'],
                 candidate_capacity=case['context'] if case['selection'] == 'variable' else 512)
        v['ising']['sample_period_ns'] = case['period']
        cls = IsingModule
    else:
        cls = DigitalModule
    evidence = {'profiles': {'g1_case3': {'frequency_hz': 100000000}}}
    model = cls(cfg, 'digital_bf16', evidence, shape)
    model.prepare(case, spec)
    return model


def cases_from_config(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    cases = []
    for g in data['groups']:
        axes = itertools.product(g['contexts'], g['samples'], g['seeds'], g['periods'], g['summaries'], g['pending'])
        for context, samples, seed, period, summary, pending in axes:
            cases.append(canonical_case(dict(mode=g['mode'], context=context, samples=samples, seed=seed,
                period=period, summary=summary, max_pending=pending, selection=g.get('selection', 'fixed_budget'))))
    return cases


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['digital_dense', 'screen_exact', 'screen_ising'], default='digital_dense')
    p.add_argument('--context', type=int, default=2048)
    p.add_argument('--samples', type=int, default=128)
    p.add_argument('--period', type=float, default=100)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--summary', choices=['cold', 'warm'], default='warm')
    p.add_argument('--max-pending', type=int, choices=[1, 32], default=1)
    p.add_argument('--selection', choices=['fixed_budget', 'variable'], default='fixed_budget')
    p.add_argument('--batch-config', type=Path)
    p.add_argument('--source-commit', help='40hex execution source revision, required for extracted snapshot without.git')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('choose a new output directory; existing results preserved')
    config = args.batch_config
    cases = cases_from_config(config) if config else [{key: getattr(args, key) for key in
        ('mode', 'context', 'samples', 'period', 'seed', 'summary', 'max_pending', 'selection')}]
    source = {name: digest((ROOT / name).read_bytes()) for name in DEPENDENCIES}
    commit = args.source_commit
    if commit is None and (REPO / '.git').exists():
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    if commit is None or len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('provide exact40hex --source-commit for a frozen server snapshot')
    args.output.mkdir(parents=True)
    provenance = dict(source_commit=commit, source_sha256=source,
                      config_sha256=digest(config.read_bytes()) if config else None,
                      command=sys.argv, runtime='Python standard library, CPU conditional TLM')
    (args.output / 'SOURCE_MANIFEST.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    rows = []
    for i, case in enumerate(cases):
        case = canonical_case(case)
        result = build(case).module_run()
        result['provenance'] = provenance
        result['case_sha256'] = digest(json.dumps(case, sort_keys=True).encode())
        filename = f'case_{i:03d}.json'
        (args.output / filename).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        row = dict(file=filename, **case, **result['timing'],
                   comparison_role='pending1_queue_diagnostic' if case['max_pending'] == 1 else 'primary_pending32_conditional',
                   proxy_mJ=result['proxy']['energy_J'] * 1000,
                   proxy_mean_W=result['proxy']['mean_power_W'],
                   proxy_area_mm2=result['proxy']['area_mm2'],
                   allocated_SRAM_KiB=result['allocation']['allocated_bytes'] / 1024,
                   logical_QK_fraction=result['workload']['logical_QK_fraction'],
                   physical_PPA_complete=False, PPL=None)
        rows.append(row)
        print(json.dumps(row), flush=True)
    with (args.output / 'summary.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
