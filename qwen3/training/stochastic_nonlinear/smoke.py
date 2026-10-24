"""Small synthetic optimization, NOT a pretrained-model quality result."""
import argparse
import copy
import json
from pathlib import Path
import time
import torch
from torch.nn import functional as F
from .core import TrainableFFN,Config,NoiseKey,noise_context
from .test_training import original,tables


def run(seed,steps=100,device='cpu'):
    torch.manual_seed(seed);torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False
    teacher=original(device)
    student=TrainableFFN(copy.deepcopy(teacher),tables(),0,Config())
    with torch.no_grad():
        for p in student.parameters():p.add_(torch.randn_like(p)*.04)
    x=torch.randn(32,64,device=device)
    held=torch.randn(32,64,device=device)
    def target(x):
        with torch.no_grad():return teacher.down_proj(F.silu(teacher.gate_proj(x))*teacher.up_proj(x))
    yy=target(x);yv=target(held)
    def measure():
        losses=[]
        with torch.no_grad():
            for r in range(16):
                with noise_context(student,NoiseKey(10000+seed,0,r)):
                    losses.append(float(F.mse_loss(student(held),yv)))
        return sum(losses)/len(losses)
    before=measure();optimizer=torch.optim.AdamW(student.parameters(),lr=.003,weight_decay=0.)
    begin=time.time();losses=[]
    for step in range(steps):
        optimizer.zero_grad(set_to_none=True)
        with noise_context(student,NoiseKey(seed,step)):
            loss=F.mse_loss(student(x),yy);loss.backward()
        torch.nn.utils.clip_grad_norm_(student.parameters(),1.,error_if_nonfinite=True)
        optimizer.step();losses.append(float(loss))
    return dict(seed=seed,steps=steps,train_first_mse=losses[0],train_last_mse=losses[-1],
        heldout_16_noise_keys_before=before,heldout_16_noise_keys_after=measure(),
        elapsed_s=time.time()-begin,finite=all(torch.isfinite(p).all().item() for p in student.parameters()))


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--device',default='cpu')
    a=p.parse_args();dest=Path(a.out)
    if dest.exists():raise FileExistsError(dest)
    result=dict(kind='synthetic 64x64 FFN, teacher MSE; NOT Qwen PPL or training quality',
        torch=torch.__version__,device=a.device,results=[run(seed,device=a.device) for seed in (0,1,2)])
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
