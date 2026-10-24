"""Fixed four-bin g/u and 32 JOINT (4 x 2 x 4) strata, T<=128.

This is not 32 marginal strata per branch, and not an FSM implementation.
Clock's high random bits enumerate Cartesian cells; independent random low
bits are drawn inside each cell. Counts compress that exact law, retaining
the common event across all Wd output columns and independent input lanes.
"""
import itertools
import math
import torch
from torch.nn import functional as F
from .core import count_events, finish_bf16
from .multiscale_core import MultiScaleFFN, sigmoid_field, shifted_output

POLICIES = {'original': (0,2,4,6), 'lower_half': (1,3,5,7),
            'lower_floor': (0,2,4,7)}
GRID = (4,2,4)  # g, sigmoid(g), u


def validate_samples(samples):
    if samples not in (32,64,128):
        raise ValueError('T must be 32,64,128; 32 joint cells, 1,2,4 draws/cell')


def joint_components(codes, samples):
    """Seven disjoint boundary-cell classes; full cells are deterministic."""
    validate_samples(samples)
    if len(codes)!=3 or any(q.shape!=codes[0].shape for q in codes):
        raise ValueError('three equally shaped threshold tensors required')
    if any(q.dtype!=torch.int64 for q in codes):
        raise ValueError('threshold codes must be int64')
    if codes[0].device.type=='cpu' and any(bool(((q<0)|(q>256)).any()) for q in codes):
        raise ValueError('thresholds must be in 0..256')
    full=[q//(256//d) for q,d in zip(codes,GRID)]
    frac=[(q%(256//d)).double()/(256//d) for q,d in zip(codes,GRID)]
    repeats=samples//32
    deterministic=full[0]*full[1]*full[2]*repeats
    terms=[]
    for mask in range(1,8):
        trials=torch.full_like(codes[0],repeats)
        probability=torch.ones_like(frac[0])
        for axis in range(3):
            if mask&(1<<axis):
                probability=probability*frac[axis]
                trials=trials*(full[axis]<GRID[axis]).long()
            else:
                trials=trials*full[axis]
        terms.append((trials,probability))
    return deterministic,terms


def joint_counts(codes,samples,generator=None):
    count,terms=joint_components(codes,samples)
    for trials,p in terms:
        count=count+torch.binomial(trials.double(),p,generator=generator).long()
    probability=(codes[0]*codes[1]*codes[2]).double()/256**3
    return count,probability


def joint_moments(codes,samples):
    count,terms=joint_components(codes,samples)
    mean=count.double();var=torch.zeros_like(mean)
    for trials,p in terms:
        mean=mean+trials*p;var=var+trials*p*(1-p)
    return mean,var


def literal_joint(codes,samples,generator=None):
    """Independent reference: three R8 comparators and AND every clock."""
    validate_samples(samples)
    count=torch.zeros_like(codes[0])
    for cell in itertools.product(*(range(d) for d in GRID)):
        for _ in range(samples//32):
            event=torch.ones_like(count,dtype=torch.bool)
            for q,i,d in zip(codes,cell,GRID):
                width=256//d
                r=i*width+torch.randint(width,q.shape,device=q.device,generator=generator)
                event=event&(r<q)
            count=count+event.long()
    return count


def encode_fixed(value,top,offsets):
    expanded=top.repeat_interleave(64)
    shift=torch.full_like(value,offsets[0],dtype=torch.int64)
    for k in offsets[1:]:
        shift=torch.where(value.abs()<=expanded*(2.**-k),k,shift)
    scale=torch.ldexp(expanded,-shift)
    code=(value.abs()/scale*256).round().clamp(0,255).long()
    _,exp=torch.frexp(expanded)
    return code,value.sign().long(),exp.long()-1-shift,shift


class ShortStreamFFN(MultiScaleFFN):
    def reset_short(self,policy,law,samples,seed):
        validate_samples(samples)
        if policy not in POLICIES or law not in ('mean','iid','joint32'):
            raise ValueError('unknown fixed policy or sampling law')
        self.policy=policy;self.offsets=POLICIES[policy];self.law=law
        self.reset_multi(4,'mean' if law=='mean' else 'sampled',samples,seed)

    def forward(self,x):
        self.calls+=1
        g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        gc,gs,ge,gshift=encode_fixed(g,self.g_top,self.offsets)
        uc,us,ue,ushift=encode_fixed(u,self.u_top,self.offsets)
        field=sigmoid_field(gc,gs,ge);hc=self.lut[field+128].long()
        sign=gs*us;shift=gshift+ushift;max_shift=2*max(self.offsets)
        codes=(gc,hc,uc)
        if self.law=='mean':
            counts=None;p=(gc*hc*uc).double()/256**3
        elif self.law=='iid':
            counts,p=count_events(codes,self.and_samples,self.rng_and)
        else:
            counts,p=joint_counts(codes,self.and_samples,self.rng_and)
        s=self.multi_stats
        s[0]+=g.numel();s[1]+=p.sum();s[2]+=0 if counts is None else (counts==0).sum()
        s[3]+=x.numel();s[4]+=x.float().square().sum(dtype=torch.float64);s[5]=torch.maximum(s[5],x.abs().amax().double())
        s[6]+=g.square().sum(dtype=torch.float64);s[7]=torch.maximum(s[7],g.abs().amax().double())
        s[8]+=u.square().sum(dtype=torch.float64);s[9]=torch.maximum(s[9],u.abs().amax().double())
        s[10]+=(gc.double()/256).sum();s[11]+=(uc.double()/256).sum()
        s[12]+=(g.abs()>self.g_top.repeat_interleave(64)*(2.**-self.offsets[0])*(255/256)).sum()
        s[13]+=(u.abs()>self.u_top.repeat_interleave(64)*(2.**-self.offsets[0])*(255/256)).sum()
        s[14]+=((field==-128)|(field==127)).sum()
        for i,a in enumerate((gshift,ushift,shift)):
            self.bin_hist[i]+=torch.bincount(a.reshape(-1),minlength=15)
        if self.law=='mean':
            return F.linear(torch.ldexp(sign.double()*p,-shift).float(),self.fixed_effective_weight).to(x.dtype)
        acc=shifted_output(counts,sign,shift,self.down_codes,self.coeff,self.and_samples,max_shift)
        s[15]=torch.maximum(s[15],acc.abs().amax().double())
        return finish_bf16(acc,self.output_exp-max_shift,self.and_samples).to(x.dtype)

    def short_report(self):
        r=super().multi_report();s=self.multi_stats.tolist();n=max(s[0],1)
        r.update(policy=self.policy,offsets=self.offsets,law=self.law,
            random_law='IID independent branches/lanes/clocks' if self.law=='iid' else
                       'conditional mean' if self.law=='mean' else
                       '32 Cartesian cells (4 g x 2 sigmoid x 4 u); independent draws/lanes/cells',
            joint_strata=32 if self.law=='joint32' else None,
            draws_per_joint_stratum=self.and_samples//32 if self.law=='joint32' else None,
            g_clip_fraction=s[12]/n,u_clip_fraction=s[13]/n,
            max_alignment_shift=2*max(self.offsets),
            required_bound_bits=(self.width*self.and_samples*127*65535*(1<<(2*max(self.offsets)))).bit_length()+1,
            fsm=False,front_T=64,front_K=64,front_fixed_bins=4)
        return r
