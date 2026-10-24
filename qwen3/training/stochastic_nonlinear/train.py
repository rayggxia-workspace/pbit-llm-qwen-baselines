"""Minimal CE trainer/calibrator for a LOCAL posttrained Qwen3-4B checkpoint.

Single GPU or torchrun DDP. Fixed pretokenized TRAIN blocks. No automatic
download, no checkpoint guesses, no fabricated dataset or PPL measurement.
Integrate core.install into the existing agent trainer for KD/FSDP instead.
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import time
import torch
from torch import nn
from torch.nn import functional as F
from .core import Config,NoiseKey,install,noise_context,contract
from .checkpoint import sha256,fingerprint,load_warm_weights,save,restore
from .calibrate import collect

MODEL_ID='Qwen/Qwen3-4B'
REVISION='1cfa9a7208912126459214e8b04321603b3df60c'


def verified(path,expected):
    if not expected or sha256(path)!=expected:raise ValueError('SHA mismatch: '+str(path))
    return Path(path)


def load_manifest(path,need_calibration=True):
    m=json.loads(Path(path).read_text(encoding='utf-8'))
    if (m['model_id'],m['revision'],m['posttrained'])!=(MODEL_ID,REVISION,True):
        raise ValueError('require the approved posttrained Qwen3-4B model, not Base')
    root=Path(m['model_dir']).resolve()
    if not m['model_files']:raise ValueError('model/tokenizer files must be hashed')
    supplied=set(m['model_files'])
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and
            p.suffix in ('.json','.safetensors','.bin','.model','.txt','.jinja') and
            '.cache' not in p.relative_to(root).parts}
    if not actual<=supplied:raise ValueError('unhashed model/tokenizer files: '+str(sorted(actual-supplied)))
    for name,digest in m['model_files'].items():
        p=(root/name).resolve()
        if root not in p.parents:raise ValueError('model manifest path escapes root')
        verified(p,digest)
    if m['train']['split']!='train':raise ValueError('training tokens must be TRAIN')
    verified(m['train']['path'],m['train']['sha256'])
    if m.get('warm_ffn'):verified(m['warm_ffn']['path'],m['warm_ffn']['sha256'])
    if need_calibration:verified(m['calibration']['path'],m['calibration']['sha256'])
    return m


class ReferenceFFN(nn.Module):
    """Calibration trajectory only: FP32 nonlinear reference, never train path."""
    def __init__(self,old):
        super().__init__()
        for name in ('gate_proj','up_proj','down_proj'):setattr(self,name,getattr(old,name).float())
    def forward(self,x):
        return self.down_proj(F.silu(self.gate_proj(x.float()))*self.up_proj(x.float())).to(x.dtype)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',required=True);p.add_argument('--config',required=True)
    p.add_argument('--out',required=True);p.add_argument('--steps',type=int,default=200)
    p.add_argument('--micro-batch',type=int,default=1);p.add_argument('--accum',type=int,default=4)
    p.add_argument('--lr',type=float,default=1e-5);p.add_argument('--seed',type=int,default=0)
    p.add_argument('--save-every',type=int,default=50);p.add_argument('--resume')
    p.add_argument('--gradient-checkpointing',action='store_true')
    p.add_argument('--make-calibration',action='store_true');p.add_argument('--calibration-blocks',type=int,default=16)
    a=p.parse_args()
    if min(a.steps,a.micro_batch,a.accum,a.save_every,a.calibration_blocks)<1:raise ValueError('positive budgets required')
    cfg=Config(**json.loads(Path(a.config).read_text(encoding='utf-8')))
    rank=int(os.environ.get('RANK','0'));world=int(os.environ.get('WORLD_SIZE','1'))
    local=int(os.environ.get('LOCAL_RANK','0'))
    if not torch.cuda.is_available():raise RuntimeError('real-model runner requires CUDA; use smoke.py on CPU')
    if a.make_calibration and world!=1:raise ValueError('calibrate once on one GPU then freeze the file')
    torch.cuda.set_device(local);device=torch.device('cuda',local)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.manual_seed(a.seed)
    if world>1:torch.distributed.init_process_group('nccl')
    m=load_manifest(a.manifest,need_calibration=not a.make_calibration)
    tokens=torch.load(m['train']['path'],map_location='cpu',weights_only=True)
    if not isinstance(tokens,torch.Tensor) or tokens.dtype!=torch.int64 or tokens.ndim!=2 or tokens.shape[1]<2:
        raise ValueError('TRAIN .pt must contain int64 [blocks, sequence] with no padding')
    from transformers import AutoModelForCausalLM
    model=AutoModelForCausalLM.from_pretrained(m['model_dir'],torch_dtype=torch.bfloat16,
        local_files_only=True,trust_remote_code=False,attn_implementation='sdpa').to(device)
    c=model.config
    if (c.model_type,c.hidden_size,c.intermediate_size,c.num_hidden_layers)!=('qwen3',2560,9728,36):
        raise ValueError('unexpected model architecture')
    if getattr(c,'attention_dropout',0)!=0:raise ValueError('reference runner requires zero dropout')
    if bool(((tokens<0)|(tokens>=c.vocab_size)).any()):raise ValueError('token IDs outside vocabulary')
    c.use_cache=False
    if m.get('warm_ffn'):load_warm_weights(model,m['warm_ffn']['path'],m['warm_ffn']['sha256'])
    source=dict(model_id=m['model_id'],revision=m['revision'],model_files=m['model_files'],
                warm_ffn_sha256=m.get('warm_ffn',{}).get('sha256'),
                train=m['train'],train_sha256=m['train']['sha256'],split='train')
    out=Path(a.out)
    if rank==0:
        if out.exists():raise FileExistsError('use a fresh output directory, including resume runs')
        out.mkdir(parents=True)
    if world>1:torch.distributed.barrier()
    if a.make_calibration:
        for layer in model.model.layers:layer.mlp=ReferenceFFN(layer.mlp)
        cal=collect(model,[row[None,:] for row in tokens[:a.calibration_blocks]],source,cfg,a.seed)
        target=out/'calibration.json'
        target.write_bytes((json.dumps(cal,indent=2)+'\n').encode())
        print(json.dumps(dict(path=str(target),sha256=sha256(target))),flush=True)
        return
    cal=json.loads(Path(m['calibration']['path']).read_text(encoding='utf-8'))
    if cal['format']!='fixed-four-and-training-v1' or cal['provenance']!=source or cal['weight_bits']!=cfg.weight_bits:
        raise ValueError('calibration belongs to another checkpoint/data/weight format')
    names=install(model,cal,cfg)
    if a.gradient_checkpointing:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    # AdamW state/grad/master remain FP32. Attention and non-FFN are frozen.
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=a.lr,weight_decay=0.)
    source.update(calibration_sha256=m['calibration']['sha256'],optimizer='AdamW',lr=a.lr,
        weight_decay=0.,micro_batch=a.micro_batch,accum=a.accum,loss='causal next-token CE; no chat template',
        gradient_checkpointing=a.gradient_checkpointing)
    try:source['code_commit']=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()
    except (OSError,subprocess.CalledProcessError):raise RuntimeError('run from recorded Git checkout')
    start=restore(a.resume,model,optimizer,cfg,source,a.seed,world) if a.resume else 0
    if start>=a.steps:raise ValueError('--steps is the desired TOTAL number of optimizer steps')
    trained=model if world==1 else torch.nn.parallel.DistributedDataParallel(model,device_ids=[local],broadcast_buffers=False)
    model.train()
    if rank==0:
        (out/'run.json').write_bytes((json.dumps(dict(contract=contract(cfg),provenance=source,
            seed=a.seed,world_size=world,start_step=start,steps=a.steps,trainable_names=names,
            torch=torch.__version__,status='running'),indent=2)+'\n').encode())
    begin=time.time()
    for step in range(start,a.steps):
        optimizer.zero_grad(set_to_none=True);total=torch.zeros((),device=device)
        for micro in range(a.accum):
            first=((step*a.accum+micro)*world+rank)*a.micro_batch
            index=torch.arange(first,first+a.micro_batch)%len(tokens)
            batch=tokens[index].to(device)
            # Keep context live through backward/checkpoint replay. Rank keys differ.
            with noise_context(model,NoiseKey(a.seed,step,micro,rank)):
                loss=trained(input_ids=batch,labels=batch,use_cache=False).loss
                if not bool(torch.isfinite(loss)):raise FloatingPointError('non-finite CE')
                (loss/a.accum).backward();total+=loss.detach()/a.accum
        norm=torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.,error_if_nonfinite=True)
        optimizer.step()
        if world>1:torch.distributed.all_reduce(total);total/=world
        if rank==0:
            record=dict(step=step+1,ce=float(total),grad_norm=float(norm),elapsed_s=time.time()-begin)
            print(json.dumps(record),flush=True)
            with (out/'train.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(record)+'\n')
            if (step+1)%a.save_every==0 or step+1==a.steps:
                save(out/('ffn-step-%06d.pt'%(step+1)),model,optimizer,step+1,cfg,source,a.seed,world)
        if world>1:torch.distributed.barrier()
    if rank==0:
        (out/'COMPLETED.json').write_bytes((json.dumps(dict(status='completed',steps=a.steps,
            training_only=True,evaluation_pending=True,elapsed_s=time.time()-begin))+'\n').encode())
    if world>1:torch.distributed.destroy_process_group()


if __name__=='__main__':main()
