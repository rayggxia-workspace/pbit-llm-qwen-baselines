"""Only GU changes: W8 magnitude/128 Bernoulli, unchanged nonlinear/direct Wd.

Conditional binomials compress the finite AND law, no Gaussian/mean fallback.
The simulation restores tile scales in FP32, as the retained upstream oracle.
"""
import torch
from qwen3.and_direct.short_core import ShortStreamFFN
from qwen3.fixed_scale.static_core import _encode_static_validated
from qwen3.stochastic.vendor.stratified_core import stratified_counts

GRIDS={32:(8,4),64:(8,8),128:(16,8),256:(16,16)}


def input_cells(q,samples,law,generator=None):
    """Shared64 A draws; for joint law retain counts by W-stratum."""
    if samples not in GRIDS or q.shape[-1]%64:raise ValueError('T32/64/128/256 and K64 required')
    rows=q.numel()//q.shape[-1];groups=q.shape[-1]//64
    if law=='iid':
        counts=stratified_counts(q.float()/256,samples,min(64,samples),generator).reshape(rows,groups,1,64)
        prefix=torch.zeros_like(counts)
    elif law=='joint':
        ka,kw=GRIDS[samples];width=256//ka
        a=torch.arange(ka,device=q.device).reshape(1,1,ka,1)*width
        thresholds=a+torch.randint(width,(rows,groups,ka,kw),device=q.device,generator=generator)
        bits=thresholds[...,None]<q.reshape(rows,groups,1,1,64)
        counts=bits.sum(2)
        prefix=torch.nn.functional.pad(counts.cumsum(-2),(0,0,1,0))[:,:,:kw,:]
    else:raise ValueError('unknown law')
    return counts.to(torch.int16).contiguous(),prefix.to(torch.int16).contiguous()


def conditional_parts(counts,prefix,weight_magnitude,kw):
    """Small CPU oracle for one input group; outputs [row,out,input]."""
    m=weight_magnitude.long();bins=m//(128//kw);rem=(m%(128//kw))*kw
    ix=bins[None,:,:].expand(counts.shape[0],-1,-1)
    n=counts.transpose(1,2).gather(2,ix.transpose(1,2)).transpose(1,2)
    base=prefix.transpose(1,2).gather(2,ix.transpose(1,2)).transpose(1,2)
    return base,n,rem.float()/128


def reference_project(encoded,codes,lsb,samples,law,generator=None,weight_generator=None):
    """CPU small-shape conditional-binomial reference, no CDF approximation."""
    q=(encoded['probability']*256).short();cnt,pre=input_cells(q,samples,law,generator)
    rows,groups,kw,_=cnt.shape;out=codes.shape[0]
    total=torch.zeros(rows,out,dtype=torch.float64,device=q.device)
    scales=encoded['scale'].reshape(rows,groups,64);sign=encoded['sign'].reshape(rows,groups,64)
    for k in range(groups):
        w=codes[:,k*64:(k+1)*64].long();base,n,p=conditional_parts(cnt[:,k],pre[:,k],w.abs(),kw)
        draw=torch.binomial(n.double(),p.double().expand_as(n),generator=weight_generator)
        weighted=((base+draw)*w.sign()[None,:,:]*sign[:,k,None,:]*scales[:,k,None,:]).sum(-1)
        total+=weighted*lsb[:,k].repeat_interleave(64)[None,:]*128/samples
    return total.float().reshape(*q.shape[:-1],out)


class DualGUFFN(ShortStreamFFN):
    def reset_gu(self,method,samples,seed):
        if method not in ('fixed','iid','joint') or samples not in GRIDS:raise ValueError('invalid GU config')
        self.gu_method,self.gu_samples=method,samples
        if bool((self.gu_codes==-128).any()):raise ValueError('symmetric W8 excludes-128')
        self.rng_weight=torch.Generator(device=self.gu_codes.device).manual_seed(910003+seed*1009+self.layer*13)
        self.gu_sample_calls=0

    def _stage(self,value,signal,matrix,generator):
        if matrix!='gu' or not hasattr(self,'gu_method'):return super()._stage(value,signal,matrix,generator)
        if self.gu_method=='fixed':
            old=(self.cycles,self.strata);self.cycles=self.gu_samples;self.strata=min(64,self.gu_samples)
            try:return super()._stage(value,signal,matrix,generator)
            finally:self.cycles,self.strata=old
        if self.x_scales is None:raise ValueError('TRAIN-frozen x scales required')
        encoded=_encode_static_validated(value,self.x_scales)
        self.gu_sample_calls+=1
        if value.is_cuda:
            from .kernel import project
            return project(encoded,self.gu_codes,self.gu_tile_lsb,self.gu_samples,self.gu_method,generator,self.rng_weight)
        return reference_project(encoded,self.gu_codes,self.gu_tile_lsb,self.gu_samples,self.gu_method,generator,self.rng_weight)
