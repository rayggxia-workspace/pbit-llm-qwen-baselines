"""User clarified contract: Wg/Wu/Wd W8 share a PoT step per64x64.

Activation x and g/u output code choices remain frozen four PoT scales,
selected per64 channels when shared. GU FP32 restore is still an oracle.
"""
import torch
from torch.nn import functional as F
from .core import Group64FFN
from .mean_diagnostic import MeanGroupFFN

def exact_pow2(exponents):
    """Construct normal binary64 PoT by IEEE bits, avoiding CUDA ldexp ULPs.

    This offline constant construction is a simulator detail; hardware keeps
    the integer exponent. Do not relax an exact scale equality into tolerance.
    """
    e=exponents.to(torch.int64)
    if bool(((e < -1022)|(e > 1023)).any()):raise ValueError('normal binary64 exponent required')
    return ((e+1023)<<52).contiguous().view(torch.float64)


def quantize_pot64(weight):
    rows,cols=weight.shape
    if rows%64 or cols%64:raise ValueError('64x64 tiles required')
    tiles=weight.float().reshape(rows//64,64,cols//64,64).permute(0,2,1,3)
    maximum=tiles.abs().amax((-1,-2)).double()
    ratio=maximum/127
    m,e=torch.frexp(ratio);e=e-(m==.5).to(e.dtype)
    e=torch.where(maximum==0,torch.zeros_like(e),e)
    step=torch.ldexp(torch.ones_like(maximum),e).float()
    if not bool(torch.isfinite(step).all()) or not bool((step>0).all()):raise ValueError('unsupported weight exponent')
    q=(tiles/step[:,:,None,None]).round().clamp(-127,127).to(torch.int8)
    code=q.permute(0,2,1,3).reshape(rows,cols).contiguous()
    decoded=code.float()*step.repeat_interleave(64,0).repeat_interleave(64,1)
    return code,decoded.contiguous(),step.contiguous()

class PoTWeightFFN(Group64FFN):
    def __init__(self,original,layer,weight_policy='pot64'):
        super().__init__(original,layer)
        if weight_policy not in ('legacy','pot64'):raise ValueError('unknown weight quantizer')
        self.weight_policy=weight_policy;self.weight_only=False;self.nonlinear_mean=False;self.weight_metrics={}
        if weight_policy=='pot64':
            weights=(('gu',torch.cat((original.gate_proj.weight.detach(),original.up_proj.weight.detach()),0)),
                     ('down',original.down_proj.weight.detach()))
            for name,w in weights:
                code,decoded,step=quantize_pot64(w)
                setattr(self,name+'_codes',code);setattr(self,name+'_decoded',decoded);setattr(self,name+'_tile_lsb',step)
                exp=torch.frexp(step)[1]-1
                self.weight_metrics[name]=dict(tile=[64,64],step_is_pot=bool((torch.frexp(step)[0]==.5).all()),
                    NMSE=float(((decoded-w.float()).double().square().sum()/w.double().square().sum().clamp_min(1e-30)).cpu()),
                    step_exponent_min=int(exp.min()),step_exponent_max=int(exp.max()),
                    fullscale='128*LSB is also PoT',codes_range=[int(code.min()),int(code.max())])

            for branch,code,w in (('Wg',self.gu_codes[:self.width],original.gate_proj.weight.detach()),
                                  ('Wu',self.gu_codes[self.width:],original.up_proj.weight.detach()),
                                  ('Wd',self.down_codes,original.down_proj.weight.detach())):
                step=self.gu_tile_lsb[:self.width//64] if branch=='Wg' else self.gu_tile_lsb[self.width//64:] if branch=='Wu' else self.down_tile_lsb
                decoded=code.float()*step.repeat_interleave(64,0).repeat_interleave(64,1)
                self.weight_metrics[branch]=dict(tile_count=step.numel(),tile=[64,64],step_is_pot=bool((torch.frexp(step)[0]==.5).all()),
                    NMSE=float(((decoded-w.float()).double().square().sum()/w.double().square().sum().clamp_min(1e-30)).cpu()))

    def freeze_down(self):
        if self.weight_policy!='pot64':return super().freeze_down()
        c=self.down_tile_lsb.double()*(self.g_top.double()*self.u_top.double()).unsqueeze(0)
        mant,ex=torch.frexp(c)
        if not bool((mant==.5).all()):raise ValueError('Wd coefficient must be exact PoT')
        ex=ex.long()-1;maximum=ex.amax(-1);shift=15+ex-maximum[:,None]
        if bool((shift<0).any()):raise ValueError('PoT coefficient exponent span exceeds15; do not silently round')
        self.coeff=torch.ones_like(shift)<<shift;self.output_exp=maximum+1
        reconstructed=self.coeff.double()*exact_pow2(self.output_exp[:,None]-16)
        assert torch.equal(reconstructed,c)
        self.fixed_effective_weight=(self.down_codes.double()*reconstructed.repeat_interleave(64,0).repeat_interleave(64,1)).float()
        self.coefficient_nmse=0.;self.weight_metrics['Wd_restoration']=dict(exact_pot_coeff=True,coefficient_bits=16,
            exponent_span_max=int((maximum-ex.amin(-1)).max()),no_general_coefficient_multiply_required=True)

    def forward(self,x):
        if self.weight_only:
            self.calls+=1;g,u=F.linear(x.float(),self.gu_decoded).chunk(2,-1)
            return F.linear(F.silu(g)*u,self.down_decoded).to(x.dtype)
        if self.nonlinear_mean:return MeanGroupFFN.forward(self,x)
        return super().forward(x)

    def shared_report(self):
        if self.weight_only:return dict(weight_policy=self.weight_policy,weight_only_exact_silu=True,
            control_only=True,weight_metrics=self.weight_metrics)
        r=super().shared_report();r.update(weight_policy=self.weight_policy,weight_metrics=self.weight_metrics)
        if self.nonlinear_mean:r.update(nonlinear_T=None,nonlinear_law='conditional nonlinear mean diagnostic',
            zero_AND_count_fraction=None,hardware_candidate=False)
        return r
