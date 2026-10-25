"""Timed, finite-record hierarchy diagnostics. No new analog or RTL simulation."""
import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

from ..backends import PROFILES
from ..model import Endpoint, RandomNetwork
from .metrics import bit_metrics, corr, probes, word_metrics

BASE = 'd6d33995754fcdcea99286e4ce43f91647aa231a'
SEEDS = (32003, 32009, 32027)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_bytes((json.dumps(obj, ensure_ascii=False, indent=2,
                                     allow_nan=False)+'\n').encode('utf-8'))


def metrics(bits):
    r = bit_metrics(bits)
    for k in (10, 100, 1000):
        if k < len(bits):
            r['rho'][str(k)] = corr(bits[:-k], bits[k:])
    return r


def conditioned(bits, indices, mode):
    """Indices retain the time of the last raw sample needed for each output."""
    bits = np.asarray(bits, dtype=np.uint8)
    indices = np.asarray(indices, dtype=np.int64)
    if mode == 'raw':
        return bits.copy(), indices.copy()
    if mode != 'vn':
        raise ValueError(mode)
    n = len(bits)//2
    pair = bits[:2*n].reshape(n, 2)
    keep = pair[:, 0] != pair[:, 1]
    return pair[keep, 0].copy(), indices[1:2*n:2][keep].copy()


def packets(bits, indices, cycles_per_sample=100, boot_index=0):
    """32-bit LSB-first words; one idealized clock of collection/CDC latency."""
    n = len(bits)//32
    b = np.asarray(bits[:n*32], dtype=np.uint64).reshape(n, 32)
    idx = np.asarray(indices[:n*32], dtype=np.int64).reshape(n, 32)
    words = (b*(np.uint64(1) << np.arange(32, dtype=np.uint64))).sum(axis=1)
    return [dict(word=int(w), available_cycle=int((i[-1]-boot_index)*cycles_per_sample+1),
                 first_raw_index=int(i[0]), last_raw_index=int(i[-1]), raw_indices=i.tolist())
            for w, i in zip(words, idx)]


class TimedWords:
    """Replay availability, not an implemented conditioner/CDC/FIFO.

    The experiment requests seed material immediately at each boot, so physical
    arrivals are slower than the seed bus. No stored history is used to reseed.
    Exhaustion is explicit; there is no looping, deterministic fill or OS fallback.
    """
    def __init__(self, entries, provenance):
        self.entries = entries
        self.index = 0
        self.transcript = []
        self.provenance = provenance

    @property
    def next_cycle(self):
        if self.index >= len(self.entries):
            raise RuntimeError('finite seed record exhausted')
        return self.entries[self.index]['available_cycle']

    def read(self, cycle):
        if cycle < self.next_cycle:
            return None
        entry = self.entries[self.index]
        self.transcript.append(dict(cycle=cycle, **entry))
        self.index += 1
        return entry['word']


def skip_wait(net, bound):
    """Exact contraction of quiescent wait edges; validated against every tick.

    Only no-command/no-request, ready=true, no response/warmup/packet delivery.
    Stop at the next source arrival or any age becoming due. No PRNG step skipped.
    """
    if net.target is None or any(p.valid or p.warm or p.error or p.locked
            for p in net.ports.values()) or any(g.valid or g.fault for g in net.ingress.values()):
        return 0
    if not net.ingress[net.target].ready(net.ports[net.target].signals()['seed_req']):
        return 0
    delta = min(net.source.next_cycle-net.cycle, bound-net.cycle)
    for p in net.ports.values():
        if p.seeded and p.reseed_cycles and not p.due:
            delta = min(delta, p.reseed_cycles-p.age)
    if delta <= 0:
        return 0
    for p in net.ports.values():
        p.counts['clock_edges'] += delta
        p.counts['seed_wait_cycles'] += delta*int(p.signals()['seed_req'])
        if p.seeded:
            p.age = min(0xffffffff, p.age+delta)
        p.cycle += delta
    net.cycle += delta
    return delta


