"""FP64 mathematical references on BF16 QKV storage; not bit-true MAC RTL.

Reuse the merged PR88 samplers, including every rejection, fair-rank retry,
configuration update and cap. The same candidate set feeds P1--P4.
"""
from collections import Counter
from pathlib import Path
import math
import random
import sys
import numpy as np

_ARCH = Path(__file__).resolve().parents[1]
if str(_ARCH) not in sys.path:
    sys.path.insert(0, str(_ARCH))
from corrected_rejection_tlm_v5 import CorrectedRejectionSampler
from winner_hold_tlm_v5 import WinnerHoldSampler
from parallel_sampler_v5 import SamplingCapError

MODES = ('D0', 'P0', 'P1', 'P2', 'P3', 'P4')


def bf16(x):
    a = np.asarray(x, dtype=np.float32).copy()
    u = a.view(np.uint32)
    u[:] = (u + np.uint32(0x7fff) + ((u >> 16) & 1)) & np.uint32(0xffff0000)
    return a.astype(np.float64)


def inputs(q, k, v):
    q, k, v = [np.asarray(a, dtype=np.float64) for a in (q, k, v)]
    if q.ndim != 1 or k.ndim != 2 or k.shape != v.shape or k.shape[1] != q.size or not k.shape[0]:
        raise ValueError('one query and matching nonempty K/V')
    if not all(np.isfinite(a).all() for a in (q, k, v)):
        raise ValueError('finite QKV required')
    return q, k, v


def softmax(z):
    w = np.exp(z - np.max(z))
    return w / w.sum()


def online(q, k, v, tile=64):
    """Unnormalized online max/sum/output; no full probability-row storage."""
    q, k, v = inputs(q, k, v)
    if type(tile) is not int or tile < 1:
        raise ValueError('positive tile')
    m, mass, acc = -math.inf, 0., np.zeros(q.size)
    for start in range(0, len(k), tile):
        z = k[start:start+tile] @ q / math.sqrt(q.size)
        new_m = max(m, float(z.max()))
        alpha = math.exp(m-new_m)
        w = np.exp(z-new_m)
        acc = alpha*acc + w @ v[start:start+tile]
        mass = alpha*mass + w.sum()
        m = new_m
    return acc/mass


def screen(q, k, rng, budget=8, block=64):
    """max4 + standardized sigmoid + Bernoulli/quota repair, synthetic calibration.

    Summaries must be maintained with KV append. Full-K preprocessing here is
    a test fixture, NOT a free operation in the proposed warm-cache datapath.
    No calibrated Qwen quality is claimed for the fixed center=0/temperature=1.
    """
    n, d = k.shape
    scores, summary_vectors = [], 0
    for start in range(0, n, block):
        parts = [a for a in np.array_split(k[start:start+block], 4) if len(a)]
        scores.append(max(float(a.mean(0) @ q / math.sqrt(d)) for a in parts))
        summary_vectors += len(parts)
    scores = np.asarray(scores)
    standardized = (scores-scores.mean()) / max(float(scores.std()), 1e-12)
    selected = set(np.flatnonzero(rng.random(len(scores)) < 1/(1+np.exp(-standardized))).tolist())
    forced = {0, len(scores)-1, max(0, len(scores)-2)}
    target = min(len(scores), budget)
    if target < len(forced):
        raise ValueError('budget must include first and last two blocks')
    # Same quota repair ordering as PR88 budget_blocks; ties use lower block id.
    ranked = sorted(range(len(scores)), key=lambda i: (i in forced, i in selected, scores[i], -i), reverse=True)
    kept = sorted(ranked[:target])
    ids = np.array([i for b in kept for i in range(b*block, min(n, (b+1)*block))], dtype=np.int64)
    return ids, dict(summary_vectors=summary_vectors, summary_read_bytes=summary_vectors*d*2,
                     summary_dot_MAC=summary_vectors*d, blocks=len(scores), selected_blocks=kept,
                     repair_sort_comparisons_upper=len(scores)*math.ceil(math.log2(max(2, len(scores)))),
                     cold_build_K_bytes=n*d*2, cold_build_adds=(n-summary_vectors)*d,
                     append_summary_adds=d, append_summary_write_bytes=d*2,
                     calibration='synthetic center0 temperature1; NOT trained max4 calibration')


def systematic(p, samples, rng):
    if type(samples) is not int or samples < 1:
        raise ValueError('positive samples')
    cdf = np.cumsum(p)
    cdf[-1] = 1.
    return np.searchsorted(cdf, (rng.random()+np.arange(samples))/samples, side='right')


