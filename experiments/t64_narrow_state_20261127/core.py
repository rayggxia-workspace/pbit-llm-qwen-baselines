"""Exact per-K64 narrow-state behavior. FP32 is only a bounded integer GEMM container."""
from contextlib import AbstractContextManager
import torch

def ceil_log2_positive(x):
    assert x.dtype==torch.int64 and bool((x>0).all())
    e=(torch.frexp(x.double())[1].long()-1).clamp(0,62)
    e=e-(x<(torch.ones_like(e)<<e)).long()
    return e+(x>(torch.ones_like(e)<<e)).long()

def rne_signed_shift(value,delta):
    left=value<<delta.clamp(0,62)
    k=(-delta).clamp(1,62);a=value.abs();q=a>>k;rem=a-(q<<k);half=torch.ones_like(q)<<(k-1)
    q=q+((rem>half)|((rem==half)&((q&1)!=0))).long()
    q=torch.where(-delta>=24,torch.zeros_like(q),q)
    return torch.where(delta>=0,left,q*value.sign())

def common_base(bounds,unit_exponents,width,role):
    level=ceil_log2_positive(bounds)+unit_exponents[None,:]
    m,nb=level.shape
    if role=='GU':
        half=nb//2;p=torch.maximum(level[:,:half],level[:,half:]);level=torch.cat((p,p),-1)
    else:level=level.reshape(m,nb//2,2).amax(-1).repeat_interleave(2,-1)
    return level-(width-2)-unit_exponents[None,:]

def narrow(counts,sign,shifts,weights,coeff,samples,R,width,role,unit_exponents=None):
    if width not in (24,32) or role not in ('GU','Wd'):raise ValueError('validated widths and roles only')
    if torch.backends.cuda.matmul.allow_tf32:raise ValueError('bounded integer FP32 GEMM requires TF32 disabled')
    k=counts.shape[-1];n=weights.shape[0];m=counts.numel()//k;ng=k//64;nb=n//64
    assert k%64==0 and n%128==0 and coeff.shape==(nb,ng)
    assert samples in (16,32) and 0<=R<=40
    assert k*samples*127*int(coeff.max())*(1<<R)<1<<63
    c=counts.reshape(m,k).long();s=sign.reshape(m,k).long();h=shifts.reshape(m,ng,64).long()
    lo=h.amin(-1);hi=h.amax(-1)
    assert bool(((hi-lo)<=2).all()),'local 23bit contract requires at most 2 correction bits'
    ce=torch.frexp(coeff.double())[1].long()-1
    assert bool((coeff==(torch.ones_like(ce)<<ce)).all()) and bool((coeff>=1).all())
    # Bound uses only shape/sample cap/W8 limit/scale metadata, never counts,
    # weight values, output magnitudes, or cancellation.
    b=((64*samples*127)<<(R-lo))[:,None,:]*coeff[None,:,:]
    b=b.sum(-1)
    if unit_exponents is None:unit_exponents=torch.zeros(nb,device=c.device,dtype=torch.int64)
    assert unit_exponents.numel()==nb
    base=common_base(b,unit_exponents.reshape(nb).long(),width,role)
    state=torch.zeros((m,nb,64),dtype=torch.int64,device=c.device)
    errors=torch.zeros_like(state,dtype=torch.bool)
    rounded=torch.zeros((),dtype=torch.int64,device=c.device)
    for g in range(ng):
        local=(c[:,g*64:(g+1)*64]<<(hi[:,g,None]-h[:,g]))*s[:,g*64:(g+1)*64]
        # Every product and any partial sum has |value| <=64*T*127*4 <2^23.
        # FP32 products/reductions are therefore exact integers (TF32 off).
        part=(local.float()@weights[:,g*64:(g+1)*64].float().T).long().reshape(m,nb,64)
        assert 64*samples*127*4<1<<23
        errors |= (part<-(1<<22))|(part>(1<<22)-1)
        delta=(R-hi[:,g,None]+ce[None,:,g]-base)[:,:,None]
        errors |= (delta>=width)&(part!=0)
        aligned=rne_signed_shift(part,delta)
        # Count changed tile values before accumulation, not changed outputs.
        inverse=torch.where(delta<0,aligned<<(-delta).clamp(0,62),part)
        rounded+=(inverse!=part).sum()
        new=state+aligned
        bad=(new<-(1<<(width-1)))|(new>(1<<(width-1))-1)
        errors |= bad
        state=torch.where(bad,state,new)
    assert not bool(errors.any()),'narrow state overflow; no wrap/saturation permitted'
    expand=base[:,:,None]
    limit=((1<<63)-1)>>expand.clamp_min(0)
    assert bool((state.abs()<=limit).all()),'restored reference transport would overflow signed64'
    fine=(-expand).clamp_min(0)
    assert not bool(((state.abs()&((torch.ones_like(fine)<<fine)-1))*(expand<0)).any())
    restored=(state<<expand.clamp_min(0))>>fine
    return restored.reshape(*counts.shape[:-1],n),dict(base_shift_min=int(base.min()),base_shift_max=int(base.max()),
        rounded_tile_values=int(rounded),cross_K_blocks=ng,stored_bits=width,
        metadata_bound_max=int(b.max()),state_abs_max=int(state.abs().max()))

class NarrowOverride(AbstractContextManager):
    def __init__(self,width):
        assert width in (24,32,64);self.width=width;self.stats={}
    def __enter__(self):
        import wide_wd,seven_forward as sf
        self.sf=sf;self.old_coeff=sf.exact_coefficients
        def coefficients(*a,**kw):
            cf,ex=self.old_coeff(*a,**kw);self.pending_ex=ex;return cf,ex
        sf.exact_coefficients=coefficients
        self.old=wide_wd.shifted_output
        def output(counts,sign,shifts,weights,coeff,samples,max_shift,qmax=127):
            assert qmax==127
            ref=self.old(counts,sign,shifts,weights,coeff,samples,max_shift,qmax)
            if self.width==64:return ref
            role='GU' if weights.shape[0]==19456 else 'Wd'
            assert weights.shape[0] in (19456,2560)
            value,info=narrow(counts,sign,shifts,weights,coeff,samples,max_shift,self.width,role,self.pending_ex)
            z=self.stats.setdefault(role,dict(calls=0,values=0,changed_integer_values=0,max_integer_error=0,
                         max_group_relative_error=0.,max_base_shift=-99,min_base_shift=99,rounded_tile_values=0))
            z['calls']+=1;z['values']+=value.numel();z['changed_integer_values']+=int((value!=ref).sum())
            err=(value-ref).abs();p=ref.abs().reshape(-1,ref.shape[-1]//64,64).amax(-1)
            p=torch.ldexp(p.double(),self.pending_ex[None,:])
            if role=='GU':
                nb=p.shape[-1]//2;pair=torch.maximum(p[:,:nb],p[:,nb:]);p=torch.cat((pair,pair),-1)
            else:p=p.reshape(p.shape[0],-1,2).amax(-1).repeat_interleave(2,-1)
            peak=p[:,:,None]
            z['max_integer_error']=max(z['max_integer_error'],int(err.max()))
            physical_error=torch.ldexp(err.reshape_as(peak.expand(-1,-1,64)).double(),self.pending_ex[None,:,None])
            ratio=torch.where(peak>0,physical_error/peak.clamp_min(torch.finfo(torch.float64).tiny),0.)
            z['max_group_relative_error']=max(z['max_group_relative_error'],float(ratio.max()))
            z['zero_reference_values_changed']=z.get('zero_reference_values_changed',0)+int(((peak==0)&(physical_error>0)).sum())
            z['max_base_shift']=max(z['max_base_shift'],info['base_shift_max'])
            z['min_base_shift']=min(z['min_base_shift'],info['base_shift_min'])
            z['rounded_tile_values']+=info['rounded_tile_values'];z['cross_K_blocks']=info['cross_K_blocks']
            return value
        wide_wd.shifted_output=output
        return self
    def __exit__(self,*exc):
        import wide_wd
        wide_wd.shifted_output=self.old
        self.sf.exact_coefficients=self.old_coeff
    def report(self):return dict(stored_state_bits=self.width,stages=self.stats,
        contract='K64 local signed23, metadata-derived common base with 2 guard bits, per-tile RNE, error on overflow; original sigmoid unchanged')
