"""Capture unchanged BF16 Qwen post-RoPE scores and real V inside Slurm.

This is an attention-row benchmark, not PPL. All sampler variants later replay
the identical rows. The backbone is unchanged; only the final vocabulary readout
is restricted to its last token, since earlier readouts cannot affect attention.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import re

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
sys.path.insert(0,str(REPO/'experiments/qwen_ising_broadcast_20261021'))


@contextmanager
def observe(model,torch,controller,selected,context,start,records):
    fn=torch.nn.functional;original=fn.scaled_dot_product_attention
    active={'layer':None};handles=[];calls=[]
    def pre(index):
        def hook(module,args):
            if active['layer'] is not None:raise RuntimeError('nested attention')
            active['layer']=index
        return hook
    def post(module,args,result):active['layer']=None
    def wrapped(q,k,v,*args,**kwargs):
        layer=active['layer'];calls.append(layer)
        if q.shape!=(1,14,context,64) or k.shape!=q.shape or v.shape!=q.shape:
            raise RuntimeError('unexpected QKV shape')
        if args or kwargs.get('attn_mask') is not None or not kwargs.get('is_causal') or kwargs.get('dropout_p',0)!=0:
            raise RuntimeError('unexpected SDPA call')
        if any(x.dtype!=torch.bfloat16 for x in (q,k,v)):raise RuntimeError('BF16 required')
        if layer in selected:
            for base in (0,7):
                for h in range(base+1,base+7):
                    if not torch.equal(k[:,base],k[:,h]) or not torch.equal(v[:,base],v[:,h]):raise RuntimeError('GQA mismatch')
            a=model.model.layers[layer].self_attn
            chosen,_=controller._select(a,q[:,:,-1:],k[:,[0,7]])
            for head in (0,6,13):
                scores=(k[0,head].float()@q[0,head,-1].float())/math.sqrt(64)
                values=v[0,head].float()
                addresses=torch.arange(context)
                pools=[('dense',addresses)]
                mask=chosen[0,head].repeat_interleave(64)[:context]
                if not bool(mask.all()):pools.append(('screen512',addresses[mask]))
                for pool,ix in pools:
                    records.append(dict(context=context,start_token=start,layer=layer,head=head,
                        kv_head=head//7,pool=pool,addresses=ix.numpy(),
                        logits=scores[ix].cpu().numpy(),values=values[ix].cpu().numpy(),
                        full_logits=scores.cpu().numpy() if pool!='dense' else None,
                        full_values=values.cpu().numpy() if pool!='dense' else None))
        return original(q,k,v,*args,**kwargs)
    try:
        for i,l in enumerate(model.model.layers):
            handles.extend((l.self_attn.register_forward_pre_hook(pre(i)),l.self_attn.register_forward_hook(post)))
        fn.scaled_dot_product_attention=wrapped
        yield calls
    finally:
        fn.scaled_dot_product_attention=original
        for h in handles:h.remove()


def sha_tensor(tensor):
    return hashlib.sha256(tensor.contiguous().view(-1).view(__import__('torch').uint8).numpy().tobytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--commit',required=True)
    p.add_argument('--threads',type=int,default=4);p.add_argument('--contexts',default='512,2048,8192')
    p.add_argument('--starts',default='0,65536');a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('requires Slurm')
    root=Path(a.project).resolve()
    if root.parent!=Path('/home/Hongjie_Zeng/projects'):raise ValueError('personal project root required')
    out=root/'outputs'/a.commit/'qkv_capture'
    if out.exists():raise FileExistsError(out)
    # Pin model/tokenizer/corpus/calibration by the established independent identity.
    from run_model import identity,load,digest,write
    ident=identity(a);model,ids,cal,env=load(a,ident)
    import numpy as np
    import torch
    from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.attention import JointAttentionController
    controller=JointAttentionController(mode='screen_ising',seed=0,calibration=cal,budget_blocks=8)
    contexts=[int(x) for x in a.contexts.split(',')];starts=[int(x) for x in a.starts.split(',')]
    if any(n<64 or n>8192 for n in contexts) or any(s<0 or s+max(contexts)>len(ids) for s in starts):raise ValueError('capture window')
    records=[];windows=[];before=time.time()
    with torch.inference_mode():
        for context in contexts:
            for start in starts:
                window=ids[start:start+context][None,:]
                reference=model.model(input_ids=window,use_cache=False,return_dict=True).last_hidden_state
                reference_last=model.lm_head(reference[:,-1:]).float()
                controller._state={i:dict(summary=None,summary_builds=0,summary_updates=0) for i in (0,12,23)}
                with observe(model,torch,controller,{0,12,23},context,start,records) as calls:
                    captured=model.model(input_ids=window,use_cache=False,return_dict=True).last_hidden_state
                if calls!=list(range(24)):raise RuntimeError('capture layer coverage '+repr(calls))
                if not torch.equal(reference,captured):
                    repeat=model.model(input_ids=window,use_cache=False,return_dict=True).last_hidden_state
                    diag=dict(context=context,start_token=start,threads=a.threads,
                        captured_max_abs=float((reference.float()-captured.float()).abs().max()),
                        captured_mismatches=int((reference!=captured).sum()),
                        untouched_repeat_equal=bool(torch.equal(reference,repeat)),
                        untouched_repeat_max_abs=float((reference.float()-repeat.float()).abs().max()))
                    print(json.dumps(dict(capture_gate_failed=diag)),flush=True)
                    raise RuntimeError('BF16 capture equality failed; no trace accepted')
                captured_last=model.lm_head(captured[:,-1:]).float()
                if not torch.equal(reference_last,captured_last):raise RuntimeError('last readout mismatch')
                windows.append(dict(context=context,start_token=start,
                    token_ids_sha256=hashlib.sha256(window.numpy().astype('<i8').tobytes()).hexdigest(),
                    backbone_bitwise_equal=True,last_readout_bitwise_equal=True,
                    backbone_sha256=sha_tensor(reference),last_readout_sha256=sha_tensor(reference_last)))
                print(json.dumps(dict(stage='captured',context=context,start_token=start,rows=len(records),elapsed=time.time()-before)),flush=True)
                del reference,captured,reference_last,captured_last
    arrays={};metadata=[]
    for i,row in enumerate(records):
        row_id=f'r{i:03d}'
        metadata.append(dict(row_id=row_id,**{k:v for k,v in row.items() if k not in ('logits','values','addresses','full_logits','full_values')}))
        for key in ('logits','values','addresses','full_logits','full_values'):
            if row[key] is not None:arrays[row_id+'_'+key]=row[key]
    out.mkdir(parents=True,exist_ok=False);path=out/'qkv_rows_private.npz'
    with path.open('xb') as stream:np.savez_compressed(stream,**arrays)
    report=dict(status='completed',source_commit=a.commit,model_input_provenance=ident,
        environment=env,windows=windows,rows=metadata,trace=dict(path=str(path),bytes=path.stat().st_size,sha256=digest(path)),
        policy=dict(original_FFN=True,original_attention=True,layer_selection=[0,12,23],head_selection=[0,6,13],
                    screening='existing max4 fixed8 blocks, seed0, prior 2048 calibration; screening bias measured separately'),
        source_sha256=digest(__file__),elapsed_seconds=time.time()-before,
        scope='CPU BF16 unchanged-backbone real last-query QK and V; not full PPL or hardware timing')
    write(out/'CAPTURE.json',report)
    print(json.dumps(dict(status='completed',rows=len(metadata),path=str(path),sha256=digest(path))),flush=True)


if __name__=='__main__':main()
