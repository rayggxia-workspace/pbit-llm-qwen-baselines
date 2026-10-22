"""Bounded, symmetric resource search over the unchanged unified-v6 decoder.

These are conditional TLM schedules, not physical feasibility or quality proof.
The CLI freezes its complete case manifest before executing any case. Resume
accepts only that same manifest and independently verified immutable receipts.
"""
import argparse
import copy
import datetime
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from architecture_tlm.unified_v6.config import load
from architecture_tlm.unified_v6.model import FullDecode

MIB = 1024**2
METHODS = {'bf16_exact': ('bf16', 'exact'), 'w8_exact': ('w8', 'exact'),
           'sc_exact': ('sc', 'exact'), 'sc_screen_pv': ('sc', 'screen_pv')}
RESOURCE_KEYS = {'sram.capacity_bytes', 'sram.banks', 'sram.fabric_GBs',
                 'dram.bandwidth_GBs', 'dram.max_pending', 'weight_chunk_bytes',
                 'macs_per_cycle', 'vector_lanes', 'ffn.engines', 'attention.tile_tokens'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode('utf-8')).hexdigest()


def generate_candidates():
    """Sixteen coarse designs shared by every method; not a Cartesian search."""
    def candidate(name, kind, **values):
        return dict(id=name, kind=kind, overrides=values)
    candidates = [candidate('baseline_1m', 'reference')]
    for capacity in (2, 4, 8):
        candidates.append(candidate('capacity_%dm' % capacity, 'capacity_only',
                                    **{'sram.capacity_bytes': capacity*MIB}))
    candidates += [
        candidate('mapped_1m', 'same_hardware_mapping', weight_chunk_bytes=256*1024,
                  **{'attention.tile_tokens': 256}),
        candidate('buffer_2m', 'buffer_mapping', weight_chunk_bytes=256*1024,
                  **{'sram.capacity_bytes': 2*MIB}),
        candidate('buffer_4m', 'buffer_mapping', weight_chunk_bytes=512*1024,
                  **{'sram.capacity_bytes': 4*MIB}),
        candidate('fabric_32', 'bank_and_fabric', weight_chunk_bytes=256*1024,
                  **{'sram.capacity_bytes': 2*MIB, 'sram.banks': 32, 'sram.fabric_GBs': 32.}),
        candidate('fabric_64', 'bank_and_fabric', weight_chunk_bytes=512*1024,
                  **{'sram.capacity_bytes': 4*MIB, 'sram.banks': 64, 'sram.fabric_GBs': 64.}),
        candidate('dram_32', 'conditional_external_interface',
                  **{'dram.bandwidth_GBs': 32., 'dram.max_pending': 64}),
        candidate('dram_64', 'conditional_external_interface',
                  **{'dram.bandwidth_GBs': 64., 'dram.max_pending': 128}),
        candidate('compute_small', 'compute', macs_per_cycle=256,
                  **{'ffn.engines': 4}),
        candidate('compute_large', 'compute', macs_per_cycle=1024, vector_lanes=128,
                  **{'ffn.engines': 16}),
        candidate('vector_128', 'restore_vector_ablation', vector_lanes=128),
        candidate('balanced_2m', 'joint', weight_chunk_bytes=256*1024, vector_lanes=128,
                  **{'sram.capacity_bytes': 2*MIB, 'sram.banks': 32, 'sram.fabric_GBs': 32.,
                     'dram.bandwidth_GBs': 32., 'dram.max_pending': 64}),
        candidate('wide_4m', 'joint', weight_chunk_bytes=512*1024, vector_lanes=128,
                  macs_per_cycle=1024,
                  **{'sram.capacity_bytes': 4*MIB, 'sram.banks': 64, 'sram.fabric_GBs': 64.,
                     'dram.bandwidth_GBs': 64., 'dram.max_pending': 128, 'ffn.engines': 16}),
    ]
    for item in candidates:
        item['assumptions'] = [
            '100MHz core/source and 80MHz SS SRAM; algorithm B4/T32/K32 unchanged',
            'SC engine feed/holds/counters and compute rates remain uncalibrated contracts',
            'DRAM link/window, controller/PHY and fabric costs remain uncalibrated',
            'provisioned SC engines are unused by digital FFN modes, never priced as zero area',
        ]
    return candidates


