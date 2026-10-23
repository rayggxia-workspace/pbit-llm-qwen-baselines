"""Independent scalar full-FFN oracle for the explicit PR122 finite contract.

No production encoder, counter, restore, PRNG or scheduler routine is imported.
The encoder uses integer significands; per-lane accepted counts are contracted
with signed W8 directly. FP32 stages round separately using binary64, which
exactly contains each finite product of two FP32 significands. This is a
numerical oracle, not RTL/STA evidence or equivalence to the BF16 source model.
"""
import math
import struct


def f32(value):
    try:
        return struct.unpack('<f', struct.pack('<f', value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


def bf16(value):
    bits = struct.unpack('<I', struct.pack('<f', value))[0]
    if bits & 0x7f800000 != 0x7f800000:
        bits = (bits + 0x7fff + ((bits >> 16) & 1)) & 0xffff0000
    return struct.unpack('<f', struct.pack('<I', bits))[0]


def encoded_counts(values, thresholds):
    raw = [struct.unpack('<I', struct.pack('<f', value))[0] for value in values]
    if any((v >> 23) & 255 == 255 for v in raw):
        raise ValueError('independent encoder requires finite FP32 inputs')
    def decode(bits):
        exponent, fraction = (bits >> 23) & 255, bits & 0x7fffff
        return ((1 << 23) | fraction, exponent-150) if exponent else (fraction, -149)
    n, e = decode(max(v & 0x7fffffff for v in raw))
    top = n.bit_length()-1+e+int(bool(n & (n-1))) if n else 0
    result = []
    for bits in raw:
        n, e = decode(bits)
        b = 0
        for candidate in (1, 2, 3):
            delta = top-2*candidate-e
            if (n << max(0, -delta)) <= (1 << max(0, delta)):
                b = candidate
        shift = e+8-top+2*b
        if shift >= 0:
            q = n << shift
        else:
            q, remainder = divmod(n, 1 << -shift)
            halfway = 1 << (-shift-1)
            q += remainder > halfway or (remainder == halfway and q & 1)
        q = min(255, q)
        delta = top-2*b-e
        one = n != 0 and (n << max(0, -delta)) >= (1 << max(0, delta))
        accepted = len(thresholds) if one else sum(t < q for t in thresholds)
        result.append((b, -accepted if bits >> 31 else accepted))
    return top, result


def reference(fixture, config):
    """Require prequantized W8 and observed/replayed x/z thresholds."""
    if 'thresholds' not in fixture:
        raise ValueError('independent oracle requires actual frozen threshold words')
    if any(not isinstance(fixture[name], dict) for name in ('wg','wu','wd')):
        raise ValueError('independent PR122 oracle requires prequantized W8 matrices')
    def projection(vector, phase, matrix):
        encoded = []
        for group, start in enumerate(range(0, len(vector), 64)):
            thresholds = fixture['thresholds'][phase][group]
            if len(thresholds) != config.samples:
                raise ValueError('threshold coverage differs from configured T')
            top, counts = encoded_counts(vector[start:start+64], thresholds)
            encoded.append((top, [[(i, count) for i, (b, count) in enumerate(counts)
                                   if b == which] for which in range(4)]))
        outputs = []
        for row, weights in enumerate(matrix['codes']):
            total = 0.0
            for group, (top, bins) in enumerate(encoded):
                partial = 0.0
                for b, lanes in enumerate(bins):
                    integer = sum(weights[group*64+i]*count for i, count in lanes)
                    # Match the existing rtl_fused0_order hook's finite path:
                    # division by T belongs to fixed->FP32 conversion.
                    converted = f32(math.ldexp(integer, top-2*b-(config.samples.bit_length()-1)))
                    restored = f32(converted*f32(matrix['scales'][row//64][group]))
                    partial = f32(partial+restored)
                total = f32(total+partial)
            outputs.append(total)
        return outputs
    gate = projection(fixture['x'], 'x', fixture['wg'])
    up = projection(fixture['x'], 'x', fixture['wu'])
    z = []
    for g, u in zip(gate, up):
        if g >= 0:
            probability = 1/(1+math.exp(-g))
        else:
            ex = math.exp(g)
            probability = ex/(1+ex)
        z.append(f32(f32(g*f32(probability))*u))
    projected = projection(z, 'z', fixture['wd'])
    residual = fixture.get('residual', [0.0]*len(projected))
    output = [bf16(f32(bf16(v)+f32(r))) if config.output_bf16 else f32(v+f32(r))
              for v, r in zip(projected, residual)]
    return dict(gate=gate, up=up, z=z, projected=projected, output=output)
