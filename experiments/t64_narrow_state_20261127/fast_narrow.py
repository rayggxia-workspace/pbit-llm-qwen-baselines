"""Fuse the frozen per-K64 RNE state updates; retain all original numerical checks."""
import torch
import triton
import triton.language as tl

@triton.jit
def _state(C,S,H,W,E,B,O,F,Q,A,M:tl.constexpr,K:tl.constexpr,N:tl.constexpr,
           R:tl.constexpr,WIDTH:tl.constexpr,BM:tl.constexpr=16,BN:tl.constexpr=64):
    pm=tl.program_id(0);pn=tl.program_id(1)
    rows=pm*BM+tl.arange(0,BM);outs=pn*BN+tl.arange(0,BN);kk=tl.arange(0,64)
    base=tl.load(B+rows*(N//64)+pn,rows<M,other=0).to(tl.int32)
    total=tl.full((BM,BN),0,tl.int64)
    bad=tl.full((BM,BN),False,tl.int1)
    rounded=tl.full((BM,BN),0,tl.int32)
    for g in range(K//64):
        ix=rows[:,None]*K+g*64+kk[None,:]
        c=tl.load(C+ix,rows[:,None]<M,other=0).to(tl.int64)
        sg=tl.load(S+ix,rows[:,None]<M,other=0).to(tl.int64)
        sh=tl.load(H+ix,rows[:,None]<M,other=0).to(tl.int32)
        hi=tl.max(sh,1)
        local=c<<(hi[:,None]-sh)
        w=tl.load(W+outs[None,:]*K+g*64+kk[:,None],outs[None,:]<N,other=0).to(tl.int8)
        lo=((local&127)*sg).to(tl.int8)
        high=((local>>7)*sg).to(tl.int8)
        part=tl.dot(lo,w,out_dtype=tl.int32).to(tl.int64)
        part+=tl.dot(high,w,out_dtype=tl.int32).to(tl.int64)<<7
        ce=tl.load(E+pn*(K//64)+g).to(tl.int32)
        delta=R-hi+ce-base
        left=tl.minimum(tl.maximum(delta,0),62)
        right=tl.minimum(tl.maximum(-delta,1),62)
        av=tl.abs(part);q=av>>right[:,None]
        rem=av-(q<<right[:,None]);half=tl.full((BM,),1,tl.int64)<<(right-1)
        q+=((rem>half[:,None])|((rem==half[:,None])&((q&1)!=0))).to(tl.int64)
        q=tl.where((-delta[:,None])>=24,0,q)
        signed=tl.where(part<0,-q,q)
        aligned=tl.where(delta[:,None]>=0,part<<left[:,None],signed)
        inverse=tl.where(delta[:,None]<0,aligned<<tl.minimum(tl.maximum(-delta,0),62)[:,None],part)
        rounded+=(inverse!=part).to(tl.int32)
        new=total+aligned
        overflow=(new<-(1<<(WIDTH-1)))|(new>((1<<(WIDTH-1))-1))
        bad|=(part<-(1<<22))|(part>((1<<22)-1))|((delta[:,None]>=WIDTH)&(part!=0))|overflow
        total=tl.where(overflow,total,new)
    pos=tl.maximum(base,0);fine=tl.maximum(-base,0)
    mask=(tl.full((BM,),1,tl.int64)<<fine)-1
    bad|=((tl.abs(total)&mask[:,None])!=0)&(base[:,None]<0)
    limit=tl.full((BM,),9223372036854775807,tl.int64)>>pos
    bad|=tl.abs(total)>limit[:,None]
    restored=(total<<pos[:,None])>>fine[:,None]
    tl.store(O+rows[:,None]*N+outs[None,:],restored,(rows[:,None]<M)&(outs[None,:]<N))
    tl.store(F+pm*(N//64)+pn,tl.sum(tl.sum((bad&(rows[:,None]<M)).to(tl.int32),1),0))
    tl.store(Q+pm*(N//64)+pn,tl.sum(tl.sum(rounded,1),0))
    tl.store(A+pm*(N//64)+pn,tl.max(tl.max(tl.abs(total),1),0))

def narrow(counts,sign,shifts,weights,coeff,samples,R,width,role,unit_exponents=None):
    from core import common_base
    assert width in (24,32) and role in ('GU','Wd') and samples in (16,32)
    assert not torch.backends.cuda.matmul.allow_tf32 and 0<=R<=40
    k=counts.shape[-1];n=weights.shape[0];m=counts.numel()//k;ng=k//64;nb=n//64
    assert k%64==0 and n%128==0 and coeff.shape==(nb,ng)
    assert k*samples*127*int(coeff.max())*(1<<R)<1<<63
    c=counts.reshape(m,k).long().contiguous();s=sign.reshape(m,k).long().contiguous()
    h=shifts.reshape(m,ng,64).long().contiguous();lo=h.amin(-1);hi=h.amax(-1)
    assert bool(((hi-lo)<=2).all())
    ce=torch.frexp(coeff.double())[1].long()-1
    assert bool((coeff==(torch.ones_like(ce)<<ce)).all()) and bool((coeff>=1).all())
    b=(((64*samples*127)<<(R-lo))[:,None,:]*coeff[None,:,:]).sum(-1)
    if unit_exponents is None:unit_exponents=torch.zeros(nb,device=c.device,dtype=torch.int64)
    base=common_base(b,unit_exponents.reshape(nb).long(),width,role).contiguous()
    out=torch.empty((m,n),device=c.device,dtype=torch.int64)
    shape=(triton.cdiv(m,16),nb)
    flags=torch.empty(shape,device=c.device,dtype=torch.int32)
    rounded=torch.empty_like(flags);maximum=torch.empty(shape,device=c.device,dtype=torch.int64)
    _state[shape](c,s,h.reshape(m,k),weights.contiguous(),ce.contiguous(),base,out,flags,rounded,maximum,
                  m,k,n,R,width,num_warps=4,num_stages=1)
    assert not bool(flags.any()),'narrow state overflow or invalid restoration; no wrap/saturation'
    return out.reshape(*counts.shape[:-1],n),dict(base_shift_min=int(base.min()),base_shift_max=int(base.max()),
        rounded_tile_values=int(rounded.sum()),cross_K_blocks=ng,stored_bits=width,
        metadata_bound_max=int(b.max()),state_abs_max=int(maximum.max()))
