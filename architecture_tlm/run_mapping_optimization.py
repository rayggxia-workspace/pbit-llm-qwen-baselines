"""Reproducible fixed-resource LOMA/TLM search and optional DRAMSys replay."""
import argparse
import copy
import csv
import hashlib
import json
import math
import time
from pathlib import Path
from mapping_decode import MatchedOriginalDecode, MappedDecode
from system_decode import ROOT, load

VARIANTS = ('digital_int8_ffn', 'fixed_sc_exact')
OUTPUT = ROOT/'results/mapping_20261015'


def checked_run(cfg, variant, evidence, shape, plan=None):
    model = (MatchedOriginalDecode(cfg, variant, evidence, shape) if plan is None
             else MappedDecode(cfg, variant, evidence, shape, plan))
    try:
        result = model.run()
    finally:
        if hasattr(model.ext, 'close'):
            model.ext.close()
    assert math.isclose(sum(result['energy_J'].values())*1000/cfg['decode_tokens'],
                        result['metrics']['scenario_mJ_per_token'], rel_tol=1e-10)
    for file in ('mapping_decode.py', 'run_mapping_optimization.py', 'zigzag_mapper.py'):
        result['source_hashes'][file] = hashlib.sha256((ROOT/file).read_bytes()).hexdigest()
    return result


def verify_same_work(reference, result):
    assert reference['actions'] == result['actions'], 'compute action counts changed'
    assert reference['resource_matching'] == result['resource_matching'], 'hardware resources changed'
    for key in ('raw_rng_bits', 'SC_wave_compute_ms', 'RNG_service_ms', 'replay_service_ms'):
        assert math.isclose(reference['bounds'][key], result['bounds'][key], abs_tol=1e-4), key
    for key in ('random_replay_write_bytes', 'random_replay_read_bytes',
                'scratch_partial_bytes', 'scratch_KV_tile_bytes',
                'external_KV_read_logical_bytes', 'external_KV_write_logical_bytes'):
        assert reference['traffic'].get(key, 0) == result['traffic'].get(key, 0), key
    for key in ('SC_logic_active', 'digital_MAC', 'digital_vector', 'digital_nonlinear'):
        assert math.isclose(reference['energy_J'].get(key, 0), result['energy_J'].get(key, 0),
                            rel_tol=1e-9, abs_tol=1e-14), key
    if 'mapping_checks' in result:
        assert result['mapping_checks']['peak_weight_SRAM_bytes'] <= result['config']['weight_macro']['cache_MiB']*2**20
    return dict(arithmetic_counts=True, RNG_service_and_replay_unchanged=True,
                same_physical_hardware=True, active_compute_energy=True,
                scratch_capacity=True, KV_logical_bytes=True, energy_sum=True)


