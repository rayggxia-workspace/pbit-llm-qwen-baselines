"""Inference-only Triton realization of Issue78 ideal independent proposals.

One program per query/head, parallel candidate bits, sequential proposal frames.
No softmax draw, no Gaussian approximation, no silent fallback. GPU speed is not
ASIC latency. Default FP32 sigmoid/Philox is not the integrated R8 hardware RNG.
"""
import torch
import triton
import triton.language as tl


@triton.jit
def _sample(P, OUT, STATS, U, R, C, SEED,
            N: tl.constexpr, S: tl.constexpr, CAP: tl.constexpr,
            WINNER: tl.constexpr, BURN: tl.constexpr, REPLAY: tl.constexpr,
            BLOCK: tl.constexpr):
    row = tl.program_id(0)
    lane = tl.arange(0, BLOCK)
    # Last probability-table plane contains the unique reference marker.
    refmark = tl.load(P + (row*26+25)*N+lane, lane < N, 0.)
    ref = tl.max(tl.where(refmark > 0, lane, 0), 0)
    state = ref
    m = 0
    collected = 0
    t = 0
    collisions = 0
    empty_rejects = 0
    ref_accepts = 0
    while (t < CAP) & (collected < S):
        p = tl.load(P+(row*26+m)*N+lane, lane<N, 0.)
        offset = ((row*CAP+t)*BLOCK+lane).to(tl.uint32)
        if REPLAY:
            u = tl.load(U+(row*CAP+t)*N+lane, lane<N, 1.)
            raw = tl.load(R+row*CAP+t).to(tl.uint32)
            coin = tl.load(C+row*CAP+t)
        else:
            u = tl.rand(SEED, offset)
            raw = tl.randint(SEED ^ 0x5a912c31, (row*CAP+t).to(tl.uint32)).to(tl.uint32)
            coin = tl.rand(SEED ^ 0x17d4b9a3, (row*CAP+t).to(tl.uint32))
        bits = (u < p) & (lane<N)
        count = tl.sum(bits.to(tl.int32), 0)
        if WINNER:
            hold = tl.sum((bits & (lane==state)).to(tl.int32),0)>0
            denom = tl.maximum(count,1).to(tl.uint32)
            # Unbiased bounded integer: reject the incomplete uint32 interval.
            threshold = (0-denom).to(tl.uint32) % denom
            retry = 0
            while raw < threshold:
                retry += 1
                raw = tl.randint(SEED ^ 0x713b098d,
                    ((row*CAP+t)*1024+retry).to(tl.uint32)).to(tl.uint32)
            rank = (raw % denom).to(tl.int32)
            prefix = tl.cumsum(bits.to(tl.int32),0)
            choice = tl.min(tl.where(bits & (prefix==rank+1),lane,BLOCK),0)
            state = tl.where(hold | (count==0),state,choice)
            if t >= BURN:
                tl.store(OUT+row*S+collected,state)
                collected += 1
        else:
            empty = count==0
            reference = empty & (coin < tl.exp2(-m.to(tl.float32)))
            take = (count==1) | reference
            choice = tl.min(tl.where(bits,lane,BLOCK),0)
            choice = tl.where(reference,ref,choice)
            if take:
                tl.store(OUT+row*S+collected,choice)
                collected += 1
            collisions += (count>1).to(tl.int32)
            empty_rejects += (empty & ~reference).to(tl.int32)
            ref_accepts += reference.to(tl.int32)
            m = tl.where(count>1,tl.minimum(m+1,24),m)
            m = tl.where(empty & ~reference,tl.maximum(m-1,0),m)
        t += 1
    tl.store(STATS+row*6+0,t)
    tl.store(STATS+row*6+1,collected)
    tl.store(STATS+row*6+2,collisions)
    tl.store(STATS+row*6+3,empty_rejects)
    tl.store(STATS+row*6+4,ref_accepts)
    tl.store(STATS+row*6+5,m)


def probabilities(logits, method):
    z=logits.float().contiguous()
    if z.ndim!=2 or not torch.isfinite(z).any(-1).all() or torch.isnan(z).any() or torch.isposinf(z).any():
        raise ValueError('finite logits / -inf padding with one valid entry per row required')
    ref=z.argmax(-1)
    d=z-z.gather(1,ref[:,None])
    shifts=torch.arange(25,device=z.device,dtype=torch.float32)
    p=torch.sigmoid(d[:,None,:]-shifts[None,:,None]*0.6931471805599453)
    marker=torch.zeros_like(z).scatter_(1,ref[:,None],1.)
    if method=='rejection':
        p=p.masked_fill(marker[:,None,:].bool(),0.)
    elif method!='winner':
        raise ValueError(method)
    return torch.cat((p,marker[:,None,:]),1).contiguous()


def sample(logits,samples,method,generator=None,burn=0,seed=None,replay=None,cap_factor=128):
    if type(samples)!=int or samples<1 or burn<0 or cap_factor<1:
        raise ValueError('invalid budget')
    if method=='rejection' and burn:
        raise ValueError('rejection has no burn-in')
    p=probabilities(logits,method)
    rows,n=logits.shape
    cap=samples+burn if method=='winner' else samples*cap_factor
    if rows*cap*triton.next_power_of_2(n)>=2**32:
        raise ValueError('Philox counter would overlap within this call')
    if seed is None:
        seed=int(torch.randint(0,2**63-1,(),device=logits.device,generator=generator,dtype=torch.int64).item())
    out=torch.full((rows,samples),-1,device=logits.device,dtype=torch.int64)
    stats=torch.empty((rows,6),device=logits.device,dtype=torch.int64)
    u,r,c=(p,p,p) if replay is None else replay
    if replay is not None and (u.shape!=(rows,cap,n) or r.shape!=(rows,cap) or c.shape!=(rows,cap)):
        raise ValueError('replay shape')
    _sample[(rows,)](p,out,stats,u,r,c,SEED=seed,N=n,S=samples,CAP=cap,
        WINNER=method=='winner',BURN=burn,REPLAY=replay is not None,
        BLOCK=triton.next_power_of_2(n),num_warps=4)
    if not bool((stats[:,1]==samples).all()):
        raise RuntimeError('proposal cap reached; no fallback: '+str(stats.cpu().tolist()))
    if not bool(((out>=0)&(out<n)&torch.isfinite(logits.gather(1,out))).all()):
        raise RuntimeError('invalid sampled address')
    return out,stats
