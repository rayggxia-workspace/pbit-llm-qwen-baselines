"""FFN-only checkpoints. Parent model and calibration are hash-bound by caller."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import torch
from .core import TrainableFFN, trainable_names


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def ffn_state(model):
    return {name:{k:v.detach().cpu().clone() for k,v in module.state_dict().items()}
            for name,module in model.named_modules() if isinstance(module,TrainableFFN)}


def load_ffn_state(model,state):
    modules={n:m for n,m in model.named_modules() if isinstance(m,TrainableFFN)}
    if set(state)!=set(modules):raise ValueError('checkpoint layer coverage mismatch')
    # Inspect every layer before mutation. Do not silently ignore missing keys.
    for name,m in modules.items():
        expected=m.state_dict()
        if set(expected)!=set(state[name]):raise ValueError('checkpoint keys mismatch: '+name)
        for key,value in expected.items():
            incoming=state[name][key]
            if incoming.shape!=value.shape or incoming.dtype!=value.dtype:
                raise ValueError('checkpoint shape/dtype mismatch: '+name+'.'+key)
            if key in ('x_scales','g_top','u_top','lut') and not torch.equal(incoming.cpu(),value.cpu()):
                raise ValueError('checkpoint calibration mismatch: '+name+'.'+key)
    for name,m in modules.items():m.load_state_dict(state[name],strict=True)


def save(path,model,optimizer,next_step,config,provenance,seed,world_size=1):
    path=Path(path)
    if path.exists():raise FileExistsError('immutable checkpoint already exists: '+str(path))
    payload=dict(format='stochastic-nonlinear-ffn-v1',ffn=ffn_state(model),
        optimizer=optimizer.state_dict(),next_step=int(next_step),config=asdict(config),
        provenance=provenance,provenance_sha256=fingerprint(provenance),seed=int(seed),
        world_size=int(world_size),trainable_names=trainable_names(model),
        torch_rng=torch.get_rng_state())
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.writing')
    torch.save(payload,temporary)
    temporary.replace(path)
    path.with_suffix(path.suffix+'.sha256').write_text(sha256(path)+'\n',encoding='ascii')


def restore(path,model,optimizer,config,provenance,seed,world_size=1):
    path=Path(path)
    expected=path.with_suffix(path.suffix+'.sha256').read_text(encoding='ascii').strip()
    if sha256(path)!=expected:raise ValueError('checkpoint SHA-256 mismatch')
    obj=torch.load(path,map_location='cpu',weights_only=True)
    checks=dict(format='stochastic-nonlinear-ffn-v1',config=asdict(config),
        provenance_sha256=fingerprint(provenance),seed=int(seed),world_size=int(world_size),
        trainable_names=trainable_names(model))
    for key,value in checks.items():
        if obj[key]!=value:raise ValueError('resume contract mismatch: '+key)
    if fingerprint(obj['provenance'])!=obj['provenance_sha256']:
        raise ValueError('checkpoint provenance content mismatch')
    load_ffn_state(model,obj['ffn']);optimizer.load_state_dict(obj['optimizer'])
    torch.set_rng_state(obj['torch_rng'])
    return obj['next_step']


def load_warm_weights(model,path,expected_sha):
    """Explicit interchange format: flat tensor map of all FFN projection names.

    Yesterday's unknown checkpoint must be exported by its owner into this
    format, not guessed here. This does not import optimizer/calibration.
    """
    if sha256(path)!=expected_sha:raise ValueError('warm-start SHA mismatch')
    state=torch.load(path,map_location='cpu',weights_only=True)
    wanted={n:p for n,p in model.named_parameters() if n.endswith(tuple(
        'mlp.'+p+'.weight' for p in ('gate_proj','up_proj','down_proj')))}
    if set(state)!=set(wanted):raise ValueError('warm-start requires exact all-layer FFN weights')
    for name,p in wanted.items():
        if state[name].shape!=p.shape or not torch.isfinite(state[name]).all():
            raise ValueError('invalid warm-start tensor: '+name)
    with torch.no_grad():
        for name,p in wanted.items():
            p.data=p.data.float()  # Preserve FP32 master values from yesterday.
            p.copy_(state[name].to(device=p.device,dtype=torch.float32))

