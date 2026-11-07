"""Keep the sampler and random keys fixed; change only the score/LUT front end."""
from pathlib import Path
import json
import torch
from experiments.sparse_attention_accuracy_20261102.methods import Patch as OriginalPatch
from experiments.sparq_ising_20261028.core import Config

CASES=['bf16','sparq128','ising64_ideal','ising64_s12_idealprob',
       'ising64_gap_fp32_p8','ising64_gap_s12_p8']
STOCHASTIC=CASES[2:]
TASK_CASES=['bf16','ising64_ideal','ising64_gap_s12_p8']
FRONTS={
 'bf16':'unchanged native BF16 SDPA',
 'sparq128':'FP32 SparQ r32/k128/local32 full weighted PV',
 'ising64_ideal':'FP32 max gap -> continuous sigmoid',
 'ising64_s12_idealprob':'RNE signed12/F4 absolute score -> integer max gap -> continuous sigmoid',
 'ising64_gap_fp32_p8':'FP32 max gap -> RNE U8/F4 saturating address -> original floor-P8 LUT',
 'ising64_gap_s12_p8':'RNE signed12/F4 absolute score -> integer max gap -> saturating U8/F4 address -> original floor-P8 LUT'}

def configuration(name):
    if name not in CASES:raise ValueError(name)
    if name=='bf16':return None
    return Config(k=128,samples=64,burn=0,mode='exact' if name=='sparq128' else 'winner')

def load_table():
    path=Path(__file__).resolve().parents[1]/'sparse_attention_accuracy_20261102/sigmoid_table.json'
    return torch.tensor(json.loads(path.read_bytes())['values'],dtype=torch.long)

def gap_probability(logits,name,table):
    z=logits.float()
    if name=='ising64_ideal':
        gap=z.amax(-1,keepdim=True)-z
        return torch.sigmoid(-gap),None,None,dict()
    if name not in STOCHASTIC:raise ValueError(name)
    if name=='ising64_gap_fp32_p8':
        gap=z.amax(-1,keepdim=True)-z
        raw_gap=torch.round(gap*16)
        clipped_scores=torch.zeros((),device=z.device,dtype=torch.long)
    else:
        raw=torch.round(z*16)
        code=raw.clamp(-2048,2047).long()  # TOTAL width12, sign included; four fractional bits.
        raw_gap=code.amax(-1,keepdim=True)-code
        gap=raw_gap.float()/16
        clipped_scores=(raw!=code).sum()
    if name=='ising64_s12_idealprob':
        return torch.sigmoid(-gap),None,None,dict(score_clipped=clipped_scores)
    # Saturation, never bit truncation/modulo: large negative fields map to tail0.
    address=raw_gap.clamp(0,255).long()
    threshold=table.to(z.device)[address]
    return threshold.float()/256,address,threshold,dict(
        score_clipped=clipped_scores,gap_clipped=(raw_gap>255).sum(),
        zero_threshold_entries=(threshold==0).sum())

class Patch(OriginalPatch):
    def __init__(self,name):
        if name not in CASES:raise ValueError(name)
        super().__init__(name)
        self.metrics={}
    def __enter__(self):
        super().__enter__()
        controller=self.Controller
        owner=self
        class GapController(controller):
            def report(self):
                r=super().report()
                r.update(ideal_sigmoid_source=owner.name in ('ising64_ideal','ising64_s12_idealprob'),
                         front_end=FRONTS[owner.name],hardware_changed=False)
                return r
        from experiments.sparq_ising_20261028 import scoring
        self.Controller=GapController
        scoring.Controller=GapController
        return self
    def probabilities(self,logits,method):
        assert method=='winner'
        p,_,_,metrics=gap_probability(logits,self.name,self.table)
        self.calls+=1;self.entries+=logits.numel()
        for name,value in metrics.items():
            self.metrics[name]=value if name not in self.metrics else self.metrics[name]+value
        planes=torch.zeros((p.shape[0],26,p.shape[1]),device=p.device)
        planes[:,0]=p;planes[:,25,0]=1  # Same slot0, burn0 and sampler as old comparison.
        return planes.contiguous()
    def report(self):
        stochastic=self.name in STOCHASTIC
        return dict(method=self.name,numeric=FRONTS[self.name],
            probability_calls=self.calls,score_entries=self.entries,
            **{key:int(value) for key,value in self.metrics.items()},
            initial_winner_slot=0 if stochastic else None,burn=0 if stochastic else None,
            samples=64 if stochastic else None,lut_entries=256 if self.name.endswith('_p8') else None,
            threshold_bits=8 if self.name.endswith('_p8') else None,
            hardware_changed=False,hardware_bittrue=False,
            screening='FP32 SparQ r32/k128/local32, no mean-V compensation' if self.name!='bf16' else None,
            rng='same Config/seed/layer/call keys across Ising front ends; independent Philox, not GF64' if stochastic else None)
