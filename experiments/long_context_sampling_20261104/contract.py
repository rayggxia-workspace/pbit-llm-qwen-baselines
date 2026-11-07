"""Bounded, label-independent plans; no Torch/CUDA import."""
import hashlib
import math
import struct

CONTEXTS = (8192, 32768)
SAMPLES = (32, 64, 128, 256)
SEEDS = (0, 1, 2)
EXAMPLES = 4
DECODE = 32


def ids_sha(values):
    return hashlib.sha256(b''.join(struct.pack('<q', int(x)) for x in values)).hexdigest()


def common_plan(token_count, context, examples=EXAMPLES, decode=DECODE,
                anchor=32768):
    if not (3 <= context <= anchor and examples > 0 and decode > 0):
        raise ValueError('invalid context/plan budget')
    last = token_count - decode
    if last < anchor:
        raise ValueError('corpus shorter than common anchor plus suffix')
    firsts = [anchor] if examples == 1 else [
        anchor + round((last-anchor)*i/(examples-1)) for i in range(examples)]
    positions = [p for first in firsts for p in range(first, first+decode)]
    if len(set(positions)) != len(positions):
        raise ValueError('target suffixes overlap')
    return [dict(segment_id=i, begin=first-context, end=first+decode,
                 first_target=first, last_target_exclusive=first+decode,
                 prefill_tokens=context-1, scored_tokens=decode)
            for i, first in enumerate(firsts)]


def cases(context, seed):
    if context not in CONTEXTS or seed not in SEEDS:
        raise ValueError('unsupported pilot configuration')
    k = 256 if context == 8192 else 512
    rows = [dict(name='BF16', k=None, s=None, mode=None)]
    if seed == 0:
        rows += [dict(name=f'K{n}_exact', k=n, s=None, mode='exact')
                 for n in (k, k*2)]
    rows += [dict(name=f'K{k}_WH_S{s}', k=k, s=s, mode='winner')
             for s in SAMPLES]
    rows += [dict(name=f'K{k*2}_WH_S128', k=k*2, s=128, mode='winner')]
    return rows


def lut_reference():
    return [math.floor(256/(1+math.exp(a/16))) for a in range(256)]


def scalar_front(scores, lut):
    codes = [max(-2048, min(2047, round(x*16))) for x in scores]
    maximum = max(codes)
    addresses = [min(255, maximum-c) for c in codes]
    return codes, addresses, [lut[a] for a in addresses]
