"""A8 three-independent-stream AND -> fixed W8 -> output integer accumulation.

No z materialization/re-encoding in sampled path. Event-count compression is
an exact conditional distribution for independent streams/lane/time, shared
across all Wd outputs. Not the FFN input's shared64 stratified RNG law.
Gate/up restoration remains the explicitly retained FP32 reference boundary.
"""
import math
import torch
from torch.nn import functional as F
from qwen3.nonlinear_width.core import NonlinearFFN, magnitude, make_lut

COEFFICIENT_BITS=16
ACCUMULATOR_BITS=52
MAX_SAMPLES=16384

def event_codes(g,u,g_top,u_top,lut):
    gq,_=magnitude(g,g_top,8);uq,_=magnitude(u,u_top,8)
    gc=(gq.abs()/g_top.repeat_interleave(64)*256).round().to(torch.int64)
    uc=(uq.abs()/u_top.repeat_interleave(64)*256).round().to(torch.int64)
    field=(gq/.125).round().clamp(-128,127).long()
    hc=lut[field+128].long() # 0..256, true-one included
    return gc,hc,uc,gq.sign()*uq.sign()

def literal_events(codes,thresholds):
    g,h,u=codes
    # threshold axes: time, branch, token..., channel
    return (thresholds[:,0]<g)&(thresholds[:,1]<h)&(thresholds[:,2]<u)

def count_events(codes,samples,generator):
    g,h,u=codes
    # integer numerator <=255*256*255 <2**24, probability exactly dyadic.
    probability=(g*h*u).double()/(256**3)
    counts=torch.binomial(torch.full_like(probability,float(samples)),probability,generator=generator)
    return counts.to(torch.int64),probability

def coefficient_table(lsb,g_top,u_top):
    c=lsb.double()*(g_top.double()*u_top.double()).unsqueeze(0)
    maximum=c.amax(-1)
    m,e=torch.frexp(maximum);e-=(m==.5).to(e.dtype)
    top=torch.ldexp(torch.ones_like(maximum),e)
    q=(c/top[:,None]*(2**COEFFICIENT_BITS)).round().clamp(0,2**COEFFICIENT_BITS-1).long()
    return q,e.long(),c