def gather(v, ids):
    """Read each unique V vector once; retain multiplicity via repeated addition."""
    counts = Counter(map(int, ids))
    if not counts:
        raise ValueError('nonempty trajectory')
    out = np.zeros(v.shape[1])
    for address, count in sorted(counts.items()):
        value = v[address]  # one finite vector holding register
        for _ in range(count):
            out += value
    return out/len(ids), counts


def bursts(ids, d, burst=64):
    """Physical aligned burst set, including row tails and shared burst overlap."""
    rowbytes = d*2
    return sorted({b for i in set(map(int, ids))
                   for b in range((i*rowbytes)//burst, ((i+1)*rowbytes-1)//burst+1)})


def kv_union(head_rows, d, burst=64):
    """Same-KV-group GQA union utility; no cross-group reuse implied."""
    return len({b for rows in head_rows for b in bursts(rows, d, burst)})*burst


def compare(q, k, v, samples, seed, tile=64, budget=8, burn=32, record_events=False):
    q, k, v = inputs(q, k, v)
    ids, screen_cost = screen(q, k, np.random.default_rng(seed), budget)
    full = np.arange(len(k), dtype=np.int64)
    reference = online(q, k, v, tile)
    candidate_ref = online(q, k[ids], v[ids], tile)
    z_full, z_candidate = k@q/math.sqrt(q.size), k[ids]@q/math.sqrt(q.size)
    rows = []
    for mode in MODES:
        candidates = full if mode in ('D0', 'P0') else ids
        logits = z_full if mode in ('D0', 'P0') else z_candidate
        receipt = None
        if mode in ('D0', 'P1'):
            result = reference if mode == 'D0' else candidate_ref
            counts = dict.fromkeys(map(int, candidates), 1)
            addresses = None
        elif mode in ('P0', 'P2'):
            local = systematic(softmax(logits), samples, np.random.default_rng(seed+10000))
            addresses = candidates[local].tolist()
            result, counts = gather(v, addresses)
        else:
            cls = CorrectedRejectionSampler if mode == 'P3' else WinnerHoldSampler
            cfg = dict(record_events=record_events, burn_updates=burn if mode == 'P4' else 0)
            sampler = cls(cfg, capacity=len(candidates))
            try:
                local, receipt = sampler.request(0., logits.tolist(), samples, random.Random(seed+20000),
                                                 mode, candidates.tolist())
            except SamplingCapError as exc:
                rows.append(dict(mode=mode, status='failed_cap', sampler=exc.receipt,
                                 candidates=candidates.tolist(), physical_energy_J=None, area_mm2=None))
                continue
            # PR88 outputs local indices, map exactly once. No second PV sampler.
            addresses = candidates[local].tolist()
            result, counts = gather(v, addresses)
            receipt['area_contract'] = sampler.area_receipt()
        screened = mode not in ('D0', 'P0')
        target = candidate_ref if screened else reference
        variance = float(softmax(logits) @ np.square(v[candidates]-target).sum(1))
        full_variance = float(softmax(z_full) @ np.square(v-reference).sum(1))
        rows.append(dict(mode=mode, status='completed', seed=seed, samples=samples if addresses is not None else None,
                         candidates=candidates.tolist(), addresses=addresses,
                         counts={str(a): int(c) for a, c in sorted(counts.items())},
                         output=result.tolist(), full_reference=reference.tolist(),
                         candidate_reference=candidate_ref.tolist() if screened else reference.tolist(),
                         squared_error_full=float(np.square(result-reference).sum()),
                         squared_error_sampling=float(np.square(result-target).sum()),
                         squared_error_screen=float(np.square(target-reference).sum()),
                         relative_error_full=float(np.linalg.norm(result-reference)/max(np.linalg.norm(reference), 1e-30)),
                         target_single_sample_variance=variance, full_single_sample_variance=full_variance,
                         normalized_mse_sampling=float(np.square(result-target).sum()/max(variance,1e-30)),
                         QK_MAC=len(candidates)*q.size,
                         PV_MAC=len(candidates)*q.size if addresses is None else 0,
                         V_adds=0 if addresses is None else samples*q.size,
                         K_physical_bytes=len(bursts(candidates, q.size))*64,
                         V_physical_bytes=len(bursts(counts, q.size))*64,
                         unique_V=len(counts), screen=screen_cost if screened else None,
                         sampler=receipt, physical_energy_J=None, area_mm2=None))
    return rows
