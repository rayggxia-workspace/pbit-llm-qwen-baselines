import json
from pathlib import Path
import torch
from metrics import METHODS


def masks(counts,c):
    ar=torch.arange(c,device=counts.device)[None]
    valid=ar<counts[:,None]
    forced=valid & ((ar==0)|(ar>=counts[:,None]-2))
    return valid[None,None],forced[None,None]


def fit(scores,counts,method,temperature,target,iterations=36):
    valid,forced=masks(counts,scores.shape[-1])
    scores=scores.masked_fill(~valid,-torch.inf)
    if method=='mean_softmax':
        p=scores.softmax(-1)
        logp=torch.log1p(-p.clamp(max=1-1e-7))
    else:relative=scores if method=='moment' else scores-scores.amax(-1,keepdim=True)
    lo=torch.full_like(scores[:,:,:1,:1],-40. if method=='mean_softmax' else -10000.)
    hi=torch.full_like(lo,80. if method=='mean_softmax' else 10000.)
    def compute(value):
        pi=-torch.expm1(value.exp()*logp) if method=='mean_softmax' else torch.sigmoid((relative+value)/temperature)
        return pi.masked_fill(~valid,0).masked_fill(forced,1)
    for _ in range(iterations):
        mid=(lo+hi)/2;pi=compute(mid)
        fraction=(pi.sum(-1)/counts).mean(-1,keepdim=True).unsqueeze(-1)
        lo=torch.where(fraction<target,mid,lo);hi=torch.where(fraction>=target,mid,hi)
    parameter=(lo+hi)/2
    return parameter.exp() if method=='mean_softmax' else parameter,compute(parameter)


def train_scales(data):
    n=data['train_n'];s=data['scores'][:,:,:n].float().cuda();counts=data['counts'][:n].cuda()
    valid,_=masks(counts,s.shape[-2]);valid=valid[...,None]
    s=s-s.masked_fill(~valid,-torch.inf).amax(-2,keepdim=True)
    mean=(s*valid).sum((2,3))/valid.sum((2,3))
    var=((s-mean[:,:,None,None]).square()*valid).sum((2,3))/valid.sum((2,3))
    return var.sqrt().clamp_min(.1)


@torch.inference_mode()
def main():
    data=torch.load('artifacts/teacher.pt',weights_only=True);n=data['train_n']
    scales=train_scales(data)
    sx=data['scores'][:,:,n:].float().cuda();mass=data['mass'][:,:,n:].cuda();counts=data['counts'][n:].cuda()
    params={};report=[]
    for ctx in (2048,8192):
        ix=counts==ctx//64;cs=counts[ix];s=sx[:,:,ix];a=mass[:,:,ix]
        for budget in (.15,.3):
            for method in METHODS:
                best=torch.full((24,14),-torch.inf,device='cuda');best_param={}
                alphas=(0.,.25,.5,.75,1.) if method=='mix' else (.5,)
                multipliers=(.1,.3,1.) if method!='mean_softmax' else (1.,)
                for alpha in alphas:
                    if method=='mix':
                        scores=alpha*s[...,0]/scales[:,:,None,None,0]+(1-alpha)*s[...,3]/scales[:,:,None,None,3]
                        scale=torch.ones_like(scales[...,0])
                    else:
                        field={'mean_softmax':0,'mean_sigmoid':0,'max2':1,'max4':2,'bound':3}[method]
                        scores=s[...,field];scale=scales[...,field]
                    for mult in multipliers:
                        tau=(mult*scale).clamp_min(.01)[:,:,None,None]
                        parameter,pi=fit(scores,cs,method,tau,budget)
                        coverage=(pi*a).sum(-1).mean(-1)
                        win=coverage>best;best=torch.maximum(best,coverage)
                        candidate={'temperature':tau[:,:,0,0],'parameter':parameter[:,:,0,0],
                            'alpha':torch.full_like(best,alpha),'scales':scales[...,[0,3]],
                            'coverage':coverage,'fraction':(pi.sum(-1)/cs).mean(-1)}
                        for key,val in candidate.items():
                            if key not in best_param:best_param[key]=val
                            else:best_param[key]=torch.where(win[...,None] if val.ndim==3 else win,val,best_param[key])
                assert (best_param['fraction']-budget).abs().max()<1e-4,(method,budget,best_param['fraction'].min().item())
                name=f'{ctx}_{budget}_{method}';params[name]={k:v.cpu() for k,v in best_param.items()}
                report.append({'context':ctx,'budget':budget,'method':method,'expected_coverage':best.mean().item(),'expected_token_fraction':best_param['fraction'].mean().item(),'alpha_mean':best_param['alpha'].mean().item(),'alpha_hist':{str(v):int((best_param['alpha']==v).sum()) for v in alphas},'temperature_mean':best_param['temperature'].mean().item()})
                print(json.dumps(report[-1]),flush=True)
    torch.save(params,'artifacts/calibrated.pt')
    Path('results/calibration.json').write_text(json.dumps({'protocol':'Each layer/head calibrated on eight held-out train-tail queries at each context to expected 15% or 30% candidates; choose temperature (and mixture alpha) by validation attention-mass coverage. Actual test retention may differ. Deterministic controls use exact ceil(budget*blocks) with mandatory blocks included.','results':report},indent=2))


if __name__=='__main__':main()
