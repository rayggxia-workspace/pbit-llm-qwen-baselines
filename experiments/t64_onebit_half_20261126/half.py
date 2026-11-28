"""One-bit S/S2 ablation on the frozen S/S4 forward, with range observations."""
import math
import torch
import onebit

FROZEN_ENCODE=onebit.encode
MIN_EXP=onebit.MIN_EXP


def encode(value,cap,correction=True,step_bits=1):
    if step_bits not in (1,2) or value.shape[-1]%64 or cap not in (256.,512.):
        raise ValueError('validated group64, cap and S/S2 or S/S4 required')
    v=value.float()
    if not bool(torch.isfinite(v).all()):raise ValueError('finite values required')
    a=v.abs().reshape(*v.shape[:-1],-1,64)
    maximum=a.amax(-1,keepdim=True)
    mantissa,e=torch.frexp(maximum)
    base=torch.where(maximum==0,MIN_EXP,e-(mantissa==.5).int())
    base=base.clamp(MIN_EXP,int(math.log2(cap))).long()
    base_lane=base.expand_as(a).reshape_as(v)
    eligible=base_lane>=MIN_EXP+step_bits
    small=(v.abs()<=torch.ldexp(torch.ones_like(v),base_lane-step_bits)) & eligible
    if not correction:small=torch.zeros_like(small)
    exponent=base_lane-step_bits*small.long()
    selected=torch.ldexp(torch.ones_like(v),exponent)
    q=torch.ldexp(v.abs(),8-exponent).round().clamp(0,255).long()
    q=torch.where((v.abs()>=selected)&(v!=0),256,q)
    return dict(q=q,sign=v.sign().long(),exponent=exponent,
                shift=int(math.log2(cap))-exponent,scale=selected,
                base_exponent=base_lane,small=small,floor_limited=~eligible)


class FractionOverride(onebit.OnebitOverride):
    def __init__(self,policy,step_bits):
        if policy not in ('gu_onebit64','all64_onebit') or step_bits not in (1,2):raise ValueError((policy,step_bits))
        super().__init__(policy)
        self.step_bits=step_bits
        self.ranges={}
        self.group_ranges={}
        self.pending_g=None

    def observe(self,name,value,enc):
        super().observe(name,value,enc)
        if name=='g':self.pending_g=enc
        if name=='u':
            assert self.pending_g is not None
            g=self.pending_g;self.pending_g=None
            exponent=(g['exponent']+enc['exponent']).reshape(-1,64)
            span=int((exponent.amax(-1)-exponent.amin(-1)).max())
            assert span<=2*self.step_bits
            z=self.group_ranges
            z['within_group_product_exponent_span_max']=max(z.get('within_group_product_exponent_span_max',0),span)
            lo,hi=int(exponent.min()),int(exponent.max())
            z['product_exponent_min']=min(z.get('product_exponent_min',lo),lo)
            z['product_exponent_max']=max(z.get('product_exponent_max',hi),hi)

    def __enter__(self):
        import wide_wd
        self.saved_encode=onebit.encode
        self.saved_output=wide_wd.shifted_output
        def encode_now(value,cap,correction=True):return encode(value,cap,correction,self.step_bits)
        def output(counts,sign,shifts,weights,coeff,samples,max_shift,qmax=127):
            result=self.saved_output(counts,sign,shifts,weights,coeff,samples,max_shift,qmax)
            role='GU' if weights.shape[0]==19456 else 'Wd'
            assert weights.shape[0] in (19456,2560)
            z=self.ranges.setdefault(role,dict(calls=0,max_alignment_bits=0,max_observed_symmetric_signed_bits=0,max_conservative_bound_signed_bits=0))
            magnitude=int(result.abs().max())
            bound=counts.shape[-1]*samples*qmax*int(coeff.max())*(1<<max_shift)
            assert magnitude<=bound and bound<1<<63
            z['calls']+=1
            z['max_alignment_bits']=max(z['max_alignment_bits'],max_shift)
            z['max_observed_symmetric_signed_bits']=max(z['max_observed_symmetric_signed_bits'],1+magnitude.bit_length())
            z['max_conservative_bound_signed_bits']=max(z['max_conservative_bound_signed_bits'],1+bound.bit_length())
            return result
        onebit.encode=encode_now
        wide_wd.shifted_output=output
        try:return super().__enter__()
        except BaseException:
            onebit.encode=self.saved_encode;wide_wd.shifted_output=self.saved_output
            raise

    def __exit__(self,*exc):
        import wide_wd
        try:return super().__exit__(*exc)
        finally:
            onebit.encode=self.saved_encode
            wide_wd.shifted_output=self.saved_output
            self.pending_g=None

    def report(self):
        return dict(probability_codes=super().report(),group_scales=self.group_ranges,integer_backend=self.ranges,
            step_bits=self.step_bits,small_scale_divisor=1<<self.step_bits,
            boundary='observed integer backend and its conservative whole-projection bound; not a calibrated RTL accumulator width')
