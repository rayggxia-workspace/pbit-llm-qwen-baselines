"""Finite-penalty, single-clock parallel heat-bath behavior model (Issue78).

Not a CTMC, and not a physical timing/PPA model. All nodes in one block read
the SAME old state/count. Blocks use a fresh random permutation each sweep.
The maximum-logit category is the clamped empty-state reference.
"""
import math
import numpy as np


class SamplingLimitError(RuntimeError):
    def __init__(self, stats):
        self.stats = stats
        super().__init__('64-address service incomplete; no IID fallback: ' + str(stats))


def sigmoid(x):
    return np.exp(-np.logaddexp(0., -x))


def sample_indices(logits, samples=64, kappa=12., block=64, burn=16,
                   spacing=4, seed=0, rng=None, enable=1., max_slots=256,
                   strict=True, observation='jitter', observation_rng=None):
    """Return [rows,S] addresses, or fail if S legal observations are unavailable.

    E = kappa*C*(C-1)/2 - sum((z_i-z_ref)*s_i), s_ref=0.
    Conditional P(s_i=1) = sigmoid(delta_i-kappa*(C-s_i)).
    C=0 decodes to ref, C=1 to its active category. C>1 produces no address.
    Such observation slots stall the service and are explicitly counted.
    burn/spacing count COMPLETE sweeps, not hardware clocks or CTMC time.
    A block<=0 updates every candidate slot together. enable is an independent
    per-site lazy-update probability; even enable<1 is not exact block Gibbs.
    """
    z = np.asarray(logits, dtype=np.float64)
    if z.ndim != 2 or min(z.shape) < 1:
        raise ValueError('nonempty [rows,candidates] logits required')
    valid = np.isfinite(z)
    if np.isnan(z).any() or np.isposinf(z).any() or not valid.any(1).all():
        raise ValueError('finite row required; only -inf padding allowed')
    if not math.isfinite(kappa) or kappa < 0 or not 0 < enable <= 1:
        raise ValueError('kappa>=0 and 0<enable<=1 required')
    if any(type(v) is not int or v < 1 for v in (samples, spacing, max_slots)):
        raise ValueError('positive integer samples/spacing/max_slots required')
    if type(burn) is not int or burn < 0 or type(block) is not int:
        raise ValueError('integer burn>=0 and block required')
    if observation not in ('fixed','jitter'):
        raise ValueError('fixed or jitter observation required')
    rows, width = z.shape
    block = width if block <= 0 else min(block, width)
    rng = np.random.default_rng(seed) if rng is None else rng
    obs_rng = np.random.default_rng(seed+987654) if observation_rng is None else observation_rng
    ref = z.argmax(1)
    delta = z - z[np.arange(rows), ref, None]
    movable = valid.copy()
    movable[np.arange(rows), ref] = False
    state = np.zeros_like(z, dtype=np.int8)
    count = np.zeros(rows, dtype=np.int32)
    output = np.full((rows, samples), -1, dtype=np.int64)
    collected = np.zeros(rows, dtype=np.int32)
    slots = np.zeros(rows, dtype=np.int32)
    invalid = np.zeros(rows, dtype=np.int32)
    flips = attempts = phases = 0
    peak_count = phase_invalid = phase_observations = phase_count_sum = 0
    next_obs = np.full(rows,burn+spacing,dtype=np.int32)
    if observation=='jitter':next_obs=burn+obs_rng.integers(1,2*spacing,size=rows)
    total_sweeps = burn + (2*spacing-1 if observation=='jitter' else spacing) * max_slots
    for sweep in range(1, total_sweeps + 1):
        running = (collected < samples) & (slots < max_slots)
        if not running.any():break
        order = np.arange(width) if block == width else rng.permutation(width)
        for start in range(0, width, block):
            ix = order[start:start + block]
            old = state[:, ix]
            prob = sigmoid(delta[:, ix] - kappa * (count[:, None] - old))
            chosen = movable[:, ix] & running[:, None]
            if enable < 1:
                chosen &= rng.random(old.shape) < enable
            new = np.where(chosen, rng.random(old.shape) < prob, old).astype(np.int8)
            change = new - old
            count += change.sum(1, dtype=np.int32)
            state[:, ix] = new
            flips += int(np.abs(change).sum())
            attempts += int(chosen.sum())
            phases += 1
            peak_count = max(peak_count, int(count.max()))
            phase_invalid += int(((count>1)&running).sum())
            phase_observations += int(running.sum())
            phase_count_sum += int(count[running].sum())
        if not np.array_equal(count, state.sum(1)):
            raise AssertionError('incremental broadcast count drifted from state')
        observe = running & (sweep == next_obs)
        if observe.any():
            slots[observe] += 1
            legal = observe & (count <= 1)
            invalid[observe & ~legal] += 1
            rr_obs=np.flatnonzero(observe)
            next_obs[rr_obs] += (obs_rng.integers(1,2*spacing,size=len(rr_obs))
                                if observation=='jitter' else spacing)
            rr = np.flatnonzero(legal)
            addresses = np.where(count[rr] == 0, ref[rr], state[rr].argmax(1))
            output[rr, collected[rr]] = addresses
            collected[rr] += 1
            if (collected == samples).all():
                break
    mask = output >= 0
    pairs = mask[:, 1:] & mask[:, :-1]
    stats = dict(kind='finite_penalty_random_partition_parallel_heat_bath',
        kappa=kappa, block=block, update_enable_probability=enable,
        rows=rows, candidates=width, samples=samples, burn_sweeps=burn,
        spacing_sweeps=spacing, executed_sweeps=sweep,
        update_phases=phases, attempted_site_updates=attempts, state_flips=flips,
        peak_active_count=peak_count, observation_slots=int(slots.sum()),
        invalid_observation_slots=int(invalid.sum()),
        invalid_fraction=float(invalid.sum()/max(1, slots.sum())),
        invalid_phase_fraction=phase_invalid/max(1,phase_observations),
        mean_active_count_per_phase=phase_count_sum/max(1,phase_observations),
        observation_schedule=observation,
        collected_min=int(collected.min()), collected_max=int(collected.max()),
        completed_rows=int((collected == samples).sum()),
        adjacent_repeat_fraction=float(((output[:, 1:] == output[:, :-1]) & pairs).sum()/max(1,pairs.sum())),
        legal_readout='C=0 reference; C=1 active; C>1 stalls, no address',
        max_slots=max_slots, failed=bool((collected < samples).any()),
        time_unit='whole sweep; not CTMC time or measured hardware clock',
        iid_fallback=False, physical_PPA=None)
    if strict and stats['failed']:
        raise SamplingLimitError(stats)
    return output, stats


