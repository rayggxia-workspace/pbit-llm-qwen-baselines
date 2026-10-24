"""Small randomly initialized HF Qwen3 on CUDA; no pretrained quality claim."""
import json
import sys
from pathlib import Path
import torch
from transformers import Qwen3Config,Qwen3ForCausalLM
from .core import install,noise_context,NoiseKey
from .test_training import tables


def main():
    torch.manual_seed(24);torch.backends.cuda.matmul.allow_tf32=False
    cfg=Qwen3Config(vocab_size=64,hidden_size=64,intermediate_size=64,
        num_hidden_layers=2,num_attention_heads=2,num_key_value_heads=1,head_dim=32,
        max_position_embeddings=128,attention_dropout=0.,use_cache=False)
    model=Qwen3ForCausalLM(cfg).bfloat16().cuda()
    names=install(model,dict(layers={'0':tables(),'1':tables()}))
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    frozen={n:p.detach().clone() for n,p in model.named_parameters() if not p.requires_grad}
    before={n:p.detach().clone() for n,p in model.named_parameters() if p.requires_grad}
    opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=1e-3)
    tokens=torch.randint(64,(2,16),device='cuda');losses=[]
    model.train()
    for step in range(5):
        opt.zero_grad(set_to_none=True)
        with noise_context(model,NoiseKey(24,step)):
            loss=model(input_ids=tokens,labels=tokens,use_cache=False).loss
            loss.backward()
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters() if p.requires_grad)
        opt.step();losses.append(float(loss))
    assert all(torch.equal(frozen[n],p) for n,p in model.named_parameters() if n in frozen)
    changed=[n for n,p in model.named_parameters() if n in before and not torch.equal(before[n],p)]
    assert set(changed)==set(names)
    result=dict(status='completed',kind='randomly initialized tiny Qwen3 CUDA integration; NOT 4B result',
        torch=str(torch.__version__),gpu=torch.cuda.get_device_name(),layers=2,steps=5,
        gradient_checkpointing='non-reentrant',losses=losses,updated_weights=changed,
        frozen_parameters_unchanged=True,peak_allocated_bytes=torch.cuda.max_memory_allocated())
    Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
