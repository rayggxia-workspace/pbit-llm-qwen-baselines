"""Portable cached scorer. New GPU port must pass gate before full runs."""
from pathlib import Path
import argparse,hashlib,importlib.metadata,json,math,platform,subprocess,time
from prepare import sha
from plans import full_window_plan,ids_sha256,summarize_records

HERE=Path(__file__).resolve().parent
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)
def source_identity():
    files={p.name:sha(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.json','.bin','.sv','.txt')}
    return hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),files
def main():
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=['gate','full'])
    p.add_argument('--assets',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--case',default='parent_bf16')
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    plan=json.loads((HERE/'PLAN.json').read_text());cases={c['id']:c for c in plan['cases']}
    case=cases[a.case];assets=json.loads(Path(a.assets).read_text());spec=assets['spec']
    assert spec==json.loads((HERE/'ASSETS.json').read_text())
    assert importlib.metadata.version('transformers')=='4.51.3'
    assert sha(assets['raw'])==spec['test']['raw_sha256']
    assert sha(assets['overlay'])==spec['overlay']['sha256']
    for rel,expected in assets['model_files_sha256'].items():
        assert sha(Path(assets['model_dir'])/rel)==expected,rel
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from safetensors.torch import load_file
    from core import Config
    from scoring import score
    from test_hardware import gpu_gate
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    model=AutoModelForCausalLM.from_pretrained(assets['model_dir'],local_files_only=True,
        torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
    assert model.config.num_hidden_layers==36 and model.config.num_attention_heads==32 and model.config.num_key_value_heads==8
    tokenizer=AutoTokenizer.from_pretrained(assets['model_dir'],local_files_only=True)
    ids=torch.tensor(tokenizer(Path(assets['raw']).read_bytes().decode('utf-8'),add_special_tokens=False)['input_ids'])
    assert len(ids)==299078 and ids_sha256(ids.tolist())==spec['test']['token_ids_sha256_le_int64']
    source,source_files=source_identity()
    try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip()
    except (OSError,subprocess.CalledProcessError):commit='export without .git; source hashes are authoritative'
    identity=dict(source_sha256=source,assets_sha256=sha(a.assets),plan_sha256=sha(HERE/'PLAN.json'),
        python=platform.python_version(),versions={x:importlib.metadata.version(x) for x in ('torch','transformers','triton','numpy','safetensors')},
        gpu=torch.cuda.get_device_name(0),cuda=torch.version.cuda)
    def config(c):
        if c['mode']=='native':return None
        return Config(r=32,k=c['k'] or 2048,local=32,samples=c['samples'] or 64,burn=0,mode=c['mode'],screening=c['k'] is not None)
    def fingerprint_nonprojection():
        h=hashlib.sha256()
        for name,value in model.state_dict().items():
            if name not in expected_keys:
                h.update(name.encode());h.update(value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
        return h.hexdigest()
    expected_keys={f'model.layers.{i}.self_attn.{proj}_proj.weight' for i in range(36) for proj in ('q','k','v','o')}
    overlay_audit=None
    def apply_overlay():
        before=fingerprint_nonprojection()
        overlay=load_file(assets['overlay'])
        assert set(overlay)==expected_keys
        params=dict(model.named_parameters())
        with torch.no_grad():
            for name,v in overlay.items():
                assert v.dtype==torch.bfloat16 and v.shape==params[name].shape
                params[name].copy_(v)
        after=fingerprint_nonprojection();assert before==after
        return dict(sha256=sha(assets['overlay']),tensors=144,non_qkvo_before=before,non_qkvo_after=after,exact_original_ffn=True)
    if a.phase=='gate':
        gatepath=out/'GATE.json'
        if gatepath.exists():raise FileExistsError('Use a fresh output directory for a new gate')
        hw=gpu_gate()
        from sampler import thresholds
        fixture=torch.tensor([[1000.,999.96875,999.90625,999.,980.]],device='cuda')
        address,threshold=thresholds(fixture)
        assert address.tolist()==[[0,0,2,16,255]]
        assert threshold.tolist()==[[128,128,120,68,0]]
        # Same native operators/dtypes: wrapper identity is independent of FP32 reference quality.
        kwargs=dict(protocol='suffix',context=64,decode=4,examples=1,batch=1,capture=True)
        native=score(model,ids[:128],native=True,**kwargs)
        wrapped=score(model,ids[:128],cfg=None,native=False,**kwargs)
        assert native['logits_sha256']==wrapped['logits_sha256'],'native wrapper identity failed'
        overlay_audit=apply_overlay()
        n2=score(model,ids[:128],native=True,**kwargs)
        w2=score(model,ids[:128],cfg=None,native=False,**kwargs)
        assert n2['logits_sha256']==w2['logits_sha256'],'overlay wrapper identity failed'
        model_checks=[]
        for k in [128,256,None]:
            c=dict(mode='winner',k=k,samples=16)
            r=score(model,ids[:2100],cfg=config(c),seed=0,protocol='suffix',context=2044,decode=4,examples=1,batch=1)
            assert r['tokens_per_layer']==[4]*36
            model_checks.append(dict(k=k,scored_tokens=r['scored_tokens'],audit=r['audit']))
        # First real scored query has one valid key; it must execute the sampled path too.
        cold=score(model,ids[:8],cfg=config(dict(mode='winner',k=None,samples=16)),seed=0,protocol='full',batch=1)
        assert cold['tokens_per_layer']==[7]*36
        save(gatepath,dict(passed=True,identity=identity,git_commit=commit,source_files=source_files,
            hardware=hw,max_first_frontend=True,wrapper_identity=True,overlay_audit=overlay_audit,model_checks=model_checks,cold=cold))
        print(gatepath);return
    gate=json.loads((out/'GATE.json').read_text());assert gate['passed'] and gate['identity']==identity,'gate environment/source changed'
    if case['id']!='parent_bf16':
        ref=json.loads((out/'parent_bf16/RESULT.json').read_text())
        assert ref['complete'] and ref['identity']==identity and ref['case']['id']=='parent_bf16'
        assert abs(ref['mean_nll']-math.log(spec['anchors']['parent_native_ppl']))<=spec['anchors']['parent_mean_nll_tolerance'],'parent reference protocol mismatch'
    if case['overlay']:overlay_audit=apply_overlay()
    dest=out/case['id'];dest.mkdir(exist_ok=True)
    if (dest/'RESULT.json').exists():raise FileExistsError('Complete case exists; do not overwrite')
    records=[];parts=[];layer_counts=[0]*36;windows=full_window_plan(len(ids))
    for start in range(0,len(windows),32):
        path=dest/f'part_{start:03d}.json'
        if path.exists():
            r=json.loads(path.read_text());assert r['identity']==identity and r['case']==case,'stale part'
        else:
            r=score(model,ids,cfg=config(case),seed=case['seed'],protocol='full',batch=32,
                native=case['mode']=='native',plan_slice=(start,min(start+32,len(windows))),rng_stream=start)
            r.update(identity=identity,case=case);save(path,r)
        assert [{k:v for k,v in row.items() if k!='nll_sum'} for row in r['records']]==windows[start:start+32]
        records.extend(r['records']);layer_counts=[a+b for a,b in zip(layer_counts,r['tokens_per_layer'])]
        parts.append(dict(file=path.name,sha256=sha(path)))
        print(case['id'],start,r['perplexity'],flush=True)
    total=summarize_records(records);assert total['scored_tokens']==299077 and layer_counts==[299077]*36
    if case['id']=='parent_bf16':assert abs(total['mean_nll']-math.log(spec['anchors']['parent_native_ppl']))<=spec['anchors']['parent_mean_nll_tolerance']
    save(dest/'RESULT.json',dict(complete=True,identity=identity,git_commit=commit,source_files=source_files,case=case,
        overlay_audit=overlay_audit,original_ffn=True,training=False,protocol='full_cached_WT2_2048_stride1024',
        tokens_per_layer=layer_counts,records=records,parts=parts,**total))
    print(dest/'RESULT.json')
if __name__=='__main__':main()
