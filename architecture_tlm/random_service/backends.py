"""Integer references. Lane 0 and the first generated bit occupy the LSBs."""
import json
from pathlib import Path

MASK = 0x80200003
PROFILES = {
    'lfsr32': dict(state_bits=32, lanes=1, steps=16, warmup=0,
                   correlation='single_word_lfsr; temporal dependence'),
    'lfsr32_shared64': dict(state_bits=32, lanes=64, steps=16, warmup=0,
                   correlation='GF mapping; pairwise state-rank only; NOT 64-way IID'),
    'bivium': dict(state_bits=177, lanes=20, steps=160, warmup=5,
                   correlation='nonlinear deterministic stream; NOT certified IID'),
}
ROWS = [[int(x, 16) for x in row] for row in json.loads(
    (Path(__file__).parent / 'shared64_mapping.json').read_text(encoding='utf-8'))
    ['output_rows_lsb_first']]


def lfsr_step(state):
    return (state >> 1) ^ (MASK if state & 1 else 0)


def generate(kind, state):
    """Return (8-bit words, next_state); does not silently repair invalid seeds."""
    c = PROFILES[kind]
    if not 0 < state < (1 << c['state_bits']):
        raise ValueError('state must be nonzero and fit the selected core')
    if kind != 'bivium':
        words = ([state & 255] if kind == 'lfsr32' else
                 [sum(((state & mask).bit_count() & 1) << bit
                      for bit, mask in enumerate(row)) for row in ROWS])
        for _ in range(16):
            state = lfsr_step(state)
        return tuple(words), state
    a, b = state & ((1 << 93)-1), state >> 93
    out = 0
    for i in range(160):
        t1 = ((a >> 65) ^ (a >> 92)) & 1
        t2 = ((b >> 68) ^ (b >> 83)) & 1
        out |= (t1 ^ t2) << i
        fa = t2 ^ (((b >> 81) & (b >> 82)) & 1) ^ ((a >> 68) & 1)
        fb = t1 ^ (((a >> 90) & (a >> 91)) & 1) ^ ((b >> 77) & 1)
        a = ((a << 1) | fa) & ((1 << 93)-1)
        b = ((b << 1) | fb) & ((1 << 84)-1)
    return tuple((out >> (8*i)) & 255 for i in range(20)), a | (b << 93)

