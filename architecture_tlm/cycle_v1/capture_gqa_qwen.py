"""Capture seven real Qwen queries sharing one KV head, in a GPU allocation.

Only a private activation fixture is emitted: no FFN or model weights. Q/K
are captured after BF16 projection then RoPE is evaluated in FP32, matching
the existing cycle_v1 capture boundary rather than bitwise model attention.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def write_json(path,value):
    path.write_text(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n',
                    encoding='utf-8',newline='\n')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--text',type=Path,required=True)
    p.add_argument('--baseline-manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--context',type=int,default=64,choices=(32,64))
    p.add_argument('--execution-commit',required=True)
    args=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('explicit Slurm GPU allocation required')
    if args.output.exists():raise FileExistsError('fresh private output directory required')
    baseline=json.loads(args.baseline_manifest.read_text(encoding='utf-8'))['provenance']
    config_hash=digest(args.model/'config.json')
    text_hash=digest(args.text)
    weight_hashes={path.name:digest(path) for path in sorted(args.model.glob('*.safetensors'))}
    if not weight_hashes:raise ValueError('no pinned model weight files found')
    for label,actual in (('config_sha256',config_hash),('text_sha256',text_hash),('model_files',weight_hashes)):
        if actual!=baseline[label]:raise AssertionError('baseline identity mismatch: '+label)
    import torch
    import transformers
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from transformers.models.qwen2.modeling_qwen2 import apply_rotary_pos_emb
    torch.set_num_threads(int(os.environ.get('SLURM_CPUS_PER_TASK','2')))
    torch.manual_seed(0)
    if not torch.cuda.is_available():raise RuntimeError('allocated CUDA device unavailable')
    tokenizer=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(args.model,local_files_only=True,
        torch_dtype=torch.bfloat16,attn_implementation='sdpa').eval().to('cuda')
    nq,nkv=model.config.num_attention_heads,model.config.num_key_value_heads
    dimension=model.config.hidden_size//nq
    if (nq,nkv,dimension)!=(14,2,64):raise ValueError('expected Qwen 14-query/2-KV heads of width64')
    token_ids=tokenizer(args.text.read_text(encoding='utf-8'),return_tensors='pt').input_ids[:,:args.context]
    if token_ids.shape!=(1,args.context):raise ValueError('not enough fixed corpus tokens')
    block=model.model.layers[12]
    cache={}
    hooks=[]
    for kind in ('q','k','v'):
        def capture(module,inputs,output,kind=kind):cache[kind]=output.detach().float().cpu()
        hooks.append(getattr(block.self_attn,kind+'_proj').register_forward_hook(capture))
    with torch.inference_mode():
        result=model(token_ids.to('cuda'),use_cache=False)
        finite=bool(torch.isfinite(result.logits).all().item())
    for hook in hooks:hook.remove()
    if not finite:raise AssertionError('nonfinite source logits')
    q=cache['q'].view(1,args.context,nq,dimension).transpose(1,2)
    k=cache['k'].view(1,args.context,nkv,dimension).transpose(1,2)
    v=cache['v'].view(1,args.context,nkv,dimension).transpose(1,2)
    positions=torch.arange(args.context).unsqueeze(0)
    with torch.inference_mode():
        inv=model.model.rotary_emb.inv_freq.detach().float().cpu()
        frequencies=(inv[None,:,None]@positions[:,None,:].float()).transpose(1,2)
        emb=torch.cat((frequencies,frequencies),dim=-1)
        q,k=apply_rotary_pos_emb(q,k,emb.cos(),emb.sin())
        selected_q=q[0,:7,-1].contiguous()
        selected_k=k[0,0].contiguous()
        selected_v=v[0,0].contiguous()
        scores=(selected_q.double()@selected_k.double().T)/(dimension**.5)
        exact=torch.softmax(scores,dim=-1)@selected_v.double()
    if not all(bool(torch.isfinite(t).all()) for t in (selected_q,selected_k,selected_v,exact)):
        raise AssertionError('nonfinite exported GQA data')
    tensor_hash=lambda t:hashlib.sha256(t.contiguous().numpy().tobytes()).hexdigest()
    tokenizer_files={p.name:digest(p) for p in sorted(args.model.iterdir())
        if p.is_file() and p.name in ('tokenizer.json','tokenizer_config.json','vocab.json','merges.txt','special_tokens_map.json')}
    provenance={'kind':'real_model_gqa_group_activation_fixture_not_full_attention_or_PPL',
        'model':baseline['model'],'revision':baseline['revision'],'layer':12,
        'context':args.context,'query_token_position':args.context-1,'query_heads':list(range(7)),
        'shared_kv_head':0,'query_to_kv_rule':'query_head // (14/2); heads0..6 all map to KVhead0',
        'head_dimension':64,'candidate_policy':'all causal keys0..context-1, no selector',
        'config_sha256':config_hash,'text_sha256':text_hash,'model_files':weight_hashes,
        'tokenizer_files':tokenizer_files,'token_ids_sha256':tensor_hash(token_ids),
        'token_ids_hash_format':'contiguous int64 native-little-endian array shape[1,context]',
        'baseline_manifest_sha256':digest(args.baseline_manifest),'baseline_identity_verified':True,
        'dtype':'BF16 model/projections; projections exported to FP32; CPU FP32 RoPE for Q/K',
        'precision_note':'same declared FP32 RoPE export boundary as original cycle_v1 capture; not bitwise model-attention evidence',
        'tensor_sha256':{'q_fp32':tensor_hash(selected_q),'k_fp32':tensor_hash(selected_k),'v_fp32':tensor_hash(selected_v)},
        'source_sha256':digest(Path(__file__)),'execution_commit':args.execution_commit,
        'job_id':os.environ['SLURM_JOB_ID'],'seed':0,'python':platform.python_version(),
        'torch':torch.__version__,'transformers':transformers.__version__,'cuda':torch.version.cuda,
        'gpu':torch.cuda.get_device_name(0),'source_logits_finite':finite,
        'boundary':'QKV projection, RoPE, KV append, screening, Wo and remaining model execution are outside group simulator timing'}
    fixture={'queries':[{'q':selected_q[h].tolist(),'candidate_ids':list(range(args.context))} for h in range(7)],
             'k':selected_k.tolist(),'v':selected_v.tolist(),'provenance':provenance}
    args.output.mkdir(parents=True)
    path=args.output/f'qwen_layer12_gqa7_context{args.context}.json'
    write_json(path,fixture)
    manifest={'provenance':provenance,'artifacts':[{'path':path.name,'sha256':digest(path),'bytes':path.stat().st_size}],
        'exact_functional_diagnostic':{'method':'double QK reduction/softmax/PV on exported FP32 tensors; independent of cycle scheduler',
            'shape':list(exact.shape),'output_sha256':tensor_hash(exact),'output':exact.tolist()},
        'publication':'keep raw activation fixture in personal artifact storage; publish source, SHA and compact summaries only'}
    write_json(args.output/'MANIFEST.json',manifest)
    print(json.dumps({'status':'complete','output':str(args.output),'artifacts':manifest['artifacts'],
                      'heads':7,'kv_heads':1,'context':args.context,'baseline_identity_verified':True}))


if __name__=='__main__':main()