def output_counts(signed_counts,weight_codes,coeff,samples,group_batch=4):
    """Exact integer reference using bounded FP32 partial GEMMs, then int64.

    Each partial absolute sum <=2**24-1, TF32 forbidden. FMA products and
    reductions are integers in the exactly representable FP32 interval.
    Coefficient multiply/reduction uses int64 and cannot overflow 52-bit bound.
    No per-input scale restoration or float Wd is used on this sampled path.
    """
    if samples<1 or samples>MAX_SAMPLES or samples&(samples-1):raise ValueError('power-of-two T<=16384 required')
    if signed_counts.is_cuda and torch.backends.cuda.matmul.allow_tf32:raise ValueError('TF32 must be disabled')
    shape=signed_counts.shape[:-1];n=signed_counts.shape[-1];out=weight_codes.shape[0]
    assert n%64==0 and out%64==0 and tuple(coeff.shape)==(out//64,n//64)
    bound=n*samples*127*((1<<COEFFICIENT_BITS)-1)
    if bound>=(1<<(ACCUMULATOR_BITS-1)):raise ValueError('accumulator bound exceeded')
    x=signed_counts.reshape(-1,n)
    total=torch.zeros(x.shape[0],out,device=x.device,dtype=torch.int64)
    split=min(64,((1<<24)-1)//(samples*127))
    # choose a power-of-two divisor of64
    chunk=1<<(split.bit_length()-1)
    for start in range(0,n//64,group_batch):
        end=min(start+group_batch,n//64);b=end-start
        grouped=x[:,start*64:end*64].reshape(x.shape[0],b,64).permute(1,0,2)
        w=weight_codes[:,start*64:end*64].reshape(out,b,64).permute(1,2,0)
        for offset in range(0,64,chunk):
            partial=torch.bmm(grouped[:,:,offset:offset+chunk].float(),w[:,offset:offset+chunk,:].float()).to(torch.int64)
            multiplier=coeff[:,start:end].T.repeat_interleave(64,dim=1)
            total+=(partial*multiplier[:,None,:]).sum(dim=0)
    return total.reshape(*shape,out)

def finish_bf16(acc,scale_exponents,samples):
    """RNE of the wide integer at output, before BF16 bit storage.

    Normal BF16 results only; reject unexpected nonzero subnormal/overflow.
    Integer quotient/remainder handles ties exactly, avoiding double rounding.
    """
    a=acc.abs()
    _,e=torch.frexp(a.double())
    shift=(e.long()-8).clamp_min(0)
    q=a>>shift;rem=a-(q<<shift)
    half=torch.ones_like(a)<<((shift-1).clamp_min(0))
    inc=(shift>0)&((rem>half)|((rem==half)&((q&1)!=0)))
    rounded=q+inc.long()
    power=scale_exponents.repeat_interleave(64)-COEFFICIENT_BITS-int(math.log2(samples))
    value=torch.ldexp(rounded.double()*acc.sign(),power+shift)
    nonzero=value!=0
    if bool((nonzero&((value.abs()<2.**-126)|(value.abs()>float(torch.finfo(torch.bfloat16).max)))).any()):
        raise ValueError('BF16 output outside validated normal range')
    return value.to(torch.bfloat16)

class DirectFFN(NonlinearFFN):
    def __init__(self,original,layer):
        super().__init__(original,layer)
        self.direct_mode='sampled';self.and_samples=64
        self.rng_and=torch.Generator(device=self.gu_decoded.device).manual_seed(810003+layer*13)
        self.register_buffer('coeff',torch.empty(0,device=self.gu_decoded.device,dtype=torch.int64))
        self.register_buffer('output_exp',torch.empty(0,device=self.gu_decoded.device,dtype=torch.int64))
        self.register_buffer('fixed_effective_weight',torch.empty(0,device=self.gu_decoded.device))
        self.register_buffer('and_stats',torch.zeros(7,device=self.gu_decoded.device,dtype=torch.float64))
        self.set_spec(8,8,8)

    def freeze_down(self):
        self.coeff,self.output_exp,original=coefficient_table(self.down_tile_lsb,self.g_top,self.u_top)
        scale=torch.ldexp(self.coeff.double(),self.output_exp[:,None]-COEFFICIENT_BITS)
        effective=self.down_codes.double()*scale.repeat_interleave(64,0).repeat_interleave(64,1)
        self.fixed_effective_weight=effective.float() # mean diagnostic only
        self.coefficient_nmse=float(((scale-original).square().sum()/original.square().sum()).cpu())

    def reset_direct(self,mode,samples,seed):
        self.direct_mode=mode;self.and_samples=samples;self.and_stats.zero_()
        self.rng_and.manual_seed(810003+seed*1000+self.layer*13)

    def forward(self,x):
        if self.direct_mode=='old_reencode':return super().forward(x)
        self.calls+=1
        g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        gc,hc,uc,sign=event_codes(g,u,self.g_top,self.u_top,self.lut)
        p=(gc*hc*uc).double()/(256**3)
        if self.direct_mode=='mean_legacy':
            value=(sign.double()*p*(self.g_top*self.u_top).repeat_interleave(64)).float()
            return F.linear(value,self.down_decoded).to(x.dtype)
        if self.direct_mode=='mean_fixed':
            return F.linear((sign.double()*p).float(),self.fixed_effective_weight).to(x.dtype)
        if self.direct_mode!='sampled':raise ValueError(self.direct_mode)
        counts,p=count_events((gc,hc,uc),self.and_samples,self.rng_and)
        acc=output_counts(counts*sign.long(),self.down_codes,self.coeff,self.and_samples)
        self.and_stats[0]+=counts.numel()
        self.and_stats[1]+=p.sum()
        self.and_stats[2]+=(counts==0).sum()
        self.and_stats[3]+=counts.sum()
        self.and_stats[4]=torch.maximum(self.and_stats[4],acc.abs().amax().double())
        self.and_stats[5]+=(g.abs()>self.g_top.repeat_interleave(64)*(255/256)).sum()
        self.and_stats[6]+=(u.abs()>self.u_top.repeat_interleave(64)*(255/256)).sum()
        return finish_bf16(acc,self.output_exp,self.and_samples).to(x.dtype)

    def direct_report(self):
        s=self.and_stats.tolist()
        return dict(mode=self.direct_mode,samples=self.and_samples,raw_stats=s,
            mean_event_probability=s[1]/max(s[0],1),zero_count_fraction=s[2]/max(s[0],1),
            g_clip_fraction=s[5]/max(s[0],1),u_clip_fraction=s[6]/max(s[0],1),
            coefficient_bits=COEFFICIENT_BITS,accumulator_bits=ACCUMULATOR_BITS,
            coefficient_nmse=self.coefficient_nmse,z_reencoding=self.direct_mode=='old_reencode',
            sampler='exact conditional binomial; independent3 streams, lanes and clocks',
            output_events_shared_across_wd_outputs=True,gate_up_restore_bittrue=False,
            sampled_wd_integer_reduction=True,bf16_output_rounding='integer RNE; normal range asserted')
