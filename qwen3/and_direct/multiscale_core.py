"""Fixed PoT g/u bins, scale-aware sigmoid, exact shifted W8 accumulation.

No test-time max or z reencoding. Stochastic law remains three IID streams.
The software digit decomposition below is exact linear accumulation, not an
additional hardware encoder or an averaging/re-generation of the z stream.
"""
import math
import torch
from torch.nn import functional as F
from .core import DirectFFN,count_events,output_counts,finish_bf16

OFFSETS={1:(0,),2:(0,6),4:(0,2,4,6),8:tuple(range(8))}

def encode_bins(value,top,bins):
    offsets=OFFSETS[bins]
    expanded=top.repeat_interleave(64)
    shift=torch.zeros_like(value,dtype=torch.int64)
    for k in offsets[1:]:shift=torch.where(value.abs()<=expanded*(2.**-k),k,shift)
    scale=torch.ldexp(expanded,-shift)
    code=(value.abs()/scale*256).round().clamp(0,255).long()
    sign=value.sign().long()
    # top is immutable positive PoT; exponent metadata can be prepared once.
    _,exp=torch.frexp(expanded);exp=exp.long()-1-shift
    return code,sign,exp,shift

def sigmoid_field(code,sign,exponent):
    """RNE(signed_code * 2^(exponent-8) / 0.125), signed8 saturation."""
    delta=exponent-5
    right=(-delta).clamp_min(0)
    assert not bool((right>40).any()) and not bool((delta>40).any())
    q=code>>right;rem=code-(q<<right)
    half=torch.ones_like(q)<<(right-1).clamp_min(0)
    inc=(right>0)&((rem>half)|((rem==half)&((q&1)!=0)))
    magnitude=torch.where(delta>=0,code<<delta.clamp_min(0),q+inc.long())
    return (sign*magnitude).clamp(-128,127)

def shifted_output(counts,sign,shifts,weights,coeff,samples,max_shift):
    """Exact equivalent of same-exponent output reduction then left alignment.

Choose smallest common unit: each count contributes count <<(R-r).
Split that exact integer into radix256 digits for bounded FP32-container GEMM.
Actual hardware can bucket r before APC, shift bucket partial sums and merge.
No arithmetic right truncation and no intermediate z estimate is used.
"""
    n=counts.shape[-1]
    bound=n*samples*127*65535*(1<<max_shift)
    if bound>=1<<63:raise ValueError('signed64 accumulator bound exceeded')
    aligned=counts<<(max_shift-shifts)
    out=None
    bits=(samples*(1<<max_shift)).bit_length()
    for k in range(0,bits,8):
        digit=((aligned>>k)&255)*sign
        partial=output_counts(digit,weights,coeff,256)
        value=partial<<k
        out=value if out is None else out+value
    return out

class MultiScaleFFN(DirectFFN):
    def __init__(self,original,layer):
        super().__init__(original,layer)
        self.bins=4;self.multi_mode='sampled'
        # n,p_sum,zeros; x_n/x_power/x_max; g_power/g_max; u_power/u_max;
        # normalized_g_sum/normalized_u_sum; clipping; field saturation
        self.register_buffer('multi_stats',torch.zeros(16,device=self.gu_decoded.device,dtype=torch.float64))
        self.register_buffer('bin_hist',torch.zeros(3,15,device=self.gu_decoded.device,dtype=torch.float64))

    def reset_multi(self,bins,mode,samples,seed):
        self.bins=bins;self.multi_mode=mode
        self.reset_direct('sampled',samples,seed)
        self.multi_stats.zero_();self.bin_hist.zero_()

    def forward(self,x):
        if self.multi_mode=='old_reencode':
            self.direct_mode='old_reencode'
            return super().forward(x)
        self.calls+=1
        g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        gc,gs,ge,gshift=encode_bins(g,self.g_top,self.bins)
        uc,us,ue,ushift=encode_bins(u,self.u_top,self.bins)
        field=sigmoid_field(gc,gs,ge)
        hc=self.lut[field+128].long()
        sign=gs*us;shift=gshift+ushift
        max_shift=2*max(OFFSETS[self.bins])
        counts,p=count_events((gc,hc,uc),self.and_samples,self.rng_and) if self.multi_mode=='sampled' else (None,(gc*hc*uc).double()/256**3)
        s=self.multi_stats
        s[0]+=g.numel();s[1]+=p.sum();s[2]+=0 if counts is None else (counts==0).sum()
        s[3]+=x.numel();s[4]+=x.float().square().sum(dtype=torch.float64);s[5]=torch.maximum(s[5],x.abs().amax().double())
        s[6]+=g.square().sum(dtype=torch.float64);s[7]=torch.maximum(s[7],g.abs().amax().double())
        s[8]+=u.square().sum(dtype=torch.float64);s[9]=torch.maximum(s[9],u.abs().amax().double())
        s[10]+=(gc.double()/256).sum();s[11]+=(uc.double()/256).sum()
        s[12]+=(g.abs()>self.g_top.repeat_interleave(64)*(255/256)).sum()
        s[13]+=(u.abs()>self.u_top.repeat_interleave(64)*(255/256)).sum()
        s[14]+=((field==-128)|(field==127)).sum()
        for i,a in enumerate((gshift,ushift,shift)):
            self.bin_hist[i]+=torch.bincount(a.reshape(-1),minlength=15)
        if self.multi_mode=='mean':
            inputs=torch.ldexp(sign.double()*p,-shift).float()
            return F.linear(inputs,self.fixed_effective_weight).to(x.dtype)
        if self.multi_mode!='sampled':raise ValueError(self.multi_mode)
        acc=shifted_output(counts,sign,shift,self.down_codes,self.coeff,self.and_samples,max_shift)
        s[15]=torch.maximum(s[15],acc.abs().amax().double())
        return finish_bf16(acc,self.output_exp-max_shift,self.and_samples).to(x.dtype)

    def multi_report(self):
        s=self.multi_stats.tolist();r=max(s[0],1)
        return dict(mode=self.multi_mode,bins=self.bins,offsets=OFFSETS[self.bins],samples=self.and_samples,
            mean_event_probability=s[1]/r,zero_count_fraction=None if self.multi_mode!='sampled' else s[2]/r,
            x_rms=math.sqrt(s[4]/max(s[3],1)),g_rms=math.sqrt(s[6]/r),u_rms=math.sqrt(s[8]/r),
            x_max=s[5],g_max=s[7],u_max=s[9],mean_g_probability=s[10]/r,mean_u_probability=s[11]/r,
            raw_stats=s,bin_hist=self.bin_hist.tolist(),coefficient_nmse=self.coefficient_nmse,
            sigmoid='integer RNE signed8 true-scale field then frozen P8 LUT',
            alignment='same-exponent bucket partial sums, exact shift to smallest unit',
            max_alignment_shift=2*max(OFFSETS[self.bins]),output_accumulator_container_bits=64,
            required_bound_bits=(self.width*self.and_samples*127*65535*(1<<(2*max(OFFSETS[self.bins])))).bit_length()+1,
            output_accumulator_observed_max=s[15],z_reencoding=self.multi_mode=='old_reencode',
            gate_up_restore_bittrue=False,random_law='independent branches/lanes/clocks; event shared across Wd outputs')
