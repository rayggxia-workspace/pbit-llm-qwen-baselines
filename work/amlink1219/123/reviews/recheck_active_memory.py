"""New reproducible execution of the 30-seed active-memory scheduler review.

Run from the publication checkout with Python 3.11+:
  python -B -P work/amlink1219/123/reviews/recheck_active_memory.py \
    --backend-root . --source-manifest /path/to/revision4/FFN_SOURCE_MANIFEST.json

Only the requested receipt is written. Existing receipts are never overwritten.
This records a fresh run, not a reconstructed receipt for the earlier inline run.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import time

sys.dont_write_bytecode = True
SEEDS = tuple(range(30))
OPERATIONS = 48
REQUIRED = (
    'architecture_tlm/cycle_v1/__init__.py',
    'architecture_tlm/cycle_v1/contracts.py',
    'architecture_tlm/cycle_v1/kernel.py',
    'architecture_tlm/cycle_v1/memory.py',
    'architecture_tlm/ffn_cycle_integration/active_memory.py',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value):
    def bytes_value(item):
        if isinstance(item, bytes):
            return {'__bytes_hex__': item.hex()}
        raise TypeError(type(item).__name__)
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, default=bytes_value).encode('utf-8')


def verify_sources(root, source_manifest):
    result = {}
    for name in REQUIRED:
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError('runtime source escapes explicit backend root: ' + name)
        raw = path.read_bytes()
        normalized = raw.replace(b'\r\n', b'\n')
        expected = source_manifest['files'][name]
        actual, normalized_hash = sha(raw), sha(normalized)
        if actual == expected:
            match = 'exact_snapshot_bytes'
        elif normalized_hash == expected:
            match = 'local_CRLF_normalized_to_snapshot_LF_bytes'
        else:
            raise ValueError('runtime source differs from snapshot: ' + name)
        result[name] = dict(sha256=actual, sha256_lf=normalized_hash,
                           snapshot_sha256=expected, snapshot_match=match)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-root', type=Path, required=True)
    parser.add_argument('--source-manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path(__file__).with_name('ACTIVE_RANDOM_REVIEW.json'))
    args = parser.parse_args()
    if args.out.exists():
        parser.error('receipt already exists; choose a new --out path')
    root = args.backend_root.resolve(strict=True)
    manifest_raw = args.source_manifest.read_bytes()
    source_manifest = json.loads(manifest_raw)
    sources = verify_sources(root, source_manifest)
    sys.path.insert(0, str(root))
    from architecture_tlm.cycle_v1.contracts import Clock, Operation, Resource
    from architecture_tlm.cycle_v1.kernel import Kernel
    from architecture_tlm.cycle_v1.memory import MemoryPort, MemoryRequest
    from architecture_tlm.ffn_cycle_integration.active_memory import ActiveMemoryKernel
    for name, module in tuple(sys.modules.items()):
        if name.startswith('architecture_tlm.') and getattr(module, '__file__', None):
            path = Path(module.__file__).resolve(strict=True)
            if not path.is_relative_to(root) or path.relative_to(root).as_posix() not in sources:
                raise ValueError('unbound runtime import: ' + str(path))

    class Audited(ActiveMemoryKernel):
        def __init__(self, *pos, **kw):
            super().__init__(*pos, **kw)
            self.guard_counts = dict(live_memory=0, dependency_ready=0, memory_hazard=0, next_event=0)

        def _step(self, t):
            super()._step(t)
            for name, live in self._live_memory.items():
                expected = [op.id for op in self.operations.values()
                            if op.resource == name and op.id not in self.completed]
                if list(live) != expected:
                    raise AssertionError(('live_registration_order', name, t))
                self.guard_counts['live_memory'] += 1
            for op in self._pending.values():
                if self._dependency_ready(op) != Kernel._dependency_ready(self, op):
                    raise AssertionError(('dependency_ready', op.id, t))
                self.guard_counts['dependency_ready'] += 1
                if self._memory_hazard(op) != Kernel._memory_hazard(self, op):
                    raise AssertionError(('memory_hazard', op.id, t))
                self.guard_counts['memory_hazard'] += 1
            if self._next_event_time(t) != Kernel._next_event_time(self, t):
                raise AssertionError(('next_event', t))
            self.guard_counts['next_event'] += 1

    def build(cls, seed):
        # This generator preserves the earlier inline review's RNG call order.
        rng = random.Random(seed)
        clocks = [Clock('a', 11, 2), Clock('b', 13, 3)]
        resources = [Resource('c' + str(i), clocks[i], rng.randint(1, 6),
            ii_cycles=rng.randint(1, 3), capacity=rng.randint(1, 4),
            instances=rng.randint(1, 2), completion_ports=rng.randint(1, 2),
            output_ii_cycles=rng.randint(1, 3), in_order_completion=bool(seed % 2)) for i in range(2)]
        ports = [MemoryPort('m' + str(i), clocks[i], banks=3, line_bytes=8,
            window=rng.randint(1, 4), latency_cycles=rng.randint(1, 5),
            ii_cycles=rng.randint(1, 3), ports_per_bank=rng.randint(1, 2),
            bank_capacity=rng.randint(1, 4), strict_reads=True,
            initial_data={0: bytes(range(128))}, response_ports=rng.randint(1, 2),
            response_ii_cycles=rng.randint(1, 3)) for i in range(2)]
        kernel = cls(resources, memory_ports=ports)
        names = [str(i).zfill(3) for i in range(OPERATIONS)]
        rng.shuffle(names)
        for i, name in enumerate(names):
            deps = tuple(rng.sample(names[:i], rng.randrange(min(i, 4) + 1)))
            resource = rng.choice(('c0', 'c1', 'm0', 'm1'))
            memory = None
            if resource.startswith('m'):
                address = rng.randrange(110)
                size = rng.randrange(1, 17)
                write = bool(rng.randrange(2))
                memory = MemoryRequest(address, size, write, bytes([i]) * size if write else None)
            kernel.add(Operation(name, resource, deps=deps, memory=memory,
                                 earliest_ps=rng.randrange(100), cdc_cycles=rng.randrange(4)))
        return kernel

    started = time.perf_counter()
    cases = []
    total_events = 0
    guard_totals = dict(live_memory=0, dependency_ready=0, memory_hazard=0, next_event=0)
    for seed in SEEDS:
        baseline_result = build(Kernel, seed).run('cycle')
        baseline = baseline_result.equivalence_payload()
        payload_hash = sha(canonical_bytes(baseline))
        runs = [dict(kernel='Kernel', mode='cycle', steps=baseline_result.steps,
                     equivalence_payload_sha256=payload_hash)]
        for cls, mode in ((Kernel, 'event'), (Audited, 'cycle'), (Audited, 'event')):
            kernel = build(cls, seed)
            run = kernel.run(mode)
            result = run.equivalence_payload()
            if result != baseline:
                different = [key for key in baseline if result[key] != baseline[key]]
                raise AssertionError(('complete_payload_mismatch', seed, cls.__name__, mode, different))
            digest = sha(canonical_bytes(result))
            if digest != payload_hash:
                raise AssertionError(('canonical_payload_hash_mismatch', seed, cls.__name__, mode))
            record = dict(kernel=cls.__name__, mode=mode, steps=run.steps,
                          equivalence_payload_sha256=digest)
            if isinstance(kernel, Audited):
                record['guard_counts'] = kernel.guard_counts
                for key in guard_totals:
                    guard_totals[key] += kernel.guard_counts[key]
                if any((kernel._dependency_cache, kernel._dependency_waiters, kernel._missing_dependencies)):
                    raise AssertionError(('dependency_state_retained_after_finish', seed, mode))
                if any(kernel._live_memory.values()):
                    raise AssertionError(('live_memory_retained_after_finish', seed, mode))
            runs.append(record)
        events = len(baseline['trace'])
        total_events += events
        cases.append(dict(seed=seed, operations=OPERATIONS, canonical_trace_events=events,
                          complete_payload_equal=True, runs=runs))
    if verify_sources(root, source_manifest) != sources:
        raise AssertionError('runtime source changed during execution')
    report = dict(schema='ffn.active_memory.random_review.1', status='PASS',
        run_kind='new reproducible verification, not a retrospective receipt for the earlier inline run',
        recorded_utc=datetime.now(timezone.utc).isoformat(), python=sys.version,
        platform=platform.platform(), helper_sha256=sha(Path(__file__).read_bytes()),
        source_manifest_sha256=sha(manifest_raw),
        source_manifest_backend_commit=source_manifest.get('backend_local_commit'),
        source_manifest_total_files=len(source_manifest['files']),
        source_binding='All five imported project source files checked before and after execution; unused manifest files are outside this review',
        runtime_sources=sources, seeds=list(SEEDS), operations_per_seed=OPERATIONS,
        runs=len(SEEDS) * 4, canonical_trace_events=total_events,
        complete_payload_fields=list(baseline), full_payload_checks=len(SEEDS) * 3,
        hash_serialization='sorted compact JSON, bytes represented as {__bytes_hex__: lowercase hexadecimal}',
        excluded_from_payload_comparison=['steps', 'mode'], guard_counts=guard_totals,
        post_finish_dependency_and_live_memory_state_empty=True,
        elapsed_wall_seconds=time.perf_counter() - started,
        scope='Synthetic scheduler equivalence only; no FFN quality, hardware timing or speedup claim; prior 3.15x observation remains prefix-only',
        reproduction='python -B -P work/amlink1219/123/reviews/recheck_active_memory.py --backend-root <checkout> --source-manifest <revision4/FFN_SOURCE_MANIFEST.json> --out <new-receipt.json>',
        cases=cases)
    encoded = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    with args.out.open('xb') as stream:
        stream.write(encoded)
    print(json.dumps(dict(status=report['status'], runs=report['runs'],
        canonical_trace_events=total_events, guard_counts=guard_totals,
        receipt_sha256=sha(encoded), helper_sha256=report['helper_sha256'])))


if __name__ == '__main__':
    main()
