import hashlib
import math
import time
import torch
import torch.nn.functional as F
from .adapter import Controller
from .vendor.plans import full_window_plan,suffix_plan,plan_batches,plan_metadata,summarize_records,ids_sha256


def score(model,ids,cfg=None,seed=0,protocol='suffix',context=2048,decode=128,examples=8,batch=8,native=False,capture=False,progress=None,plan_slice=None):
    plan=(suffix_plan(len(ids),context,decode,examples) if protocol=='suffix' else full_window_plan(len(ids),context,1024))
    if plan_slice is not None:plan=plan[plan_slice[0]:plan_slice[1]]
    controller=None if native else Controller(model,cfg,seed)
    # Even the unchanged control has an independent all-layer execution audit.
    counters=[0]*len(model.model.layers)
    phase=['prefill']
    hooks=[]
    for i,layer in enumerate(model.model.layers):
        def hook(module,args,index=i):
            if phase[0]=='decode':
                if args[0].shape[1]!=1:raise AssertionError('scored query is not single-token')
                counters[index]+=args[0].shape[0]
        hooks.append(layer.register_forward_pre_hook(hook))
    started=time.perf_counter()
    records=[]
    digest=hashlib.sha256()
    try:
        with torch.inference_mode():
            for rows in plan_batches(plan,batch):
                tokens=torch.stack([ids[r['begin']:r['end']] for r in rows]).to(model.device)
                prefix,steps=rows[0]['prefill_tokens'],rows[0]['scored_tokens']
                cache=None
                phase[0]='prefill'
                if controller:controller.prefix=True
                if prefix:cache=model.model(tokens[:,:prefix],use_cache=True).past_key_values
                phase[0]='decode'
                if controller:controller.prefix=False
                losses=torch.zeros(len(rows),device=model.device,dtype=torch.float64)
                for step in range(steps):
                    pos=prefix+step
                    output=model.model(tokens[:,pos:pos+1],past_key_values=cache,use_cache=True)
                    cache=output.past_key_values
                    logits=model.lm_head(output.last_hidden_state[:,-1]).float()
                    if capture:digest.update(logits.detach().cpu().contiguous().numpy().tobytes())
                    losses+=F.cross_entropy(logits,tokens[:,pos+1],reduction='none').double()
                for row,nll in zip(rows,losses.tolist()):
                    if not math.isfinite(nll):raise RuntimeError('nonfinite NLL')
                    records.append(dict(row,nll_sum=nll))
                if progress:progress(records)
                del cache,output,logits,tokens
        total=sum(r['scored_tokens'] for r in records)
        if counters != [total]*len(counters):raise AssertionError('incomplete layer/target coverage')
        audit=controller.report() if controller else {'native':True,'original_ffn':True}
        if controller and cfg and cfg.mode!='exact':
            if any(s['sampled_head_rows']!=total*model.config.num_attention_heads for s in controller.state.values()):
                raise AssertionError('some scored targets bypassed the sampler')
    finally:
        if controller:controller.close()
        for h in hooks:h.remove()
    return dict(**summarize_records(records),records=records,audit=audit,tokens_per_layer=counters,
                seconds=time.perf_counter()-started,plan=plan_metadata(plan,len(ids),protocol),
                scope='full' if protocol=='full' and plan_slice is None else protocol+'_subset',
                logits_sha256=digest.hexdigest() if capture else None,
                token_ids_sha256=ids_sha256(ids.tolist()),original_ffn=True)
