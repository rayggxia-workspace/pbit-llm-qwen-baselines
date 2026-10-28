"""Larger TRAIN calibration;within64 Gram risk;PoT switch-threshold shifts."""
import itertools
import torch
from torch.nn import functional as F
from .recal_core import RecalibratedFFN,ceil_exp,pack_carriers,catalog_accumulate
from .pot_weight import exact_pow2
from .independent_gate import original_g_field
from qwen3.and_direct.short_core import joint_counts,joint_moments
from qwen3.and_direct.core import finish_bf16

CANDIDATE_OFFSETS=torch.arange(-8,2,dtype=torch.long)
LEVEL_COMBOS=torch.tensor(list(itertools.combinations(range(10),4)),dtype=torch.long)

def encode_threshold(value,levels,delta,carrier):
    v=value.float().reshape(*value.shape[:-1],-1,64)
    if tuple(levels.shape)!=(v.shape[-2],4) or tuple(delta.shape)!=(v.shape[-2],):raise ValueError('group64 levels/delta shape')
    if not bool((levels[:,1:]>levels[:,:-1]).all()) or not bool(((delta>=-1)&(delta<=1)).all()):raise ValueError('invalid catalog/threshold shift')
    maximum=v.abs().amax(-1);idx=torch.full_like(maximum,3,dtype=torch.long)
    for k in (2,1,0):idx=torch.where(maximum<=exact_pow2(levels[:,k]+delta).float(),k,idx)
    e=levels[:,-1].expand_as(maximum).clone()
    for k in (2,1,0):e=torch.where(idx==k,levels[:,k],e)
    q=(v.abs()/exact_pow2(e).float().unsqueeze(-1)*256).round().clamp(0,255).long()
    exponent=e.unsqueeze(-1).expand_as(v).reshape_as(value);shift=(carrier-e).unsqueeze(-1).expand_as(v).reshape_as(value)
    return q.reshape_as(value),value.sign().long(),exponent,shift,idx.unsqueeze(-1).expand_as(v).reshape_as(value)

def risk_components(g,u,hcode,sg,su,norm,gram):
    gc=(g.abs()/sg*256).round().clamp(0,255).long();uc=(u.abs()/su*256).round().clamp(0,255).long()
    mean,var=joint_moments((gc,hcode,uc),128)
    product=(sg*su).double();bias=g.sign()*u.sign()*product*mean/128-g.double()*u.double()*hcode.double()/256
    variance=(product.square()*var/(128**2)*norm.double()).sum(-1)
    diagonal=(bias.square()*norm.double()).sum(-1)
    b=bias.permute(1,0,2)
    within=(torch.bmm(b,gram.double())*b).sum(-1).T.clamp_min(0)
    return diagonal,within,variance

def policy_set(device,tune_threshold):
    c=LEVEL_COMBOS.to(device)
    if not tune_threshold:return c,torch.zeros(len(c),device=device,dtype=torch.long)
    return c.repeat(3,1),torch.repeat_interleave(torch.tensor([-1,0,1],device=device),len(c))

def policy_picks(required,combos,deltas):
    out=combos[:,-1,None,None].expand(-1,*required.shape).clone()
    for k in (2,1,0):out=torch.where(required[None]<=combos[:,k,None,None]+deltas[:,None,None],combos[:,k,None,None],out)
    return out

