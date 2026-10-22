"""Exact integer diagnostics for W8 SC per-bin counter structures A and B.

Weights are output-major [output][input], signed integers in [-128, 127].
input_sign is 0 for positive and 1 for negative; bins are 0..3. samples[t][i]
is the accepted activation bit. true_one[i] overrides a raw bit with one.
All outputs remain [output][bin] integers: no floating conversion, scaling,
cross-bin fusion or changed FP32 rounding order is implemented here.

This is a mathematical functional check, not RTL, STA, physical PPA or PPL.
It does not generate or establish the statistical quality of sample streams.
Run ``python -B -P counter.py`` for a deterministic seed-20261023 diagnostic.
"""

import json
import random


BINS = 4
SEED = 20261023


def required_widths(inputs, samples, outputs=64):
    """Return exact worst-case storage widths, including positive endpoints."""
    for name, value in (("inputs", inputs), ("samples", samples), ("outputs", outputs)):
        if type(value) is not int or value < 1:
            raise ValueError(name + " must be a positive integer")
    max_count = inputs * samples
    max_bin = max_count * 128  # -128 weight times negative input gives +128.
    count_bits = max_count.bit_length()
    sum_bits = max_bin.bit_length() + 1
    return {
        "max_unsigned_count": max_count,
        "count_bits": count_bits,
        "max_abs_bin_sum": max_bin,
        "sum_bits": sum_bits,
        "sample_sum_bits": (inputs * 128).bit_length() + 1,
        "a_counter_state_bits": outputs * BINS * 2 * 8 * count_bits,
        "b_accumulator_state_bits": outputs * BINS * sum_bits,
        "excluded_state": "weights, inputs, scales, pipeline, control and readout",
    }


def _validated(weights, input_sign, bins, samples, true_one):
    weights = tuple(tuple(row) for row in weights)
    input_sign, bins = tuple(input_sign), tuple(bins)
    samples = tuple(tuple(row) for row in samples)
    n = len(input_sign)
    true_one = (0,) * n if true_one is None else tuple(true_one)
    if not n or not weights or not samples:
        raise ValueError("nonempty inputs, outputs and sample frame are required")
    if len(bins) != n or len(true_one) != n:
        raise ValueError("input_sign, bins and true_one lengths must match")
    if any(len(row) != n for row in weights + samples):
        raise ValueError("every weight and sample row must match input width")
    if any(type(w) is not int or not -128 <= w <= 127 for row in weights for w in row):
        raise ValueError("weights must be signed W8 integers")
    if any(type(b) is not int or not 0 <= b < BINS for b in bins):
        raise ValueError("bin indices must be integers 0..3")
    for seq in (input_sign, true_one) + samples:
        if any(type(bit) not in (int, bool) or bit not in (0, 1) for bit in seq):
            raise ValueError("sign, true_one and sample inputs must be bits")
    return weights, input_sign, bins, samples, true_one


def _width(value, default):
    if value is None:
        return default
    if type(value) is not int or value < 1:
        raise ValueError("storage width must be a positive integer")
    return value


def accumulate_a(weights, input_sign, bins, samples, true_one=None, count_bits=None):
    """A: unsigned per-sign/bit-plane counters followed by signed reconstruction.

    Counter coordinates are [output][bin][input sign][weight bit]. Bit 7 has
    weight -128, not +128. Counters include every accepted time sample.
    An explicitly insufficient physical width raises OverflowError.
    """
    weights, signs, bins, samples, ones = _validated(weights, input_sign, bins, samples, true_one)
    width = _width(count_bits, required_widths(len(signs), len(samples))["count_bits"])
    limit = (1 << width) - 1
    counts = [[[[0] * 8 for _ in range(2)] for _ in range(BINS)] for _ in weights]
    for sample in samples:
        for i, bit in enumerate(sample):
            if not (bit or ones[i]):
                continue
            for out, row in enumerate(weights):
                code = row[i] & 255  # Signed W8 to its actual two's-complement bits.
                cell = counts[out][bins[i]][signs[i]]
                for p in range(8):
                    cell[p] += (code >> p) & 1
                    if cell[p] > limit:
                        raise OverflowError("A unsigned bit-plane counter overflow")
    result = []
    for output in counts:
        result.append(tuple(sum((cell[0][p] - cell[1][p]) *
                                (1 << p if p < 7 else -128)
                                for p in range(8)) for cell in output))
    return tuple(result)


