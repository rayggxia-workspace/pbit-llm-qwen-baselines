"""Analytical work/traffic ledger, NOT measured hardware or cycle-accurate TLM.

The arithmetic schedule is an assumed serialized mapping. Resource lower bounds
are reported separately. Missing compute/IO/wrapper costs forbid full PPA totals.
"""
import argparse
import copy
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).with_name('reference_config.json')
PINNED_MODEL = dict(layers=24, hidden=896, query_heads=14, kv_heads=2, head_dim=64, batch=1)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(config_path=DEFAULT_CONFIG):
    path = Path(config_path)
    cfg = json.loads(path.read_text(encoding='utf-8'))
    return cfg


def macro(cfg, root=ROOT):
    path = Path(root) / cfg['sources']['sram_table']
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    row = next(r for r in rows if (r['id'], r['corner']) ==
               (cfg['memory']['sram_macro_id'], cfg['memory']['corner']))
    return {key: value if key in ('id', 'corner') else float(value)
            for key, value in row.items()}, sha(path)


def validate(cfg, spec):
    if cfg['model'] != PINNED_MODEL:
        raise ValueError('reference is pinned to batch1 Qwen2.5-0.5B Base')
    c, m = cfg['compute'], cfg['memory']
    if m['weights_resident']:
        raise ValueError('resident weights need approved capacity/placement; streaming reference only')
    for key in ('clock_hz', 'abstract_mac_slots_per_cycle', 'vector_ops_per_cycle',
                'exp_ops_per_cycle', 'reciprocal_ops_per_cycle', 'physical_head_slots_per_group'):
        if not isinstance(c[key], int) or isinstance(c[key], bool) or c[key] < 1:
            raise ValueError('positive integer compute parameter: ' + key)
    for key in ('sram_clock_hz', 'lanes', 'macros_per_lane', 'stripe_bytes', 'projection_staging_bytes', 'extra_work_bytes'):
        if not isinstance(m[key], int) or isinstance(m[key], bool) or m[key] < 1:
            raise ValueError('positive integer memory parameter: ' + key)
    for key in ('fabric_GBs', 'DDR_peak_GBs', 'DRAM_service_cap_GBs'):
        if not math.isfinite(m[key]) or m[key] <= 0:
            raise ValueError('positive finite memory rate: ' + key)
    if m['DRAM_service_cap_GBs'] > m['DDR_peak_GBs']:
        raise ValueError('service cap exceeds physical peak')
    if m['stripe_bytes'] % int(spec['width'] / 8):
        raise ValueError('stripe must contain whole SRAM words')
    if max(spec['read_cycle_ns'], spec['write_cycle_ns']) > 1e9 / m['sram_clock_hz']:
        raise ValueError('SS SRAM clock violates characterized macro cycle')
    group = cfg['model']['query_heads'] // cfg['model']['kv_heads']
    if c['physical_head_slots_per_group'] < group:
        raise ValueError('physical group slots cannot be smaller than seven live Q heads')
    if not isinstance(cfg['tile_tokens'], int) or cfg['tile_tokens'] < 1:
        raise ValueError('positive integer tile_tokens')
    for length in cfg['contexts']:
        if not isinstance(length, int) or isinstance(length, bool) or not 1 <= length <= 32768:
            raise ValueError('context outside native Qwen limit')


