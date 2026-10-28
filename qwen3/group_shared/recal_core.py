"""Train-only shared-group PoT catalogs;exact finite-law diagonal Wd risk."""
import itertools
import torch
from torch.nn import functional as F
from .independent_gate import IndependentGateFFN,original_g_field
from .pot_weight import exact_pow2
from qwen3.and_direct.short_core import joint_counts,joint_moments
from qwen3.and_direct.multiscale_core import shifted_output
from qwen3.and_direct.core import finish_bf16

OFFSETS=torch.arange(-6,2,dtype=torch.int64)
COMBOS=torch.tensor(list(itertools.combinations(range(8),4)),dtype=torch.int64)

def ceil_exp(maximum):
    m,e=torch.frexp(maximum.float());return torch.where(maximum>0,e.long()-(m==.5).long(),torch.zeros_like(e,dtype=torch.long))

def encode_catalog(value,levels,active=None):
    """Each64 share ONE exponent;four ascending PoT choices,ordinaryP8."""
    v=value.float().reshape(*value.shape[:-1],-1,64)
    if levels.shape!=(v.shape[-2],4) or not bool((levels[:,1:]>levels[:,:-1]).all()):raise ValueError('four ascending exponents/group required')
    mag=v.abs() if active is None else torch.where(active.reshape_as(v),v.abs(),torch.zeros_like(v))
    maximum=mag.amax(-1);idx=torch.full_like(maximum,3,dtype=torch.long)
    for k in (2,1,0):idx=torch.where(maximum<=exact_pow2(levels[:,k]).float(),k,idx)
    exponent=levels[:,3].expand_as(maximum).clone()
    for k in (2,1,0):exponent=torch.where(idx==k,levels[:,k],exponent)
    scale=exact_pow2(exponent).float().unsqueeze(-1)
    q=(v.abs()/scale*256).round().clamp(0,255).long()
    e=exponent.unsqueeze(-1).expand_as(v).reshape_as(value)
    h=(levels[:,3]-exponent).unsqueeze(-1).expand_as(v).reshape_as(value)
    return q.reshape_as(value),value.sign().long(),e,h,idx.unsqueeze(-1).expand_as(v).reshape_as(value)

def output_risk(g,u,hcode,sg,su,weight_norm):
    """Per token/group proxy:sum colNorm*(squared bias+exact NL variance).

    Ignores cross-channel/group bias covariance;not full Wd reconstructionMSE.
    sg/su shapes broadcast with [tokens,groups,64];weight_norm=[groups,64].
    """
    gc=(g.abs()/sg*256).round().clamp(0,255).long();uc=(u.abs()/su*256).round().clamp(0,255).long()
    count_mean,count_var=joint_moments((gc,hcode,uc),128)
    sign=g.sign()*u.sign();mean=sign*(sg*su).double()*count_mean/128
    target=g.double()*u.double()*hcode.double()/256
    variance=(sg*su).double().square()*count_var/(128**2)
    return (((mean-target).square()+variance)*weight_norm.double()).sum(-1)

def _picks(required):
    combos=COMBOS.to(required.device);p=combos[:,-1,None,None].expand(-1,*required.shape).clone()
    for k in (2,1,0):p=torch.where(required[None]<=combos[:,k,None,None],combos[:,k,None,None],p)
    return p

