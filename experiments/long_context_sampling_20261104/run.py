"""Small long-context suffix PPL. All compute is Slurm-submitted, no training."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from .contract import common_plan,cases,ids_sha,CONTEXTS,SEEDS,lut_reference


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def seal(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
    with path.open('xb') as f:f.write(raw)
    with path.with_suffix(path.suffix+'.sha256').open('x') as f:f.write(hashlib.sha256(raw).hexdigest()+'\n')


def read(path):
    path=Path(path)
    assert sha(path)==path.with_suffix(path.suffix+'.sha256').read_text().strip()
    return json.loads(path.read_bytes())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True)
    ap.add_argument('--phase',choices=('cpu','gate','ppl'),required=True)
    ap.add_argument('--index',type=int,default=0)
    a=ap.parse_args();root=Path(a.root).resolve(strict=True)
    assert root.parent==Path.home()/'projects' and root.stat().st_uid==os.getuid()
    assert os.environ.get('SLURM_JOB_ID')
    source=Path(__file__).resolve().parents[2]
    manifest=json.loads((source/'execution.json').read_bytes())
    for rel,digest in manifest['files_sha256'].items():assert sha(source/rel)==digest,rel
    runtime=json.loads((root/'runtime.json').read_bytes())
    from .vendor.sparq_ising.vendor.support import verify_files,check_config
    prepared=Path(runtime['prepared']);prep=json.loads(prepared.read_bytes())
    verify_files(prep)
    assert prep['model']==runtime['model']
    for rel,digest in runtime['data_sha256'].items():assert sha(Path(runtime['data_root'])/rel)==digest
    output=root/'results'/manifest['source_id'];output.mkdir(parents=True,exist_ok=True)
    if a.phase=='cpu':
        suite=unittest.defaultTestLoader.loadTestsFromName(__package__+'.test_contract')
        result=unittest.TextTestRunner(verbosity=2).run(suite);assert result.wasSuccessful()
        import torch
        assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not torch.cuda.is_initialized()
        seal(output/'CPU_GATE.json',dict(status='completed',passed=True,tests=result.testsRun,
             source_manifest_sha256=sha(source/'execution.json'),prepared_sha256=sha(prepared),
             runtime_sha256=sha(root/'runtime.json'),cpu_only=True))
        return
    assert read(output/'CPU_GATE.json')['passed']
    import torch
    from .vendor.sparq_ising import scoring
    from .vendor.sparq_ising.core import Config
    from .frontend import Frontend,replay_gate
    assert torch.cuda.device_count()==1
    assert importlib.metadata.version('transformers')=='4.51.3'
    torch.set_num_threads(4);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    from transformers import AutoTokenizer,AutoModelForCausalLM
    tokenizer=AutoTokenizer.from_pretrained(prep['local_path'],local_files_only=True,trust_remote_code=False)
    ids=tokenizer((Path(runtime['data_root'])/'wiki.test.raw').read_bytes().decode(),
                  return_tensors='pt',add_special_tokens=False).input_ids[0]
    assert ids_sha(ids.tolist())==prep['test_token_ids_sha256_le_int64']
    model=AutoModelForCausalLM.from_pretrained(prep['local_path'],local_files_only=True,
           trust_remote_code=False,torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
    check_config(model.config,runtime['model'])
    assert model.config.max_position_embeddings>=32768+32
    immutable=[(p,p._version,p.data_ptr()) for p in model.parameters()]
    table=torch.tensor(lut_reference(),device='cuda',dtype=torch.long)
    def score(cfg,context,seed,decode=32,examples=4,capture=False,native=False):
        plan=common_plan(len(ids),context,examples=examples,decode=decode)
        with patch.object(scoring,'suffix_plan',lambda *args,**kwargs:plan):
            with Frontend(table) as front:
                result=scoring.score(model,ids,cfg,seed=seed,context=context,decode=decode,
                                     examples=examples,batch=1,capture=capture,native=native)
                result['numeric']=front.report()
        assert all(p._version==v and p.data_ptr()==ptr for p,v,ptr in immutable)
        result.update(status='completed',context_start=context,context_max=context+decode-1,
                      original_ffn=True,original_projections=True,
                      chat_template=False,thinking=False,
                      scoring_scope='matched short suffix at long history; not full WT2; accurate prefill')
        return result
    if a.phase=='gate':
        replay=replay_gate(table)
        gates=[]
        for n,k in ((8192,256),(32768,512)):
            native=score(None,n,0,decode=2,examples=1,capture=True,native=True)
            wrapper=score(None,n,0,decode=2,examples=1,capture=True)
            assert native['logits_sha256']==wrapper['logits_sha256']
            assert native['nll_sum']==wrapper['nll_sum']
            probe=score(Config(k=k,samples=32,burn=0),n,0,decode=2,examples=1)
            assert probe['numeric']['probability_calls']==36*2
            assert all(row['sampled_head_rows']==64 for row in probe['audit']['layers'].values())
            gates.append(dict(context=n,native_wrapper_bitwise=True,
                              probe=probe,native=native,wrapper=wrapper))
            print('GATE_CONTEXT_DONE',n,flush=True)
        seal(output/'GPU_GATE.json',dict(status='completed',passed=True,replay=replay,contexts=gates,
             source_manifest_sha256=sha(source/'execution.json'),runtime_sha256=sha(root/'runtime.json')))
        return
    assert read(output/'GPU_GATE.json')['passed']
    assert 0<=a.index<6
    context=CONTEXTS[a.index//3];seed=SEEDS[a.index%3]
    dest=output/f'N{context}'/f'seed{seed}';dest.mkdir(parents=True,exist_ok=True)
    provenance=dict(status='prepared',source_manifest=manifest,source_manifest_sha256=sha(source/'execution.json'),
        runtime_sha256=sha(root/'runtime.json'),prepared_sha256=sha(prepared),model=runtime['model'],
        model_files=prep['files'],data_sha256=runtime['data_sha256'],token_ids_sha256=ids_sha(ids.tolist()),
        plan=common_plan(len(ids),context),command=sys.argv,job=os.environ['SLURM_JOB_ID'],
        gpu=torch.cuda.get_device_name(),versions={n:importlib.metadata.version(n) for n in ('torch','transformers','triton','tokenizers')},
        seed=seed,context=context,original_ffn=True,chat_template=False,thinking=False,
        numerical_contract='FP32 reference SparQ and exact candidate QK; S12F4 integer max gap -> U8F4 floor-P8; slot0/burn0',
        limitations=['128 targets; four fixed WT2 suffixes, not full WT2 or retrieval benchmark',
                     'posttrained original BF16 weights, no trained stochastic FFN included',
                     'independent Philox, no physical/shared-GF bittrue or ASIC PPA',
                     'same target positions across lengths, no paired stochastic prefixes across S',
                     'accurate multi-token prefill; only scored single-token queries replace all36 attention layers'])
    if not (dest/'PROVENANCE.json').exists():seal(dest/'PROVENANCE.json',provenance)
    for case in cases(context,seed):
        path=dest/(case['name']+'.json')
        if path.exists():read(path);continue
        print('START',context,seed,case['name'],flush=True)
        torch.cuda.reset_peak_memory_stats()
        cfg=None if case['k'] is None else Config(k=case['k'],samples=case['s'] or 128,burn=0,mode=case['mode'])
        result=score(cfg,context,seed)
        result.update(case=case,seed=seed,peak_memory_bytes=torch.cuda.max_memory_allocated(),
                      provenance_sha256=sha(dest/'PROVENANCE.json'))
        seal(path,result)
        print('DONE',context,seed,case['name'],result['perplexity'],result['seconds'],flush=True)
    seal(dest/'COMPLETE.json',dict(status='completed',context=context,seed=seed,
         cases=len(cases(context,seed)),files_sha256={p.name:sha(p) for p in dest.glob('*.json') if p.name!='COMPLETE.json'}))


if __name__=='__main__':main()
