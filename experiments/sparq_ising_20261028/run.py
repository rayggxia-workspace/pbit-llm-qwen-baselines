"""Slurm-only Qwen3 attention-only matched PPL, immutable per-case receipts."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import torch
from .core import Config
from .scoring import score
from .test_core import gpu_tests
from .vendor.support import sha256,verify_files,check_config
from .vendor.plans import ids_sha256,full_window_plan,summarize_records


def seal(path,value):
    path=Path(path)
    if path.exists():raise FileExistsError(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_bytes(data);tmp.replace(path)
    path.with_suffix(path.suffix+'.sha256').write_text(hashlib.sha256(data).hexdigest()+'\n',encoding='ascii')


def read_sealed(path):
    path=Path(path)
    if not path.exists():return None
    if sha256(path)!=path.with_suffix(path.suffix+'.sha256').read_text().strip():raise ValueError('sealed result changed')
    return json.loads(path.read_bytes())


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--phase',choices=['preflight','short','full'],required=True);p.add_argument('--seed',type=int,default=0);p.add_argument('--samples',type=int,default=128)
    a=p.parse_args()
    root=Path(a.root).resolve(strict=True)
    assert root==Path('/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028') and root.stat().st_uid==os.getuid()
    assert os.environ.get('SLURM_JOB_ID') and torch.cuda.device_count()==1
    source=Path(__file__).resolve().parents[2]
    manifest=json.loads((source/'execution.json').read_bytes())
    for rel,sha in manifest['files_sha256'].items():assert sha256(source/rel)==sha,rel
    config=json.loads((Path(__file__).parent/'config.json').read_bytes())
    prep_path=Path(config['prepared']);prep=json.loads(prep_path.read_bytes())
    assert prep['model']==config['model'];verify_files(prep)
    for name,expected in config['data_sha256'].items():assert sha256(Path(config['data_root'])/name)==expected
    assert importlib.metadata.version('transformers')=='4.51.3'
    from transformers import AutoModelForCausalLM,AutoTokenizer
    torch.set_num_threads(4);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False)
    ids=tok((Path(config['data_root'])/'wiki.test.raw').read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    out=root/'results'/manifest['commit'][:12]/a.phase/(f'seed{a.seed}' if a.phase!='full' else f'seed{a.seed}_S{a.samples}')
    out.mkdir(parents=True,exist_ok=True)
    provenance=dict(source=manifest,config=config,prepared_sha256=sha256(prep_path),token_ids_sha256=ids_sha256(ids.tolist()),
        token_count=len(ids),model_files=prep['files'],environment={n:importlib.metadata.version(n) for n in ['torch','transformers','triton','tokenizers']},
        command=sys.argv,job=os.environ['SLURM_JOB_ID'],gpu=torch.cuda.get_device_name(),gpu_uuid=str(torch.cuda.get_device_properties(0).uuid),
        boundary='posttrained Qwen3-4B, original BF16 FFN/QKV/Wo/norms, native dense prefill, every scored predictor patched through all36layers',
        sampler='PR163/Issue78 winner-hold, ideal FP32 sigmoid/independent Philox, argmax initialization, burn32, spacing1; no second PV draw',
        tokenizer_protocol='raw teacher-forced WT2; no chat template, no generated thinking, no BOS')
    if not (out/'provenance.json').exists():seal(out/'provenance.json',provenance)
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
    check_config(model.config,config['model'])
    immutable=[(x,x._version,x.data_ptr()) for x in model.parameters()]
    def run_case(name,cfg,**options):
        path=out/(name+'.json')
        old=read_sealed(path)
        if old is not None:return old
        print('START',name,flush=True);torch.cuda.reset_peak_memory_stats()
        result=score(model,ids,cfg,seed=a.seed,**options)
        assert all(x._version==version and x.data_ptr()==ptr for x,version,ptr in immutable)
        result.update(case=name,seed=a.seed,config=asdict(cfg) if cfg else None,peak_memory_bytes=torch.cuda.max_memory_allocated(),provenance_sha256=sha256(out/'provenance.json'))
        seal(path,result);print('COMPLETE',name,result['perplexity'],result['seconds'],flush=True)
        return result
    if a.phase=='preflight':
        checks=gpu_tests()
        opt=dict(context=256,decode=16,examples=2,batch=2,capture=True)
        native=run_case('native_gate',None,native=True,**opt)
        dense=run_case('dense_gate',None,**opt)
        assert native['logits_sha256']==dense['logits_sha256'] and native['nll_sum']==dense['nll_sum'],'native wrapper mismatch'
        run_case('sparq_gate',Config(mode='exact'),**opt)
        for s in (32,128,512):run_case(f'winner_S{s}',Config(samples=s),**opt)
        run_case('iid_S128',Config(mode='iid'),**opt)
        # Production context/batch memory and sampler check uses the same 8 windows.
        run_case('production_memory',Config(),context=2048,decode=2,examples=8,batch=8)
        seal(out/'GATE.json',dict(passed=True,gpu_core=checks,native_wrapper_bitwise=True,all_layer_targets=True))
    elif a.phase=='short':
        gate=root/'results'/manifest['commit'][:12]/'preflight/seed0/GATE.json'
        assert read_sealed(gate)['passed']
        opt=dict(context=2048,decode=128,examples=8,batch=8)
        run_case('bf16',None,**opt)
        run_case('sparq_exact',Config(mode='exact'),**opt)
        for s in (32,128,512):run_case(f'winner_S{s}',Config(samples=s),**opt)
        run_case('iid_S128',Config(mode='iid'),**opt)
    else:
        gate=root/'results'/manifest['commit'][:12]/'preflight/seed0/GATE.json'
        assert read_sealed(gate)['passed']
        plan=full_window_plan(len(ids));chunk=16
        cases=[('bf16',None),('sparq_exact',Config(mode='exact')),(f'winner_S{a.samples}',Config(samples=a.samples))]
        for start in range(0,len(plan),chunk):
            for name,cfg in cases:
                run_case(f'{name}_part{start:04d}',cfg,protocol='full',batch=16,plan_slice=(start,min(start+chunk,len(plan))))
        for name,cfg in cases:
            parts=[read_sealed(out/f'{name}_part{start:04d}.json') for start in range(0,len(plan),chunk)]
            rows=[row for part in parts for row in part['records']]
            assert len(rows)==len(plan) and all(all(row[k]==planned[k] for k in planned) for row,planned in zip(rows,plan))
            assert sum(row['scored_tokens'] for row in rows)==len(ids)-1
            if not (out/(name+'.json')).exists():seal(out/(name+'.json'),dict(**summarize_records(rows),records=rows,scope='full_WT2_2048_1024',complete=True,seed=a.seed,config=asdict(cfg) if cfg else None,seconds=sum(part['seconds'] for part in parts)))
    seal(out/'complete.json',dict(status='completed',phase=a.phase,files={p.name:sha256(p) for p in out.glob('*.json') if p.name!='complete.json'}))


if __name__=='__main__':main()
