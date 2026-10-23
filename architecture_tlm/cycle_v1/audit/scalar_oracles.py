"""Independent scalar numerical oracles for frozen, prequantized fixtures.

No cycle_v1 implementation module is imported here. Counts are compressed per
input lane, unlike the implementation's frame-by-frame row accumulation. The
rounding boundaries are the explicitly declared prototype contract, not a claim
of equivalence to a PyTorch reduction tree or synthesized arithmetic datapath.
"""
import math
import random
import struct
from fractions import Fraction


def f32(value):
    return struct.unpack("!f", struct.pack("!f", float(value)))[0]


def rational_f32(value):
    """Round an exact rational to binary32, including subnormals, using integers.

    The inputs used by this oracle stay below binary32 overflow. This does not
    reuse the implementation's host-float arithmetic or struct-pack rounding.
    """
    value = Fraction(value)
    negative = value < 0
    value = abs(value)
    if not value:
        return 0.0
    exponent = value.numerator.bit_length()-value.denominator.bit_length()
    unit = Fraction(2)**exponent
    if value < unit:
        exponent -= 1
    quantum_exponent = max(exponent-23, -149)
    scaled = value / Fraction(2)**quantum_exponent
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    if 2*remainder > scaled.denominator or (2*remainder == scaled.denominator and quotient & 1):
        quotient += 1
    result = math.ldexp(float(quotient), quantum_exponent)
    return -result if negative else result


def scalar_restore(integer, activation_scale, weight_scale, samples, rounding="host_order"):
    scale = Fraction(activation_scale)
    weight = Fraction(weight_scale)
    if rounding == "host_order":
        first = rational_f32(integer*scale)
        result = rational_f32(Fraction(first)*weight/samples)
    elif rounding == "rtl_fused0_order":
        first = rational_f32(integer*scale/samples)
        result = rational_f32(Fraction(first)*weight)
    else:
        raise ValueError("unknown scalar restoration profile")
    # Fraction has no signed zero; both positive scales preserve integer sign.
    return -0.0 if result == 0 and integer < 0 else result


def bfloat16(value):
    raw = struct.unpack("!I", struct.pack("!f", f32(value)))[0]
    exponent = raw & 0x7f800000
    if exponent == 0x7f800000:
        return f32(value)
    high, low = raw >> 16, raw & 65535
    if low > 32768 or (low == 32768 and high & 1):
        high += 1
    return struct.unpack("!f", struct.pack("!I", (high << 16) & 0xffffffff))[0]


def frozen_thresholds(input_width, hidden_width, *, samples=32, strata=32, seed=617):
    rng = random.Random(seed)
    width = 256 // strata
    return {phase: [[stratum*width+rng.randrange(width)
                     for stratum in range(strata) for _ in range(samples//strata)]
                    for _ in range((size+63)//64)]
            for phase, size in (("x", input_width), ("z", hidden_width))}


def _encoding_counts(values, thresholds, bins):
    values = list(map(f32, values))
    peak = max(map(abs, values))
    if peak == 0:
        top = 1.0
    else:
        bits = struct.unpack("!I", struct.pack("!f", peak))[0]
        exponent, fraction = (bits >> 23) & 255, bits & 0x7fffff
        if exponent:
            top = f32(2.0 ** (exponent-127+int(bool(fraction))))
        else:
            top = 2.0 ** math.ceil(math.log2(peak))
    result = []
    for value in values:
        selected, scale = 0, top
        for index in range(1, bins):
            candidate = max(f32(top / (4**index)), 2.0**-126)
            if abs(value) <= candidate:
                selected, scale = index, candidate
        full = value != 0 and abs(value) >= scale
        q = min(255, max(0, round(rational_f32(Fraction(abs(value))*256/Fraction(scale)))))
        magnitude_count = len(thresholds) if full else sum(word < q for word in thresholds)
        signed_count = magnitude_count * ((value > 0) - (value < 0))
        result.append((selected, scale, signed_count))
    return result


def scalar_ffn(fixture, *, samples=32, bins=4, output_bf16=True, restore_rounding="host_order"):
    """Exact prototype scalar contract from explicit W8/scales/threshold words.

    Inputs must be prequantized; raw weight quantizer correctness is a different
    interface. The oracle does not share the implementation's encoder, sample
    accumulator, restoration helper, PRNG, scheduler, memory, or reference_ffn.
    """
    if "thresholds" not in fixture:
        raise ValueError("oracle requires explicit frozen thresholds")
    for name in ("wg", "wu", "wd"):
        if not isinstance(fixture[name], dict):
            raise ValueError("oracle requires prequantized W8 matrices")

    def projection(vector, phase, matrix):
        result = [0.0] * len(matrix["codes"])
        for start in range(0, len(vector), 64):
            group = start // 64
            words = fixture["thresholds"][phase][group]
            if len(words) != samples:
                raise ValueError("threshold count does not match sample budget")
            encoded = _encoding_counts(vector[start:start+64], words, bins)
            for row, weights in enumerate(matrix["codes"]):
                block_total = 0.0
                for bin_index in range(bins):
                    lanes = [(offset, scale, count) for offset, (b, scale, count) in enumerate(encoded) if b == bin_index]
                    integer = sum(count*weights[start+offset] for offset, _, count in lanes)
                    scale = lanes[0][1] if lanes else 0.0
                    restored = scalar_restore(integer, scale, f32(matrix["scales"][row//64][group]), samples, restore_rounding)
                    block_total = f32(block_total+restored)
                result[row] = f32(result[row]+block_total)
        return result

    gate = projection(fixture["x"], "x", fixture["wg"])
    up = projection(fixture["x"], "x", fixture["wu"])
    z = []
    for g, u in zip(gate, up):
        if g >= 0:
            probability = 1 / (1+math.exp(-g))
        else:
            exponent = math.exp(g)
            probability = exponent / (1+exponent)
        z.append(f32(f32(g*f32(probability))*u))
    projected = projection(z, "z", fixture["wd"])
    residual = fixture.get("residual", [0.0]*len(projected))
    if output_bf16:
        output = [bfloat16(f32(bfloat16(value)+f32(skip))) for value, skip in zip(projected, residual)]
    else:
        output = [f32(value+f32(skip)) for value, skip in zip(projected, residual)]
    return dict(gate=gate, up=up, z=z, projected=projected, output=output)
