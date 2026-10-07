"""Frozen-head output distillation of mean/bound mixture with straight-through bits."""
import copy
import json
import time
from pathlib import Path
import torch
from calibrate import fit,masks


def main():
    torch.manual_seed(2026);torch.backends.cuda.matmul.allow_tf32=False
    data=torch.load('artifacts/teacher.pt',weights_only=True);n=data['train_n']
    calibrated=torch.load('artifacts/calibrated.pt',map_location='cuda',weights_only=True)
    output={};reports=[]
    for context in (2048,8192):
        counts=data['counts'];train_ix=(counts==context//64)&(torch.arange(len(counts))<n)
        valid_ix=(counts==context//64)&(torch.arange(len(counts))>=n)
        c=context//64
        def subset(ix):
            scores=data['scores'][:,:,ix,:c].float().cuda()[...,[0,3]]
            mass=data['mass'][:,:,ix,:c].cuda();contrib=data['contrib'][:,:,ix,:c].float().cuda()
            return scores,mass,contrib
        sx,a,v=subset(train_ix);vx,va,vv=subset(valid_ix)
        y=v.sum(-2);vy=vv.sum(-2)
        normalizer=y.square().mean((-1,-2)).clamp_min(1e-4)[:,:,None]
        train_counts=torch.full((sx.shape[2],),c,device='cuda');valid_counts=torch.full((vx.shape[2],),c,device='cuda')
        _,force=masks(train_counts,c);_,vforce=masks(valid_counts,c)
        for budget in (.15,.3):
            initial=calibrated[f'{context}_{budget}_mix'];scales=initial['scales'][:,:,None,None]
            x=sx/scales;xt=vx/scales
            alpha=torch.nn.Parameter(torch.logit(initial['alpha'].clamp(.02,.98)))
            bias=torch.nn.Parameter(initial['parameter'].clone())
            logtau=torch.nn.Parameter(initial['temperature'].log().clone())
            opt=torch.optim.Adam((alpha,bias,logtau),lr=.015)
            history=[];best=float('inf');begin=time.perf_counter()
            def scores(xx):
                mix=alpha.sigmoid()[:,:,None,None]
                return mix*xx[...,0]+(1-mix)*xx[...,1]
            def error(mask,mass,contrib,target):
                pred=torch.einsum('lhnc,lhncd->lhnd',mask,contrib)/(mask*mass).sum(-1).clamp_min(1e-8)[...,None]
                return ((pred-target).square().mean(-1)/normalizer).mean()
            @torch.no_grad()
            def validate():
                s=scores(xt);tau=logtau.exp().clamp(.02,2.)[:,:,None,None]
                parameter,pi=fit(s,valid_counts,'distill',tau,budget)
                generator=torch.Generator(device='cuda').manual_seed(818)
                loss=0.
                for _ in range(16):
                    mask=(torch.rand(pi.shape,device='cuda',generator=generator)<pi).float()
                    loss+=error(mask,va,vv,vy).item()/16
                return loss,parameter,pi
            for step in range(1501):
                if step%100==0:
                    loss,parameter,pi=validate();history.append({'step':step,'validation_output_NMSE':loss,'fraction':(pi.sum(-1)/c).mean().item()})
                    if loss<best:
                        best=loss;best_step=step
                        state={'alpha':alpha.sigmoid().detach().cpu(),'temperature':logtau.exp().clamp(.02,2.).detach().cpu(),'parameter':parameter[:,:,0,0].cpu(),'scales':initial['scales'].cpu()}
                    print(json.dumps({'context':context,'budget':budget,**history[-1]}),flush=True)
                if step==1500:break
                ix=torch.randint(sx.shape[2],(8,),device='cuda')
                s=scores(x[:,:,ix]);relative=s-s.amax(-1,keepdim=True)
                pi=((relative+bias[:,:,None,None])/logtau.exp().clamp(.02,2.)[:,:,None,None]).sigmoid().masked_fill(force[:,:,ix],1.)
                hard=(torch.rand_like(pi)<pi).float();mask=hard+pi-pi.detach()
                mse=error(mask,a[:,:,ix],v[:,:,ix],y[:,:,ix])
                cost=(pi.mean((-1,-2))-budget).square().mean()
                loss=mse+20*cost
                opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_((alpha,bias,logtau),1.);opt.step()
            output[f'{context}_{budget}_distill']=state
            reports.append({'context':context,'budget':budget,'best_step':best_step,'best_validation_NMSE':best,'seconds':time.perf_counter()-begin,'history':history,'train_queries_per_head':sx.shape[2],'valid_queries_per_head':vx.shape[2]})
            torch.save(output,'artifacts/distilled.pt')
            Path('results/distillation.json').write_text(json.dumps({'protocol':'Only mean/bound mixture, threshold and temperature trained; original Qwen frozen. Hard Bernoulli masks with straight-through gradient; output NMSE +20*expected-budget deviation squared. Checkpoint selected by 16-draw validation output NMSE after recalibrating validation expected retention. This is local frozen-input distillation, not joint end-to-end language-model adaptation.','results':reports},indent=2))


if __name__=='__main__':main()
