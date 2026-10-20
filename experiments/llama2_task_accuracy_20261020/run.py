"""Issue73 Slurm-only Llama2 task suite; immutable source and output separation."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO/'baselines/llama2_7b'))
from protocol import verify_identity, EXPECTED_SHAPE, CORPUS_SHA256, windows
from experiments.qwen_task_accuracy_20261019.task_data import (
    load_tasks, token_documents, metrics_for, harness_sources, sha, write)

TASKS = ('piqa', 'arc_easy')
REVISION = '01c7f73d771dfac7d292323805ebc428287df4f9'
TOKEN_SHA = 'd47afcd2762c6a3e70f50c5b7de0e4ccad565d812aee21772b7cd276b7b8626c'


def configurations(batch=4):
    rows = [dict(name='bf16', ffn='none', mode='sdpa', samples=128, seed=0)]
    rows += [dict(name=f'ffn_only_s{s}', ffn='b4_t32', mode='sdpa', samples=128, seed=s)
             for s in range(3)]
    rows += [dict(name=f'attention_S128_s{s}', ffn='none', mode='ising_only', samples=128, seed=s)
             for s in range(3)]
    rows += [dict(name=f'joint_S{n}_s{s}', ffn='b4_t32', mode='ising_only', samples=n, seed=s)
             for n in (128, 512) for s in range(3)]
    for row in rows:
        row.update(batch=batch, context=2048, burn=16., spacing=4., selection='fixed',
                   budget_blocks=8, target_fraction=.30)
    return rows


def sources():
    return {str(p.relative_to(REPO)): sha(p) for base in
            (REPO/'experiments', REPO/'baselines/llama2_7b')
            for p in sorted(base.rglob('*')) if p.is_file() and
            p.suffix in ('.py', '.json', '.sbatch') and '__pycache__' not in p.parts}


def outdir(a, gpu=False):
    if not os.environ.get('SLURM_JOB_ID') or (gpu and not os.environ.get('CUDA_VISIBLE_DEVICES')):
        raise RuntimeError('allocated Slurm job required')
    project = Path(a.project_root).resolve(strict=True)
    out = Path(a.output).resolve()
    if project != Path('/home/Hongjie_Zeng/projects/pbit-llama2-task-accuracy-20261020-issue73'):
        raise ValueError('verified personal project required')
    if project not in out.parents or REPO in out.parents:
        raise ValueError('output must be separate from frozen source')
    out.mkdir(parents=True, exist_ok=True)
    if len(a.code_commit) != 40 or os.environ.get('SOURCE_COMMIT') != a.code_commit:
        raise ValueError('exact source commit required')
    return out


def tasks(a):
    registered, identity = load_tasks(a.task_data)
    return {n: registered[n] for n in TASKS}, {n: identity[n] for n in TASKS}


def data(a):
    out = outdir(a)
    if (out/'TASK_DATA.json').exists():
        raise FileExistsError('never overwrite prepared requests')
    verified = verify_identity(Path(a.model), Path(a.identity_manifest))
    if verified['revision'] != REVISION or sha(a.data) != CORPUS_SHA256:
        raise ValueError('official model revision or WT2 bytes mismatch')
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model, local_files_only=True, use_fast=True)
    registered, identity = tasks(a)
    artifacts, stats = {}, {}
    for name, task in registered.items():
        docs = token_documents(task, name, tok)
        path = out/'tokenized'/f'{name}.jsonl'
        path.parent.mkdir(exist_ok=True)
        with path.open('x', encoding='utf-8', newline='\n') as f:
            for d in docs:
                f.write(json.dumps(d, separators=(',', ':'))+'\n')
        artifacts[name] = dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)
        stats[name] = dict(documents=len(docs), selection='full split',
            answer_targets=sum(len(c) for d in docs for c in d['choices_ids']),
            max_scored_context=max(len(d['context_ids'])+max(map(len,d['choices_ids']))-1 for d in docs),
            selected_doc_ids_sha256=hashlib.sha256(json.dumps([d['doc_id'] for d in docs],separators=(',',':')).encode()).hexdigest())
    write(out/'identity.json', verified)
    write(out/'TASK_DATA.json', dict(code_commit=a.code_commit, tasks=identity, tokenized=artifacts,
        statistics=stats, source_sha256=sources(), harness_sources=harness_sources(),
        harness_version=importlib.metadata.version('lm_eval'), num_fewshot=0,
        add_bos_token=False, chat_template=False, protocol='same explicit no-extra-BOS Harness pair encoding as Issue59'))
    print(json.dumps(stats), flush=True)


def read_docs(out, name):
    entry = json.loads((out/'TASK_DATA.json').read_text())['tokenized'][name]
    if sha(entry['path']) != entry['sha256']:
        raise ValueError('request bytes changed')
    return list(map(json.loads, Path(entry['path']).read_text().splitlines()))


def load_model(a, seed=0):
    import torch
    import transformers
    from transformers import AutoModelForCausalLM
    if transformers.__version__ != '4.45.2':
        raise RuntimeError('inspected Transformers 4.45.2 required')
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model = AutoModelForCausalLM.from_pretrained(a.model, local_files_only=True,
        trust_remote_code=False, use_safetensors=True, low_cpu_mem_usage=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa').eval().to('cuda')
    for key, expected in EXPECTED_SHAPE.items():
        if getattr(model.config, key) != expected:
            raise ValueError('unexpected Llama2 shape: '+key)
    return model


def score_case(a, cfg, docs, registered, path):
    import torch
    import transformers
    from .cached_score import evaluate_tasks
    path = Path(path)
    progress_path = path.with_suffix('.progress.jsonl')
    if path.exists() or progress_path.exists():
        raise FileExistsError('never overwrite executed case')
    path.parent.mkdir(parents=True, exist_ok=True)
    model = load_model(a, cfg['seed'])
    torch.cuda.reset_peak_memory_stats()
    rows = {d['id']: d for d in docs}
    completed = 0
    def progress(item):
        nonlocal completed
        with progress_path.open('a',encoding='utf-8',newline='\n') as f:
            for r in item['documents']:
                row = dict(rows[r['id']], **r)
                evidence = dict(id=r['id'],doc_id=row['doc_id'],task=row['task'],
                    choices=r['choices'], metrics=metrics_for(registered,row))
                f.write(json.dumps(evidence,separators=(',',':'))+'\n')
                completed += 1
        print(json.dumps(dict(event='progress',case=cfg['name'],documents=completed)),flush=True)
    result = evaluate_tasks(model, docs, cfg, None, progress=progress)
    scored=[]
    for r in result.pop('documents'):
        row=dict(rows[r['id']], **r)
        scored.append(dict(id=r['id'],doc_id=row['doc_id'],task=row['task'],
                           choices=r['choices'],metrics=metrics_for(registered,row)))
    if len(scored)!=len(docs) or {d['id'] for d in scored}!=set(rows):
        raise ValueError('missing or duplicate task results')
    docpath=path.with_suffix('.documents.jsonl')
    with docpath.open('x',encoding='utf-8',newline='\n') as f:
        for r in sorted(scored,key=lambda x:x['doc_id']):
            f.write(json.dumps(r,separators=(',',':'))+'\n')
    result.update(status='completed', configuration=cfg, task=docs[0]['task'],
        n_documents=len(scored), code_commit=a.code_commit,
        metrics={k:sum(r['metrics'][k] for r in scored)/len(scored) for k in ('acc','acc_norm')},
        configuration_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        document_artifact=dict(path=str(docpath),sha256=sha(docpath),bytes=docpath.stat().st_size),
        task_data_sha256=sha(Path(a.output)/'TASK_DATA.json'),identity_sha256=sha(Path(a.output)/'identity.json'),
        slurm_job_id=os.environ['SLURM_JOB_ID'],command=[sys.executable,*sys.argv],
        environment=dict(torch=torch.__version__,transformers=transformers.__version__,
                         lm_eval=importlib.metadata.version('lm_eval'),python=sys.version,
                         cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),tf32=False),
        peak_allocated_bytes=torch.cuda.max_memory_allocated())
    write(path,result)
    del model
    torch.cuda.empty_cache()
    return result


def naive_cached(model, docs, batch):
    """Independent original-model prefix recomputation; no branch restoration."""
    import torch
    from .cached_score import document_batches
    result={}
    with torch.inference_mode():
        for rows in document_batches(docs,batch):
            context=torch.tensor([d['context_ids'] for d in rows],device='cuda')
            for j in range(len(rows[0]['choices_ids'])):
                cache=model.model(input_ids=context[:,:-1],use_cache=True).past_key_values
                answers=[d['choices_ids'][j] for d in rows]
                total=torch.zeros(len(rows),device='cuda',dtype=torch.float64)
                greedy=torch.ones(len(rows),device='cuda',dtype=torch.bool)
                for step in range(max(map(len,answers))):
                    x=context[:,-1:] if step==0 else torch.tensor(
                        [[c[step-1] if step-1<len(c) else 0] for c in answers],device='cuda')
                    output=model.model(input_ids=x,past_key_values=cache,use_cache=True)
                    cache=output.past_key_values
                    logits=model.lm_head(output.last_hidden_state[:,-1]).float()
                    target=torch.tensor([c[step] if step<len(c) else 0 for c in answers],device='cuda')
                    active=torch.tensor([step<len(c) for c in answers],device='cuda')
                    ll=logits.log_softmax(-1).gather(-1,target[:,None]).squeeze(-1).double()
                    total+=torch.where(active,ll,0.)
                    greedy&=(~active)|(logits.argmax(-1)==target)
                for d,ll,exact in zip(rows,total.tolist(),greedy.tolist()):
                    result.setdefault(d['id'],[]).append(dict(logprob=ll,is_greedy=exact))
    return result


def prepare(a):
    out=outdir(a,gpu=True)
    meta=json.loads((out/'TASK_DATA.json').read_text())
    if meta['source_sha256']!=sources() or meta['code_commit']!=a.code_commit:
        raise ValueError('frozen source mismatch')
    import torch
    from transformers import AutoTokenizer
    from evaluate import evaluate_window
    verified=verify_identity(Path(a.model),Path(a.identity_manifest))
    if verified!=json.loads((out/'identity.json').read_text()):
        raise ValueError('model identity changed')
    model=load_model(a)
    tok=AutoTokenizer.from_pretrained(a.model,local_files_only=True,use_fast=True)
    if sha(a.data)!=CORPUS_SHA256:
        raise ValueError('WT2 raw bytes changed')
    ids=tok(Path(a.data).read_text(),add_special_tokens=False,return_tensors='pt').input_ids
    if sha_ids(ids)!=TOKEN_SHA:
        raise ValueError('WT2 tokenization changed')
    nll=0.;count=0
    with torch.inference_mode():
        for item in windows(ids.shape[1],2048,512):
            value,n=evaluate_window(model,ids,item,torch,torch.nn.functional)
            nll+=value;count+=n
    ppl=math.exp(nll/count)
    passed=count==335686 and abs(ppl-4.979502845218782)<1e-8
    write(out/'fresh_bf16_full_wt2.json',dict(scored_tokens=count,nll=nll,ppl=ppl,passed=passed,
        data_sha256=CORPUS_SHA256,token_sha256=TOKEN_SHA,code_commit=a.code_commit))
    if not passed:raise RuntimeError('fresh unchanged BF16 WT2 gate failed')
    registered,_=tasks(a)
    pilot={n:sorted(read_docs(out,n),key=lambda d:(-len(d['context_ids']),d['id']))[:4] for n in TASKS}
    reference={n:naive_cached(model,docs,a.batch) for n,docs in pilot.items()}
    write(out/'independent_cached_reference.json',reference)
    del model;torch.cuda.empty_cache()
    gates=[]
    for name,docs in pilot.items():
        original=score_case(a,configurations(a.batch)[0],docs,registered,out/'pilot'/f'{name}_bf16.json')
        cached=list(map(json.loads,Path(original['document_artifact']['path']).read_text().splitlines()))
        for r in cached:
            other=reference[name][r['id']]
            dif=max(abs(x['logprob']-y['logprob']) for x,y in zip(r['choices'],other))
            same=all(x['is_greedy']==y['is_greedy'] for x,y in zip(r['choices'],other))
            gates.append(dict(id=r['id'],max_sum_logprob_error=dif,greedy_equal=same))
            if dif>1e-5 or not same:raise RuntimeError('cached branch/target alignment failed')
        # Matching BF16 SDPA operators, not an FP32 explicit-softmax surrogate.
        diagnostic=dict(configurations(a.batch)[0],name='digital_sdpa',mode='digital_sdpa')
        wrapped=score_case(a,diagnostic,docs,registered,out/'pilot'/f'{name}_digital_sdpa.json')
        if sha(wrapped['document_artifact']['path'])!=sha(original['document_artifact']['path']):
            raise RuntimeError('Llama wrapper changed original BF16 task logits/scores')
    # Real 7B allocation and finite sampler pilot, longest selected prompts.
    for index in (1,4,7,10):
        cfg=configurations(a.batch)[index]
        score_case(a,cfg,pilot['arc_easy'],registered,out/'pilot'/f'arc_easy_{cfg["name"]}.json')
    write(out/'BF16_TASK_BRIDGE.json',dict(passed=True,records=gates,tolerance=1e-5,
        digital_sdpa='per-choice document artifact byte-identical to original BF16 cached scoring'))
    suite=dict(tasks=TASKS,configurations=configurations(a.batch),count=26,
               scope='32 FFNs prefill+decode; attention replacement all 32 scored q_len=1 layers; original attention in multi-token prefill; no K screening')
    write(out/'suite.json',suite)
    write(out/'READY.json',dict(code_commit=a.code_commit,source_sha256=sources(),
        task_data_sha256=sha(out/'TASK_DATA.json'),identity_sha256=sha(out/'identity.json'),
        suite_sha256=sha(out/'suite.json'),baseline_gate_passed=True,bf16_task_bridge_passed=True))
    print('READY',flush=True)


def sha_ids(ids):
    return hashlib.sha256(ids.numpy().astype('<i8',copy=False).tobytes()).hexdigest()


def worker(a):
    out=outdir(a,gpu=True)
    ready=json.loads((out/'READY.json').read_text())
    if ready['code_commit']!=a.code_commit or ready['source_sha256']!=sources() or not ready['baseline_gate_passed'] or not ready['bf16_task_bridge_passed']:
        raise ValueError('strict preparation not passed')
    for key,f in [('task_data_sha256','TASK_DATA.json'),('identity_sha256','identity.json'),('suite_sha256','suite.json')]:
        if ready[key]!=sha(out/f):raise ValueError('prepared artifact changed: '+f)
    if verify_identity(Path(a.model),Path(a.identity_manifest))!=json.loads((out/'identity.json').read_text()):
        raise ValueError('model changed')
    registered,identity=tasks(a)
    meta=json.loads((out/'TASK_DATA.json').read_text())
    if identity!=meta['tasks'] or meta['harness_sources']!=harness_sources():
        raise ValueError('task definitions changed')
    suite=json.loads((out/'suite.json').read_text())
    if not 0<=a.index<suite['count']:raise ValueError('case index out of range')
    name=suite['tasks'][a.index//len(suite['configurations'])]
    cfg=suite['configurations'][a.index%len(suite['configurations'])]
    score_case(a,cfg,read_docs(out,name),registered,out/'full'/f'{name}_{cfg["name"]}.json')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['data','prepare','worker'])
    for key in ('model','identity-manifest','data','task-data','project-root','output','code-commit'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--batch',type=int,default=4)
    p.add_argument('--index',type=int,default=0)
    a=p.parse_args()
    if not 1<=a.batch<=4:p.error('memory-bounded batch 1..4 required')
    globals()[a.action](a)


if __name__=='__main__':main()
