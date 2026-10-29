"""Group64 selects ONE of frozen four PoT scales. No new online scale.

Only x/g/u encoding changes; Wd/direct AND and source RNG laws are retained.
GU restoration remains the upstream FP32 oracle, not fullchain bittrue.
"""
import torch
from qwen3.dual_gu.core import DualGUFFN
from qwen3.fixed_scale.static_core import _encode_static_validated
from qwen3.stochastic.vendor.stratified_core import project_encoded
from qwen3.and_direct.short_core import encode_fixed,joint_counts
from qwen3.and_direct.multiscale_core import sigmoid_field,shifted_output
from qwen3.and_direct.core import finish_bf16

VARIANTS={'lane':(False,False,0),'x_max':(True,False,0),
          'gu_max':(False,True,0),'all_max':(True,True,0),
          'all_trim1':(True,True,1),'all_trim4':(True,True,4)}


def group_choice(value,scales,allow=0):
    """Three threshold-exceedance counts, not data-dependent new scale/sort."""
    if value.shape[-1]%64 or tuple(scales.shape)!=(value.shape[-1]//64,4) or allow not in (0,1,4):
        raise ValueError('group64, four frozen scales and allow0/1/4 required')
    mag=value.float().reshape(*value.shape[:-1],-1,64).abs()
    chosen=torch.zeros_like(mag[...,:1],dtype=torch.long)
    for i in range(1,4):
        exceed=(mag>scales[:,i,None]).sum(-1,keepdim=True)
        chosen=torch.where(exceed<=allow,i,chosen)
    # Gather without a row/group reorder; broadcast only the one group index.
    scale=torch.ones_like(mag)*scales[:,0,None]
    for i in range(1,4):scale=torch.where(chosen==i,scales[:,i,None],scale)
    return scale.reshape_as(value),chosen.expand_as(mag).reshape_as(value)


def encode_x(value,scales,shared,allow):
    if not shared:return _encode_static_validated(value,scales)
    value=value.float();scale,bins=group_choice(value,scales,allow)
    q=(value.abs()/scale*256).round().clamp(0,255)
    full=(value.abs()>=scale)&(value!=0)
    p=torch.where(full,torch.ones_like(q),q/256)
    return dict(q=q.short(),sign=value.sign(),scale=scale,probability=p,
                decoded=value.sign()*scale*p,full_one=full,bin_id=bins)


def encode_nl(value,top,offsets,shared,allow):
    if not shared:return encode_fixed(value,top,offsets)
    scales=torch.stack([top*(2.**-k) for k in offsets],-1)
    scale,bins=group_choice(value,scales,allow)
    shift=torch.zeros_like(bins)
    for i,k in enumerate(offsets):shift=torch.where(bins==i,k,shift)
    code=(value.abs()/scale*256).round().clamp(0,255).long()
    _,e=torch.frexp(scale)
    return code,value.sign().long(),e.long()-1,shift


class Group64FFN(DualGUFFN):
    def __init__(self,original,layer):
        super().__init__(original,layer)
        self.register_buffer('shared_stats',torch.zeros(3,10,dtype=torch.float64,device=self.gu_codes.device))
        self.register_buffer('shared_hist',torch.zeros(3,4,dtype=torch.float64,device=self.gu_codes.device))
        self.register_buffer('event_stats',torch.zeros(3,dtype=torch.float64,device=self.gu_codes.device))

    def reset_shared(self,variant):
        if variant not in VARIANTS:raise ValueError('unknown shared-scale variant')
        self.variant=variant;self.shared_x,self.shared_gu,self.allow=VARIANTS[variant]
        self.shared_stats.zero_();self.shared_hist.zero_();self.event_stats.zero_()

    def _record(self,index,value,scale,prob,decoded,bins,shared):
        s=self.shared_stats[index];v=value.double();s[0]+=value.numel()
        s[1]+=prob.sum(dtype=torch.float64);s[2]+=(value.abs()>scale).sum()
        s[3]+=(decoded.double()-v).square().sum();s[4]+=v.square().sum()
        s[5]+=(prob==0).sum();s[6]+=(prob==1).sum();s[7]+=value.numel()//64
        grouped=bins.reshape(-1,64)
        s[8]+=(grouped.amax(-1)!=grouped.amin(-1)).sum()
        s[9]+=(value.abs()-scale).clamp_min(0).square().sum(dtype=torch.float64)
        self.shared_hist[index]+=torch.bincount(bins.reshape(-1),minlength=4)

    def _stage(self,value,signal,matrix,generator):
        if matrix!='gu' or not hasattr(self,'variant'):return super()._stage(value,signal,matrix,generator)
        encoded=encode_x(value,self.x_scales,self.shared_x,self.allow)
        self._record(0,value,encoded['scale'],encoded['probability'],encoded['decoded'],encoded['bin_id'],self.shared_x)
        if self.gu_method=='fixed':
            return project_encoded(encoded,self.gu_decoded,self.mode,self.gu_samples,generator,min(64,self.gu_samples))
        self.gu_sample_calls+=1
        if value.is_cuda:
            from qwen3.dual_gu.kernel import project
            return project(encoded,self.gu_codes,self.gu_tile_lsb,self.gu_samples,self.gu_method,generator,self.rng_weight)
        from qwen3.dual_gu.core import reference_project
        return reference_project(encoded,self.gu_codes,self.gu_tile_lsb,self.gu_samples,self.gu_method,generator,self.rng_weight)

    def forward(self,x):
        self.calls+=1
        g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        gc,gs,ge,gshift=encode_nl(g,self.g_top,self.offsets,self.shared_gu,self.allow)
        uc,us,ue,ushift=encode_nl(u,self.u_top,self.offsets,self.shared_gu,self.allow)
        for i,v,c,s,e,h in ((1,g,gc,gs,ge,gshift),(2,u,uc,us,ue,ushift)):
            scale=torch.ldexp(torch.ones_like(v),e)
            bins=torch.zeros_like(h)
            for k,off in enumerate(self.offsets):bins=torch.where(h==off,k,bins)
            self._record(i,v,scale,c.double()/256,torch.ldexp(c.float()*s/256,e),bins,self.shared_gu)
        field=sigmoid_field(gc,gs,ge);hc=self.lut[field+128].long()
        counts,p=joint_counts((gc,hc,uc),self.and_samples,self.rng_and)
        self.event_stats[0]+=p.numel();self.event_stats[1]+=p.sum();self.event_stats[2]+=(counts==0).sum()
        shift=gshift+ushift;limit=2*max(self.offsets)
        acc=shifted_output(counts,gs*us,shift,self.down_codes,self.coeff,self.and_samples,limit)
        return finish_bf16(acc,self.output_exp-limit,self.and_samples).to(x.dtype)

    def shared_report(self):
        stage={}
        for i,name in enumerate(('x','g','u')):
            n,psum,clipped,sse,power,zero,full,groups,mixed,clip_sse=self.shared_stats[i].tolist()
            shared=self.shared_x if i==0 else self.shared_gu
            if shared:assert mixed==0
            stage[name]=dict(elements=int(n),shared_group64=shared,groups=int(groups),mixed_scale_groups=int(mixed),
                mean_probability=psum/max(n,1),clip_fraction=clipped/max(n,1),encoding_nmse=sse/max(power,1e-30),
                clipping_nmse=clip_sse/max(power,1e-30),zero_fraction=zero/max(n,1),full_fraction=full/max(n,1),
                scale_hist=self.shared_hist[i].tolist())
        n,psum,zero=self.event_stats.tolist()
        return dict(variant=self.variant,allow_clipped_per_group=self.allow,stages=stage,
            gu_law=self.gu_method,gu_T=self.gu_samples,GU_restore='FP32 upstream oracle',
            nonlinear_T=self.and_samples,nonlinear_law='joint32',g_u_scales_separate=True,
            sigmoid='signed8 real-g field, P8 LUT unchanged',Wd='fixedW8 direct integer readout unchanged',
            mean_AND_probability=psum/max(n,1),zero_AND_count_fraction=zero/max(n,1),
            scale_source='TRAIN frozen four PoT choices, no new online scale',
            clipping_selector='64 threshold flags, count<=allow; no runtime sorting')
