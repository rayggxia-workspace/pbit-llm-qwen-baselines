"""Fixed g binary point -> scale-aware FSM -> AND(u) -> fixed W8 Wd."""
import math
import torch
from torch.nn import functional as F
from qwen3.and_direct.core import DirectFFN,finish_bf16
from qwen3.and_direct.short_core import encode_fixed
from qwen3.and_direct.multiscale_core import shifted_output

class FSMFFN(DirectFFN):
    def setup(self,G,Sneg,utop,tables):
        dev=self.gu_decoded.device
        self.G=G;self.Sneg=Sneg
        self.negative_shift=int(math.log2(G/Sneg));assert G/Sneg==2**self.negative_shift
        self.g_top=torch.full_like(self.g_top,float(G));self.u_top=torch.tensor(utop,device=dev,dtype=torch.float32)
        self.freeze_down()
        self.fsm_tables={T:{k:torch.tensor(b[k],device=dev,dtype=torch.int64 if k in ('theta','lut') else torch.float64)
                           for k in ('theta','lut','mean')} for T,b in tables.items()}
        self.register_buffer('fsm_stats',torch.zeros(9,device=dev,dtype=torch.float64))

    def reset_fsm(self,mode,T,seed):
        assert mode in ('lut_mean','fsm_mean','fsm') and T in (64,128)
        self.fsm_mode=mode;self.and_samples=T;self.fsm_seed=seed;self.fsm_stats.zero_()

    def forward(self,x):
        self.calls+=1
        g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        # Model simulator FP32 container -> explicit fixed binary-point RNE.
        # Front matrix finite restoration is still a reference, not bittrue RTL.
        q=(g.abs()*(256/self.G)).round().clamp(0,255).long()
        neg=(g<0).long();gs=g.sign().long()
        uc,us,_,ushift=encode_fixed(u,self.u_top,(1,3,5,7))
        shift=ushift+neg*self.negative_shift;sign=gs*us
        tab=self.fsm_tables[self.and_samples]
        f=tab['lut'][neg,q].double()/256 if self.fsm_mode=='lut_mean' else tab['mean'][neg,q]
        p=f*uc.double()/256
        s=self.fsm_stats;s[0]+=q.numel();s[1]+=(g.abs()>self.G*255/256).sum()
        s[2]+=(q==0).sum();s[3]+=p.sum();s[4]+=g.square().sum(dtype=torch.float64)
        s[5]=torch.maximum(s[5],g.abs().amax().double())
        if self.fsm_mode!='fsm':
            # Diagnostic only, keeps front stochastic matrix; not deployable LUT mean.
            return F.linear(torch.ldexp(sign.double()*p,-shift).float(),self.fixed_effective_weight).to(x.dtype)
        from .model_kernel import counts
        seed=971003+self.fsm_seed*100003+self.layer*101+self.calls*1009
        c=counts(q,uc,neg,tab['theta'],self.and_samples,seed)
        s[6]+=(c==0).sum();s[7]+=c.sum()
        max_shift=7+self.negative_shift
        acc=shifted_output(c,sign,shift,self.down_codes,self.coeff,self.and_samples,max_shift)
        s[8]=torch.maximum(s[8],acc.abs().amax().double())
        return finish_bf16(acc,self.output_exp-max_shift,self.and_samples).to(x.dtype)

    def report(self):
        s=self.fsm_stats.tolist();n=max(s[0],1)
        return dict(mode=self.fsm_mode,T=self.and_samples,G=self.G,Sneg=self.Sneg,
                    g_clip_fraction=s[1]/n,g_zero_code_fraction=s[2]/n,
                    expected_event_probability=s[3]/n,g_rms=math.sqrt(s[4]/n),g_max=s[5],
                    zero_count_fraction=s[6]/n if self.fsm_mode=='fsm' else None,
                    measured_event_probability=s[7]/n/self.and_samples if self.fsm_mode=='fsm' else None,
                    accumulator_observed_max=s[8],raw_stats=s,z_reencoding=False,
                    front_T=64,front_K=64,front_fixed_bins=4,gate_up_restore_bittrue=False,
                    g_online_absmax=False,g_per_value_bin_selector=False,
                    g_fixed_step=self.G/256,u_fixed_offsets=[1,3,5,7],
                    fsm_reset=0,fsm_sample_after_update=True,burnin=0,
                    output_events_shared_across_wd_outputs=True)
