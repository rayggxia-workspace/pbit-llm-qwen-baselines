"""Finite-binomial inverse CDF GPU accelerator for the GU AND-count law.

CDF uses SciPy FP64; 53-bit uniform quantiles. Numeric sampling, not a physical
SNG implementation and not bit-exact arbitrary-precision rational sampling.
No Gaussian, expected-value or deterministic rounding replaces random counts.
"""
import hashlib
import numpy as np
import torch
import triton
import triton.language as tl
from .core import input_cells

_TABLE={};TABLE_METADATA={}


def table(device):
    key=str(device)
    if key not in _TABLE:
        from scipy.stats import binom
        n=np.arange(257)[:,None,None];p=np.arange(128)[None,:,None]/128.;k=np.arange(257)[None,None,:]
        values=np.ascontiguousarray(binom.cdf(k,n,p),dtype=np.float64)
        assert np.isfinite(values).all() and (np.diff(values,axis=-1)>=-1e-14).all()
        _TABLE[key]=torch.from_numpy(values).to(device)
        TABLE_METADATA[key]=dict(shape=list(values.shape),dtype='float64',sha256=hashlib.sha256(values.tobytes()).hexdigest(),
            uniform_bits=53,cdf='SciPy binom.cdf(n,p=code/128)',gaussian=False,
            precision='FP64 CDF and53-bit inverse sampling; not arbitrary-precision rational bittrue')
    return _TABLE[key]


@triton.jit
def _project(C,P,A,S,W,LUT,LSB,Y,U,SEED,GLOBAL_B,
             N:tl.constexpr,O:tl.constexpr,G:tl.constexpr,KW:tl.constexpr,T:tl.constexpr,
             REPLAY:tl.constexpr,BLOCK:tl.constexpr):
    ob=tl.program_id(0);b=tl.program_id(1);g=tl.program_id(2)
    oo=ob*BLOCK+tl.arange(0,BLOCK);ii=tl.arange(0,64)
    w=tl.load(W+oo[:,None]*N+g*64+ii[None,:],oo[:,None]<O,0).to(tl.int32)
    mag=tl.abs(w);wb=mag//(128//KW);pc=(mag%(128//KW))*KW
    n=tl.load(C+((b*G+g)*KW+wb)*64+ii[None,:]).to(tl.int32)
    base=tl.load(P+((b*G+g)*KW+wb)*64+ii[None,:]).to(tl.int32)
    if REPLAY:
        u=tl.load(U+((b*O+oo[:,None])*N+g*64+ii[None,:]),oo[:,None]<O,0.5).to(tl.float64)
    else:
        # Each row uses a distinct64-bit key. The within-row W address fits
        # uint32 (<50M), so2048-token prefills cannot wrap the Philox offset.
        key=SEED.to(tl.uint64)+(b+GLOBAL_B).to(tl.uint64)*0x9e3779b97f4a7c15
        off=(oo[:,None]*N+g*64+ii[None,:]).to(tl.uint32)
        r0=tl.randint(key,off).to(tl.uint32).to(tl.float64)
        r1=tl.randint(key^0x5a912c31,off).to(tl.uint32)&0x1fffff
        u=(r0*2097152.+r1.to(tl.float64)+.5)*(1./9007199254740992.)
    lo=tl.full((BLOCK,64),0,tl.int32);hi=n
    for _ in range(9):
        mid=(lo+hi)//2
        cdf=tl.load(LUT+(n*128+pc)*257+mid)
        right=u>cdf
        lo=tl.where(right,mid+1,lo);hi=tl.where(right,hi,mid)
    count=base+lo
    scale=tl.load(S+b*N+g*64+ii)
    sign=tl.load(A+b*N+g*64+ii)
    ws=tl.where(w<0,-1,tl.where(w>0,1,0))
    value=tl.sum(count.to(tl.float32)*ws.to(tl.float32)*sign[None,:]*scale[None,:],1)
    coeff=tl.load(LSB+(oo//64)*G+g,oo<O,0.)
    tl.store(Y+(b*O+oo)*G+g,value*coeff*(128./T),oo<O)


def project(encoded,codes,lsb,samples,law,input_generator,weight_generator,*,chunk=16,replay=None):
    from .core import GRIDS
    if samples not in GRIDS or codes.shape[1]!=encoded['probability'].shape[-1]:raise ValueError('invalid shape/T')
    shape=encoded['probability'].shape;flat={k:v.reshape(-1,shape[-1]) for k,v in encoded.items() if k in ('probability','scale','sign')}
    rows=flat['probability'].shape[0];out,n=codes.shape;groups=n//64
    kw=1 if law=='iid' else GRIDS[samples][1]
    cdf=table(codes.device);result=torch.empty(rows,out,device=codes.device,dtype=torch.float32)
    seed=int(torch.randint(0,2**63-1,(),device=codes.device,generator=weight_generator).item())
    for begin in range(0,rows,chunk):
        end=min(begin+chunk,rows);q=(flat['probability'][begin:end]*256).short()
        counts,prefix=input_cells(q,samples,law,input_generator)
        partial=torch.empty(end-begin,out,groups,device=codes.device,dtype=torch.float32)
        u=cdf if replay is None else replay[begin:end].contiguous()
        _project[(triton.cdiv(out,16),end-begin,groups)](counts,prefix,flat['sign'][begin:end].contiguous(),flat['scale'][begin:end].contiguous(),codes,cdf,lsb,partial,u,
            SEED=seed,GLOBAL_B=begin,N=n,O=out,G=groups,KW=kw,T=samples,REPLAY=replay is not None,BLOCK=16,num_warps=4)
        result[begin:end]=partial.sum(-1)
    return result.reshape(*shape[:-1],out)
