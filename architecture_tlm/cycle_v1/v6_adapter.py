"""Run supported v6 operator boundaries beside cycle_v1, with explicit differences.

This is an executable configuration/shape bridge, not replacement of FullDecode
or calibration of one timing model against another. It never changes v6 files.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
import json
import math
from pathlib import Path
import time

from architecture_tlm.unified_v6 import config as v6_config
from architecture_tlm.unified_v6.model import FullDecode
from . import attention, ffn
from .run import canonical, digest, json_write, run_case, source_provenance


class UnsupportedMapping(ValueError):
    pass


MODE_MAP = {'exact': 'exact', 'pv': 'pv', 'screen_exact': 'exact',
            'screen_pv': 'pv', 'screen_winner': 'winner', 'screen_rejection': 'rejection'}


def legacy_source_provenance(cfg):
    root = Path(__file__).resolve().parents[2]
    names = ['architecture_tlm/unified_v6/'+name for name in
             ('__init__.py', 'core.py', 'model.py', 'config.py', 'rng_integrated.py')]
    names += ['architecture_tlm/'+name for name in ('attention_reference_v3.py', 'screen_ising_tlm_v4.py',
              'parallel_sampler_v5.py', 'winner_hold_tlm_v5.py', 'corrected_rejection_tlm_v5.py',
              'sram_cacti_calibration_v1.py')]
    names += ['architecture_tlm/'+cfg['sram']['calibration'],
              'architecture_tlm/unified_v6/configs/rng_ppa100.json']
    return {name: digest((root/name).read_bytes()) for name in names}


def _require(condition, message):
    if not condition:
        raise UnsupportedMapping(message)


def map_config(operator, cfg, shape, fixture):
    """Map only shared algorithm/source/compute dimensions; list independent contracts."""
    _require(operator in ('ffn', 'attention'), 'operator must be ffn or attention')
    _require(cfg['core_hz'] == 100_000_000, 'cycle_v1 operator frontend currently requires core_hz=100MHz')
    _require(cfg['sram']['clock_hz'] == 80_000_000, 'cycle_v1 memory frontend currently requires SRAM 80MHz')
    _require(cfg['dram']['backend'] == 'link', 'DRAMSys is not connected to this adapter; use a separately declared Link case')
    random = cfg['random']
    _require(random.get('backend') == 'integrated_service', 'only integrated_service maps to the native finite RNG frontend')
    _require(random['clock_hz'] == cfg['core_hz'], 'v6 integrated random source requires matching source/core clock')
    _require(cfg['ffn']['mode'] == 'sc', 'this bridge requires the v6 SC FFN contract, not BF16/W8 dense mode')
    shared = dict(seed=cfg['seed'], random_backend='native',
                  seed_word_interval=random['seed_word_interval_cycles'],
                  seed_startup=random['seed_startup_cycles'], reseed_cycles=random['reseed_cycles'],
                  vector_lanes=cfg['vector_lanes'])
    mapped = ['seed', 'core_hz=100MHz', 'sram.clock_hz=80MHz', 'vector_lanes',
              'random.backend', 'random.clock_hz', 'random.seed_word_interval_cycles',
              'random.seed_startup_cycles', 'random.reseed_cycles']
    if operator == 'ffn':
        f = cfg['ffn']
        _require((f['startup_cycles'], f['sample_II_cycles'], f['drain_cycles']) == (1, 1, 1),
                 'only the baseline v6 SC startup/II/drain=1/1/1 is admitted; no latency/II conflation')
        _require(cfg['double_buffer'] is True, 'serial weight scheduling has no supported cycle_v1 mapping')
        _require(cfg['weight_chunk_bytes'] >= f['engines'] * 4096,
                 'v6 weight chunk must hold a complete configured engine wave')
        hidden, middle = shape['hidden_size'], shape['intermediate_size']
        _require(hidden % 64 == middle % 64 == 0, 'v6 SC requires full 64-channel groups')
        matrices = {name: ffn.matrix_spec(fixture[name]) for name in ('wg', 'wu', 'wd')}
        _require(len(fixture['x']) == hidden and len(fixture.get('residual', [])) == hidden,
                 'FFN fixture must contain complete hidden-size activation and residual')
        _require(all(matrices[n]['rows'] == middle and matrices[n]['cols'] == hidden for n in ('wg', 'wu'))
                 and matrices['wd']['rows'] == hidden and matrices['wd']['cols'] == middle,
                 'cropped FFN cannot be labeled as the v6 complete FFN shape')
        result = ffn.FFNConfig(samples=f['samples'], strata=f['strata'], bins=f['bins'],
                               engines=f['engines'], **shared)
        mapped += ['ffn.samples', 'ffn.strata', 'ffn.bins', 'ffn.engines',
                   'shape.hidden_size', 'shape.intermediate_size']
        scope = 'one complete shaped FFN: gate/up, SwiGLU, down, output conversion and residual'
    else:
        mode = cfg['attention']['mode']
        _require(mode in MODE_MAP, 'serial Ising or unknown attention mode has no mapping')
        _require(shape['num_attention_heads'] == shape['num_key_value_heads'] == 1,
                 'query bridge currently requires an explicit single-head, single-KV shape; GQA is not mapped')
        hidden = shape['hidden_size']
        _require(len(fixture['q']) == hidden and all(len(row) == hidden for row in fixture['v']),
                 'Q and V dimensions must match the single-head shape')
        _require(len(fixture['k']) == cfg['context_tokens'], 'KV token count must match v6 context_tokens')
        ids = fixture.get('candidate_ids', list(range(len(fixture['k']))))
        _require(mode.startswith('screen_') or ids == list(range(cfg['context_tokens'])),
                 'unscreened exact/PV modes require all physical context candidates')
        a, sampler = cfg['attention'], cfg['sampler_v5']
        _require(sampler.get('drive_step') is None and sampler.get('offset_update_mode') == 'per_candidate',
                 'quantized input drive codes or global offset programming are not supported')
        samples = a['samples'] if a['samples'] is not None else max(a['minimum_samples'], math.ceil(len(fixture['k']) * a['sample_ratio']))
        if mode == 'screen_winner':
            samples *= a['winner_update_multiplier']
        result = attention.AttentionConfig(mode=MODE_MAP[mode], samples=samples,
                    mac_lanes=cfg['macs_per_cycle'], exp_lanes=cfg['nonlinear_lanes'],
                    drive_step=random['sigmoid_step'],
                    max_proposals_per_sample=sampler.get('max_proposals_per_sample', 64),
                    max_shift=sampler.get('max_shift', 24), burn_updates=sampler.get('burn_updates', 0),
                    winner_shift=sampler.get('winner_shift', 0.), rank_retry_cap=sampler.get('rank_retry_cap', 1024),
                    **shared)
        attention.validate_fixture(fixture, result)
        mapped += ['attention.mode at post-screen boundary', 'attention.samples/sample_ratio/minimum_samples',
                   'attention.winner_update_multiplier', 'macs_per_cycle', 'nonlinear_lanes', 'random.sigmoid_step',
                   'sampler_v5.max_proposals_per_sample/max_shift/burn_updates/winner_shift/rank_retry_cap']
        scope = 'one query after projection/RoPE and candidate screening; QK through selected V output'
    result.validate()
    return result, {'scope': scope, 'mapped_fields': mapped,
        'v6_only_contracts': ['blocking SRAM bank+shared-fabric descriptors, calibrated macro costs, additive cdc_ns',
            'Link 64B burst windows draining in batches; bandwidth_GBs and max_pending are NOT cycle descriptor parameters',
            'weight ping-pong chunk scheduling, macro startup/drain/restore arithmetic scheduling',
            'priced_subtotal and unpriced action ledger; no cycle_v1 price set is inferred'],
        'cycle_only_contracts': ['explicit latency versus II, old-state commit and output backpressure',
            'three destination-edge CDC visibility, finite byte credits and address-ordered RAW/WAR/WAW',
            'configured memory banks/windows/latencies from the cycle runner, independently reported',
            'configured finite encoder/restore/nonlinear pipelines and one-cycle native response bridge'],
        'no_direct_equivalence': ['elapsed time and action vocabulary use different granularity/resources',
            'legacy input activations are assumed SRAM-resident; cycle FFN performs its explicit initial reads',
            'legacy KV is BF16 and exact attention is fused/online; cycle query stores FP32 and explicit scores',
            'bridge legacy sampler logits round each FP32 product/add; cycle QK uses double products/fsum then FP32, so logits can differ',
            'same seed does not imply the same stream trajectory: endpoint count/request timing differs',
            'legacy FFN is a workload/timing model with no fixture-weight numerical output',
            'neither result is whole-model TPOT, PPL, STA, total physical energy or a speedup measurement']}


def _legacy_operator(operator, cfg, shape, fixture):
    model = FullDecode(cfg, shape)
    t = 0.
    if operator == 'ffn':
        t = model.phase('FFN_gate_up', 0, 0, t, lambda z: model.matrix_sc(z, 'L0/gu'))
        t = model.phase('FFN_SwiGLU', 0, 0, t, lambda z: model.vec(z, 'SwiGLU_FP32', 2*model.F, model.F,
            read=8*model.F, write=4*model.F, read_address=model.matrix_output, write_address=model.z))
        t = model.phase('FFN_down', 0, 0, t, lambda z: model.matrix_sc(z, 'L0/down'))
        t = model.phase('ffn_output_conversion', 0, 0, t, lambda z: model.vec(z, 'FP32_to_BF16', model.h,
            read=model.h*4, write=model.h*2, read_address=model.matrix_output,
            write_address=model.matrix_output, energy_unit='FP32_to_BF16'))
        t = model.phase('ffn_residual', 0, 0, t, model.residual_add)
    else:
        ids = fixture.get('candidate_ids', list(range(len(fixture['k']))))
        logits = []
        for index in ids:
            value = 0.
            for q, key in zip(fixture['q'], fixture['k'][index]):
                value = ffn.fp32(value + ffn.fp32(ffn.fp32(q)*ffn.fp32(key)))
            logits.append(ffn.fp32(value / math.sqrt(len(fixture['q']))))
        rows = [{'head': 0, 'ids': ids, 'logits': logits}]
        fused = cfg['attention']['mode'] in ('exact', 'screen_exact')
        t = model.phase('QK_and_fused_PV' if fused else 'QK', 0, 0, t,
                        lambda z: model.qk(z, 0, 0, rows, fused))
        if not fused:
            a = cfg['attention']
            samples = a['samples'] if a['samples'] is not None else max(a['minimum_samples'], math.ceil(cfg['context_tokens']*a['sample_ratio']))
            t = model.phase('sampler_and_sparse_V', 0, 0, t,
                            lambda z: model.sampled_attention(z, 0, 0, 0, rows, samples))
        t = model.mem.transfer(t, model.activation, model.h*2, True, 'attention_output')
    _require(abs(model.s.end()-t) < 1e-6, 'legacy operator left an unretired resource')
    random = model.rng.finish(t)
    dram, sram = model.dram.finish(t), model.mem.report(t)
    return {'schema': 'v6_adapter.legacy_operator.1', 'operator': operator,
        'elapsed_ns': t, 'core_cycles_elapsed': t/model.period,
        'phases': model.phases, 'actions': dict(model.e.actions), 'resource_busy_ns': dict(model.s.busy),
        'events': model.s.events, 'trace_truncated': model.s.count > len(model.s.events),
        'random_interface': random, 'DRAM': dram, 'SRAM': sram,
        'FFN_activity': dict(model.metadata), 'sampler_audit': model.sampler_audit,
        'priced_subtotal_J': sum(model.e.energy.values()), 'unpriced_actions': dict(model.e.missing),
        'numeric_output': None, 'scope': 'native v6 operator methods only; no full decoder run',
        'query_score_fixture': None if operator == 'ffn' else {
            'sha256': digest(canonical(logits)),
            'arithmetic': 'bridge-computed per-product/per-add FP32, not a native v6 arithmetic datapath',
            'not_bit_equal_to_cycle_qk': 'cycle uses double products/fsum then FP32'},
        'not_comparable_as': ['whole decoder TPOT', 'numerical oracle', 'same-resource speedup', 'total physical energy']}


def run_adapter(operator, cfg, shape, fixture, output, *, memory_latency=4, event_only=False):
    cfg, shape, fixture = copy.deepcopy(cfg), copy.deepcopy(shape), copy.deepcopy(fixture)
    mapped, boundary = map_config(operator, cfg, shape, fixture)
    legacy_hashes = legacy_source_provenance(cfg)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    json_write(output/'mapping.json', {'v6_config': cfg, 'shape': shape,
                                      'cycle_config': asdict(mapped), 'boundary': boundary})
    json_write(output/'START.json', {'source': source_provenance(), 'legacy_source_sha256': legacy_hashes,
                                    'fixture_sha256': digest(canonical(fixture)),
                                    'operator': operator, 'memory_latency_cycles': memory_latency})
    try:
        start = time.perf_counter()
        legacy = _legacy_operator(operator, cfg, shape, fixture)
        legacy['source_sha256'] = legacy_hashes
        legacy['wall_seconds'] = time.perf_counter()-start
        json_write(output/'v6_summary.json', legacy)
        bundle = {operator: fixture, 'provenance': {'kind': 'explicit v6 bridge operator fixture',
                    'input_sha256': digest(canonical(fixture)), 'shape': shape}}
        cycle = run_case(operator, bundle, mapped, output/'cycle', memory_latency=memory_latency,
                         compare_modes=not event_only)
        summary = {'schema': 'v6_adapter.comparison.1', 'status': 'passed', 'operator': operator,
                   'boundary': boundary,
                   'legacy': {'elapsed_ns': legacy['elapsed_ns'], 'summary': 'v6_summary.json'},
                   'cycle': {'elapsed_ns': cycle['latency_ns'], 'summary': 'cycle/summary.json',
                             'cycle_event_equivalence': cycle['mode_equivalence']},
                   'speedup': None, 'reason_no_speedup': 'independent timing, storage and source scheduling contracts',
                   'source': source_provenance()}
        json_write(output/'summary.json', summary)
        return summary
    except Exception as exc:
        json_write(output/'FAILED.json', {'type': type(exc).__name__, 'message': str(exc)})
        raise


def smoke_input(operator, mode='exact'):
    cfg, _ = v6_config.load('qwen')
    shape = dict(hidden_size=64, intermediate_size=64, num_attention_heads=1,
                 num_key_value_heads=1, num_hidden_layers=1, vocab_size=128,
                 tie_word_embeddings=True, attention_bias=False, max_position_embeddings=2048)
    cfg.update(context_tokens=9, trace_event_limit=512)
    cfg['attention'].update(mode={'winner': 'screen_winner', 'rejection': 'screen_rejection'}.get(mode, mode),
                            samples=4, winner_update_multiplier=1)
    row = lambda n, phase: [ffn.fp32(math.sin(i*.31+phase)*.12) for i in range(n)]
    if operator == 'ffn':
        fixture = {'x': row(64, .1), 'residual': row(64, .2),
                   'wg': [row(64, i*.17) for i in range(64)],
                   'wu': [row(64, i*.23) for i in range(64)],
                   'wd': [row(64, i*.29) for i in range(64)]}
    else:
        fixture = {'q': row(64, .1), 'k': [row(64, i*.19) for i in range(9)],
                   'v': [row(64, i*.27) for i in range(9)], 'candidate_ids': list(range(9))}
    return cfg, shape, fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator', choices=('ffn', 'attention'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true', help='explicit reduced single-head 64x64 B4/T32/K32 fixture')
    parser.add_argument('--smoke-mode', choices=('exact', 'pv', 'winner', 'rejection'), default='exact')
    parser.add_argument('--v6-config', type=Path, help='full v6 config JSON or saved v6 result containing config/model')
    parser.add_argument('--shape', type=Path, help='explicit shape JSON; otherwise use model record in v6 config')
    parser.add_argument('--fixture', type=Path, help='complete shaped FFN or one projected Q/K/V query')
    parser.add_argument('--memory-latency', type=int, default=4, help='independent cycle memory latency, not v6 Link latency')
    parser.add_argument('--event-only', action='store_true')
    args = parser.parse_args()
    if args.smoke:
        if args.v6_config or args.shape or args.fixture:
            parser.error('--smoke cannot be mixed with supplied inputs')
        cfg, shape, fixture = smoke_input(args.operator, args.smoke_mode)
    else:
        if not args.v6_config or not args.fixture:
            parser.error('provide --v6-config and --fixture, or explicitly choose --smoke')
        record = json.loads(args.v6_config.read_text(encoding='utf-8'))
        cfg = record.get('config', record)
        if args.shape:
            shape = json.loads(args.shape.read_text(encoding='utf-8'))
        elif 'model' in record:
            shape = record['model']
        else:
            shape = cfg['model_record']['shape']
        bundle = json.loads(args.fixture.read_text(encoding='utf-8'))
        fixture = bundle.get(args.operator, bundle)
    result = run_adapter(args.operator, cfg, shape, fixture, args.output,
                         memory_latency=args.memory_latency, event_only=args.event_only)
    print(json.dumps({key: result[key] for key in ('status', 'operator', 'legacy', 'cycle', 'speedup')}))


if __name__ == '__main__':
    main()
