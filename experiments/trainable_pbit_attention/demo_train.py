"""Small CPU training smoke: optimize the REAL stochastic finite-forward loss.

This is neither language-model training nor a PPL result.
"""
import argparse
import json
import platform
import time
from pathlib import Path

import torch
from .samplers import WinnerHoldAttention, CorrectedRejectionAttention


def run(steps=100, batch=256):
    torch.set_num_threads(1)
    results=[]
    start=time.time()
    for kind,cls in [('winner_hold',WinnerHoldAttention),('corrected_rejection',CorrectedRejectionAttention)]:
        for seed in (0,1,2):
            options=dict(samples=4)
            if kind=='winner_hold':options['burn_in']=4
            module=cls(**options)
            logits=torch.nn.Parameter(torch.tensor([.2,-.1,.1]))
            values=torch.tensor([[-1.],[0.],[1.]])
            optimizer=torch.optim.Adam([logits],lr=.05)
            generator=torch.Generator().manual_seed(seed)
            def evaluate(eval_seed):
                with torch.no_grad():
                    r=module(logits.expand(16000,-1),values,
                             generator=torch.Generator().manual_seed(eval_seed))
                    return ((r.output.squeeze(-1)-1)**2).mean().item()
            before=evaluate(1000+seed)
            baseline=1.0
            losses=[]
            for _ in range(steps):
                optimizer.zero_grad()
                r=module(logits.expand(batch,-1),values,generator=generator)
                loss=(r.output.squeeze(-1)-1)**2
                # Baseline uses only preceding batches; current batch is not its own baseline.
                objective=r.objective(loss,baseline).mean()
                objective.backward()
                if not bool(torch.isfinite(logits.grad).all()):
                    raise RuntimeError('nonfinite training gradient')
                optimizer.step()
                baseline=.9*baseline+.1*loss.detach().mean().item()
                losses.append(loss.detach().mean().item())
            after=evaluate(2000+seed)
            if not after < before*.5:
                raise RuntimeError('training smoke did not reduce held-out stochastic loss')
            results.append(dict(kind=kind,seed=seed,config=options,batch=batch,steps=steps,
                                before_mse=before,after_mse=after,final_logits=logits.detach().tolist(),
                                final_training_batch_mse=losses[-1],
                                evaluation_repeats=16000,evaluation_seed_before=1000+seed,
                                evaluation_seed_after=2000+seed))
    return dict(kind='synthetic CPU training validation, NOT model PPL or hardware measurement',
                torch=torch.__version__,python=platform.python_version(),device='cpu',
                elapsed_seconds=time.time()-start,learning_rate=.05,optimizer='Adam',
                values=[-1,0,1],target=1,gradient='full-trajectory score_function',runs=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=run()
    body=json.dumps(result,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('w',encoding='utf-8',newline='\n') as f:f.write(body)
    print(body)
