"""Independent integer and ready/valid golden tests; no EDA/PPA claim.

API: run_tests(output, simulator='iverilog', ..., case_id=None,
               ivl=None, generate_only=False) -> summary dict.
Cases: restore_b4_c20, restore_b7_c21, accumulator64.
Portable Icarus uses -B/-M with the supplied ivl directory. VCS commands can
be generated here; only simulators actually run are reported as verified.
"""
from pathlib import Path
import argparse
import hashlib
import json
import random
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
RTL = HERE.parent / 'rtl'
MASK64 = (1 << 64) - 1
MIN64, MAX64 = -(1 << 63), (1 << 63) - 1
CASES = ('restore_b4_c20', 'restore_b7_c21', 'accumulator64')


def rne_signed(value, shift):
    """Integer-only round to nearest, ties to even, symmetric about zero."""
    assert 0 <= shift <= 63
    magnitude = abs(value)
    quotient, remainder = divmod(magnitude, 1 << shift)
    divisor = 1 << shift
    if 2 * remainder > divisor or (2 * remainder == divisor and quotient & 1):
        quotient += 1
    return -quotient if value < 0 else quotient


def restore_golden(counts, coefficient, shift):
    assert 0 <= coefficient <= 65535
    total = sum(count << (2 * (len(counts) - 1 - index))
                for index, count in enumerate(counts))
    result = rne_signed(total * coefficient, shift)
    assert MIN64 <= result <= MAX64
    return result


def accumulator_golden(state, delta, clear, sticky):
    if clear:
        return delta, False, False
    full = state + delta
    overflow = not MIN64 <= full <= MAX64
    return min(MAX64, max(MIN64, full)), overflow, bool(sticky or overflow)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, lines):
    path.write_bytes(('\n'.join(lines) + '\n').encode('ascii'))


def _restore_vectors(bins, cw):
    rng = random.Random(193000 + bins)
    low, high = -(1 << (cw - 1)), (1 << (cw - 1)) - 1
    vectors = []
    # Every bucket individually, including bucket6, endpoints and cancellation.
    for b in range(bins):
        for value in (low, high, -1, 0, 1):
            counts = [0] * bins
            counts[b] = value
            for coeff, shift in ((0, 0), (65535, 0), (65535, 63), (1, 1)):
                vectors.append((counts, coeff, shift))
    # Signed ties exercise parity both ways: +-0.5, +-1.5, +-2.5, +-3.5.
    for value in (-15, -13, -7, -5, -3, -1, 1, 3, 5, 7, 13, 15):
        counts = [0] * bins
        counts[-1] = value
        vectors.append((counts, 1, 1))
    for shift in range(64):
        vectors.append(([high] * bins, 65535, shift))
        vectors.append(([low] * bins, 65535, shift))
        vectors.append(([low if b & 1 else high for b in range(bins)], 65535, shift))
    directed = len(vectors)
    for _ in range(600):
        vectors.append(([rng.randint(low, high) for _ in range(bins)],
                        rng.randrange(65536), rng.randrange(64)))
    return vectors, directed


