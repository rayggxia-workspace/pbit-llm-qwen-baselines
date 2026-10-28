"""SparQ paper-v6 routing + finite winner-hold PV; original FFN stays intact.

Derived routing: PR163 ca3da3a5, vendor/sparq_reference.py. No mean-V.
The sampler is an ideal FP32 sigmoid/Philox behavioral model, not measured PPA.
"""
from dataclasses import dataclass
import math
import torch


@dataclass(frozen=True)
class Config:
    r: int = 32
    k: int = 128
    local: int = 32
    samples: int = 128
    burn: int = 32
    mode: str = 'winner'

    def __post_init__(self):
        if self.mode not in ('exact', 'winner', 'iid'):
            raise ValueError('unknown method')
        if min(self.r, self.k, self.samples) < 1 or not 0 <= self.local <= self.k or self.burn < 0:
            raise ValueError('invalid budget')


def select(q, k, cfg):
    """Unpadded post-RoPE Q[B,Hkv,G,D], K[B,Hkv,N,D]."""
    b, h, g, d = q.shape
    n = k.shape[2]
    if not 1 <= cfg.r <= d:
        raise ValueError('r exceeds head dimension')
    if n <= cfg.k:
        ids = torch.arange(n, device=q.device).expand(b, h, n)
        return ids, torch.zeros((b,h), dtype=torch.bool, device=q.device)
    channels = q.abs().sum(2).topk(cfg.r, dim=-1).indices
    qs = q.gather(-1, channels[:,:,None,:].expand(b,h,g,cfg.r))
    total = q.abs().sum(-1,keepdim=True)
    selected = qs.abs().sum(-1,keepdim=True)
    zero = ((total == 0) | (selected == 0)).any(2).squeeze(-1)
    tau = torch.sqrt(d * selected / torch.where(total > 0, total, 1))
    tau = torch.where(tau > 0, tau, 1)
    ks = k.gather(-1,channels[:,:,None,:].expand(b,h,n,cfg.r))
    prob = ((qs/tau) @ ks.transpose(-1,-2)).softmax(-1)
    score = prob.sum(2)
    if cfg.local:
        score[:,:,-cfg.local:] = torch.inf
    return score.topk(cfg.k,dim=-1).indices, zero


def torch_winner_replay(bits, ranks, initial, burn):
    """Independent CPU/tensor state oracle. ranks are valid active-set ranks."""
    state = initial.clone()
    result = []
    for t in range(bits.shape[1]):
        frame = bits[:,t]
        count = frame.sum(-1)
        hold = frame.gather(1,state[:,None]).squeeze(1)
        prefix = frame.long().cumsum(-1)
        choice = (frame & (prefix == ranks[:,t,None]+1)).long().argmax(-1)
        state = torch.where(hold | (count == 0),state,choice)
        if t >= burn:
            result.append(state.clone())
    return torch.stack(result,1)


def readout(logits, value, cfg, seed):
    """logits[B,Hkv,G,K], value[B,Hkv,K,D]; actual returned addresses feed V."""
    b,h,g,n = logits.shape
    d = value.shape[-1]
    if cfg.mode == 'exact':
        return logits.softmax(-1) @ value, None, None
    flat = logits.reshape(-1,n)
    if cfg.mode == 'winner':
        from .vendor.kernels import sample
        local, activity = sample(flat,cfg.samples,'winner',burn=cfg.burn,seed=seed)
    else:
        generator = torch.Generator(device=flat.device).manual_seed(seed)
        local = torch.multinomial(flat.softmax(-1),cfg.samples,replacement=True,generator=generator)
        activity = torch.zeros((flat.shape[0],6),device=flat.device,dtype=torch.int64)
        activity[:,1] = cfg.samples
    local = local.reshape(b,h,g,cfg.samples)
    # Map each Q to its shared KV group without replicating the full V cache.
    bb = torch.arange(b,device=value.device)[:,None,None,None]
    hh = torch.arange(h,device=value.device)[None,:,None,None]
    fetched = value[bb,hh,local]
    output = fetched.sum(-2) / cfg.samples
    return output, local, activity


def attention(q,k,v,cfg,seed=0,diagnostics=False):
    if q.ndim != 4 or q.shape[2] != 1 or k.shape != v.shape or q.shape[0] != k.shape[0]:
        raise ValueError('single-token unpadded Q and matching K/V required')
    b,hq,_,d = q.shape
    h,n = k.shape[1:3]
    if hq % h or k.shape[-1] != d:
        raise ValueError('invalid GQA shape')
    g = hq//h
    dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    query = q.to(dtype).reshape(b,h,g,d)
    key = k.to(dtype)
    ids, zero = select(query,key,cfg)
    count = ids.shape[-1]
    ki = ids[:,:,:,None].expand(b,h,count,d)
    ck, cv = key.gather(2,ki),v.gather(2,ki).to(dtype)
    logits = (query/math.sqrt(d)) @ ck.transpose(-1,-2)
    out, local, activity = readout(logits,cv,cfg,seed)
    # Match PR163's explicit zero-coverage dense fallback; report it separately.
    # Sampling variants still sample full K/V for affected groups, not exact PV.
    zero_count = int(zero.sum().item())
    if zero_count:
        for bi,hi in zero.nonzero().tolist():
            z = (query[bi:bi+1,hi:hi+1]/math.sqrt(d)) @ key[bi:bi+1,hi:hi+1].transpose(-1,-2)
            fallback,_,_ = readout(z,v[bi:bi+1,hi:hi+1].to(dtype),cfg,seed+bi*h+hi+1)
            out[bi,hi] = fallback[0,0]
    result = out.reshape(b,hq,1,d).to(q.dtype)
    if not diagnostics:
        return result
    info = dict(candidate_ids=ids,zero_fallback_groups=zero_count,local_indices=local,
                n=n,k=count,b=b,h=h,g=g,activity=activity)
    if local is not None:
        info['token_ids'] = ids[:,:,None,:].expand(b,h,g,count).gather(-1,local)
        hit = torch.zeros((b,h,g,count),device=q.device,dtype=torch.int32)
        hit.scatter_add_(-1,local,torch.ones_like(local,dtype=torch.int32))
        info['unique_v_group_union'] = (hit.sum(2)>0).sum()
    return result,info
