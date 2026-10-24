"""Independent SMURF reconstruction; runtime is integer FSM + R8 comparators.

Offline fitting/analysis may use floats. The simulator does not substitute an
IID binomial output for the stateful process. Output is taken AFTER updating.
"""
import numpy as np
from scipy.optimize import lsq_linear
from scipy.special import expit


def target(p, scale=1., sign=1):
    """Sign/magnitude output: signed SiLU(sign*S*p) = sign*S*target(p)."""
    return np.asarray(p) * expit(sign * scale * np.asarray(p))


def stationary(p, states):
    p = np.asarray(p, dtype=np.float64).reshape(-1)
    if states < 2 or np.any((p < 0) | (p > 1)):
        raise ValueError('invalid probability/states')
    pi = np.zeros((p.size, states))
    pi[p == 0, 0] = 1
    pi[p == 1, -1] = 1
    inner = (p > 0) & (p < 1)
    logs = np.log(p[inner] / (1-p[inner]))[:, None] * np.arange(states)
    logs -= logs.max(axis=1, keepdims=True)
    v = np.exp(logs)
    pi[inner] = v / v.sum(axis=1, keepdims=True)
    return pi


def initial(states, mode):
    return {'zero': 0, 'mid': states//2, 'top': states-1}[mode]


def propagate(v, p):
    """Row-distribution or joint moments advanced through saturating chain."""
    p = np.asarray(p)[:, None]
    out = np.zeros_like(v)
    out[:, 1:] += v[:, :-1] * p
    out[:, -1:] += v[:, -1:] * p
    out[:, :-1] += v[:, 1:] * (1-p)
    out[:, :1] += v[:, :1] * (1-p)
    return out


def fit(states, scale=1., sign=1):
    # Uniform 4097-point trapezoidal quadrature of the paper's squared error.
    p = np.linspace(0, 1, 4097)
    weights = np.ones(p.size); weights[[0, -1]] = .5
    weights = np.sqrt(weights)
    a = stationary(p, states)
    solution = lsq_linear(a * weights[:, None], target(p, scale, sign)*weights,
                         bounds=(0, 1), tol=1e-12, max_iter=1000)
    if not solution.success:
        raise RuntimeError(solution.message)
    codes = np.clip(np.rint(solution.x*256), 0, 256).astype(np.int16)
    return codes, solution.x


def moments(codes, q, cycles, init='mid'):
    """Exact finite-time output-count expectation/variance for IID R8 inputs."""
    codes = np.asarray(codes)
    p = np.asarray(q, dtype=float)/256
    theta = codes[None, :]/256
    v = np.zeros((p.size, codes.size)); v[:, initial(codes.size, init)] = 1
    m = np.zeros_like(v); h = np.zeros_like(v)
    for _ in range(cycles):
        v, m, h = (propagate(a, p) for a in (v, m, h))
        h += 2*theta*m + theta*v
        m += theta*v
    mean = m.sum(axis=1)/cycles
    var = np.maximum(0, h.sum(axis=1)/cycles**2 - mean**2)
    return mean, var


def threshold_stream(rng, cycles, shape, mode):
    if mode == 'iid':
        return rng.integers(0, 256, size=(cycles,)+shape, dtype=np.int16)
    if mode not in ('ordered32', 'shuffle32') or cycles % 32:
        raise ValueError('invalid stratified sequence')
    # Fresh independent random permutation per q/trial and each 32-clock round.
    chunks=[]
    for _ in range(cycles//32):
        order=np.broadcast_to(np.arange(32, dtype=np.int16).reshape((32,)+(1,)*len(shape)), (32,)+shape).copy()
        if mode == 'shuffle32':
            for i in range(31, 0, -1):
                j=rng.integers(0, i+1, size=shape)[None, ...]
                other=np.take_along_axis(order, j, axis=0)[0].copy()
                cur=order[i].copy()
                np.put_along_axis(order, j, cur[None, ...], axis=0)
                order[i]=other
        chunks.append(8*order + rng.integers(0, 8, size=(32,)+shape, dtype=np.int16))
    return np.concatenate(chunks)


def simulate(codes, q, cycles, seed, trials=256, init='mid', input_mode='iid'):
    if cycles not in (32, 64, 128):
        raise ValueError('Operational sample budget is 32/64/128')
    codes=np.asarray(codes, dtype=np.int16)
    q=np.asarray(q, dtype=np.int16)
    if np.any((q<0)|(q>256)) or np.any((codes<0)|(codes>256)):
        raise ValueError('R8 probability code outside 0..256')
    a,b=np.random.SeedSequence(seed).spawn(2)
    rg_in=np.random.default_rng(a);rg_out=np.random.default_rng(b)
    shape=(q.size, trials)
    r=threshold_stream(rg_in, cycles, shape, input_mode)
    state=np.full(shape, initial(codes.size, init), dtype=np.int16)
    counts=np.zeros(shape, dtype=np.int16)
    ones=np.zeros(q.size, dtype=np.int64)
    prev_ones=np.zeros(q.size, dtype=np.int64)
    pairs=np.zeros(q.size, dtype=np.int64)
    prev=np.zeros(shape, dtype=bool)
    for t in range(cycles):
        state=np.clip(state+2*(r[t]<q[:,None]).astype(np.int16)-1, 0, codes.size-1)
        bit=rg_out.integers(0,256,size=shape,dtype=np.int16)<codes[state]
        counts+=bit
        if t:
            ones+=bit.sum(axis=1);prev_ones+=prev.sum(axis=1);pairs+=(bit&prev).sum(axis=1)
        prev=bit
    denom=(cycles-1)*trials
    a=ones/denom;b=prev_ones/denom
    rho=np.divide(pairs/denom-a*b,np.sqrt(a*(1-a)*b*(1-b)),out=np.zeros_like(a),where=(a*(1-a)*b*(1-b))>0)
    return counts/cycles, rho


def weighted_planes(bits, weights):
    """One clock's exact fixed signed W8 reduction; never feeds raw planes to FSM."""
    bits=np.asarray(bits, dtype=np.int64);w=np.asarray(weights,dtype=np.int64)
    if np.any(np.abs(w)>127) or np.any((bits!=0)&(bits!=1)):
        raise ValueError('expected W8 sign/magnitude and binary input')
    acc=np.zeros(bits.shape[:-1], dtype=np.int64)
    for j in range(7):
        acc+=(bits * np.sign(w) * ((np.abs(w)>>j)&1)).sum(axis=-1) << j
    return acc
