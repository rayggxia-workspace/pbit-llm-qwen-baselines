"""Offline finite workloads plus original exceptional-value regression."""
import gzip
import json
import random
import types
from package import KINDS, sha


def reference(root):
    r = types.ModuleType('exact_ref')
    exec(compile((root/'reference/reference.py').read_text(), 'reference.py', 'exec'), r.__dict__)
    v = types.ModuleType('original_reference')
    text = (root/'reference/original_validate.py').read_text()
    # Keep the archived source untouched; use only its pure reference functions.
    a, b = text.index('def fbits'), text.index('\ndef run(')
    import math
    import struct
    v.__dict__.update(R=r, random=random, math=math, struct=struct)
    exec(compile(text[a:b], 'original_validate.py', 'exec'), v.__dict__)
    return v


def finite(v, kind, seed):
    rng = random.Random(seed)
    rows, gold = [], []
    # Complete accumulation frames, including real S=128/512 and short frames.
    frames = [1, 14, 76, 128, 512] if kind in (2, 8) else [256]
    for length in frames:
        state = 0
        for i in range(length):
            a, b = v.fbits(rng.uniform(-4, 4)), v.fbits(rng.uniform(-2, 2))
            u0, u1, e, mean = v.fbits(.03125), 0, rng.randint(-4, 4), 7 if length != 512 else 9
            first, last = i == 0, i == length-1
            if kind == 0:
                y = v.add(a, b)
            elif kind == 21:
                y = v.R.evaluate(6, a, 0, 0, 0, 0)[0]
            elif kind in (2, 8):
                a >>= 16
                b >>= 16
                op = a << 16 if kind == 8 else v.mul(a << 16, b << 16)
                state = v.add(0 if first else state, op)
                y = state if kind == 2 else v.scaled(state, -mean, 7)
            elif kind in (4, 5):
                words = [v.fbits(rng.uniform(-8, 8)*2**rng.randint(-6, 3)) for _ in range(64)]
                if kind == 4:
                    words = [x >> 16 for x in words]
                a = sum(x << ((16 if kind == 4 else 32)*j) for j, x in enumerate(words))
                b = 0
                y = v.encoder(words, 7 if kind == 4 else 23)
            elif kind == 6:
                counts = [rng.randint(0, 2048) for _ in range(64)]
                a = sum(x << (12*j) for j, x in enumerate(counts))
                b = 0
                y = 0
                for bn in range(4):
                    n = sum((counts[bn*16+j]-counts[bn*16+8+j]) * (-1 if j == 7 else 1)*(1 << j) for j in range(8))
                    y = v.add(y, v.mul(v.R.pack(n, e-2*bn-5, 23)[0], u0))
            elif kind == 7:
                y = v.mul(v.mul(a, v.unary(a, 0)), b)
            rows.append((1, int(first), int(last), a, b, u0, u1, e & 65535, mean))
            if kind not in (2, 8) or last:
                gold.append(y)
    return rows, gold


def generate(root):
    v = reference(root)
    dest = root/'vectors'
    dest.mkdir()
    cases = []
    for kind in KINDS:
        for seed in (17, 43, 101):
            stress, stress_gold = v.vectors(kind, seed)
            stream, gold = finite(v, kind, seed)
            burst = []
            for i, row in enumerate(stream):
                burst.append(row)
                if i % 16 == 15:
                    burst.extend([(0,)*9]*48)
            # Warmup settles all used state; idle measurement uses quiet input pins.
            idle = stream + [(0,)*9]*256
            for mode, data, expected in [('stress', stress, stress_gold), ('stream', stream, gold),
                                          ('burst', burst, gold), ('idle', idle, gold)]:
                name = 'k{}_s{}_{}'.format(kind, seed, mode)
                raw = ''.join(' '.join(format(x, 'x') for x in row)+'\n' for row in data).encode('ascii')
                with (dest/(name+'.hex.gz')).open('wb') as f:
                    with gzip.GzipFile(filename='', mode='wb', fileobj=f, mtime=0) as z:
                        z.write(raw)
                (dest/(name+'.gold')).write_text(''.join(format(x, 'x')+'\n' for x in expected))
                cases.append(dict(name=name, kind=kind, seed=seed, mode=mode, rows=len(data),
                    inputs=sum(x[0] for x in data), outputs=len(expected),
                    idle_start_row=len(stream)+16 if mode == 'idle' else None,
                    frame_lengths=([1, 14, 76, 128, 512] if kind in (2, 8) else None),
                    gold_sha256=sha(dest/(name+'.gold'))))
    (dest/'cases.json').write_text(json.dumps(cases, indent=2)+'\n')
