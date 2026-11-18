"""Exact matched WT2 sliding-window scoring for original or packed exports."""
import argparse,hashlib,json,math,time
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F

TEXT_SHA='173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08'
TOKEN_SHA='8557ef42be22a592e5f1704026fedbedc937b484e52f517add9f478adc0de20f'
def spans(length,window=2048,stride=1024):
    if not 0<stride<=window or length<2:raise ValueError('invalid scoring window/input')
    previous=1
    for start in range(0,length-1,stride):
        end=min(start+window,length);first=max(previous,start+1)
        if first>=end:break
        yield start,end,first;previous=end
        if end==length:break

@torch.no_grad()
def score(model,tokens,output,context=None,seed=101):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    total=0.;targets=0;windows=0;started=time.monotonic();coverage={}
    device=next(model.parameters()).device
    for wi,(start,end,first) in enumerate(spans(len(tokens))):
        ids=torch.as_tensor(np.asarray(tokens[start:end],dtype=np.int64),device=device).unsqueeze(0)
        if context:context.begin(0,wi,domain='ffn-wt2-deployment')
        logits=model(ids,use_cache=False).logits[0]
        a=first-start-1;b=end-start-1;window_loss=logits.new_zeros((),dtype=torch.float32)
        for lo in range(a,b,128):
            hi=min(b,lo+128);window_loss+=F.cross_entropy(logits[lo:hi].float(),ids[0,lo+1:hi+1],reduction='sum')
        loss=float(window_loss)
        if context:
            if len(context.coverage)!=model.config.num_hidden_layers:raise ValueError('FFN layer coverage missing')
            if any(v['calls']!=1 or v['tokens']!=end-start for v in context.coverage.values()):raise ValueError('FFN token path coverage mismatch')
            for layer in context.coverage:coverage[str(layer)]=coverage.get(str(layer),0)+end-start
        targets+=end-first;total+=loss;windows+=1
        with (output/'WINDOWS.jsonl').open('a') as f:f.write(json.dumps(dict(window=wi,start=start,end=end,first_scored=first,targets=end-first,nll_sum=loss))+'\n')
        if wi%10==0:(output/'PROGRESS.json').write_text(json.dumps(dict(windows=windows,targets=targets,seconds=time.monotonic()-started))+'\n')
    if targets!=len(tokens)-1:raise ValueError('scoring target count mismatch')
    result=dict(complete=True,scope='full WT2 sliding windows',window=2048,stride=1024,targets=targets,windows=windows,nll_sum=total,
                nll=total/targets,ppl=math.exp(total/targets),seed=seed,seconds=time.monotonic()-started,ffn_token_coverage=coverage,
                token_sha256=hashlib.sha256(np.asarray(tokens,dtype='<u4').tobytes()).hexdigest(),physical_PPA=None)
    (output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');return result

def main():
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from .export import load_export
    from .trainable_ffn import RunContext,FFNConfig,replace_ffns
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--text',required=True);p.add_argument('--output',required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--native',action='store_true');g.add_argument('--deployment');g.add_argument('--untrained-config')
    p.add_argument('--tables')
    p.add_argument('--seed',type=int,default=101);a=p.parse_args()
    text=Path(a.text).read_bytes()
    if hashlib.sha256(text).hexdigest()!=TEXT_SHA:raise ValueError('WT2 text bytes differ')
    tokenizer=AutoTokenizer.from_pretrained(a.model,local_files_only=True);tokens=np.asarray(tokenizer.encode(text.decode('utf-8'),add_special_tokens=False),dtype=np.uint32)
    if hashlib.sha256(tokens.astype('<u4').tobytes()).hexdigest()!=TOKEN_SHA:raise ValueError('WT2 tokenizer bytes differ')
    model=AutoModelForCausalLM.from_pretrained(a.model,local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
    context=None
    if a.deployment:context,_=load_export(model,a.deployment,RunContext(a.seed))
    if a.untrained_config:
        cfg=FFNConfig(**json.loads(Path(a.untrained_config).read_text()));tables=None
        if a.tables:
            calibrated=torch.load(a.tables,map_location='cpu',weights_only=True)
            if calibrated['manifest']['weight_bits']!=cfg.weight_bits:raise ValueError('untrained reference table bitwidth differs')
            tables=calibrated['tables']
        context=replace_ffns(model,cfg,RunContext(a.seed),tables)
        if cfg.strategy=='L':
            for layer in model.model.layers:layer.mlp.freeze_scales()
    model.requires_grad_(False)
    result=score(model,tokens,a.output,context,a.seed)
    if result['targets']!=299077 or result['windows']!=292:raise ValueError('full matched WT2 protocol mismatch')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