def fit_catalogs(cost,required_g,required_u,fit_tokens):
    """Two-restart block coordinate catalog selection,fit partition ONLY."""
    if cost.ndim!=4 or cost.shape[-2:]!=(8,8) or not 0<fit_tokens<=cost.shape[0]:raise ValueError('invalid fitting shape')
    t=torch.arange(cost.shape[0],device=cost.device)[None,:,None];j=torch.arange(cost.shape[1],device=cost.device)[None,None,:]
    pg,pu=_picks(required_g),_picks(required_u);combos=COMBOS.to(cost.device)
    def get(p,c):return p[c[None,:],t[0],j[0]]
    best=None
    for initial in ((3,4,5,6),(0,2,4,6)):
        index=((combos==torch.tensor(initial,device=cost.device)).all(-1)).nonzero().item()
        cg=torch.full((cost.shape[1],),index,device=cost.device,dtype=torch.long);cu=cg.clone()
        for _ in range(3):
            ug=get(pu,cu);cg=cost[t,j,pg,ug[None]].narrow(1,0,fit_tokens).sum(1).argmin(0)
            gg=get(pg,cg);cu=cost[t,j,gg[None],pu].narrow(1,0,fit_tokens).sum(1).argmin(0)
        gg,uu=get(pg,cg),get(pu,cu);risk=cost[t[0],j[0],gg,uu][:fit_tokens].sum(0)
        if best is None:best=(risk,cg,cu)
        else:
            use=risk<best[0];best=tuple(torch.where(use,a,b) for a,b in zip((risk,cg,cu),best))
    # A group with zero observed risk has no fitting evidence:retain dense table.
    dense=((combos==torch.tensor((3,4,5,6),device=cost.device)).all(-1)).nonzero().item()
    noinfo=cost[:fit_tokens].abs().sum((0,2,3))==0
    return combos[torch.where(noinfo,dense,best[1])],combos[torch.where(noinfo,dense,best[2])]

class RecalibratedFFN(IndependentGateFFN):
    def __init__(self,original,layer):
        super().__init__(original,layer);self.register_buffer('g_levels',torch.empty(0,device=self.gu_codes.device,dtype=torch.long));self.register_buffer('u_levels',torch.empty(0,device=self.gu_codes.device,dtype=torch.long));self.active_catalog=False

    def install_catalog(self,g_levels,u_levels,active=False):
        device=self.gu_codes.device
        self.g_levels=torch.tensor(g_levels,device=device,dtype=torch.long);self.u_levels=torch.tensor(u_levels,device=device,dtype=torch.long)
        for a in (self.g_levels,self.u_levels):
            if tuple(a.shape)!=(self.width//64,4) or not bool((a[:,1:]>a[:,:-1]).all()):raise ValueError('invalid catalog')
        self.g_top=exact_pow2(self.g_levels[:,-1]).float();self.u_top=exact_pow2(self.u_levels[:,-1]).float()
        self.active_catalog=bool(active);self.freeze_down()
        self.catalog_limit=int((self.g_levels[:,-1]-self.g_levels[:,0]).max()+(self.u_levels[:,-1]-self.u_levels[:,0]).max())

    def forward(self,x):
        if not self.g_levels.numel():return super().forward(x)
        self.calls+=1;g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        hc=self.lut[original_g_field(g)+128].long();mask=hc>0 if self.active_catalog else None
        gc,gs,ge,gh,gb=encode_catalog(g,self.g_levels,mask);uc,us,ue,uh,ub=encode_catalog(u,self.u_levels,mask)
        for i,v,c,s,e,b in ((1,g,gc,gs,ge,gb),(2,u,uc,us,ue,ub)):
            scale=exact_pow2(e).float();self._record(i,v,scale,c.double()/256,s*c.float()*scale/256,b,True)
        if self.nonlinear_mean:
            p=(gc*hc*uc).double()/256**3;self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum()
            value=torch.ldexp(gs*us*p,-gh-uh).float();return F.linear(value,self.fixed_effective_weight).to(x.dtype)
        counts,p=joint_counts((gc,hc,uc),128,self.rng_and);self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum();self.event_stats[2]+=(counts==0).sum()
        acc=shifted_output(counts,gs*us,gh+uh,self.down_codes,self.coeff,128,self.catalog_limit)
        return finish_bf16(acc,self.output_exp-self.catalog_limit,128).to(x.dtype)

    def shared_report(self):
        r=super().shared_report()
        if self.g_levels.numel():r.update(scale_source='TRAIN recalibrated four PoT exponents per64 group',catalog_active_gate_mask=self.active_catalog,
            catalog_hist_order='ascending scale,opposite old table order',g_exponents=self.g_levels.tolist(),u_exponents=self.u_levels.tolist(),
            sigmoid='original-g signed8/P8 LUT independent of amplitude catalog',catalog_alignment_limit=self.catalog_limit)
        return r