def fit_policies(cost,required_g,required_u,fit_tokens,tune_threshold):
    if cost.ndim!=4 or cost.shape[-2:]!=(10,10) or not 0<fit_tokens<=cost.shape[0]:raise ValueError('invalid fitting input')
    combos,deltas=policy_set(cost.device,tune_threshold);pg=policy_picks(required_g,combos,deltas);pu=policy_picks(required_u,combos,deltas)
    t=torch.arange(cost.shape[0],device=cost.device)[None,:,None];j=torch.arange(cost.shape[1],device=cost.device)[None,None,:]
    priority=(combos[:,-1]-combos[:,0])*8+deltas.abs()*2
    def best(scores):
        minimum=scores.amin(0);eligible=scores<=minimum[None]+minimum.abs()[None]*1e-12+1e-18
        ranks=torch.where(eligible,priority[:,None],torch.full_like(scores,100000,dtype=torch.long))
        return ranks.argmin(0)
    def get(p,c):return p[c[None,:],t[0],j[0]]
    result=None
    for initial in ((5,6,7,8),(2,4,6,8),(0,2,4,6),(4,6,8,9)):
        start=(((combos==torch.tensor(initial,device=cost.device)).all(-1))&(deltas==0)).nonzero().item()
        cg=torch.full((cost.shape[1],),start,device=cost.device,dtype=torch.long);cu=cg.clone()
        for _ in range(4):
            q=get(pu,cu);cg=best(cost[t,j,pg,q[None]][:,:fit_tokens].sum(1))
            p=get(pg,cg);cu=best(cost[t,j,p[None],pu][:,:fit_tokens].sum(1))
        p,q=get(pg,cg),get(pu,cu);r=cost[t[0],j[0],p,q][:fit_tokens].sum(0)
        if result is None:result=(r,cg,cu)
        else:
            use=r<result[0];result=tuple(torch.where(use,a,b) for a,b in zip((r,cg,cu),result))
    dense=(((combos==torch.tensor((5,6,7,8),device=cost.device)).all(-1))&(deltas==0)).nonzero().item()
    empty=cost[:fit_tokens].abs().sum((0,2,3))==0
    cg=torch.where(empty,dense,result[1]);cu=torch.where(empty,dense,result[2])
    return combos[cg],combos[cu],deltas[cg],deltas[cu]

class TunedFFN(RecalibratedFFN):
    def __init__(self,original,layer):
        super().__init__(original,layer);self.thresholds_enabled=False
        for n in ('g_threshold_delta','u_threshold_delta'):self.register_buffer(n,torch.empty(0,device=self.gu_codes.device,dtype=torch.long))

    def install_tuned(self,g,u,dg,du):
        self.install_catalog(g,u,False);self.g_threshold_delta=torch.tensor(dg,device=self.gu_codes.device,dtype=torch.long);self.u_threshold_delta=torch.tensor(du,device=self.gu_codes.device,dtype=torch.long)
        for d in (self.g_threshold_delta,self.u_threshold_delta):
            if tuple(d.shape)!=(self.width//64,) or not bool(((d>=-1)&(d<=1)).all()):raise ValueError('invalid threshold shift')
        self.thresholds_enabled=True

    def forward(self,x):
        if not self.thresholds_enabled:return super().forward(x)
        self.calls+=1;g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        h=self.lut[original_g_field(g)+128].long()
        gc,gs,ge,gh,gb=encode_threshold(g,self.g_levels,self.g_threshold_delta,self.g_carrier)
        uc,us,ue,uh,ub=encode_threshold(u,self.u_levels,self.u_threshold_delta,self.u_carrier)
        for i,v,c,s,e,b in ((1,g,gc,gs,ge,gb),(2,u,uc,us,ue,ub)):
            scale=exact_pow2(e).float();self._record(i,v,scale,c.double()/256,s*c.float()*scale/256,b,True)
        if self.nonlinear_mean:
            p=(gc*h*uc).double()/256**3;self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum()
            return F.linear(torch.ldexp(gs*us*p,-gh-uh).float(),self.fixed_effective_weight).to(x.dtype)
        counts,p=joint_counts((gc,h,uc),128,self.rng_and);self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum();self.event_stats[2]+=(counts==0).sum()
        acc=catalog_accumulate(counts,gs*us,gh+uh,self.down_codes,self.coeff,128,self.catalog_limit)
        return finish_bf16(acc,self.output_exp-self.catalog_limit,128).to(x.dtype)

    def shared_report(self):
        r=super().shared_report()
        if self.thresholds_enabled:r.update(scale_source='expanded TRAIN calibration,four-level catalogs plus static PoT thresholds',
            threshold_g_delta=self.g_threshold_delta.tolist(),threshold_u_delta=self.u_threshold_delta.tolist(),
            threshold_rule='select smallest level with maxabs<=2^(level+delta);last fallback clips',
            gate_probability_changed_fraction=None,gate_probability_mean_absolute_change=None)
        return r
