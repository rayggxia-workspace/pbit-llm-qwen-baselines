"""Reproducible FFN/query runner with full cycle/event equivalence gates.

Examples (from repository root):
  python -m architecture_tlm.cycle_v1.run --operator ffn --output results/ffn
  python -m architecture_tlm.cycle_v1.run --operator attention --mode rejection --output results/query
  python -m architecture_tlm.cycle_v1.run --operator ffn --fixture PRIVATE.json --output results/real

The runner publishes summaries, hashes, timeline and addressed request traces,
never raw fixture weights. Configured timing is not STA or full-model quality.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, fields
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import struct
import subprocess
import time

from . import attention, ffn
from .reporting import timeline_summary, write_inspector


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def json_write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def synthetic_fixture():
    """Fixed public input with two input tiles, tail rows and sparse KV IDs."""
    row = lambda n, phase: [math.sin(i*.37+phase)*.17 for i in range(n)]
    return {'provenance': {'kind': 'deterministic_synthetic', 'version': 1},
        'ffn': {'x': row(67, .2), 'wg': [row(67, i*.19) for i in range(70)],
                'wu': [row(67, i*.23+.8) for i in range(70)],
                'wd': [row(70, i*.11+1.7) for i in range(16)], 'residual': row(16, 2.1)},
        'attention': {'q': row(16, .2), 'k': [row(16, i*.13) for i in range(24)],
                      'v': [row(12, i*.27) for i in range(24)],
                      'candidate_ids': [0, 1, 3, 4, 6, 8, 10, 13, 15, 17, 20, 22, 23]}}


def source_provenance():
    root = Path(__file__).resolve().parent
    hashes = {p.name: digest(p.read_bytes()) for p in sorted(root.glob('*.py'))}
    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True,
                                encoding='utf-8', errors='replace', check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    return {'commit': git('rev-parse', 'HEAD'), 'source_sha256': hashes,
            'working_tree_status': git('status', '--porcelain', '--untracked-files=no'),
            'python': platform.python_version(), 'platform': platform.platform()}


def _safe_payload(result):
    payload = result.equivalence_payload()
    payload['memory_reads'] = {k: {'bytes': len(v), 'sha256': digest(v)}
                               for k, v in result.memory_reads.items()}
    return payload


def _buffer_accounting(kernel, trace):
    occupancy = {name: spec.initial for name, spec in kernel.buffer_specs.items()}
    minimum = dict(occupancy)
    maximum = dict(occupancy)
    # Events sharing an edge commit together; aggregate before measuring occupancy.
    by_time = {}
    for event in trace:
        if event['kind'] not in ('accept', 'complete'):
            continue
        changes = by_time.setdefault(event['time_ps'], Counter())
        sign, field = (-1, 'inputs') if event['kind'] == 'accept' else (1, 'outputs')
        for name, count in event.get(field, {}).items():
            changes[name] += sign*count
    for changes in by_time.values():
        for name, amount in changes.items():
            occupancy[name] += amount
            minimum[name] = min(minimum[name], occupancy[name])
            maximum[name] = max(maximum[name], occupancy[name])
    answer = {}
    for name, spec in kernel.buffer_specs.items():
        if not 0 <= minimum[name] <= maximum[name] <= spec.capacity:
            raise AssertionError('buffer occupancy violated: '+name)
        answer[name] = {**asdict(spec), 'minimum_tokens_or_credits': minimum[name],
                       'maximum_tokens_or_credits': maximum[name], 'final': occupancy[name]}
        if spec.initial == spec.capacity:
            answer[name]['peak_reserved_units'] = spec.capacity-minimum[name]
    return answer


def _numeric(operator, fixture, config, state):
    if operator == 'ffn':
        frozen = ffn.replay_fixture(fixture,state) if hasattr(ffn,'replay_fixture') else fixture
        ref = ffn.reference_ffn_tiled(frozen, config)
        checks = {name: state[name] == ref[name] for name in ('gate','up','z','projected','output')}
        if not all(checks.values()):
            raise AssertionError('FFN tiled numeric mismatch: '+str(checks))
        return {'oracle': 'count-compressed tiled FP32 regression; separate independent audit required',
                'bit_equal_fields': checks}
    indices = None if config.mode == 'exact' else state['local_indices']
    ref = attention.reference_attention(fixture, indices, config)
    errors = [abs(x-y) for x,y in zip(state['output'], ref['output'])]
    # Different oracle reduction order: fsum versus per-product/per-add FP32.
    scale = max(1., max(abs(v) for v in ref['output']))
    bound = 8*2**-23*max(1,len(fixture.get('candidate_ids',fixture['k'])))*scale
    if max(errors, default=0.) > bound:
        raise AssertionError('Attention numerical reduction exceeds documented FP32 bound')
    exact = attention.reference_attention(fixture, None, config)['output']
    return {'oracle': 'double fsum weighted V, compared at documented FP32 reduction tolerance',
            'max_absolute_error': max(errors, default=0.), 'absolute_tolerance': bound,
            'sampled_vs_exact_rmse': math.sqrt(sum((x-y)**2 for x,y in zip(state['output'],exact))/len(exact)),
            'quality_scope': 'one query output error; not PPL or model accuracy'}


def run_case(operator, fixture_bundle, config, output, *, fixture_sha256=None,
             memory_latency=4, compare_modes=True, write_trace=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    fixture = dict(fixture_bundle.get(operator, fixture_bundle))
    fixture['provenance'] = fixture_bundle.get('provenance', {})
    module = ffn if operator == 'ffn' else attention
    build = module.build_ffn if operator == 'ffn' else module.build_attention
    completed = []
    for mode in (('cycle','event') if compare_modes else ('event',)):
        start = time.perf_counter()
        kernel = module.make_kernel(config, memory_latency=memory_latency)
        state = build(kernel, fixture, config)
        result = kernel.run(mode)
        elapsed = time.perf_counter()-start
        if state.get('output') is None or state.get('complete_ps') != result.finish_ps:
            raise AssertionError('final result was not committed to memory')
        if result.buffer_final != {n:s.initial for n,s in kernel.buffer_specs.items()}:
            raise AssertionError('local credits or sampled queue leaked at completion')
        stored = kernel.read_memory('sram', state['output_address'], state['output_bytes'])
        if operator == 'ffn' and config.output_bf16:
            expected = b''.join(struct.pack('<f', value)[2:] for value in state['output'])
        else:
            expected = struct.pack('<'+'f'*len(state['output']), *state['output'])
        if stored != expected:
            raise AssertionError('stored final output differs from functional output')
        completed.append((kernel, state, result, elapsed, stored))
    kernel, state, result, elapsed, stored = completed[-1]
    if compare_modes:
        if completed[0][2].equivalence_payload() != result.equivalence_payload():
            raise AssertionError('cycle/event timing, memory, trace, actions or final-state mismatch')
        for field in ('output','local_indices','histogram','frames','thresholds'):
            if completed[0][1].get(field) != state.get(field):
                raise AssertionError('cycle/event functional mismatch: '+field)
    payload = _safe_payload(result)
    numeric = _numeric(operator, fixture, config, state)
    timing_details, timeline_rows = timeline_summary(kernel,result)
    specs = {'resources': [asdict(x) for x in kernel.resources.values()],
             'memory_ports': [{k:v for k,v in asdict(x).items() if k!='initial_data'} for x in kernel.memory_ports.values()],
             'buffers': _buffer_accounting(kernel, result.trace)}
    summary = {'schema': 'cycle_v1.execution.1', 'operator': operator, 'config': asdict(config),
        'fixture_sha256': fixture_sha256 or digest(canonical(fixture_bundle)),
        'fixture_provenance': fixture_bundle.get('provenance', {}),
        'source': source_provenance(), 'created_utc': datetime.now(timezone.utc).isoformat(),
        'mode_equivalence': {'checked': compare_modes, 'equal': True if compare_modes else None,
           'fields': 'all acceptance/completion times, full trace, actual read bytes, actions, buffer/resource state; functional outputs and trajectories'},
        'numerical_validation': numeric, 'finish_ps': result.finish_ps,
        'latency_ns': result.finish_ps/1000, 'core_cycles_elapsed': result.finish_ps/10000,
        'operations': len(result.accepted_ps), 'trace_events': len(result.trace),
        'execution_modes': {r.mode: {'visited_edges': r.steps, 'wall_seconds': t} for _,_,r,t,_ in completed},
        'actions': result.actions, 'resource_peak': result.resource_peak, 'resource_stats': result.resource_stats,
        'resource_stats_note': 'execution_ps and held_ps are overlapping per-operation sums, not utilization or energy',
        'storage': specs['buffers'], 'local_state_bytes': state.get('local_state_bytes'),
        'output': state['output'], 'output_memory_sha256': digest(stored),
        'equivalence_payload_sha256': digest(canonical(payload)),
        'model_boundary': state['provenance'],
        'energy': {'status': 'unknown', 'reason': 'no matched characterized coefficient set; action counts only; no fabricated total'},
        'global_memory_capacity': 'not allocated; finite local working storage and finite request windows only',
        'hardware_status': 'configured cycle model; no full-datapath STA, synthesis or silicon evidence'}
    summary['timing_details']=timing_details
    if 'native_random' in state:
        summary['native_random']=state['native_random']
    if operator == 'attention':
        summary['sampler'] = {k: state.get(k) for k in ('proposals','rejected_empty','rejected_multi',
            'source_requests','source_frames','source_waves','fair_draws','rank_retries',
            'winner_holds','winner_switches','algorithm_updates','retained_samples','unique_V','physical_indices','histogram')}
        summary['K_addresses'] = state['K_addresses']
        summary['V_addresses'] = state['V_addresses']
    if write_trace:
        blob = canonical({'trace': result.trace, 'accepted_ps': result.accepted_ps,
                          'completion_ps': result.completion_ps, 'memory_reads': payload['memory_reads']})
        compressed = gzip.compress(blob, mtime=0)
        (output/'trace.json.gz').write_bytes(compressed)
        summary['trace_artifact'] = {'path': 'trace.json.gz', 'sha256': digest(compressed),
                                     'uncompressed_sha256': digest(blob), 'bytes': len(compressed)}
    json_write(output/'contracts.json', specs)
    json_write(output/'summary.json', summary)
    write_inspector(output/'timeline.html',{'operator':operator,'finish_ps':result.finish_ps,
                    'config':asdict(config),'model_boundary':state['provenance']},timeline_rows)
    lines = [f'# {operator} cycle execution', '',
             f'Latency: **{summary["latency_ns"]:,.2f} ns** under declared timing assumptions.',
             f'Operations: {summary["operations"]}; cycle/event equivalence checked: {compare_modes}.',
             '', 'This is a shaped FFN/query execution, not a full-model quality or physical PPA result.',
             '', 'See `summary.json` for provenance, numeric gates, action counts and boundaries; '
             '`contracts.json` for clocks, resources and storage; `trace.json.gz` for the complete timeline.']
    (output/'README.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator', choices=('ffn','attention'), required=True)
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, help='JSON overrides for the selected dataclass')
    parser.add_argument('--mode', choices=('exact','pv','winner','rejection'), default='exact')
    parser.add_argument('--samples', type=int, default=32)
    parser.add_argument('--strata', type=int, default=32)
    parser.add_argument('--bins', type=int, default=4)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--memory-latency', type=int, default=4)
    parser.add_argument('--event-only', action='store_true', help='explicitly skip cross-mode verification')
    parser.add_argument('--no-trace', action='store_true')
    args = parser.parse_args()
    bundle = json.loads(args.fixture.read_text(encoding='utf-8')) if args.fixture else synthetic_fixture()
    cls = ffn.FFNConfig if args.operator=='ffn' else attention.AttentionConfig
    values = dict(samples=args.samples, seed=args.seed)
    values.update(dict(strata=args.strata,bins=args.bins) if args.operator=='ffn' else dict(mode=args.mode))
    if args.config:
        values.update(json.loads(args.config.read_text(encoding='utf-8')))
    unknown = set(values)-{f.name for f in fields(cls)}
    if unknown:
        parser.error('Unknown config fields: '+str(sorted(unknown)))
    result = run_case(args.operator, bundle, cls(**values), args.output,
        fixture_sha256=digest(args.fixture.read_bytes()) if args.fixture else None,
        memory_latency=args.memory_latency, compare_modes=not args.event_only, write_trace=not args.no_trace)
    print(json.dumps({k:result[k] for k in ('operator','latency_ns','operations','mode_equivalence','numerical_validation')}))


if __name__=='__main__':
    main()