def finite_equilibrium(logits, kappa, max_count=8):
    """Cardinality DP gives exact small-count mass plus a rigorous tail bound.

    delta<=0 allows bounding omitted cardinalities by binomial(n,k). Conditional
    on C<=1 the exact equilibrium law is ALWAYS the original Softmax; this says
    nothing about whether the parallel transition rule reaches that law.
    """
    z = np.asarray(logits, dtype=np.float64)
    z = z[np.isfinite(z)]
    d = np.delete(z-z.max(), z.argmax())
    n = len(d); limit=min(n,max_count)
    coeff = np.full(limit+1,-np.inf);coeff[0]=0.
    for j,x in enumerate(d):
        hi=min(j+1,limit)
        coeff[1:hi+1]=np.logaddexp(coeff[1:hi+1],coeff[:hi]+x)
    k=np.arange(limit+1)
    masses=coeff-kappa*k*(k-1)/2
    logz=np.logaddexp.reduce(masses)
    legal=np.logaddexp(0.,coeff[1]) if n else 0.
    tails=[math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)-kappa*i*(i-1)/2
           for i in range(limit+1,n+1)]
    tail_log=np.logaddexp.reduce(tails) if tails else -np.inf
    return dict(equilibrium_invalid_fraction=float(-np.expm1(legal-logz)),
        omitted_tail_partition_upper_bound=float(np.exp(tail_log-logz)),
        conditional_legal_distribution='exact softmax; equilibrium only')
