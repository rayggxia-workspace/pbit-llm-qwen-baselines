"""Deterministic synthetic workload, exact integer oracle; Python 3.6+."""
import json
import pathlib
import random
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from golden_model import evaluate, sigmoid_raw


def generate(folder, profile, mode, seed, cycles=4096):
    if profile not in ('full', 'central') or mode not in ('active', 'burst', 'idle'):
        raise ValueError('Unknown workload')
    if cycles < 256:
        raise ValueError('Use at least 256 measured cycles')
    rng = random.Random(seed)
    pipe = [None] * 3
    held = (0, 0, 0)
    lines = []
    accepted = produced = clamped = 0
    # All windows start with a warmed datapath and an empty pipeline.
    warmup = 72
    for i in range(warmup + cycles + 8):
        g = rng.randrange(-32768, 32768) if profile == 'full' else rng.randrange(-8191, 8192)
        u = rng.randrange(-32768, 32768)
        j = i - warmup
        valid = int(i < 64) if i < warmup else int(0 <= j < cycles and
                    (mode == 'active' or (mode == 'burst' and j % 256 < 64)))
        old = pipe.pop()
        if old is not None:
            held = evaluate(*old)
        pipe.insert(0, (g, u) if valid else None)
        if i >= warmup:
            accepted += valid
            produced += int(old is not None)
            clamped += int(valid and sigmoid_raw(g) in (0, 65536))
        lines.append('{} {} {} {} {} {} {}'.format(valid, g, u, int(old is not None), *held))
    assert accepted == produced
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'vectors.txt').write_bytes(('\n'.join(lines) + '\n').encode('ascii'))
    meta = dict(profile=profile, mode=mode, seed=seed, measured_cycles=cycles,
                warmup_cycles=warmup, drain_cycles=8, rows=len(lines),
                start_ns=40 + warmup * 10, end_ns=40 + len(lines) * 10,
                duration_ns=(cycles + 8) * 10, accepted=accepted, produced=produced,
                sigmoid_clamped_inputs=clamped, input_kind='synthetic_not_model_trace',
                clock_MHz=100, out_width=24, ce=1)
    (folder / 'workload.json').write_text(json.dumps(meta, indent=2) + '\n')
    return meta
