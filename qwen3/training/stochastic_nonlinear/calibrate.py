"""TRAIN-only fixed tables on the loaded teacher/warm-start trajectory.

Pass 1 collects x. Pass 2 estimates g/u with sampled x and quantized Wg/Wu,
while unpatched downstream layers follow the loaded reference trajectory.
This is explicit offline calibration, not online dynamic scale adaptation.
"""
import torch
from torch.nn import functional as F
from .core import Config,NoiseKey,quantize
from qwen3.weight_quantization.pot64 import FORMAT,choose_exponents
from qwen3.fixed_scale.static_core import _encode_static_validated
from qwen3.stochastic.vendor.stratified_core import stratified_counts


def _pot(maximum):
    maximum=maximum.clamp_min(2.**-10)
    m,e=torch.frexp(maximum)
    return torch.ldexp(torch.ones_like(maximum),e-(m==.5).int())


@torch.no_grad()
def collect(model,batches,provenance,config=Config(),seed=0):
    if provenance.get('split')!='train':raise ValueError('TRAIN-only calibration required')
    if torch.backends.cuda.matmul.allow_tf32:raise ValueError('disable TF32')
    batches=list(batches)
    if not batches:raise ValueError('no calibration batches')
    layers=model.model.layers;stats=[{} for _ in layers];handles=[]
    def maximum(i,name,value):
        v=value.float().reshape(-1,value.shape[-1]//64,64).abs().amax((0,2))
        stats[i][name]=v if name not in stats[i] else torch.maximum(v,stats[i][name])
    device=next(model.parameters()).device
    was_training=model.training;model.eval()
    try:
        for i,layer in enumerate(layers):
            def hook(module,args,i=i):maximum(i,'xmax',args[0])
            handles.append(layer.mlp.register_forward_pre_hook(hook))
        for tokens in batches:model(input_ids=tokens.to(device),use_cache=False)
        for h in handles:h.remove()
        handles=[]
        tables={str(i):dict(x=(_pot(s['xmax'])[:,None]*torch.tensor(
            [1.,.25,.0625,.015625],device=device)).tolist()) for i,s in enumerate(stats)}
        for i, layer in enumerate(layers):
            module = layer.mlp
            tables[str(i)]['weight_exponents'] = {
                name: choose_exponents(weight, config.weight_bits).tolist()
                for name, weight in (
                    ('gu', torch.cat((module.gate_proj.weight,module.up_proj.weight),0)),
                    ('down', module.down_proj.weight))}
        current=[0]
        for i,layer in enumerate(layers):
            def hook(module,args,i=i):
                with torch.autocast(device_type=device.type,enabled=False):
                    x=args[0].float();table=torch.tensor(tables[str(i)]['x'],device=device)
                    enc=_encode_static_validated(x,table)
                    c=stratified_counts(enc['probability'],64,64,
                        NoiseKey(seed,0,current[0]).generator(device,i,'calibration'),64)
                    _,w,_=quantize(torch.cat((module.gate_proj.weight,module.up_proj.weight),0),config.weight_bits,
                        torch.tensor(tables[str(i)]['weight_exponents']['gu'],device=device,dtype=torch.int8))
                    g,u=(F.linear(enc['sign']*enc['scale']*c,w)/64).chunk(2,-1)
                    maximum(i,'g',g);maximum(i,'u',u)
            handles.append(layer.mlp.register_forward_pre_hook(hook))
        for n,tokens in enumerate(batches):
            current[0]=n;model(input_ids=tokens.to(device),use_cache=False)
        for i,s in enumerate(stats):
            for name in ('g','u'):tables[str(i)][name]=_pot(s[name]).tolist()
    finally:
        for h in handles:h.remove()
        model.train(was_training)
    return dict(format='fixed-four-and-training-pot64-v2',weight_format=FORMAT,
        layers=tables,provenance=provenance,
        weight_bits=config.weight_bits,input_samples=64,input_strata=64,seed=seed,
        method='x reference trajectory; g/u sampled-input quantized-projection reference trajectory',
        note='g/u top S=ceilPow2(TRAIN max); lower_half maximum S/2 intentionally allows clipping')