def generate_restore_trace(path, bins, cw):
    vectors, directed = _restore_vectors(bins, cw)
    latency = 8 if bins == 4 else 10
    pipeline = [None] * latency
    rng = random.Random(193700 + bins)
    lines, next_vector, pending = [], 0, None
    accepted = completed = dropped = stalled = 0
    fresh_latencies, continuous_handshakes = [], []
    mid_reset = directed + 30
    cycle = 0
    while next_vector < len(vectors) or pending is not None or any(x is not None for x in pipeline) or cycle < 3:
        reset = cycle in (0, 1, mid_reset, mid_reset + 1)
        continuous = 2 <= cycle < directed + 2
        out_ready = True if continuous or next_vector == len(vectors) else (
            cycle % 43 not in range(7, 19) and rng.random() < .75)
        if pending is None and next_vector < len(vectors) and (continuous or rng.random() < .8):
            pending = (next_vector, vectors[next_vector])
            next_vector += 1
        in_valid = pending is not None
        advance = pipeline[-1] is None or out_ready
        in_ready = not reset and advance
        out_valid = not reset and pipeline[-1] is not None
        counts, coeff, shift = pending[1] if pending else ([0] * bins, 0, 0)
        packed = sum((count & ((1 << cw) - 1)) << (i * cw) for i, count in enumerate(counts))
        expected = pipeline[-1][0] if out_valid else 0
        lines.append(f'{int(not reset)} {int(in_valid)} {int(out_ready)} {packed:x} {coeff:x} {shift:x} '
                     f'{int(in_ready)} {int(out_valid)} {expected & MASK64:016x}')
        if out_valid and out_ready:
            completed += 1
            if cycle < mid_reset:
                fresh_latencies.append(cycle - pipeline[-1][1])
            if continuous:
                continuous_handshakes.append(cycle)
        if out_valid and not out_ready:
            stalled += 1
        if reset:
            dropped += sum(item is not None for item in pipeline)
            pipeline = [None] * latency
        elif advance:
            value = None
            if in_valid:
                value = (restore_golden(counts, coeff, shift), cycle, pending[0])
                accepted += 1
                pending = None
            pipeline = [value] + pipeline[:-1]
        cycle += 1
        if cycle > 20000:
            raise AssertionError('Trace failed to drain')
    # End with a reset and an observed reset state.
    lines.extend(['0 0 1 0 0 0 0 0 0000000000000000', '1 0 1 0 0 0 1 0 0000000000000000'])
    assert accepted == completed + dropped
    assert min(fresh_latencies) == latency
    assert all(b-a == 1 for a, b in zip(continuous_handshakes, continuous_handshakes[1:]))
    assert stalled > 0 and dropped > 0
    _write(path, lines)
    return dict(bins=bins, count_bits=cw, signed_bucket_zero='low packed bits',
                expected_handshake_latency_cycles=latency, expected_steady_II_cycles=1,
                output_present_register_edges=latency, first_present_periods_after_accept=latency-1,
                directed_vectors=directed, transactions_accepted=accepted,
                transactions_completed=completed, transactions_dropped_by_reset=dropped,
                blocked_output_cycles=stalled, trace_cycles=len(lines),
                trace_sha256=_sha(path), random_seed=193700 + bins)


def generate_accumulator_trace(path):
    rng = random.Random(193864)
    vectors = [(MAX64, True), (1, False), (-1, False), (-MAX64, False),
               (MIN64, True), (-1, False), (1, False), (MAX64, False),
               (0, True), (MAX64, False), (MAX64, False), (MIN64, False),
               (MIN64, False), (3, True), (-5, False), (2, False)]
    directed = len(vectors)
    for _ in range(650):
        vectors.append((rng.choice((MIN64, MAX64, 0, 1, -1, rng.randint(MIN64, MAX64))),
                        rng.random() < .1))
    state = 0
    overflow = sticky = full = False
    pending = None
    lines = []
    next_vector = accepted = completed = dropped = stalled = overflows = 0
    resets = (0, 1, 57, 58, 101, 102)
    cycle = 0
    while next_vector < len(vectors) or pending is not None or full or cycle < 3:
        reset = cycle in resets
        continuous = 2 <= cycle < directed + 2
        out_ready = True if continuous or next_vector == len(vectors) else (
            cycle % 37 not in range(3, 14) and rng.random() < .7)
        if pending is None and next_vector < len(vectors) and (continuous or rng.random() < .8):
            pending = vectors[next_vector]
            next_vector += 1
        valid = pending is not None
        delta, clear = pending if pending else (0, False)
        can_accept = not full or out_ready
        ready = not reset and can_accept
        out_valid = not reset and full
        lines.append(f'{int(not reset)} {int(valid)} {int(out_ready)} {delta & MASK64:016x} {int(clear)} '
                     f'{int(ready)} {int(out_valid)} {state & MASK64:016x} {int(overflow)} {int(sticky)}')
        if out_valid and out_ready:
            completed += 1
        if out_valid and not out_ready:
            stalled += 1
        if reset:
            dropped += int(full)
            full = overflow = sticky = False
            state = 0
        elif can_accept:
            full = valid
            if valid:
                state, overflow, sticky = accumulator_golden(state, delta, clear, sticky)
                overflows += int(overflow)
                accepted += 1
                pending = None
        cycle += 1
        if cycle > 20000:
            raise AssertionError('Trace failed to drain')
    lines.append(f'0 0 1 0 0 0 0 {state & MASK64:016x} {int(overflow)} {int(sticky)}')
    lines.append('1 0 1 0 0 1 0 0000000000000000 0 0')
    assert accepted == completed + dropped
    assert stalled > 0 and overflows > 0 and dropped > 0
    _write(path, lines)
    return dict(expected_handshake_latency_cycles=1, expected_steady_II_cycles=1,
                feedback_distance_cycles=1, state_bits=64, directed_vectors=directed,
                transactions_accepted=accepted, transactions_completed=completed,
                transactions_dropped_by_reset=dropped, overflow_transactions=overflows,
                blocked_output_cycles=stalled, trace_cycles=len(lines),
                trace_sha256=_sha(path), random_seed=193864)


