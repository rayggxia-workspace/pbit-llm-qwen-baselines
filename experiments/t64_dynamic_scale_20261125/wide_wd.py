"""Exact bounded integer Wd, same exact integer operator; 64-bit pre-digit alignment for dynamic scales.
INT8 tensor-core partial dots, INT64 coefficient/shift/accumulation. Does not
change random law, counts, finite coefficients or final BF16 rounding.
"""
import torch
import triton
import triton.language as tl
@triton.jit
def _wd(C,S,H,W,F,O,M,K:tl.constexpr,N:tl.constexpr,R:tl.constexpr,D:tl.constexpr,QMAX:tl.constexpr,CR:tl.constexpr,BM:tl.constexpr=16,BN:tl.constexpr=64):
 pm=tl.program_id(0);pn=tl.program_id(1)
 rows=pm*BM+tl.arange(0,BM);out=pn*BN+tl.arange(0,BN);kk=tl.arange(0,64)
 total=tl.full((BM,BN),0,tl.int64)
 for g in range(K//64):
  ix=rows[:,None]*K+g*64+kk[None,:]
  c=tl.load(C+ix,rows[:,None]<M,other=0).to(tl.int64)
  sg=tl.load(S+ix,rows[:,None]<M,other=0).to(tl.int32)
  sh=tl.load(H+ix,rows[:,None]<M,other=R).to(tl.int32)
  aligned=c << (R-sh)
  w=tl.load(W+out[None,:]*K+g*64+kk[:,None],out[None,:]<N,other=0).to(tl.int32)
  ws=tl.where(w<0,-1,1);wa=tl.abs(w)
  wl=((wa&127)*ws).to(tl.int8)
  if QMAX>127:wh=((wa>>7)*ws).to(tl.int8)
  if CR:cf=tl.load(F+rows*((N//64)*(K//64))+pn*(K//64)+g,rows<M,other=0).to(tl.int64)[:,None]
  else:cf=tl.load(F+pn*(K//64)+g).to(tl.int64)
  for d in tl.static_range(D):
   digit=(((aligned>>(7*d))&127)*sg).to(tl.int8)
   part=tl.dot(digit,wl,out_dtype=tl.int32).to(tl.int64)
   if QMAX>127:part=part+(tl.dot(digit,wh,out_dtype=tl.int32).to(tl.int64)<<7)
   total=total+((part*cf)<<(7*d))
 tl.store(O+rows[:,None]*N+out[None,:],total,(rows[:,None]<M)&(out[None,:]<N))

def shifted_output(counts,sign,shifts,weights,coeff,samples,max_shift,qmax=127):
 k=counts.shape[-1];n=weights.shape[0];m=counts.numel()//k;cr=coeff.ndim==3
 if not counts.is_cuda or k%64 or n%64 or tuple(coeff.shape)!=((m,n//64,k//64) if cr else (n//64,k//64)):raise ValueError('CUDA and exact64 tile shapes required')
 if samples<1 or samples>256 or samples&(samples-1) or max_shift<0 or max_shift>40:raise ValueError('unvalidated count/alignment bounds')
 actual_coeff_max=int(coeff.max().item())
 if qmax not in (31,127,511) or actual_coeff_max<1 or k*samples*qmax*actual_coeff_max*(1<<max_shift)>=1<<63:raise ValueError('unvalidated actual signed64 bound')
 if any(not t.is_contiguous() for t in (counts,sign,shifts,weights,coeff)):raise ValueError('contiguous integer tensors required')
 out=torch.empty((*counts.shape[:-1],n),device=counts.device,dtype=torch.int64);m=counts.numel()//k;d=((samples*(1<<max_shift)).bit_length()+6)//7
 _wd[(triton.cdiv(m,16),n//64)](counts,sign,shifts,weights,coeff,out,m,k,n,max_shift,d,qmax,cr,num_warps=4)
 return out
