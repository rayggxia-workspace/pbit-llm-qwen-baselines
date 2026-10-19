"""Integer-exact oracle for this RTL candidate; not a BF16/PPL simulator."""
from pathlib import Path
import json
import math
import random

LUT = json.loads((Path(__file__).parent / "sigmoid_lut_q16.json").read_text())['values']


def sigmoid_raw(g):
    magnitude = abs(g)
    positive = 65536 if magnitude >= 8192 else LUT[magnitude // 32]
    return 65536 - positive if g < 0 else positive


def evaluate(g, u, out_w=24):
    assert -32768 <= g <= 32767 and -32768 <= u <= 32767
    product = g * u * sigmoid_raw(g)
    magnitude, remainder = divmod(abs(product), 1 << 26)
    if remainder > (1 << 25) or (remainder == (1 << 25) and magnitude % 2):
        magnitude += 1
    rounded = -magnitude if product < 0 else magnitude
    lo, hi = -(1 << (out_w - 1)), (1 << (out_w - 1)) - 1
    saturated = rounded < lo or rounded > hi
    return max(lo, min(hi, rounded)), int(saturated), int(bool(remainder) or saturated)


def self_check():
    assert evaluate(0, -32768) == (0, 0, 0)
    assert sigmoid_raw(-32768) == 0 and sigmoid_raw(32767) == 65536
    assert evaluate(8192, 1024) == (8192, 0, 0)
    assert evaluate(32767, 32767, 16)[1:] == (1, 1)
    # Explicit positive/negative ties, even/odd retained integer.
    for u, rounded in [(8192, 32178), (24576, 96536),
                       (-8192, -32178), (-24576, -96536)]:
        assert abs(4096 * u * sigmoid_raw(4096)) % (1 << 26) == 1 << 25
        assert evaluate(4096, u)[0] == rounded
    for g in range(32768):
        assert sigmoid_raw(g) + sigmoid_raw(-g) == 65536
    sigmoid_errors = []
    silu_errors = []
    for g in range(-32768, 32768):
        reference = 1.0 / (1.0 + math.exp(-g / 1024.0))
        sigmoid_errors.append(abs(sigmoid_raw(g) / 65536.0 - reference))
        silu_errors.append(abs(g / 1024.0) * sigmoid_errors[-1])
    return {"checked_g_values": 65536,
            "maximum_sigmoid_absolute_error": max(sigmoid_errors),
            "maximum_silu_absolute_error_before_output_rounding": max(silu_errors),
            "swiglu_absolute_error_bound_abs_u_le_32_before_output_rounding": max(silu_errors) * 32,
            "maximum_final_rounding_error_without_saturation": 0.5 / 1024,
            "error_scope": "LUT/final rounding over declared Q10 inputs, not model accuracy"}


def write_cycle_vectors(path, seed=20261017, random_vectors=12000):
    rng = random.Random(seed)
    cycles = [(1, 0, 0, 0, 0), (1, 1, 1, 32767, -32768)]
    gs = [-32768, -8193, -8192, -8191, -4096, -33, -32, -31, -1,
          0, 1, 31, 32, 33, 4096, 8191, 8192, 8193, 32767]
    us = [-32768, -24576, -8192, -1024, -1, 0, 1, 1024, 8192, 24576, 32767]
    directed = [(g, u) for g in gs for u in us]
    for i, (g, u) in enumerate(directed):
        cycles.append((0, 1, 1, g, u))
        if i % 7 == 0:
            cycles += [(0, 0, 1, -g if g != -32768 else 123, u),
                       (0, 1, 0, rng.randrange(-32768, 32768), 317)]
    for i in range(random_vectors):
        # Resets interrupt occupied pipelines; CE pauses valid and invalid cycles.
        rst = int(i in (47, 2048, 8193))
        ce = int(rng.random() > 0.2)
        valid = int(rng.random() > 0.25)
        cycles.append((rst, ce, valid, rng.randrange(-32768, 32768),
                       rng.randrange(-32768, 32768)))
    cycles += [(0, 1, 0, rng.randrange(-32768, 32768),
                rng.randrange(-32768, 32768)) for _ in range(24)]
    pipeline = [None] * 3
    last_output = [(0, 0, 0), (0, 0, 0)]
    output_valid = 0
    lines = []
    accepted, produced, paused = 0, 0, 0
    for rst, ce, valid, g, u in cycles:
        if rst:
            pipeline = [None] * 3
            output_valid = 0
            last_output = [(0, 0, 0), (0, 0, 0)]
        elif ce:
            old_last = pipeline[-1]
            output_valid = int(old_last is not None)
            if old_last is not None:
                last_output = [evaluate(*old_last, 24), evaluate(*old_last, 16)]
                produced += 1
            pipeline = [(g, u) if valid else None] + pipeline[:-1]
            accepted += valid
        else:
            paused += 1
        row = [rst, ce, valid, g, u, output_valid,
               *last_output[0], *last_output[1]]
        lines.append(' '.join(map(str, row)))
    path.write_bytes(('\n'.join(lines) + '\n').encode('ascii'))
    return {"seed": seed, "cycles": len(cycles), "accepted": accepted,
            "produced": produced, "ce_pauses": paused,
            "directed_transactions": len(directed),
            "note": "Midstream synchronous resets intentionally discard in-flight inputs."}
