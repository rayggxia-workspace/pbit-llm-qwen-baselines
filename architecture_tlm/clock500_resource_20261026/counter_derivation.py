"""Exact integer algebra audit; not RTL timing, PPA, or model quality validation."""
import hashlib
import json
from pathlib import Path
import random


def rne(v, shift):
    sign = -1 if v < 0 else 1
    q, rem = divmod(abs(v), 1 << shift)
    if shift and (rem > (1 << (shift-1)) or (rem == (1 << (shift-1)) and q & 1)):
        q += 1
    return sign*q


def audit():
    rows, checked = [], 0
    for bins, samples in [(4, 64), (7, 128)]:
        cw = 1 + (64*127*samples).bit_length()
        shift_max = 2*(bins-1)
        merged_cw = 1 + (64*127*samples*(1 << shift_max)).bit_length()
        for merged in [False, True]:
            for cuts in [(1,2,3,4,5,6), (2,4,6)]:
                bits = sum((64 >> level)*(8 + level + (shift_max if merged else 0)) for level in cuts)
                bits *= 1 if merged else bins
                rows.append(dict(bins=bins, samples=samples, merged=merged, cuts=list(cuts),
                    pipeline_bits_per_output=bits, pipeline_bits_2048=bits*2048,
                    accumulator_bits_per_output=merged_cw if merged else bins*cw))
        for seed in [17, 31, 193]:
            rng = random.Random(seed)
            for mode in ['iid', 'stratified32', 'zero', 'max_positive', 'max_negative', 'cancel']:
                for trial in range(4):
                    w = [rng.randint(-127,127) for _ in range(64)]
                    b = [rng.randrange(bins) for _ in range(64)]
                    p = [rng.randrange(257) for _ in range(64)]
                    if mode.startswith('max_'):
                        w = [127 if mode == 'max_positive' else -127]*64
                        b = [trial % bins]*64
                    if mode == 'cancel':
                        w = [127,-127]*32
                        b = [trial % bins]*64
                        p = [128]*64
                    counts, folded = [0]*bins, 0
                    for t in range(samples):
                        r = (t % 32)*8 + rng.randrange(8) if mode == 'stratified32' else rng.randrange(256)
                        # One R8 shared across 64 inputs. Identical accepted event stream in both forms.
                        event = [0 if mode == 'zero' else 1 if mode.startswith('max_') else int(r < v) for v in p]
                        for n in range(64):
                            term = w[n]*event[n]
                            counts[b[n]] += term
                            folded += term << (2*(bins-1-b[n]))
                        assert all(-(1 << (cw-1)) <= v < (1 << (cw-1)) for v in counts)
                        assert -(1 << (merged_cw-1)) <= folded < (1 << (merged_cw-1))
                    reference = sum(v << (2*(bins-1-i)) for i,v in enumerate(counts))
                    assert reference == folded
                    for coeff, shift in [(0,0),(1,0),(32769,17),(65535,31)]:
                        assert rne(reference*coeff,shift) == rne(folded*coeff,shift)
                    checked += 1
    return dict(kind='integer_algebra_and_state_count_only', frames_checked=checked,
        seeds=[17,31,193], rows=rows, pipeline_or_rtl_verified=False,
        ppa_measured=False, new_ppl=False,
        qualifications=['No early per-bin rounding/saturation', 'One bin per event',
            'Fixed power-of-two bin ratios; final shared coefficient and RNE',
            'No control, output buffer, leaf register, mux area, or clock-tree costs in bit counts'],
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


if __name__ == '__main__':
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