def evaluate(cfg, length, root=ROOT):
    """All work and bytes below are per single output token across 24 layers."""
    cfg = copy.deepcopy(cfg)
    spec, table_sha = macro(cfg, root)
    validate(cfg, spec)
    peak_source = json.loads((Path(root) / cfg['sources']['dram_provenance']).read_text(encoding='utf-8-sig'))
    if not math.isclose(cfg['memory']['DDR_peak_GBs'], peak_source['peak_bandwidth_GBs'], rel_tol=1e-12):
        raise ValueError('DDR raw peak must match the cited source-model provenance')
    if length not in cfg['contexts']:
        raise ValueError('context must be listed in config')
    s, c, m = cfg['model'], cfg['compute'], cfg['memory']
    layers, h, q, kv, d = (s[k] for k in ('layers', 'hidden', 'query_heads', 'kv_heads', 'head_dim'))
    group = q // kv
    tile = min(cfg['tile_tokens'], length)
    sizes = [min(tile, length - offset) for offset in range(0, length, tile)]
    tiles = len(sizes)
    capacity = int(spec['capacity_bytes']) * m['lanes'] * m['macros_per_lane']
    # Process one KV group (seven live Q heads) at a time; pool reused by projections.
    working = dict(KV_pingpong=2 * 2 * tile * d * 2,
                   Q_BF16=group * d * 2, O_FP32=group * d * 4,
                   max_and_sum_FP32=group * 2 * 4, score_FP32=group * tile * 4,
                   extra=m['extra_work_bytes'])
    live = sum(working.values())
    if max(live, m['projection_staging_bytes'] + m['extra_work_bytes']) > capacity:
        raise ValueError('working set/projection staging exceeds allocated SRAM')
    qk = layers * q * d * length
    pv = qk
    proj_qkv = layers * h * (h + 2 * kv * d)
    proj_o = layers * h * h
    projection = proj_qkv + proj_o
    kv_bytes = layers * length * kv * d * 2 * 2
    weight_bytes = projection * 2
    append = layers * kv * d * 2 * 2
    # Explicit algorithmic operations. First-tile merge/alpha is conservatively
    # charged rather than silently optimized; comparisons count as vector ops.
    vectors = dict(QK_scale=q * length, tile_max=q * (length - tiles),
                   shifted_logit=q * length, exp_sum=q * (length - tiles),
                   running_max=q * tiles, alpha_shift=q * tiles,
                   denominator_rescale=q * tiles, denominator_merge=q * tiles,
                   accumulator_rescale=q * d * tiles,
                   accumulator_merge=q * d * tiles, final_normalize=q * d)
    vectors = {key: value * layers for key, value in vectors.items()}
    exp_count = layers * q * (length + tiles)
    reciprocal = layers * q
    projection_vectors = layers * ((h + 2 * kv * d) + 3 * (h + kv * d))
    period = 1e9 / c['clock_hz']
    mac_rate = c['abstract_mac_slots_per_cycle']

    def core_schedule(head_slots):
        cycles = 0
        for n in sizes:
            # Actual vector/exp rows stay seven. Padding only affects MAC issue.
            per_group_vec = group * (4 * n + 2 * d + 2)
            cycles += kv * (2 * math.ceil(head_slots * d * n / mac_rate)
                            + math.ceil(per_group_vec / c['vector_ops_per_cycle'])
                            + math.ceil(group * (n + 1) / c['exp_ops_per_cycle']))
        cycles += kv * (math.ceil(group * d / c['vector_ops_per_cycle'])
                        + math.ceil(group / c['reciprocal_ops_per_cycle']))
        return cycles * layers * period

    proj_cycles = layers * (math.ceil(h * (h + 2 * kv * d) / mac_rate)
                            + math.ceil(h * h / mac_rate)
                            + math.ceil(projection_vectors / layers / c['vector_ops_per_cycle']))
    # Known streaming subset only: each DRAM-delivered weight/KV byte written
    # then read once locally. Register/control/partial-operand traffic unclosed.
    streaming = kv_bytes + weight_bytes
    word = int(spec['width'] / 8)
    read_words = math.ceil(kv_bytes / word) + math.ceil(weight_bytes / word)
    write_words = read_words
    sram_rate = min(m['fabric_GBs'], m['lanes'] * word * m['sram_clock_hz'] / 1e9)
    total_mac = qk + pv + projection
    lower = dict(MAC_work_at_assumed_peak=total_mac / mac_rate * period,
                 EXP_work_at_assumed_peak=exp_count / c['exp_ops_per_cycle'] * period,
                 reciprocal_work_at_assumed_peak=reciprocal / c['reciprocal_ops_per_cycle'] * period,
                 vector_work_at_assumed_peak=(sum(vectors.values()) + projection_vectors) / c['vector_ops_per_cycle'] * period,
                 DRAM_bytes_at_raw_peak=(streaming + append) / m['DDR_peak_GBs'],
                 DRAM_bytes_at_assumed_service_cap=(streaming + append) / m['DRAM_service_cap_GBs'],
                 known_SRAM_streaming_at_port_fabric_cap=2 * streaming / sram_rate)
    full_kv_macros = math.ceil(kv_bytes / 65536)
    with (Path(root) / cfg['sources']['sram_table']).open(encoding='utf-8-sig', newline='') as stream:
        f = next(row for row in csv.DictReader(stream) if row['id'] == 'F' and row['corner'] == m['corner'])
    missing = dict(QK_MAC='pJ/op and mm2 for BF16 multiply / FP32 accumulate',
                   PV_MAC='pJ/op and mm2 for FP32 probability times BF16-extended V / FP32 accumulate',
                   projection_MAC='pJ/op and mm2 for BF16 multiply / FP32 accumulate',
                   vector='pJ/op; FP32 max/add/mul/conversion resource area',
                   EXP='pJ/op and mm2 for selected finite-wordlength exp',
                   reciprocal='pJ/op and mm2 for shared finite-wordlength reciprocal',
                   registers='FP32 accumulators/state/Q reuse/operand distribution energy and area',
                   SRAM_wrapper='mux/output loads/CDC/clock/control/extra operand accesses',
                   DMA_DRAM='descriptor/control/DRAM device+PHY+IO energy and area',
                   RoPE='coefficient generation/table access and exact finite-format behavior')
    return dict(context=length, scope=cfg['scope'], model=s, precision=cfg['precision'],
                work=dict(QK_MAC=qk, PV_MAC=pv, core_MAC=qk + pv,
                          QKV_projection_MAC=proj_qkv, O_projection_MAC=proj_o,
                          projection_MAC=projection, full_Attention_MAC=total_mac,
                          core_vector_ops=vectors, projection_RoPE_bias_vector_ops=projection_vectors,
                          exp_ops=exp_count, reciprocal_ops=reciprocal),
                traffic_bytes=dict(KV_read=kv_bytes, projection_weight_read=weight_bytes,
                                   KV_append_write=append, probability_DRAM=0,
                                   known_SRAM_streaming_read=streaming,
                                   known_SRAM_streaming_write=streaming),
                allocation=dict(policy='one GQA group serially, projection/Attention phase reuse',
                                allocated_bytes=capacity, working_set=working,
                                extra_reservation=dict(QKV_retention_BF16=2304,
                                    completed_group_output_BF16=896, Wo_partial_FP32=3584,
                                    remaining_control_RoPE_alignment=1408,
                                    note='8KiB reservation, phase peaks do not all overlap; operand schedule is not RTL validated'),
                                peak_live_bytes=live, macros=m['lanes'] * m['macros_per_lane'],
                                SRAM_only_area_mm2=m['lanes'] * m['macros_per_lane'] * spec['area_mm2'],
                                SRAM_CEoff_leakage_W=m['lanes'] * m['macros_per_lane'] * spec['ce_off_leakage_W'],
                                timing_status='macro period-only eligibility check; no integrated wrapper/clock/STA verification',
                                full_KV_residency_counterfactual=dict(bytes=kv_bytes, F_macros=full_kv_macros,
                                    F_macro_only_area_mm2=full_kv_macros * float(f['area_mm2']),
                                    allocated=False, excludes='wrapper/mux/CDC/CTS; requires independent timing/placement')),
                timing=dict(resource_lower_bounds_ns=lower, max_resource_lower_bound_ns=max(lower.values()),
                            serialized_compute_only_no_padding_ns=core_schedule(group) + proj_cycles * period,
                            serialized_compute_only_padded_ns=core_schedule(c['physical_head_slots_per_group']) + proj_cycles * period,
                            achieved_latency_ns=None, warning='rate/serialization assumptions only; no memory+compute schedule, pipeline or STA validation'),
                known_SRAM_internal_subset=dict(read_words=read_words, write_words=write_words,
                    read_J=read_words * spec['read_internal_pJ'] * 1e-12,
                    write_J=write_words * spec['write_internal_pJ'] * 1e-12,
                    component_internal_J=dict(KV_fill=kv_bytes / word * spec['write_internal_pJ'] * 1e-12,
                        KV_operand=kv_bytes / word * spec['read_internal_pJ'] * 1e-12,
                        projection_weight_fill=weight_bytes / word * spec['write_internal_pJ'] * 1e-12,
                        projection_weight_operand=weight_bytes / word * spec['read_internal_pJ'] * 1e-12),
                    warning='known streaming pass subset, not complete Attention energy; no wrapper/output loads/clock/extra operands'),
                totals=dict(full_energy_J=None, full_area_mm2=None, full_power_W=None, complete=False),
                missing_PPA_coefficients=missing, quality=cfg['quality'],
                source=dict(sram_table_sha256=table_sha, sram_macro=spec,
                            dram_provenance_sha256=sha(Path(root) / cfg['sources']['dram_provenance'])),
                status='analytical evaluation only; no model inference, RTL, DC/PT, GPU or silicon experiment')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('refusing to overwrite an existing output directory')
    cfg = load(args.config)
    results = [evaluate(cfg, length) for length in cfg['contexts']]
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    args.output.mkdir(parents=True)
    data = dict(config=cfg, config_sha256=sha(args.config), source_commit=commit,
                evaluator_sha256=sha(__file__), results=results)
    (args.output / 'ledger.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    fields = ('context', 'MAC', 'KV_MiB', 'weights_MiB', 'known_streaming_SRAM_J',
              'SRAM_only_area_mm2', 'max_resource_floor_ms', 'serialized_compute_assumption_ms',
              'full_energy_J', 'full_area_mm2', 'achieved_latency_ms')
    rows = []
    for r in results:
        rows.append(dict(context=r['context'], MAC=r['work']['full_Attention_MAC'],
            KV_MiB=r['traffic_bytes']['KV_read'] / 2**20,
            weights_MiB=r['traffic_bytes']['projection_weight_read'] / 2**20,
            known_streaming_SRAM_J=r['known_SRAM_internal_subset']['read_J'] + r['known_SRAM_internal_subset']['write_J'],
            SRAM_only_area_mm2=r['allocation']['SRAM_only_area_mm2'],
            max_resource_floor_ms=r['timing']['max_resource_lower_bound_ns'] / 1e6,
            serialized_compute_assumption_ms=r['timing']['serialized_compute_only_padded_ns'] / 1e6,
            full_energy_J=None, full_area_mm2=None, achieved_latency_ms=None))
    with (args.output / 'summary.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report = ['# 数字 Attention 解析参考', '',
              '单 token decode；24 层 QKV/RoPE/KV/QK/online Softmax/PV/Wo。概率和PV累加为FP32。',
              '本程序只核对工作量、容量和资源速率边界，未运行模型、RTL、综合或功耗仿真。',
              '时间为资源下界或假设的串行计算阶段之和，不是已实现端到端延迟；两者不相加。',
              '完整能量/面积/功率为 null。SRAM面积和内部流式读写能量仅为有来源的局部项。', '',
              '| L | 完整Attention MAC | KV MiB | 投影权重MiB | 最大资源下界ms |',
              '|---:|---:|---:|---:|---:|']
    for row in rows:
        report.append(f"| {row['context']} | {row['MAC']} | {row['KV_MiB']:.3f} | {row['weights_MiB']:.3f} | {row['max_resource_floor_ms']:.6f} |")
    report += ['', '既有BF16 PPL仅为原始SDPA质量锚点，不代表此有限字长数字架构已经过PPL验证。',
               'ledger.json逐项列出精度、算法操作、宏来源SHA、缺失系数及限制。']
    (args.output / 'RESULTS_ZH.md').write_text('\n'.join(report) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
