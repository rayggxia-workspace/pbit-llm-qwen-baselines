"""Small opt-in frontends for the Issue95 service, not a full-decode backend.

They preserve the v6 q/256 + exact-one input encoding. Output is streamed one
frame at a time; no hardware random-sequence SRAM is implied. SAVE/RESTORE and
RELEASE are controlled by the caller across all output waves of one input group.
The parent FullDecode default is deliberately unchanged.
"""
import math


def stratified_shared64(port, codes, samples=32, strata=32):
    """Yield one common R8 threshold and 64 comparator bits per sample.

    For K32 this is {stratum[4:0], R[2:0]}, NOT a uniform R8 comparison.
    Natural PRNG output supplies the within-stratum jitter; an ordinary counter
    supplies the stratum. This does not certify IID randomness or inherit PPL.
    """
    if (type(samples) is not int or type(strata) is not int or samples < 1
            or strata < 1 or strata > 256 or strata & (strata-1)
            or samples % strata):
        raise ValueError('positive T divisible by power-of-two K <= 256 required')
    if len(codes) != 64 or any(type(c['q']) is not int or not 0 <= c['q'] <= 255
                               or type(c['one']) is not bool for c in codes):
        raise ValueError('64 existing q8 + exact-one input codes required')
    if port.endpoint.kind != 'lfsr32':
        raise ValueError('one common word shared by all64, not64 distinct GF words')
    width = 256//strata
    for k in range(strata):
        for _ in range(samples//strata):
            response = port.frame()
            threshold = k*width+(response['words'][0] & (width-1))
            bits = tuple(c['one'] or threshold < c['q'] for c in codes)
            port.counts['frontend_comparisons'] += 64
            port.counts['stratum_counter_updates'] += 1
            port.counts['within_stratum_bits_used'] += int(math.log2(width))
            # The native endpoint's unused comparison remains in its ledger.
            yield dict(threshold=threshold, bits=bits,
                       valid_cycle=response['valid_cycle'], epoch=response['epoch'])


def uniform32(port):
    """Pack fresh native bytes, little-endian; charge every accepted frame.

    A single-word LFSR endpoint needs4 successive frames. A Bivium endpoint can
    deliver this in1 frame, but its remaining16 bytes still toggle/count.
    """
    value, used, start = 0, 0, port.network.cycle
    while used < 4:
        response = port.frame()
        for word in response['words']:
            if used < 4:
                value |= word << (8*used)
                used += 1
            else:
                port.counts['unused_native_bytes'] += 1
    port.counts['uniform32_calls'] += 1
    return dict(value=value, valid_cycle=port.network.cycle,
                service_cycles=port.network.cycle-start)
