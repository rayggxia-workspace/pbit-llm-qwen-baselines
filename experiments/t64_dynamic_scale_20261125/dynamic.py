"""Group max -> smallest covering PoT, global bounds; no per-group scale table."""
from contextlib import AbstractContextManager
import math
import torch

MIN_EXP=-6
CAPS={'x':512.,'g':256.,'u':512.}


def encode(value, group, cap):
    if group not in (16,32,64) or value.shape[-1]%group:
        raise ValueError('complete group16/32/64 required')
    v=value.float();a=v.abs().reshape(*v.shape[:-1],-1,group)
    maximum=a.amax(-1,keepdim=True)
    mantissa,exponent=torch.frexp(maximum)
    # Exact PoT stays at its own exponent; other magnitudes round upward.
    exponent=torch.where(maximum==0,MIN_EXP,exponent-(mantissa==.5).int()).clamp(MIN_EXP,int(math.log2(cap)))
    scale=torch.ldexp(torch.ones_like(maximum),exponent).expand_as(a).reshape_as(v)
    e=exponent.expand_as(a).reshape_as(v).long()
    q=(v.abs()/scale*256).round().clamp(0,255).long()
    full=(v.abs()>=scale)&(v!=0)
    q=torch.where(full,256,q)
    return q,v.sign().long(),e,int(math.log2(cap))-e,scale


class DynamicOverride(AbstractContextManager):
    def __init__(self,group):
        import seven_forward as sf
        self.sf=sf;self.group=group;self.old=sf.upstream.hard_forward
        self.stats={}

    def observe(self,name,value,q,e,scale):
        v=value.float();n=q.new_tensor(q.numel())
        row=torch.stack([n,q.sum(),(q==0).sum(),(q==256).sum(),(v.abs()>scale).sum(),
                         *[(e==j).sum() for j in range(-6,10)]])
        if name not in self.stats:self.stats[name]=row
        else:self.stats[name]+=row

    def __enter__(self):
        sf=self.sf
        from wide_wd import shifted_output
        def hard(x,wg,wu,wd,module,key):
            cfg=module.config
            if not isinstance(cfg,sf.Config):return self.old(x,wg,wu,wd,module,key)
            with torch.no_grad(),torch.autocast(device_type=x.device.type,enabled=False):
                assert cfg.mode=='sampled' and cfg.backend=='exact_int8' and cfg.weight_bits==8
                xc,xs,xe,xshift,xscale=encode(x,self.group,CAPS['x'])
                self.observe('x',x,xc,xe,xscale)
                counts=sf.iid_shared64_counts(xc,cfg.input_samples,key.generator(x.device,module.layer,'input_iid'))
                gcodes,gu,gl,dc,dd,dl=sf.projection_state(module,wg,wu,wd)
                topx=torch.full_like(module.x_scales[:,0],CAPS['x'])
                coeff,gexp=sf.exact_coefficients(gl,topx,torch.ones_like(topx))
                rx=int(xshift.max())
                acc=shifted_output(counts.contiguous(),xs.contiguous(),xshift.contiguous(),gcodes,coeff,
                                   cfg.input_samples,rx,127)
                g,u=sf.finish_fp32(acc,gexp,cfg.input_samples,rx).chunk(2,-1)
                gq,gs,ge,gh,gscale=encode(g,self.group,CAPS['g'])
                uq,us,ue,uh,uscale=encode(u,self.group,CAPS['u'])
                self.observe('g',g,gq,ge,gscale);self.observe('u',u,uq,ue,uscale)
                field=sf.sigmoid_field(gq,gs,ge);hq=module.lut[field+128].long()
                events,_=sf.count_events((gq,hq,uq),cfg.nonlinear_samples,key.generator(x.device,module.layer,'and_iid'))
                tg=torch.full_like(module.g_top,CAPS['g']);tu=torch.full_like(module.u_top,CAPS['u'])
                cf,ex=sf.exact_coefficients(dl,tg,tu)
                shift=gh+uh;rr=int(shift.max())
                acc=shifted_output(events.contiguous(),(gs*us).contiguous(),shift.contiguous(),dc,cf,
                                   cfg.nonlinear_samples,rr,127)
                y=sf.finish_bf16(acc,ex-rr,cfg.nonlinear_samples).to(x.dtype)
                module.last_arithmetic=dict(mode='sampled',T_x=cfg.input_samples,T_AND=cfg.nonlinear_samples,
                    scale_group=self.group,input_rng='stratified R8 shared64',dynamic_caps=CAPS,
                    active_alignment_bits_gu=rx,active_alignment_bits_wd=rr,
                    accumulator_container_bits=64,and_events=int(events.sum()),and_zero=int((events==0).sum()))
                return y,None
        sf.upstream.hard_forward=hard
        return self

    def __exit__(self,*exc):
        self.sf.upstream.hard_forward=self.old
        return False

    def report(self):
        d={}
        for name,row in self.stats.items():
            n,total,zeros,ones,clip,*hist=row.cpu().tolist()
            d[name]=dict(elements=n,mean_probability=total/(256*n),zero_code_fraction=zeros/n,
                         full_one_fraction=ones/n,clipped_fraction=clip/n,exponent_hist=dict(zip(range(-6,10),hist)))
        return d