def accumulate_b(weights, input_sign, bins, samples, true_one=None, sum_bits=None):
    """B: per-sample signed dot contribution into each bin's integer state.

    Overflow is checked after each accepted time sample, not only at the final
    frame boundary. Within-sample reduction uses exact integers; it does not
    assume a physical adder ordering or claim timing for that reduction.
    No floating-point restoration or across-bin weighted fusion is performed.
    """
    weights, signs, bins, samples, ones = _validated(weights, input_sign, bins, samples, true_one)
    width = _width(sum_bits, required_widths(len(signs), len(samples))["sum_bits"])
    low, high = -(1 << (width - 1)), (1 << (width - 1)) - 1
    totals = [[0] * BINS for _ in weights]
    for sample in samples:
        for out, row in enumerate(weights):
            contributions = [0] * BINS
            for i, bit in enumerate(sample):
                if bit or ones[i]:
                    contributions[bins[i]] += row[i] * (-1 if signs[i] else 1)
            for b in range(BINS):
                totals[out][b] += contributions[b]
                if not low <= totals[out][b] <= high:
                    raise OverflowError("B signed bin accumulator overflow")
    return tuple(tuple(output) for output in totals)


def dot_reference(weights, input_sign, bins, samples, true_one=None):
    """Independent scalar dot expansion, without bit planes or shared state."""
    weights, signs, bins, samples, ones = _validated(weights, input_sign, bins, samples, true_one)
    return tuple(tuple(sum(w * (1 - 2 * signs[i])
                           for sample in samples
                           for i, w in enumerate(row)
                           if bins[i] == b and (ones[i] == 1 or sample[i] == 1))
                       for b in range(BINS)) for row in weights)


def diagnose(seed=SEED, random_cases_per_t=12):
    """Reproducible synthetic random and adversarial cases at T16/32/64."""
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(random_cases_per_t) is not int or random_cases_per_t < 0:
        raise ValueError("random_cases_per_t must be a nonnegative integer")
    rng = random.Random(seed)
    cases = []

    def check(label, t, weights, signs, bins, samples, ones):
        a = accumulate_a(weights, signs, bins, samples, ones)
        b = accumulate_b(weights, signs, bins, samples, ones)
        reference = dot_reference(weights, signs, bins, samples, ones)
        if a != b or a != reference:
            raise AssertionError(label + ": integer structure mismatch")
        cases.append({"case": label, "samples": t, "outputs": len(weights),
                      "bin_outputs": len(weights) * BINS, "equal": True})

    for t in (16, 32, 64):
        n = 64
        for sign in (0, 1):
            for bin_id in range(BINS):
                check("extreme_bin%d_sign%d" % (bin_id, sign), t,
                      [[-128] * n, [127] * n, [0] * n], [sign] * n,
                      [bin_id] * n, [[1] * n for _ in range(t)], [0] * n)
        check("true_one_overrides_all_zero_raw", t, [[-128] * n], [1] * n,
              [i % BINS for i in range(n)], [[0] * n for _ in range(t)], [1] * n)
        check("zero_without_true_one", t, [[-128] * n], [1] * n,
              [i % BINS for i in range(n)], [[0] * n for _ in range(t)], [0] * n)
        for case in range(random_cases_per_t):
            weights = [[rng.randrange(-128, 128) for _ in range(n)] for _ in range(4)]
            signs = [rng.randrange(2) for _ in range(n)]
            bins = [i % BINS for i in range(n)]
            rng.shuffle(bins)
            samples = [[rng.randrange(2) for _ in range(n)] for _ in range(t)]
            ones = [int(rng.randrange(8) == 0) for _ in range(n)]
            check("random_%d" % case, t, weights, signs, bins, samples, ones)
    return {
        "scope": "synthetic exact integer functional diagnostic; not RTL/STA/PPA/PPL",
        "seed": seed,
        "preserved_boundary": "four distinct integer bin sums; FP32 restoration unchanged and unexecuted",
        "random_cases_per_t": random_cases_per_t,
        "case_count": len(cases),
        "bin_outputs_checked": sum(case["bin_outputs"] for case in cases),
        "passed": True,
        "widths": {str(t): required_widths(64, t) for t in (16, 32, 64)},
        "cases": cases,
    }


if __name__ == "__main__":
    print(json.dumps(diagnose(), indent=2, ensure_ascii=False))
