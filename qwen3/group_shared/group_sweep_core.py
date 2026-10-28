"""Isolate nonlinear shared-group size and catalog density. Upstream x stays64.

Old successful TRAIN-only risk4 tables remain immutable. Smaller groups inherit
the parent64 catalog. Eight levels densify that same catalog without raising its
maximum. No new calibration or TEST selection;GU restoration remains an oracle.
"""
import torch
from torch.nn import functional as F
from .recal_core import RecalibratedFFN,pack_carriers,catalog_accumulate
from .pot_weight import exact_pow2
from .independent_gate import original_g_field
from qwen3.and_direct.short_core import joint_counts
from qwen3.and_direct.core import finish_bf16


def inherited_catalog(levels,group_size,level_count):
    if group_size not in (16,32,64) or level_count not in (4,8):
        raise ValueError('NL groups16/32/64 and levels4/8 only')
    a=torch.as_tensor(levels,dtype=torch.long)
    if a.ndim!=2 or a.shape[1]!=4 or not bool((a[:,1:]>a[:,:-1]).all()):
        raise ValueError('ascending parent64 four-level catalog required')
    if level_count==8:
        dense=a[:,-1,None]+torch.arange(-7,1,device=a.device)
        if not bool((a[:,:,None]==dense[:,None,:]).any(-1).all()):
            raise ValueError('eight-level densification must contain all old levels')
        a=dense
    return a.repeat_interleave(64//group_size,0)


def encode_grouped(value,levels,group_size,carrier=None):
    if group_size not in (16,32,64) or value.shape[-1]%group_size:
        raise ValueError('unsupported nonlinear group')
    n=value.shape[-1]//group_size
    if levels.ndim!=2 or levels.shape[0]!=n or levels.shape[1] not in (4,8):
        raise ValueError('catalog shape mismatch')
    if not bool((levels[:,1:]>levels[:,:-1]).all()):raise ValueError('ascending levels required')
    v=value.float().reshape(*value.shape[:-1],n,group_size)
    maximum=v.abs().amax(-1);last=levels.shape[1]-1
    idx=torch.full_like(maximum,last,dtype=torch.long)
    for k in range(last-1,-1,-1):
        idx=torch.where(maximum<=exact_pow2(levels[:,k]).float(),k,idx)
    e=levels[:,-1].expand_as(maximum).clone()
    for k in range(last-1,-1,-1):e=torch.where(idx==k,levels[:,k],e)
    q=(v.abs()/exact_pow2(e).float().unsqueeze(-1)*256).round().clamp(0,255).long()
    c=levels[:,-1] if carrier is None else carrier
    if c.shape!=(n,) or bool((c<levels[:,-1]).any()):raise ValueError('invalid carrier')
    broadcast=lambda a:a.unsqueeze(-1).expand_as(v).reshape_as(value)
    return q.reshape_as(value),value.sign().long(),broadcast(e),broadcast(c-e),broadcast(idx)


class GroupSweepFFN(RecalibratedFFN):
    def __init__(self,original,layer):
        super().__init__(original,layer)
        self.nl_group_size=64;self.nl_level_count=4;self.sweep_enabled=False
        self.register_buffer('nl_stats',torch.zeros(2,10,device=self.gu_codes.device,dtype=torch.float64))
        self.register_buffer('nl_hist',torch.zeros(2,4,device=self.gu_codes.device,dtype=torch.float64))

    def install_sweep(self,parent_g,parent_u,group_size,level_count):
        d=self.gu_codes.device
        self.nl_group_size=group_size;self.nl_level_count=level_count
        self.g_levels=inherited_catalog(parent_g,group_size,level_count).to(d)
        self.u_levels=inherited_catalog(parent_u,group_size,level_count).to(d)
        if self.g_levels.shape[0]!=self.width//group_size or self.u_levels.shape!=self.g_levels.shape:
            raise ValueError('parent catalog width mismatch')
        self.coeff,self.output_exp,self.g_carrier,self.u_carrier,self.catalog_limit=pack_carriers(
            self.down_tile_lsb,self.g_levels,self.u_levels)
        self.g_top=exact_pow2(self.g_carrier).float();self.u_top=exact_pow2(self.u_carrier).float()
        scale=self.coeff.double()*exact_pow2(self.output_exp[:,None]-16)
        reference=self.g_carrier+self.u_carrier
        assert bool((reference==reference[0]).all())
        assert torch.equal(scale,self.down_tile_lsb.double()*exact_pow2(reference[0]))
        self.fixed_effective_weight=(self.down_codes.double()*scale.repeat_interleave(64,0).repeat_interleave(64,1)).float()
        bound=self.width*128*127*int(self.coeff.max())*(1<<self.catalog_limit)
        if bound>=1<<63:raise ValueError('signed64 catalog accumulation overflow')
        self.catalog_accumulator_bound_bits=bound.bit_length()+1
        self.nl_hist=torch.zeros(2,level_count,device=d,dtype=torch.float64)
        self.nl_stats.zero_();self.sweep_enabled=True;self.active_catalog=False
        self.weight_metrics['Wd_restoration']=dict(exact_pot_coeff=True,coefficient_bits=int(self.coeff.max()).bit_length(),
            no_general_coefficient_multiply_required=True,carrier_product_common=True)

    def reset_sweep_stats(self):
        self.nl_stats.zero_();self.nl_hist.zero_()

    def _record(self,index,value,scale,prob,decoded,bins,shared):
        if index==0 or not self.sweep_enabled:return super()._record(index,value,scale,prob,decoded,bins,shared)
        s=self.nl_stats[index-1];v=value.double();s[0]+=value.numel();s[1]+=prob.sum(dtype=torch.float64)
        s[2]+=(value.abs()>scale).sum();s[3]+=(decoded.double()-v).square().sum();s[4]+=v.square().sum()
        s[5]+=(prob==0).sum();s[6]+=(prob==1).sum();s[7]+=value.numel()//self.nl_group_size
        b=bins.reshape(-1,self.nl_group_size);s[8]+=(b.amax(-1)!=b.amin(-1)).sum()
        s[9]+=(value.abs()-scale).clamp_min(0).square().sum(dtype=torch.float64)
        self.nl_hist[index-1]+=torch.bincount(bins.flatten(),minlength=self.nl_level_count)

    def forward(self,x):
        if not self.sweep_enabled:return super().forward(x)
        self.calls+=1;g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        h=self.lut[original_g_field(g)+128].long()
        a=encode_grouped(g,self.g_levels,self.nl_group_size,self.g_carrier)
        b=encode_grouped(u,self.u_levels,self.nl_group_size,self.u_carrier)
        gc,gs,ge,gh,gb=a;uc,us,ue,uh,ub=b
        for i,v,c,s,e,bin_id in ((1,g,gc,gs,ge,gb),(2,u,uc,us,ue,ub)):
            scale=exact_pow2(e).float();self._record(i,v,scale,c.double()/256,s*c.float()*scale/256,bin_id,True)
        if self.nonlinear_mean:
            p=(gc*h*uc).double()/256**3;self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum()
            value=torch.ldexp(gs*us*p,-gh-uh).float()
            return F.linear(value,self.fixed_effective_weight).to(x.dtype)
        counts,p=joint_counts((gc,h,uc),128,self.rng_and)
        self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum();self.event_stats[2]+=(counts==0).sum()
        acc=catalog_accumulate(counts,gs*us,gh+uh,self.down_codes,self.coeff,128,self.catalog_limit)
        return finish_bf16(acc,self.output_exp-self.catalog_limit,128).to(x.dtype)

    def shared_report(self):
        r=super().shared_report()
        if not self.sweep_enabled:return r
        for i,name in enumerate(('g','u')):
            n,p,clip,sse,power,zero,full,groups,mixed,clip_sse=self.nl_stats[i].tolist()
            assert mixed==0
            r['stages'][name]=dict(elements=int(n),shared_group_size=self.nl_group_size,groups=int(groups),
                mixed_scale_groups=int(mixed),mean_probability=p/max(n,1),clip_fraction=clip/max(n,1),
                encoding_nmse=sse/max(power,1e-30),clipping_nmse=clip_sse/max(power,1e-30),
                zero_fraction=zero/max(n,1),full_fraction=full/max(n,1),scale_hist=self.nl_hist[i].tolist())
        r.update(nonlinear_shared_group=self.nl_group_size,nonlinear_levels=self.nl_level_count,
            scale_source='old successful TRAIN risk4 inherited per parent64;B8 contiguous PoT ending at same maximum',
            calibration_refitted=False,input_shared_group=64,weight_tile=[64,64],
            unchanged='x frozen4/shared64;PoTW8/GU64/NLjoint32T128/originalg signed8 sigmoid/accurateSDPA',
            hardware_candidate_not_PPA=True)
        return r