def simulate(kind, entries, frames=4096, fast=True, provenance='finite diagnostic replay'):
    source = TimedWords(entries, provenance)
    net = RandomNetwork({k: Endpoint(kind, 100_000_000) for k in ('a', 'b')}, source, clock_ns=10)
    arrays = {k: [] for k in net.ports}
    cycles = []
    failure = None
    skipped = 0
    bound = (entries[-1]['available_cycle'] if entries else 0)+frames*4+100
    while net.cycle < bound:
        try:
            ready = all(p.signals()['req_ready'] and not net.ingress[k].valid
                        for k, p in net.ports.items())
            if not ready and fast:
                skipped += skip_wait(net, bound)
            req = {k: [128]*p.profile['lanes'] for k, p in net.ports.items()} if ready else {}
            cycle = net.cycle
            out = net.tick(req)
        except RuntimeError as e:
            failure = str(e)
            break
        if out['a']['accepted'] != out['b']['accepted']:
            raise AssertionError('unpaired frame acceptance')
        if out['a']['accepted']:
            cycles.append(cycle)
            for k in arrays:
                arrays[k].append(out[k]['words'])
        if len(cycles) == frames:
            net.tick()  # consume the last registered response
            break
    if len(cycles) != frames and failure is None:
        failure = 'bounded replay incomplete'
    a = np.asarray(arrays['a'], dtype=np.uint8).reshape(-1, PROFILES[kind]['lanes'])
    b = np.asarray(arrays['b'], dtype=np.uint8).reshape(-1, PROFILES[kind]['lanes'])
    result = dict(status='complete' if len(cycles) == frames else 'incomplete', failure=failure,
                  cycles=net.cycle, idle_edges_contracted=skipped, network=net.report())
    result['loaded_seed_diagnostics'] = []
    width = PROFILES[kind]['state_bits']
    for event in net.seed_events:
        state = int(event['seed_hex'], 16)
        state_bits = np.asarray([(state >> i) & 1 for i in range(width)], dtype=np.uint8)
        result['loaded_seed_diagnostics'].append(dict(port=event['port'], cycle=event['cycle'],
            rejected=event['rejected'], state_bits=width, bus_bits=((width+31)//32)*32,
            padding_bits_discarded=(-width)%32, metrics=metrics(state_bits),
            caveat='short serialized state only; not a seed entropy estimate or full input-window statistic'))
    if len(a) >= 256:
        result.update(output=word_metrics(a), endpoint_b_output=word_metrics(b), probes=probes(a, b))
        q = max(1, round(256/a.shape[1]))
        hits = (a < q).sum(axis=1)
        prob = q/256
        result['sparse_proposal'] = dict(q=q, lanes=a.shape[1],
            one_hit_rate=float(np.mean(hits == 1)),
            iid_one_hit_reference=float(a.shape[1]*prob*(1-prob)**(a.shape[1]-1)),
            all_zero_rate=float(np.mean(hits == 0)),
            iid_all_zero_reference=float((1-prob)**a.shape[1]))
        first = a[:, :4] < 128
        patterns = (first.astype(np.uint8)*(1 << np.arange(first.shape[1]))).sum(axis=1)
        result['joint'] = dict(first_four_q128_xor_one_fraction=float(
            np.logical_xor.reduce(first, axis=1).mean()) if a.shape[1] >= 4 else None,
            first_four_pattern_counts=np.bincount(patterns.astype(int), minlength=16).tolist() if a.shape[1] >= 4 else None,
            common_first_four_pair_rho=[corr(first[:, i], first[:, j])
                for i in range(first.shape[1]) for j in range(i+1, first.shape[1])],
            interpretation='GF64 first four q128 bits obey exact XOR=0; small pair correlations do not imply joint independence')
    return result, a, b, np.asarray(cycles, dtype=np.int64)


def read_inputs(directory):
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for name, rec in manifest.items():
        p = directory/name
        if p.stat().st_size != rec['bytes'] or digest(p) != rec['sha256']:
            raise ValueError('input changed: '+name)
    summary = json.loads((directory/'SUMMARY.json').read_text(encoding='utf-8'))
    inputs = []
    for seed in SEEDS:
        with (directory/f'seed{seed}_samples.csv').open(encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        timestamps = np.asarray([float(r['time_s']) for r in rows])
        assert len(rows) == 20000 and np.allclose(timestamps, .002+np.arange(20000)*1e-6, rtol=0, atol=1e-12)
        assert [int(r['sample_index']) for r in rows] == list(range(20000))
        for label, suffix, column in [('ideal','ideal_0p6V','ideal_0p6V_bit'),
                                       ('old','old_comparator_threshold','old_threshold_bit')]:
            bits = np.loadtxt(directory/f'seed{seed}_{suffix}.txt', dtype=np.uint8)
            assert len(bits) == 20000 and np.isin(bits, [0, 1]).all()
            assert np.array_equal(bits, [int(r[column]) for r in rows])
            expected = [float(r['core_V']) > .6 if label == 'ideal'
                        else float(r['old_comparator_V']) > .4 for r in rows]
            assert np.array_equal(bits, expected)
            inputs.append((label, seed, bits, timestamps))
        for r in rows:
            v = float(r['old_comparator_V'])
            assert bool(int(r['old_level_valid'])) == (v <= .16 or v >= .64)
        bits = np.random.Generator(np.random.PCG64(seed)).integers(0, 2, 20000, dtype=np.uint8)
        inputs.append(('iid', seed, bits, timestamps))
    return inputs, dict(directory=str(directory), manifest=manifest, summary=summary,
                        manifest_sha256=digest(directory/'manifest.json'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--raw-out', type=Path, required=True)
    p.add_argument('--frames', type=int, default=4096)
    a = p.parse_args()
    if a.frames < 256 or a.frames % 128:
        raise ValueError('frames >=256 and divisible by128')
    if a.out.exists() or a.raw_out.exists():
        raise FileExistsError('Use new immutable output directories')
    inputs, evidence = read_inputs(a.input)
    a.out.mkdir(parents=True)
    a.raw_out.mkdir(parents=True)
    root = Path(__file__).resolve().parents[3]
    paths = [Path(__file__), Path(__file__).with_name('metrics.py')]
    paths += [root/'architecture_tlm/random_service'/name for name in ('backends.py','model.py','shared64_mapping.json')]
    source = {p.relative_to(root).as_posix(): digest(p) for p in paths}
    config = dict(base_commit=BASE, seeds=list(SEEDS), input_samples=20000, sample_interval_ns=1000,
        clock_ns=10, physical_origin_s=.002, window_samples=5000, cold_boot_windows=4,
        frames_per_boot_endpoint=a.frames, modes=['raw','vn'], backends=list(PROFILES),
        reseed_cycles=100_000_000, periodic_reseed_observed=False,
        source_transport='32bit arrives after last constituent sample +1 idealized clock; no health/CDC RTL or unlimited queue claim',
        boot_policy='four separate cold boots at fixed 0/5/10/15ms offsets; fresh non-overlapping seed material, not period reseed',
        iid='NumPy PCG64 deterministic statistical control, not physical entropy',
        scope='diagnostic local probes; no whole FFN/Attention/LLM/PPA/entropy qualification')
    dump(a.out/'CONFIG.json', config)
    dump(a.out/'SOURCE_MANIFEST.json', source)
    dump(a.out/'INPUT_MANIFEST.json', evidence)
    rows = []
    stages = []
    started = time.monotonic()
    for label, seed, bits, timestamps in inputs:
        for mode in config['modes']:
            output, indices = conditioned(bits, np.arange(len(bits)), mode)
            packed = packets(output, indices)
            decoded = np.asarray([((e['word'] >> k) & 1) for e in packed for k in range(32)], dtype=np.uint8)
            assert np.array_equal(decoded, output[:len(decoded)])
            stages.append(dict(source=label, seed=seed, mode=mode, raw=metrics(bits),
                conditioned=metrics(output), seed_serialized=metrics(decoded), retained_ratio=len(output)/len(bits),
                qualified_claim=False, available_words=len(packed), discarded_tail=len(output)%32,
                packed_unique_words=len({e['word'] for e in packed}), packed_zero_words=sum(e['word']==0 for e in packed),
                conditioned_gap_us=dict(min=float(np.diff(indices).min()),max=float(np.diff(indices).max()),mean=float(np.diff(indices).mean())),
                rho_time_axis='raw:1us; VN/packed:adjacent retained output indices, varying physical interval'))
            for kind in config['backends']:
                for boot in range(4):
                    start = boot*5000
                    conditioned_bits, idx = conditioned(bits[start:start+5000], np.arange(start,start+5000), mode)
                    entries = packets(conditioned_bits, idx, boot_index=start)
                    case = f'{label}-{seed}-{mode}-{kind}-boot{boot}'
                    result, x, y, cycles = simulate(kind, entries, a.frames,
                        provenance=f'{label}/{seed}, raw indices {start}..{start+4999}, {mode}; diagnostic assumption only')
                    file = a.raw_out/(case+'.npz')
                    np.savez_compressed(file, a=x, b=y, accepted_cycles=cycles,
                                        conditioned_bits=conditioned_bits, raw_indices=idx)
                    rows.append(dict(case_id=case, source=label, seed=seed, mode=mode, backend=kind,
                        boot=boot, raw_start_index=start, physical_boot_s=float(timestamps[start]),
                        artifact=dict(path=str(file),sha256=digest(file),bytes=file.stat().st_size),**result))
        print(label, seed, len(rows), round(time.monotonic()-started,1), flush=True)
    # Same material for both endpoints: intentional synchronization fault control.
    for seed in SEEDS:
        bits = next(bits for label,s,bits,t in inputs if label=='iid' and s==seed)
        for kind in config['backends']:
            beats = (PROFILES[kind]['state_bits']+31)//32
            entries = packets(bits, np.arange(20000))[:2*beats]
            for i in range(beats):
                entries[i+beats]['word'] = entries[i]['word']
            result, x, y, cycles = simulate(kind, entries, a.frames, provenance='intentional repeated seed fault; not physical transport')
            case = f'duplicate-{seed}-{kind}'
            file = a.raw_out/(case+'.npz')
            np.savez_compressed(file,a=x,b=y,accepted_cycles=cycles)
            rows.append(dict(case_id=case,source='duplicate',seed=seed,mode='raw',backend=kind,boot=0,
                artifact=dict(path=str(file),sha256=digest(file),bytes=file.stat().st_size),**result))
    dump(a.out/'STAGES.json', stages)
    dump(a.out/'RESULTS.json', dict(config_sha256=digest(a.out/'CONFIG.json'),
        source_manifest_sha256=digest(a.out/'SOURCE_MANIFEST.json'), cases=rows,
        environment=dict(python=sys.version,numpy=np.__version__,platform=platform.platform()),
        seconds=time.monotonic()-started))
    print(json.dumps(dict(cases=len(rows),complete=sum(r['status']=='complete' for r in rows),
                         seconds=time.monotonic()-started)),flush=True)


if __name__ == '__main__':
    main()