def bounds(result, cfg, evidence, shape, variant):
    n = cfg['decode_tokens']; f = cfg['frequency_hz']
    digital_cycles = (result['energy_J']['digital_MAC']/(cfg['digital']['mac_pJ']*1e-12)
                      /cfg['digital']['macs_per_cycle']
                      + result['energy_J']['digital_vector']/(cfg['digital']['vector_op_pJ']*1e-12)
                      /cfg['digital']['vector_ops_per_cycle']
                      + result['energy_J']['digital_nonlinear']/(cfg['digital']['nonlinear_op_pJ']*1e-12)
                      /cfg['digital']['nonlinear_ops_per_cycle'])
    compute_ms = digital_cycles/f*1000/n
    sc_ms = result['actions'].get('sc_tile_frames', 0)*(cfg['samples']+1)/cfg['sc_engines']/f*1000/n
    # Necessary unique weight bytes in the existing format; only the configured
    # weight SRAM is allowed to retain weights across iterations in this bound.
    h = shape['hidden_size']; m = shape['intermediate_size']; kv = shape['num_key_value_heads']*(h//shape['num_attention_heads'])
    W = shape['num_hidden_layers']*(h*(h+2*kv)*2+h*h*2+3*h*m)+shape['vocab_size']*h*2
    Dkv = result['traffic']['external_KV_read_logical_bytes']/n
    capacity = cfg['weight_macro']['cache_MiB']*2**20
    bandwidth = cfg['external_memory']['bandwidth_GBs']
    comm_ms = (max(0, W-capacity)+Dkv)/bandwidth/1e6
    lb = max(compute_ms, sc_ms, comm_ms)
    ideal = copy.deepcopy(cfg)
    ideal['external_memory'] = dict(cfg['external_memory'], backend='simplified',
                                   bandwidth_GBs=1e30, latency_ns=0)
    ideal['weight_macro'].update(load_bandwidth_GBs=1e30, load_latency_ns=0)
    ideal['scratchpad']['bandwidth_GBs'] = 1e30
    oracle = checked_run(ideal, variant, evidence, shape)
    # Conditional energy floor for the retained simplified linear memory model.
    # Cold first token plus optimistic full-cache retention on later tokens.
    min_weight_bytes = W+max(0, n-1)*max(0, W-capacity)
    e = result['energy_J']; d = cfg['digital']; w = cfg['weight_macro']; sp = cfg['scratchpad']; r = cfg['rng']
    fixed = sum(e.get(k, 0) for k in ('SC_logic_active', 'digital_MAC', 'digital_vector',
                                    'digital_nonlinear', 'scratch_access', 'weight_resident_prepare'))
    weight_floor = W*n*w['read_pJ_per_byte']*1e-12+min_weight_bytes*w['write_pJ_per_byte']*1e-12
    static_power = (w['cache_MiB']*w['leakage_W_per_MiB']
                    + sp['capacity_MiB']*sp['leakage_W_per_MiB']+d['idle_W']
                    + cfg['control_interconnect_W']+cfg['sc_engines']*w['active_tile_hold_W']
                    + r['sources']*r['source_power_W']+r['fifo_distribution_W'])
    horizon = lb*n/1000
    active_engine_seconds = result['actions'].get('sc_tile_frames', 0)*(cfg['samples']+1)/f
    idle_floor = max(0, cfg['sc_engines']*horizon-active_engine_seconds)*cfg['sc_cost']['idle_W_per_engine']
    non_dram_floor = fixed+weight_floor+static_power*horizon+idle_floor
    simple_energy_floor = (non_dram_floor
        + min_weight_bytes*cfg['external_memory']['read_pJ_per_byte']*1e-12
        + e.get('external_KV', 0)+cfg['external_memory']['background_W']*horizon)*1000/n
    return dict(digital_resource_compute_ms=compute_ms, SC_work_conservation_ms=sc_ms,
                fixed_SC_wave_ms=result['bounds']['SC_wave_compute_ms']/n,
                conditional_communication_ms=comm_ms,
                resource_lower_bound_ms=lb,
                ideal_memory_same_arithmetic_and_RNG_ms=oracle['metrics']['mean_TPOT_ms'],
                conditional_simplified_energy_lower_bound_mJ_per_token=simple_energy_floor,
                non_DRAM_energy_floor_mJ_per_token=non_dram_floor*1000/n,
                caveat='resource bound is optimistic; conditional weight-SRAM partition; ideal-memory oracle retains current phase order and RNG service, not a universal global bound')


def compact(result):
    return dict(metrics=result['metrics'], plan=result.get('mapping_plan'),
                weight_cache=result['weight_cache'], resource_matching=result['resource_matching'])


def score(result):
    m = result['metrics']
    return m['mean_TPOT_ms']*m['scenario_mJ_per_token']


def search(output, contexts, tokens):
    from zigzag_mapper import generate
    cfg, evidence, shape = load()
    cfg['decode_tokens'] = tokens
    generated = generate(shape, cfg, output/'zigzag')
    rows = []; selection = {}; reference = {}
    # Coordinate search over all LOMA-derived DMA blocks/pin policies, then
    # attention blocking/SC early load. Not an unrestricted global optimum.
    for context in contexts:
        selection[str(context)] = {}
        for variant in VARIANTS:
            c = copy.deepcopy(cfg); c['context_tokens'] = context
            base = checked_run(c, variant, evidence, shape)
            reference[(context, variant)] = base
            (output/f'{variant}_{context}_before.json').write_text(json.dumps(base, indent=2)+'\n')
            trials = []
            plans = [dict(chunk_bytes=chunk, pin=pin, attention_tokens=128,
                          early_sc_weights=True)
                     for chunk in generated['dma_chunk_bytes'] for pin in (False, True)]
            for stage in ('dma_pin', 'attention'):
                for plan in plans:
                    started = time.monotonic()
                    result = checked_run(c, variant, evidence, shape, plan)
                    result['mapping_verification'] = verify_same_work(base, result)
                    trials.append(result)
                    rows.append(dict(context=context, variant=variant, stage=stage,
                                     **plan, **result['metrics'], wall_seconds=time.monotonic()-started))
                best = min(trials, key=score)
                plans = [dict(best['mapping_plan'], attention_tokens=b, early_sc_weights=early)
                         for b in (64, 256, 512)
                         for early in ((False, True) if variant == 'fixed_sc_exact' else (True,))]
            best = min(trials, key=score)
            fastest = min(trials, key=lambda r:r['metrics']['mean_TPOT_ms'])
            least_energy = min(trials, key=lambda r:r['metrics']['scenario_mJ_per_token'])
            lower = bounds(base, c, evidence, shape, variant)
            for label, result in [('after', best), ('fastest', fastest), ('least_energy', least_energy)]:
                result['lower_bounds'] = lower
                result['optimization'] = dict(objective='EDP', search='LOMA-derived DMA/pin then attention coordinate search',
                                              candidates=len(trials), ZigZag_valid_mappings=generated['valid_mappings'])
                (output/f'{variant}_{context}_{label}.json').write_text(json.dumps(result, indent=2)+'\n')
            selection[str(context)][variant] = dict(
                before=compact(base), after=compact(best), fastest=compact(fastest),
                least_energy=compact(least_energy), lower_bounds=lower,
                candidates=len(trials), selected_plan=best['mapping_plan'],
                time_reduction=1-best['metrics']['mean_TPOT_ms']/base['metrics']['mean_TPOT_ms'],
                energy_reduction=1-best['metrics']['scenario_mJ_per_token']/base['metrics']['scenario_mJ_per_token'])
            (output/'selection.json').write_text(json.dumps(selection, indent=2)+'\n')
            print(json.dumps(dict(context=context, variant=variant,
                                  before=base['metrics'], after=best['metrics'], plan=best['mapping_plan'])), flush=True)
    with (output/'search.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    return selection


def validate(output, selected_file, bridge, context, tokens, policy, variant, which):
    cfg, evidence, shape = load(); cfg['decode_tokens'] = tokens; cfg['context_tokens'] = context
    selected = json.loads(Path(selected_file).read_text())
    plan = selected[str(context)][variant]['selected_plan'] if which == 'after' else None
    name = f'{variant}_{context}_{which}_{policy}'
    target = output/'dramsys'; target.mkdir(parents=True, exist_ok=True)
    provenance = json.loads((ROOT/'dramsys/provenance.json').read_text())
    cfg['external_memory'].update(backend='dramsys', bridge_executable=str(Path(bridge).resolve()),
        bandwidth_GBs=provenance['peak_bandwidth_GBs'],
        configuration=str(ROOT/f'dramsys/ddr4_2ch_{policy}.json'), max_pending=32,
        output_prefix=str(target/name))
    started = time.monotonic()
    result = checked_run(cfg, variant, evidence, shape, plan)
    result['simulation_wall_seconds'] = time.monotonic()-started
    if which == 'after':
        before_path = target/f'{variant}_{context}_before_{policy}.json'
        if before_path.exists():
            result['mapping_verification'] = verify_same_work(json.loads(before_path.read_text()), result)
    # Keep original IO-voltage/PHY limitations explicit.
    result['scenario_cost_coverage'] = 'DRAMSys full-horizon core model; bundled vddq=0, PHY/CTS/host/prefill excluded; on-chip costs parameterized'
    (target/f'{name}.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(name=name, metrics=result['metrics'], wall_seconds=result['simulation_wall_seconds'])), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--mode', choices=['search', 'validate'], default='search')
    p.add_argument('--output', type=Path, default=OUTPUT); p.add_argument('--contexts', nargs='+', type=int, default=[2048, 8192])
    p.add_argument('--tokens', type=int, default=2); p.add_argument('--selection', type=Path)
    p.add_argument('--bridge'); p.add_argument('--context', type=int, default=2048)
    p.add_argument('--policy', choices=['NoPowerDown', 'Staggered'], default='NoPowerDown')
    p.add_argument('--variant', choices=VARIANTS, default=VARIANTS[0]); p.add_argument('--which', choices=['before', 'after'], default='before')
    args = p.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    if args.mode == 'search':
        search(args.output, args.contexts, args.tokens)
    else:
        validate(args.output, args.selection, args.bridge, args.context, args.tokens,
                 args.policy, args.variant, args.which)