def apply_candidate(candidate, method='w8_exact', context=2048, seed=0, base_config=None):
    if method not in METHODS or not re.fullmatch(r'[a-z0-9_]+', candidate['id']):
        raise ValueError('unknown method or invalid candidate ID')
    cfg = copy.deepcopy(base_config if base_config is not None else load('qwen')[0])
    for key, value in candidate['overrides'].items():
        if key not in RESOURCE_KEYS:
            raise ValueError('not a supported resource/mapping variable: '+key)
        target = cfg
        parts = key.split('.')
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    cfg.update(context_tokens=context, seed=seed, decode_tokens=1)
    cfg['ffn'].update(mode=METHODS[method][0], bins=4, samples=32, strata=32)
    cfg['attention']['mode'] = METHODS[method][1]
    cfg['random']['backend'] = 'integrated_service'
    return cfg


def _finite(value, path='value'):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite '+path)
    if isinstance(value, dict):
        for key, child in value.items():
            _finite(child, path+'.'+str(key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _finite(child, path+'[%d]' % index)


def validate_candidate(candidate, cfg=None, shape=None):
    """Reject violations before running; constructor exercises the real Arena."""
    cfg = cfg if cfg is not None else apply_candidate(candidate)
    shape = shape if shape is not None else load('qwen')[1]
    _finite(cfg)
    for name in ('core_hz', 'context_tokens', 'decode_tokens', 'macs_per_cycle',
                 'vector_lanes', 'nonlinear_lanes', 'weight_chunk_bytes'):
        if type(cfg[name]) is not int or cfg[name] <= 0:
            raise ValueError('positive integer required: '+name)
    for section, fields in [('sram', ('capacity_bytes', 'banks', 'word_bytes', 'macro_depth', 'clock_hz')),
                            ('dram', ('burst_bytes', 'max_pending')),
                            ('ffn', ('engines', 'bins', 'samples', 'strata', 'sample_II_cycles')),
                            ('attention', ('tile_tokens', 'candidate_blocks', 'minimum_samples'))]:
        for field in fields:
            if type(cfg[section][field]) is not int or cfg[section][field] <= 0:
                raise ValueError('positive integer required: '+section+'.'+field)
    if type(cfg['seed']) is not int or cfg['seed'] < 0:
        raise ValueError('nonnegative integer seed required')
    s, d, f = cfg['sram'], cfg['dram'], cfg['ffn']
    if cfg['core_hz'] != 100000000 or cfg['random']['clock_hz'] != 100000000 or s['clock_hz'] != 80000000:
        raise ValueError('fixed core/source/SRAM clocks required')
    if (f['bins'], f['samples'], f['strata']) != (4, 32, 32):
        raise ValueError('fixed B4/T32/K32 required')
    if cfg['random']['backend'] != 'integrated_service' or d['backend'] != 'link':
        raise ValueError('fixed integrated_service/link backends required')
    if s['word_bytes'] != 16 or s['macro_depth'] != 4096 or s['corner'] != 'SS':
        raise ValueError('fixed calibrated SRAM macro geometry/corner required')
    if s['fabric_GBs'] <= 0 or d['bandwidth_GBs'] <= 0 or d['latency_ns'] < 0:
        raise ValueError('positive bandwidth/nonnegative latency required')
    bank_roof = s['banks']*s['word_bytes']*s['clock_hz']/1e9
    if s['fabric_GBs'] > bank_roof:
        raise ValueError('fabric exceeds aggregate single-port bank bandwidth')
    granule = s['banks']*s['macro_depth']*s['word_bytes']
    physical = math.ceil(s['capacity_bytes']/granule)*granule
    if physical != s['capacity_bytes']:
        raise ValueError('budget must include rounded physical SRAM macros')
    model = FullDecode(cfg, shape)
    for name, info in model.matrix_info.items():
        if f['mode'] == 'sc' and name.endswith(('/gu', '/down')):
            need = min(f['engines'], info['out']//64)*4096
        else:
            need = info['inp']*info['width']
        if need > cfg['weight_chunk_bytes']:
            raise ValueError('weight slot cannot supply '+name)
    return dict(status='conditional_contract_pass', bank_bandwidth_GBs=bank_roof,
                configured_capacity_bytes=s['capacity_bytes'], physical_capacity_bytes=physical,
                reserved_peak_bytes=model.arena.peak, layout=copy.deepcopy(model.arena.regions),
                macro_count=model.mem.macros, macro_area_mm2=model.mem.macros*model.mem.spec['area_mm2'],
                provisioned=dict(mac_per_cycle=cfg['macs_per_cycle'], vector_lanes=cfg['vector_lanes'],
                                 sc_engines=f['engines'], sc_engines_used=f['mode'] == 'sc'),
                sc_weight_wave_bytes=f['engines']*4096,
                sc_chunk_policy='SC wave is 4096*active engines; increasing slot does not increase SC wave',
                double_buffer=cfg['double_buffer'],
                feasibility_warning='bank/capacity/timing contract checked; not STA, PHY or total-area closure')


def source_record():
    """Record transitive imported repository Python and all runtime input files."""
    paths = {Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        raw = getattr(module, '__file__', None)
        if raw:
            path = Path(raw).resolve()
            if path.is_relative_to(ROOT) and path.suffix == '.py' and 'test' not in path.name:
                paths.add(path)
    paths.update((ROOT/'architecture_tlm/unified_v6/configs').glob('*.json'))
    paths.add(ROOT/'architecture_tlm/random_service/shared64_mapping.json')
    paths.add(ROOT/'architecture_tlm/llama7b/runtime/results/sram_calibration_v1_20261016/calibration.json')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    files = {}
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        payload = path.read_bytes()
        committed = subprocess.check_output(['git', 'show', head+':'+relative], cwd=ROOT)
        if payload != committed:
            raise ValueError('commit exact execution source before running: '+relative)
        files[relative] = dict(sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
    return dict(commit=head, files=files, source_sha256=digest(files),
                python=platform.python_version(), platform=platform.platform(),
                command=sys.argv, created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())


def case_id(candidate, method, context, seed, cfg, shape):
    return '%s_%s_L%d_seed%d_%s' % (candidate['id'], method, context, seed,
                                  digest(dict(config=cfg, shape=shape))[:12])


def run_case(candidate, method, context, seed, sources=None, shape=None, base_config=None):
    sources = source_record() if sources is None else sources
    shape = load('qwen')[1] if shape is None else shape
    cfg = apply_candidate(candidate, method, context, seed, base_config)
    validated = validate_candidate(candidate, cfg, shape)
    begin = time.perf_counter()
    result = FullDecode(cfg, shape).run()
    seconds = time.perf_counter()-begin
    _finite(result)
    if result['SRAM']['physical_bytes'] != validated['physical_capacity_bytes']:
        raise AssertionError('execution/validation physical memory mismatch')
    if result['random_interface']['random_stream_SRAM_bytes'] != 0:
        raise AssertionError('unexpected stored random stream')
    result.update(execution_commit=sources['commit'], execution_source_sha256=sources['source_sha256'],
                  config_sha256=digest(cfg), source_wall_seconds=seconds)
    result['resource_search'] = dict(candidate=copy.deepcopy(candidate), validation=validated,
        case_id=case_id(candidate, method, context, seed, cfg, shape), method=method,
        input_shape_sha256=digest(shape), candidate_sha256=digest(candidate),
        routing_sha256=digest(dict(receipts=result['row_receipts'], activity=result['attention_activity'])),
        physical_traffic_sha256=digest(dict(DRAM=result['DRAM']['traffic'], SRAM=result['SRAM']['traffic'])),
        source_output_sha256=result['random_interface']['frame_output_sha256'],
        source_activity_sha256=digest(result['random_interface']),
        route_scope='activity plus bounded row receipts; not a complete all-layer sample trace',
        randomness_warning='elapsed-time source clocks/reseeding can change realized draws across resource configurations despite equal seed; compare traffic and three-seed confirmation',
        energy_warning='priced subtotal is not full energy; full area/energy/quality remain unknown')
    return result


def _write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write('\n')


def _save_case(folder, result):
    name = result['resource_search']['case_id']+'.json'
    path = folder/name
    _write(path, result)
    _write(folder/(name+'.receipt.json'), dict(file=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                             config_sha256=result['config_sha256']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', nargs='+', default=['baseline_1m'])
    parser.add_argument('--methods', nargs='+', choices=METHODS, default=['w8_exact'])
    parser.add_argument('--contexts', nargs='+', type=int, choices=[2048, 8192], default=[2048])
    parser.add_argument('--seeds', nargs='+', type=int, default=[0])
    parser.add_argument('--max-cases', type=int, default=128)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    available = {c['id']: c for c in generate_candidates()}
    names = list(available) if args.candidates == ['all'] else args.candidates
    if len(names)*len(args.methods)*len(args.contexts)*len(args.seeds) > args.max_cases:
        raise ValueError('bounded case count exceeded')
    if args.max_cases < 1 or any(len(x) != len(set(x)) for x in (names, args.methods, args.contexts, args.seeds)):
        raise ValueError('positive bound and unique case selectors required')
    sources, (_, shape) = source_record(), load('qwen')
    cases = []
    for name in names:
        candidate = available[name]
        for method in args.methods:
            for context in args.contexts:
                for seed in args.seeds:
                    cfg = apply_candidate(candidate, method, context, seed)
                    validate_candidate(candidate, cfg, shape)
                    cases.append(dict(id=case_id(candidate, method, context, seed, cfg, shape),
                                      candidate=candidate, method=method, context=context, seed=seed,
                                      config_sha256=digest(cfg)))
    manifest = dict(schema=1, execution_commit=sources['commit'], source_sha256=sources['source_sha256'],
                    shape=shape, cases=cases)
    if args.output.exists():
        if not args.resume:
            raise ValueError('output exists; use new directory or explicit exact-manifest resume')
        if json.loads((args.output/'RUN_MANIFEST.json').read_text(encoding='utf-8')) != manifest:
            raise ValueError('resume manifest differs')
        original = json.loads((args.output/'EXECUTION.json').read_text(encoding='utf-8'))
        if original['commit'] != sources['commit'] or original['files'] != sources['files']:
            raise ValueError('resume execution bytes differ')
    else:
        if args.resume:
            raise ValueError('cannot resume missing output')
        args.output.mkdir(parents=True)
        _write(args.output/'EXECUTION.json', sources)
        _write(args.output/'RUN_MANIFEST.json', manifest)
    for case in cases:
        path = args.output/(case['id']+'.json')
        if path.exists():
            receipt = json.loads(path.with_name(path.name+'.receipt.json').read_text(encoding='utf-8'))
            if receipt != dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                               config_sha256=case['config_sha256']):
                raise ValueError('existing result receipt mismatch: '+case['id'])
            previous = json.loads(path.read_text(encoding='utf-8'))
            if (previous['resource_search']['case_id'] != case['id'] or
                previous['config_sha256'] != case['config_sha256'] or
                previous['execution_source_sha256'] != sources['source_sha256'] or
                previous['execution_commit'] != sources['commit']):
                raise ValueError('existing result identity mismatch')
            continue
        result = run_case(case['candidate'], case['method'], case['context'], case['seed'], sources)
        _save_case(args.output, result)
        print(json.dumps(dict(case=case['id'], TPOT_ms=result['metrics']['TPOT_ms'],
                              source_wall_seconds=result['source_wall_seconds'])), flush=True)
    return manifest


if __name__ == '__main__':
    main()
