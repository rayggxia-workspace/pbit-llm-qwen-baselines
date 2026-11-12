"""Only this module defines the numerical front end of the new sweep."""
import math
import torch

TABLE = [math.floor(256/(1+math.exp(a/16))) for a in range(256)]
active = None

def begin(cfg, seed):
    global active
    active = None
    if cfg is not None and cfg.mode == 'winner':
        from hardware_rng import Sampler
        active = Sampler('gf64_bivium', cfg.k, seed)

def set_layer(layer):
    if active is not None:
        active.layer = layer

def thresholds(scores):
    z = scores.float()
    gap = z.amax(-1, keepdim=True) - z
    address = torch.round(gap*16).clamp(0,255).long()
    table = torch.tensor(TABLE, device=z.device, dtype=torch.long)
    return address, table[address]

def draw(scores, samples, seed):
    _, t = thresholds(scores)
    planes = torch.zeros((scores.shape[0],26,scores.shape[-1]),device=scores.device)
    planes[:,0] = t.float()/256
    planes[:,25,0] = 1
    indices, activity, _ = active.sample(planes, samples, seed)
    return indices, activity

def report():
    return dict(front='FP32 max first -> FP32 gap -> RNE U8/F4 -> floor-P8',
                initial_winner_slot=0,burn=0,spacing=1,
                random_source=active.report() if active is not None else None)
