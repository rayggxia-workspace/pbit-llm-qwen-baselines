"""Decouple real-g sigmoid drive from shared/clipped magnitude encodings."""
import torch
from torch.nn import functional as F
from .pot_weight import PoTWeightFFN
from .core import encode_nl
from qwen3.and_direct.multiscale_core import sigmoid_field,shifted_output
from qwen3.and_direct.short_core import joint_counts
from qwen3.and_direct.core import finish_bf16

POLICIES={'max':(0,0),'g_trim1':(1,0),'u_trim1':(0,1),'both_trim1':(1,1),'both_trim4':(4,4)}

def original_g_field(g):
    """Real g -> signed8 field, step1/8,RNE,saturate. No FP sigmoid.

    GU is the declared upstream FP32 numerical oracle. Hardware must use the
    equivalent rounded shift from its fixed-point accumulator,not FP sigmoid.
    """
    return (g.float()*8).round().clamp(-128,127).long()

class IndependentGateFFN(PoTWeightFFN):
    def __init__(self,original,layer):
        super().__init__(original,layer)
        self.gate_mode='original_g';self.amplitude_policy='max';self.allow_g=0;self.allow_u=0
        self.register_buffer('gate_stats',torch.zeros(3,device=self.gu_codes.device,dtype=torch.float64))

    def reset_gate(self,policy,gate_mode='original_g'):
        if policy not in POLICIES or gate_mode not in ('original_g','old_coupled'):raise ValueError('unknown gate policy')
        self.reset_shared('all_max');self.amplitude_policy=policy;self.allow_g,self.allow_u=POLICIES[policy]
        self.gate_mode=gate_mode;self.gate_stats.zero_()
        if gate_mode=='old_coupled' and policy!='max':raise ValueError('old replay only uses max')

    def forward(self,x):
        if self.gate_mode=='old_coupled':return super().forward(x)
        self.calls+=1;g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        field=original_g_field(g) # BEFORE amplitude encode/clip, independent of Sg/Su.
        gc,gs,ge,gshift=encode_nl(g,self.g_top,self.offsets,True,self.allow_g)
        uc,us,ue,ushift=encode_nl(u,self.u_top,self.offsets,True,self.allow_u)
        for i,v,c,s,e,h in ((1,g,gc,gs,ge,gshift),(2,u,uc,us,ue,ushift)):
            scale=torch.ldexp(torch.ones_like(v),e);bins=torch.zeros_like(h)
            for k,off in enumerate(self.offsets):bins=torch.where(h==off,k,bins)
            self._record(i,v,scale,c.double()/256,torch.ldexp(c.float()*s/256,e),bins,True)
        hc=self.lut[field+128].long();previous=self.lut[sigmoid_field(gc,gs,ge)+128].long()
        self.gate_stats[0]+=field.numel();self.gate_stats[1]+=(hc!=previous).sum();self.gate_stats[2]+=(hc-previous).abs().sum(dtype=torch.float64)/256
        if self.nonlinear_mean:
            p=(gc*hc*uc).double()/256**3
            self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum()
            v=torch.ldexp(gs*us*p,-gshift-ushift).float()
            return F.linear(v,self.fixed_effective_weight).to(x.dtype)
        counts,p=joint_counts((gc,hc,uc),self.and_samples,self.rng_and)
        self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum();self.event_stats[2]+=(counts==0).sum()
        limit=2*max(self.offsets);acc=shifted_output(counts,gs*us,gshift+ushift,self.down_codes,self.coeff,self.and_samples,limit)
        return finish_bf16(acc,self.output_exp-limit,self.and_samples).to(x.dtype)

    def shared_report(self):
        r=super().shared_report();n,changed,total=self.gate_stats.tolist()
        r.update(amplitude_policy=self.amplitude_policy,allow_g=self.allow_g,allow_u=self.allow_u,gate_mode=self.gate_mode,
            sigmoid='real-g before amplitude clipping -> RNE signed8 step1/8 -> existing P8 LUT' if self.gate_mode=='original_g' else 'old magnitude-reconstructed g field replay',
            allow_clipped_per_group=None,gate_probability_changed_fraction=changed/max(n,1),gate_probability_mean_absolute_change=total/max(n,1),
            unchanged='x groupmax four frozen PoT,Wg/Wu/Wd PoT64x64,GU64,NLjoint32T128,accurateSDPA')
        return r
