"""Cheap query-dependent thresholds using free-block score mean/std; no root at inference."""
import json
from pathlib import Path
import torch
from calibrate import fit,masks


@torch.inference_mode()
def main():
    data=torch.load('artifacts/teacher.pt',weights_only=True);n=data['train_n']
    scores=data['scores'][:,:,n:].float().cuda();mass=data['mass'][:,:,n:].cuda();counts=data['counts'][n:].cuda()
    params=torch.load('artifacts/calibrated.pt',map_location='cuda',weights_only=True);out={};report=[]
    for ctx in (2048,8192):
        ix=counts==ctx//64;c=ctx//64;cs=counts[ix]
        valid,forced=masks(cs,c);free=(valid&~forced).float()
        for method,field in (('max2',1),('max4',2)):
            raw=scores[:,:,ix,:c,field]
            mu=(raw*free).sum(-1,keepdim=True)/free.sum(-1,keepdim=True)
            std=(((raw-mu).square()*free).sum(-1,keepdim=True)/free.sum(-1,keepdim=True)).sqrt().clamp_min(.01)
            normalized=(raw-mu)/std
            for budget in (.15,.3):
                best=torch.full((24,14),-torch.inf,device='cuda');state={}
                for t in (.1,.3,1.):
                    tau=torch.full((24,14,1,1),t,device='cuda')
                    bias,pi=fit(normalized,cs,'moment',tau,budget)
                    cov=(pi*mass[:,:,ix,:c]).sum(-1).mean(-1);win=cov>best;best=torch.maximum(best,cov)
                    for key,val in {'parameter':bias[:,:,0,0],'temperature':tau[:,:,0,0]}.items():
                        state[key]=torch.where(win,val,state[key]) if key in state else val
                name=f'{ctx}_{budget}_{method}';out[name]={k:v.cpu() for k,v in params[name].items()}
                out[name].update({k:v.cpu() for k,v in state.items()})
                report.append({'context':ctx,'budget':budget,'method':method,'expected_coverage':best.mean().item(),'temperature_mean':state['temperature'].mean().item()})
    torch.save(out,'artifacts/moment.pt')
    Path('results/moment_calibration.json').write_text(json.dumps({'protocol':'Added after observing fixed-threshold retention drift. Normalize free-block scores using current-query mean/std; train-tail-only calibration of head bias and temperature. No test-label fitting; no iterative threshold search at inference.','results':report},indent=2))


if __name__=='__main__':main()
