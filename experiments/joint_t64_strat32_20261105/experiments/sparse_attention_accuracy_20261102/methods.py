"""Explicit experimental adapters; do not mutate historical implementations."""
from contextlib import AbstractContextManager
from pathlib import Path
import json
import math
import torch
from experiments.sparq_ising_20261028 import core, adapter, scoring

CASES = ['bf16', 'sparq64', 'sparq128', 'sparq128_top64',
         'ising64_ideal', 'ising64_i8p8', 'quest64', 'quest128']


def configuration(name):
    if name not in CASES:
        raise ValueError(name)
    if name == 'bf16':
        return None
    return core.Config(k=64 if name in ('sparq64', 'quest64') else 128,
                       samples=64, burn=0,
                       mode='winner' if name.startswith('ising') else 'exact')


def quest_indices(query, key, budget, page=16):
    """Q[B,Hkv,G,D], K[B,Hkv,N,D]; independent page selection per Q head.

    Algebraic equivalent of official Quest evaluation/quest_attention.py:
    maximize sign(Q)*K per page/channel, then dot with abs(Q). No recent-token
    forcing. Padded entries never count as real KV. Budgets are token-equivalent.
    """
    b,h,g,d=query.shape
    n=key.shape[2]
    pages=(n+page-1)//page
    pad=pages*page-n
    hi=torch.nn.functional.pad(key,(0,0,0,pad),value=-torch.inf).reshape(b,h,pages,page,d).amax(-2)
    lo=torch.nn.functional.pad(key,(0,0,0,pad),value=torch.inf).reshape(b,h,pages,page,d).amin(-2)
    bound=(query.clamp_min(0) @ hi.transpose(-1,-2)
           + query.clamp_max(0) @ lo.transpose(-1,-2))
    chosen=bound.topk(min(max(3,budget//page),pages),dim=-1).indices
    ids=(chosen[...,None]*page+torch.arange(page,device=key.device)).flatten(-2)
    return ids.clamp_max(n-1),ids<n,bound


def quest_attention(q,k,v,cfg,seed=0,diagnostics=False):
    b,hq,_,d=q.shape
    h,n=k.shape[1:3];g=hq//h
    dtype=torch.float64 if q.dtype==torch.float64 else torch.float32
    query=q.to(dtype).reshape(b,h,g,d)
    key=k.to(dtype)
    ids,valid,_=quest_indices(query,key,cfg.k)
    bb=torch.arange(b,device=q.device)[:,None,None,None]
    hh=torch.arange(h,device=q.device)[None,:,None,None]
    ck,cv=key[bb,hh,ids],v.to(dtype)[bb,hh,ids]
    logits=(query[...,None,:]*ck).sum(-1)/math.sqrt(d)
    logits=logits.masked_fill(~valid,-torch.inf)
    out=(logits.softmax(-1)[...,None]*cv).sum(-2).reshape(b,hq,1,d).to(q.dtype)
    info=dict(zero_fallback_groups=0,n=n,k=ids.shape[-1],b=b,h=h,g=g,
              local_indices=None,activity=None,candidate_ids=ids,valid=valid)
    return (out,info) if diagnostics else out


class Patch(AbstractContextManager):
    def __init__(self,name):
        self.name=name
        self.original_attention=adapter.attention
        self.original_readout=core.readout
        self.original_controller=scoring.Controller
        self.calls=0;self.entries=0;self.clipped=None
        self.table=None
        self.kernels=None

    def probabilities(self,logits,method):
        assert method=='winner'
        z=logits.float()
        if self.name=='ising64_i8p8':
            raw=torch.round(z*16)
            code=raw.clamp(-128,127).long()
            gap=code.amax(-1,keepdim=True)-code
            table=self.table.to(z.device)
            p=table[gap].float()/256
            clipped=(raw!=code).sum()
            self.clipped=clipped if self.clipped is None else self.clipped+clipped
            self.calls+=1;self.entries+=z.numel()
        else:
            p=torch.sigmoid(z-z.amax(-1,keepdim=True))
        # Hardware starts at candidate slot 0, not argmax. Burn is exactly zero.
        planes=torch.zeros((z.shape[0],26,z.shape[1]),device=z.device)
        planes[:,0]=p;planes[:,25,0]=1
        return planes.contiguous()

    def readout(self,logits,value,cfg,seed):
        if self.name!='sparq128_top64':
            return self.original_readout(logits,value,cfg,seed)
        z,ids=logits.topk(min(64,logits.shape[-1]),dim=-1)
        b,h,g,n=ids.shape
        bb=torch.arange(b,device=ids.device)[:,None,None,None]
        hh=torch.arange(h,device=ids.device)[None,:,None,None]
        out=(z.softmax(-1)[...,None]*value[bb,hh,ids]).sum(-2)
        return out,None,None

    def __enter__(self):
        core.readout=self.readout
        owner=self
        if self.name.startswith('ising'):
            from experiments.sparq_ising_20261028.vendor import kernels
            self.kernels=kernels;self.original_probability=kernels.probabilities
            self.table=torch.tensor(json.loads((Path(__file__).parent/'sigmoid_table.json').read_text())['values'],dtype=torch.long)
            kernels.probabilities=self.probabilities
        if self.name.startswith('quest'):
            adapter.attention=quest_attention
        class Controller(owner.original_controller):
            def dispatch(self,a,*args,**kwargs):
                old=self.cfg
                # Official QUEST preserves the first two layers dense.
                if owner.name.startswith('quest') and a.layer_idx<2:self.cfg=None
                try:return super().dispatch(a,*args,**kwargs)
                finally:self.cfg=old
            def report(self):
                r=super().report()
                r.update(method=owner.name,ideal_sigmoid_source=owner.name=='ising64_ideal',
                         dense_first_layers=2 if owner.name.startswith('quest') else 0,
                         hardware_bittrue=False,
                         rng='independent SHA256-keyed Philox; no GF64/Bivium/LFSR correlations',
                         counts='behavioral diagnostics; not hardware traffic or PPA')
                return r
        self.Controller=Controller
        scoring.Controller=Controller
        return self

    def report(self):
        return dict(quantized_calls=self.calls,score_entries=self.entries,
                    clipped_score_entries=0 if self.clipped is None else int(self.clipped),
                    initial_winner_slot=0,burn=0,samples=64,
                    numeric='RNE signed8/F4 absolute -> candidate max gap -> exact frozen P8 LUT' if self.name=='ising64_i8p8' else 'FP32 attention reference arithmetic',
                    gf64_bittrue=False,screening='existing FP32 SparQ selector; no mean-V compensation')

    def __exit__(self,*args):
        adapter.attention=self.original_attention
        core.readout=self.original_readout
        scoring.Controller=self.original_controller
        if self.kernels:self.kernels.probabilities=self.original_probability
