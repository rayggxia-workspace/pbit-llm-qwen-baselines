"""Literal sequential FSM histories, vectorized over independent channels.

Philox implements the ideal independent R8 interface in simulation; this is
not a silicon RNG design or a binomial/mean approximation of FSM outputs.
"""
import torch
import triton as tr
import triton.language as tl

@tr.jit
def _fsm(Q,U,SIGN,THETA,OUT,TRACE,N:tl.constexpr,STATES:tl.constexpr,T:tl.constexpr,
         SEED,DEBUG:tl.constexpr,B:tl.constexpr):
    i=tl.program_id(0)*B+tl.arange(0,B);valid=i<N
    q=tl.load(Q+i,valid,0).to(tl.int32);u=tl.load(U+i,valid,0).to(tl.int32)
    neg=tl.load(SIGN+i,valid,0).to(tl.int32)
    state=tl.full((B,),0,tl.int32);count=tl.full((B,),0,tl.int32)
    for t in range(T):
        # Each stream has a separate Philox key; clock*lane offset is unique.
        offset=i.to(tl.uint32)+t*N
        rg=tl.randint(SEED,offset).to(tl.uint32)&255
        rh=tl.randint(SEED^0x5a17c9e3,offset).to(tl.uint32)&255
        ru=tl.randint(SEED^0xc83d2197,offset).to(tl.uint32)&255
        state=tl.minimum(tl.maximum(state+tl.where(rg<q,1,-1),0),STATES-1)
        theta=tl.load(THETA+neg*STATES+state,valid,0).to(tl.int32)
        event=(rh<theta)&(ru<u);count+=event.to(tl.int32)
        if DEBUG:
            tl.store(TRACE+(t*3+0)*N+i,rg,valid)
            tl.store(TRACE+(t*3+1)*N+i,rh,valid)
            tl.store(TRACE+(t*3+2)*N+i,ru,valid)
    tl.store(OUT+i,count,valid)

def counts(q,u,negative,theta,T,seed,debug=False):
    assert q.is_cuda and q.shape==u.shape==negative.shape
    assert T in (64,128) and theta.shape[0]==2 and theta.shape[1] in (4,8)
    n=q.numel()
    if n*T>=2**32:raise ValueError('Philox per-key counter reuse')
    out=torch.empty_like(q,dtype=torch.int32)
    trace=torch.empty((T,3,n) if debug else (1,),device=q.device,dtype=torch.int16)
    _fsm[(tr.cdiv(n,256),)](q.contiguous(),u.contiguous(),negative.contiguous(),theta.contiguous(),out,trace,
         n,theta.shape[1],T,int(seed)&0xffffffff,debug,256)
    return (out.long(),trace) if debug else out.long()
