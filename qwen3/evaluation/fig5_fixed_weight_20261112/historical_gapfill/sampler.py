"""Historical S12-first floor-P8 law; this module does NOT use max-first/GF64."""
from pathlib import Path
import json
import torch
import philox_kernels

TABLE=json.loads((Path(__file__).parent/'sigmoid_table.json').read_text())['values']

def thresholds(scores):
    code=torch.round(scores.float()*16).clamp(-2048,2047).long()
    address=(code.amax(-1,keepdim=True)-code).clamp(0,255)
    table=torch.tensor(TABLE,device=scores.device,dtype=torch.long)
    return address,table[address]

def probabilities(logits,method):
    assert method=='winner'
    _,t=thresholds(logits)
    planes=torch.zeros((logits.shape[0],26,logits.shape[-1]),device=logits.device)
    planes[:,0]=t.float()/256
    planes[:,25,0]=1
    return planes.contiguous()

philox_kernels.probabilities=probabilities
sample=philox_kernels.sample