def run_tests(output, simulator='iverilog', iverilog=None, vvp=None, vcs='vcs',
              case_id=None, ivl=None, generate_only=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    selected = CASES if case_id is None else (case_id,)
    if any(case not in CASES for case in selected):
        raise ValueError('unknown case_id')
    if simulator not in ('iverilog', 'vcs'):
        raise ValueError('unsupported simulator')
    iverilog = str(Path(iverilog or shutil.which('iverilog') or 'iverilog'))
    vvp = str(Path(vvp or shutil.which('vvp') or 'vvp'))
    # The portable Windows Icarus driver shells out internally: normalize
    # explicitly supplied paths to native separators without inventing ivl.
    ivl = str(Path(ivl)) if ivl is not None else None
    results = []
    for name in selected:
        destination = output / name
        destination.mkdir(exist_ok=True)
        trace = destination / 'TRACE.txt'
        restore = name.startswith('restore_')
        top = 'tb_ffn_restore' if restore else 'tb_ffn_accumulator'
        definitions = []
        if restore:
            bins, cw = (4, 20) if name == 'restore_b4_c20' else (7, 21)
            properties = generate_restore_trace(trace, bins, cw)
            definitions = [f'TEST_BINS={bins}', f'TEST_CW={cw}']
        else:
            properties = generate_accumulator_trace(trace)
        source = RTL / ('ffn_restore.sv' if restore else 'ffn_accumulator.sv')
        bench = HERE / (top + '.sv')
        executable = destination / ('simulation.vvp' if simulator == 'iverilog' else 'simv')
        if simulator == 'iverilog':
            compile_command = [iverilog] + (['-B', ivl] if ivl else [])
            compile_command += ['-g2012', '-Wall', '-s', top]
            compile_command += ['-D' + definition for definition in definitions]
            compile_command += ['-o', str(executable), str(source), str(bench)]
            simulate_command = [vvp] + (['-M', ivl] if ivl else [])
            simulate_command += [str(executable), '+TRACE=' + str(trace)]
        else:
            compile_command = [str(vcs), '-full64', '-sverilog', '-top', top]
            compile_command += ['+define+' + definition for definition in definitions]
            compile_command += [str(source), str(bench), '-o', str(executable)]
            simulate_command = [str(executable), '+TRACE=' + str(trace)]
        item = dict(case_id=name, status='generated' if generate_only else 'pending',
                    properties=properties, source_sha256=_sha(source), bench_sha256=_sha(bench),
                    golden_sha256=_sha(__file__), compile_command=compile_command,
                    simulate_command=simulate_command, simulator=simulator)
        if not generate_only:
            for phase, command in (('compile', compile_command), ('simulate', simulate_command)):
                try:
                    result = subprocess.run(command, cwd=destination, text=True,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
                except (OSError, subprocess.TimeoutExpired) as error:
                    item['status'] = 'failed'
                    item['failed_phase'] = phase
                    item['execution_error'] = str(error)
                    (destination / (phase + '.log')).write_bytes(str(error).encode('utf-8'))
                    break
                (destination / (phase + '.log')).write_bytes(result.stdout.encode('utf-8'))
                item[phase + '_returncode'] = result.returncode
                if result.returncode or (phase == 'simulate' and 'PASS ' not in result.stdout):
                    item['status'] = 'failed'
                    item['failed_phase'] = phase
                    break
            else:
                item['status'] = 'passed'
        (destination / 'RESULT.json').write_bytes((json.dumps(item, indent=2) + '\n').encode('utf-8'))
        results.append(item)
    status = 'generated' if generate_only else ('passed' if all(x['status'] == 'passed' for x in results) else 'failed')
    summary = dict(status=status, cases=results,
                   scope='integer/handshake functional simulation only; no STA, PT, PPA or Qwen quality claim')
    (output / 'SUMMARY.json').write_bytes((json.dumps(summary, indent=2) + '\n').encode('utf-8'))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--simulator', choices=('iverilog', 'vcs'), default='iverilog')
    parser.add_argument('--case-id', choices=CASES)
    parser.add_argument('--iverilog')
    parser.add_argument('--vvp')
    parser.add_argument('--ivl')
    parser.add_argument('--vcs', default='vcs')
    parser.add_argument('--generate-only', action='store_true')
    args = parser.parse_args()
    result = run_tests(**vars(args))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] in ('passed', 'generated') else 1)


if __name__ == '__main__':
    main()
