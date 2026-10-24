"""Two-GPU tiny Qwen3 checkpointed DDP integration, not a 4B benchmark."""
import json
import os
import sys
from pathlib import Path
import torch
from transformers import Qwen3Config,Qwen3ForCausalLM
from .core import install,noise_context,NoiseKey
from .test_training import tables


def main():
    rank=int(os.environ['RANK']);local=int(os.environ['LOCAL_RANK'])
    torch.cuda.set_device(local);torch.distributed.init_process_group('nccl')
    torch.backends.cuda.matmul.allow_tf32=False;torch.manual_seed(24)
    cfg=Qwen3Config(vocab_size=64,hidden_size=64,intermediate_size=64,num_hidden_layers=2,
        num_attention_heads=2,num_key_value_heads=1,head_dim=32,max_position_embeddings=128,
        attention_dropout=0.,use_cache=False)
    m=Qwen3ForCausalLM(cfg).bfloat16().cuda();names=install(m,dict(layers={'0':tables(),'1':tables()}))
    frozen={n:p.detach().clone() for n,p in m.named_parameters() if not p.requires_grad}
    m.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});m.train()
    ddp=torch.nn.parallel.DistributedDataParallel(m,device_ids=[local],broadcast_buffers=False)
    opt=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=.001)
    losses=[]
    for step in range(3):
        opt.zero_grad(set_to_none=True)
        batch=torch.randint(64,(2,16),device='cuda')
        with noise_context(m,NoiseKey(24,step,rank=rank)):
            loss=ddp(input_ids=batch,labels=batch,use_cache=False).loss;loss.backward()
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters() if p.requires_grad)
        opt.step();torch.distributed.all_reduce(loss.detach());losses.append(float(loss)/torch.distributed.get_world_size())
    for name,p in m.named_parameters():
        if name in frozen:assert torch.equal(frozen[name],p)
        else:
            ref=p.detach().clone();torch.distributed.broadcast(ref,0);assert torch.equal(ref,p)
    if rank==0:
        Path(sys.argv[1]).write_text(json.dumps(dict(status='completed',kind='tiny random Qwen3 DDP',
            world_size=torch.distributed.get_world_size(),steps=3,losses=losses,
            checkpointing='non-reentrant',weights_equal_across_ranks=True,
            frozen_unchanged=True,trainable_names=names),indent=2)+'\n',encoding='utf-8')
    torch.distributed.destroy_process_group()


if __name__=='__main__':main()
