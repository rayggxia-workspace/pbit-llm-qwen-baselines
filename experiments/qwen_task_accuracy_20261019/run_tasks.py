"""Slurm-only Qwen MC accuracy: unchanged official tasks, cached sampled model."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
import random
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO))
from experiments.qwen_joint_stratified_attention_20261019 import run_joint as joint
from experiments.qwen_task_accuracy_20261019.task_data import (
    TASKS, harness_sources, load_tasks, metrics_for, sha, token_documents, write)


def configurations():
    rows = [dict(name='bf16', ffn='none', mode='sdpa', samples=128, seed=0)]
    rows += [dict(name=f'ffn_only_s{s}', ffn='b4_t32', mode='sdpa', samples=128, seed=s)
             for s in (0, 1, 2)]
    rows += [dict(name=f'joint_S{n}_s{s}', ffn='b4_t32', mode='screen_ising', samples=n, seed=s)
             for n in (64, 128, 512) for s in (0, 1, 2)]
    for r in rows:
        r.update(batch=16, burn=16., spacing=4., selection='fixed', budget_blocks=8,
                 target_fraction=.30, context=2048)
    return rows


def sources():
    areas = [ROOT, REPO/'experiments/qwen_joint_stratified_attention_20261019',
             REPO/'experiments/qwen_multiscale_stratified_20261019',
             REPO/'experiments/qwen_fixedw_multiscale_20261019',
             REPO/'experiments/qwen_dual_range_20261018',
             REPO/'experiments/qwen_dual_iid_exact_20261018']
    return {str(p.relative_to(REPO)): sha(p) for area in areas for p in sorted(area.rglob('*'))
            if p.is_file() and p.suffix in ('.py', '.json', '.md', '.sbatch') and '__pycache__' not in p.parts}


def outdir(a, gpu=True):
    if not os.environ.get('SLURM_JOB_ID') or (gpu and not os.environ.get('CUDA_VISIBLE_DEVICES')):
        raise RuntimeError('Use an allocated Slurm job')
    project = Path(a.project_root).resolve(strict=True)
    out = Path(a.output).resolve()
    if Path.home() != Path('/home/Hongjie_Zeng') or project.parent != Path('/home/Hongjie_Zeng/projects'):
        raise ValueError('Verified personal project required')
    if project not in out.parents or REPO in out.parents:
        raise ValueError('Output must be separate from immutable source snapshot')
    out.mkdir(parents=True, exist_ok=True)
    return out


def data(a):
    out = outdir(a, gpu=False)
    if (out/'TASK_DATA.json').exists():
        raise FileExistsError('Preparation already exists')
    import transformers
    tokenizer = transformers.AutoTokenizer.from_pretrained(a.model, local_files_only=True)
    tasks, identity = load_tasks(a.task_data)
    rows, statistics, artifacts = {}, {}, {}
    for name, task in tasks.items():
        docs = token_documents(task, name, tokenizer)
        total_documents = len(docs)
        if name == 'hellaswag':
            # Fixed before any inference, not selected using baseline outcomes.
            chosen = set(random.Random(20261019).sample(range(len(docs)), 1000))
            docs = [d for i, d in enumerate(docs) if i in chosen]
        rows[name] = docs
        path = out/'tokenized'/f'{name}.jsonl'
        path.parent.mkdir(exist_ok=True)
        with path.open('x', encoding='utf-8', newline='\n') as f:
            for d in docs:
                f.write(json.dumps(d, separators=(',', ':'))+'\n')
        contexts = [len(d['context_ids']) for d in docs]
        targets = [len(c) for d in docs for c in d['choices_ids']]
        statistics[name] = dict(documents=len(docs), full_split_documents=total_documents,
            selection='full split' if name != 'hellaswag' else '1000 without replacement, Python Random(20261019), before inference',
            selected_doc_ids_sha256=hashlib.sha256(json.dumps([d['doc_id'] for d in docs],separators=(',', ':')).encode()).hexdigest(),
            requests=len(targets), answer_targets=sum(targets),
            prompt_min=min(contexts), prompt_max=max(contexts), prompt_mean=sum(contexts)/len(contexts),
            answer_max=max(targets), answer_mean=sum(targets)/len(targets),
            prompts_over_512=sum(x > 512 for x in contexts),
            any_scored_length_over_512=sum(len(d['context_ids']) + max(map(len, d['choices_ids'])) - 1 > 512 for d in docs),
            max_scored_context=max(len(d['context_ids']) + max(map(len, d['choices_ids'])) - 1 for d in docs))
        artifacts[name] = dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))
    write(out/'TASK_DATA.json', dict(code_commit=a.code_commit, tasks=identity, statistics=statistics,
        tokenized=artifacts, harness_version=importlib.metadata.version('lm_eval'),
        harness_sources=harness_sources(), num_fewshot=0, chat_template=False,
        metrics='Official task.process_results; acc_norm normalizes by original choice character length, not token count',
        source_sha256=sources(), created_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(statistics), flush=True)


def read_docs(out, name):
    meta = json.loads((out/'TASK_DATA.json').read_text())
    entry = meta['tokenized'][name]
    if sha(entry['path']) != entry['sha256']:
        raise ValueError('Tokenized task changed')
    return [json.loads(line) for line in Path(entry['path']).read_text().splitlines()]


def vector_reference(model, docs, tasks):
    """Diagnostic only: unchanged unpadded multi-token BF16 scoring."""
    import torch
    rows = []
    with torch.inference_mode():
        for d in docs:
            choices = []
            for answer in d['choices_ids']:
                tokens = torch.tensor([d['context_ids'] + answer],device='cuda',dtype=torch.long)
                h = model.model(input_ids=tokens[:, :-1],use_cache=False).last_hidden_state[:, -len(answer):]
                lp = model.lm_head(h).float().log_softmax(-1)
                target = tokens[:, -len(answer):]
                selected = lp.gather(-1,target[...,None]).squeeze(-1)
                choices.append(dict(logprob=float(selected.double().sum()),
                    is_greedy=bool((lp.argmax(-1)==target).all()),tokens=len(answer)))
            row = dict(d,choices=choices)
            rows.append(dict(id=d['id'],choices=choices,metrics=metrics_for(tasks,row)))
    return rows


def score_case(a, cfg, docs, tasks, path):
    import torch
    import transformers
    from experiments.qwen_task_accuracy_20261019.cached_score import evaluate_tasks
    torch.manual_seed(cfg['seed'])
    tokenizer, model = joint.load_model(a)
    torch.cuda.reset_peak_memory_stats()
    path = Path(path)
    if path.exists() or path.with_suffix('.progress.jsonl').exists():
        raise FileExistsError('Never overwrite an executed task case')
    path.parent.mkdir(parents=True, exist_ok=True)
    row_map = {d['id']: d for d in docs}
    progress_file = path.with_suffix('.progress.jsonl')
    def progress(items, *args, **kwargs):
        # Stable per-doc evidence survives cancellation without claiming a full result.
        if isinstance(items, dict):
            items = items.get('documents', items.get('rows', []))
        with progress_file.open('a', encoding='utf-8', newline='\n') as f:
            for row in items:
                row = dict(row_map[row['id']], **row)
                row['metrics'] = metrics_for(tasks, row)
                evidence = {k: row[k] for k in ('id', 'task', 'doc_id', 'choices', 'metrics')}
                f.write(json.dumps(evidence, separators=(',', ':'))+'\n')
        print(json.dumps(dict(event='progress', case=cfg['name'], documents=sum(1 for _ in progress_file.open()))), flush=True)
    result = evaluate_tasks(model, docs, cfg, joint.calibration(a), progress=progress)
    scored = []
    for row in result.pop('documents'):
        enriched = dict(row_map[row['id']], **row)
        scored.append(dict(id=row['id'], task=enriched['task'], doc_id=enriched['doc_id'],
                           choices=row['choices'], metrics=metrics_for(tasks, enriched)))
    if len(scored) != len(docs) or {x['id'] for x in scored} != set(row_map):
        raise RuntimeError('Missing or repeated task documents')
    result.update(configuration=cfg, code_commit=a.code_commit, status='completed',
        task=docs[0]['task'], n_documents=len(scored),
        metrics={k:sum(r['metrics'][k] for r in scored)/len(scored) for k in ('acc', 'acc_norm')},
        configuration_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        task_data_sha256=sha(Path(a.output)/'TASK_DATA.json'), slurm_job_id=os.environ['SLURM_JOB_ID'],
        environment=dict(torch=torch.__version__, transformers=transformers.__version__,
                         lm_eval=importlib.metadata.version('lm_eval'), cuda=torch.version.cuda,
                         gpu=torch.cuda.get_device_name(), python=sys.version),
        peak_allocated_bytes=torch.cuda.max_memory_allocated(), command=sys.argv)
    samples_path = path.with_suffix('.documents.jsonl')
    with samples_path.open('x',encoding='utf-8',newline='\n') as f:
        for row in sorted(scored,key=lambda x:x['doc_id']):
            f.write(json.dumps(row,separators=(',', ':'))+'\n')
    result['document_artifact'] = dict(path=str(samples_path), sha256=sha(samples_path), bytes=samples_path.stat().st_size)
    write(path, result)
    del model
    torch.cuda.empty_cache()
    return result


def prepare(a):
    out = outdir(a)
    meta = json.loads((out/'TASK_DATA.json').read_text())
    if meta['code_commit'] != a.code_commit or meta['source_sha256'] != sources() or meta['harness_sources'] != harness_sources():
        raise ValueError('Source or task definitions changed')
    if (out/'READY.json').exists():
        raise FileExistsError('Preparation already finished')
    identity = joint.verify(a.model, a.data, out/'identity.json')
    tokenizer, model = joint.load_model(a)
    ids = joint.test_ids(a, tokenizer, identity)
    baseline = joint.score(model, ids, True)
    passed = baseline['scored_tokens'] == 299077 and abs(baseline['perplexity'] - 11.652735047455899) < 1e-8
    write(out/'fresh_bf16_full_wt2.json', dict(baseline, baseline_gate_passed=passed))
    if not passed:
        raise RuntimeError('Unchanged BF16 reference failed')
    tasks, _ = load_tasks(a.task_data)
    pilot_docs = {name: sorted(read_docs(out, name), key=lambda x: (-len(x['context_ids']), x['id']))[:4]
                  for name in TASKS}
    vector = {name:vector_reference(model,docs,tasks) for name,docs in pilot_docs.items()}
    write(out/'bf16_vector_task_pilot.json',vector)
    del model
    import torch
    torch.cuda.empty_cache()
    pilots = []
    for name in TASKS:
        docs = pilot_docs[name]
        for cfg in (configurations()[0], configurations()[4], configurations()[-3]):
            pilots.append(score_case(a, cfg, docs, tasks, out/'pilot'/f'{name}_{cfg["name"]}.json'))
    bridge = []
    for name in TASKS:
        cached_path=out/'pilot'/f'{name}_bf16.documents.jsonl'
        cached={r['id']:r for r in map(json.loads,cached_path.read_text().splitlines())}
        for reference in vector[name]:
            other=cached[reference['id']]
            differences=[abs(x['logprob']-y['logprob'])/x['tokens']
                         for x,y in zip(reference['choices'],other['choices'])]
            same=reference['metrics']==other['metrics']
            bridge.append(dict(id=reference['id'],max_mean_token_logprob_difference=max(differences),
                               same_task_decisions=same))
            if max(differences)>.05 or not same:
                raise ValueError('BF16 cached/vector task bridge failed: '+reference['id'])
    write(out/'BF16_TASK_BRIDGE.json',dict(passed=True,records=bridge,
        tolerance='max per-choice mean absolute sum-logprob difference / answer tokens <=0.05 nats and same official acc/acc_norm decisions on 12 longest-prompt pilot docs'))
    write(out/'suite.json', dict(configurations=configurations(), tasks=list(TASKS),
        protocol='official 0shot multiple-choice likelihood; cached unpadded model; shared first scored decode query; independent branches restored',
        count=len(TASKS)*len(configurations()), task_statistics=meta['statistics']))
    write(out/'READY.json', dict(code_commit=a.code_commit, task_data_sha256=sha(out/'TASK_DATA.json'),
        identity_sha256=sha(out/'identity.json'), source_sha256=sources(),
        suite_sha256=sha(out/'suite.json'), baseline_gate_passed=passed, bf16_task_bridge_passed=True,
        pilots=[dict(task=p['task'],case=p['configuration']['name'],seconds=p.get('elapsed_seconds'),
                     metrics=p['metrics'], peak_allocated_bytes=p['peak_allocated_bytes']) for p in pilots]))


def worker(a):
    out = outdir(a)
    ready = json.loads((out/'READY.json').read_text())
    if ready['code_commit'] != a.code_commit or ready['source_sha256'] != sources() or not ready['baseline_gate_passed']:
        raise ValueError('Preparation/code mismatch')
    for key, filename in [('task_data_sha256','TASK_DATA.json'),('identity_sha256','identity.json'),('suite_sha256','suite.json')]:
        if ready[key] != sha(out/filename):
            raise ValueError('Preparation changed')
    identity=json.loads((out/'identity.json').read_text())
    for entry in identity['files'].values():
        if Path(entry['path']).stat().st_size != entry['bytes'] or sha(entry['path']) != entry['sha256']:
            raise ValueError('Frozen model/tokenizer/corpus bytes changed')
    if json.loads((out/'TASK_DATA.json').read_text())['harness_sources'] != harness_sources():
        raise ValueError('Installed harness source changed')
    name = list(TASKS)[a.index // len(configurations())]
    cfg = configurations()[a.index % len(configurations())]
    tasks, _ = load_tasks(a.task_data)
    result = score_case(a, cfg, read_docs(out, name), tasks, out/'full'/f'{name}_{cfg["name"]}.json')
    print(json.dumps(dict(event='completed', task=name, case=cfg['name'], metrics=result['metrics'])), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['data','prepare','worker'])
    for key in ('model','data','calibration','project-root','output','code-commit','task-data'):
        p.add_argument('--'+key, required=True)
    p.add_argument('--index',type=int,default=0)
    a = p.parse_args()
    if len(a.code_commit) != 40:
        p.error('Exact execution commit required')
    {'data':data,'prepare':prepare,'worker':worker}[a.action](a)


if __name__ == '__main__':
    main()
