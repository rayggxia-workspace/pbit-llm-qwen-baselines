"""Slurm-only Issue145 task input freeze, real-model smoke and MC evaluation.

The official Issue59 task_data.py is imported unchanged. This runner never
imports its old joint Attention/FFN scorer. Checkpoints remain floating point;
no training, W8 conversion or implicit checkpoint discovery is performed.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import random
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

OWNER = 'Weican_Chen'
HOME = Path('/home/Weican_Chen')
PROJECT = HOME / 'projects/pbit-pdnn-task-accuracy-issue145'
TASK_IDS = {
    'piqa': '4c9f51a5292e593fe5632b28f92c8405171a0102789840f42bd949b804e3a9ab',
    'arc_easy': '922c84ada5637d14c1d1483cf8e15c828b0c6051da9be3d2543bc5ff53a26044',
    'hellaswag': 'b3bedbdf96e593ddb07a08f71bb7bf5906b85af0953f798e87a517097b1abed0',
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def artifact(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def check_artifact(entry, root):
    path = Path(entry['path']).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('artifact outside verified personal root')
    if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
        raise ValueError('artifact changed: ' + str(path))
    return path


def setup(a):
    # Identity and canonical roots are verified before any directory creation.
    import pwd
    user = pwd.getpwuid(os.getuid())
    home = Path(user.pw_dir).resolve(strict=True)
    if user.pw_name != OWNER or getpass.getuser() != OWNER or home != HOME or Path.home().resolve() != HOME:
        raise PermissionError('run only as verified Weican_Chen in its canonical home')
    project = Path(a.project_root).resolve(strict=True)
    if project != PROJECT or not project.is_relative_to(home):
        raise PermissionError('unexpected Issue145 personal project root')
    model, task_data, config = (Path(p).resolve(strict=True) for p in (a.model, a.task_data, a.config))
    output = Path(a.output).resolve()
    if not model.is_relative_to(home) or not task_data.is_relative_to(project) or not config.is_relative_to(project):
        raise PermissionError('model must be personal; input data/config must be in this project')
    if not output.is_relative_to(project / 'runs') or output == project / 'runs' or REPO in output.parents:
        raise PermissionError('output must be a separate new run under personal project/runs')
    if not REPO.resolve().is_relative_to(project):
        raise PermissionError('execute a source snapshot within the personal project')
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('computation requires a Slurm allocation')
    visible = os.environ.get('CUDA_VISIBLE_DEVICES', '')
    if a.action == 'data':
        if visible != '':
            raise RuntimeError('CPU data jobs must explicitly hide GPUs')
    elif visible in ('', '-1', 'NoDevFiles'):
        raise RuntimeError('smoke/run require a Slurm GPU allocation with visible devices')
    if not re.fullmatch('[0-9a-f]{40}', a.code_commit):
        raise ValueError('exact execution code commit SHA required')
    caches = {'HF_HOME': 'cache/hf', 'HF_HUB_CACHE': 'cache/hf/hub',
              'HF_DATASETS_CACHE': 'cache/hf/datasets', 'HF_MODULES_CACHE': 'cache/hf/modules',
              'XDG_CACHE_HOME': 'cache/xdg', 'TORCH_HOME': 'cache/torch',
              'PYTORCH_KERNEL_CACHE_PATH': 'cache/torch/kernels', 'TMPDIR': 'tmp'}
    for key, suffix in caches.items():
        value = project / suffix
        value.mkdir(parents=True, exist_ok=True)
        if not value.resolve().is_relative_to(project):
            raise PermissionError('cache symlink leaves personal project')
        os.environ[key] = str(value)
    os.environ.update(HF_HUB_OFFLINE='1', HF_DATASETS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    output.mkdir(parents=True, exist_ok=True)
    a.project, a.home, a.model, a.task_data, a.config, a.output = project, home, model, task_data, config, output
    return validate_config(read(config))


def validate_config(config):
    from experiments.pdnn_task_accuracy_20261023.pdnn_score import _variant
    if config.get('protocol_version') != 1 or not re.fullmatch('[0-9a-f]{64}', config.get('model_weight_sha256', '')):
        raise ValueError('unknown protocol version or invalid model SHA')
    seen = set()
    for variant in config['variants']:
        name = variant['name']
        if not re.fullmatch('[a-zA-Z0-9_-]+', name) or name in seen:
            raise ValueError('unique filesystem-safe variant names required')
        seen.add(name)
        case = _variant({k: v for k, v in variant.items() if k != 'name'})
        if case['samples'] != 4 or case['context'] != 2048:
            raise ValueError('Issue145 freezes four complete paths and context=2048')
    if len(config['variants']) != 7 or sum(not v['layers'] for v in config['variants']) != 1:
        raise ValueError('one BF16 and six P-DNN variants required')
    for count in (2, 4):
        variants = [v for v in config['variants'] if len(v['layers']) == count]
        if len(variants) != 3 or sorted(v['seed'] for v in variants) != [0, 1, 2]:
            raise ValueError('two/four layer groups require seeds 0,1,2')
    indices = [c['layer'] for c in config['checkpoints']]
    if len(indices) != len(set(indices)) or set(indices) != {i for v in config['variants'] for i in v['layers']}:
        raise ValueError('checkpoint set must exactly cover explicitly requested layers')
    for checkpoint in config['checkpoints']:
        if not PurePosixPath(checkpoint['path']).is_absolute() or not re.fullmatch('[0-9a-f]{64}', checkpoint['sha256']):
            raise ValueError('explicit absolute checkpoint path and SHA required')
    return config


def sources():
    areas = [HERE, REPO / 'experiments/pdnn_ffn', REPO / 'experiments/qwen_task_accuracy_20261019/task_data.py']
    paths = []
    for area in areas:
        paths += [area] if area.is_file() else [p for p in area.rglob('*') if p.is_file()
            and p.suffix in ('.py', '.json', '.md', '.sbatch', '.sh') and '__pycache__' not in p.parts]
    return {p.relative_to(REPO).as_posix(): sha(p) for p in sorted(paths)}


def environment():
    import torch
    import transformers
    if importlib.metadata.version('lm_eval') != '0.4.8' or transformers.__version__ != '4.45.2':
        raise ValueError('frozen lm_eval0.4.8 and Transformers4.45.2 required')
    return dict(python=sys.version, executable=sys.executable, torch=torch.__version__,
                transformers=transformers.__version__, lm_eval=importlib.metadata.version('lm_eval'),
                cuda=torch.version.cuda, slurm_job_id=os.environ['SLURM_JOB_ID'],
                cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES', ''),
                hostname=os.uname().nodename)


def model_identity(a, config):
    files = {}
    for name in ('model.safetensors', 'config.json', 'tokenizer.json', 'tokenizer_config.json',
                 'special_tokens_map.json', 'vocab.json', 'merges.txt', 'generation_config.json', 'added_tokens.json'):
        path = a.model / name
        if path.exists():
            canonical = path.resolve(strict=True)
            if not canonical.is_relative_to(a.home):
                raise PermissionError('model/tokenizer symlink leaves personal home')
            files[name] = artifact(canonical)
    required = {'model.safetensors', 'config.json', 'tokenizer.json', 'tokenizer_config.json'}
    if not required <= set(files) or files['model.safetensors']['sha256'] != config['model_weight_sha256']:
        raise ValueError('base model/tokenizer identity mismatch')
    cfg = read(a.model / 'config.json')
    if cfg.get('hidden_size') != 896 or cfg.get('num_hidden_layers') != 24 or cfg.get('model_type') != 'qwen2':
        raise ValueError('Qwen2.5-0.5B Base 24-layer configuration required')
    return dict(path=str(a.model), files=files, model_config=cfg)


def load_model(a):
    import torch
    from transformers import AutoModelForCausalLM
    if not torch.cuda.is_available():
        raise RuntimeError('allocated GPU not available')
    torch.backends.cuda.matmul.allow_tf32 = False
    model = AutoModelForCausalLM.from_pretrained(str(a.model), local_files_only=True,
        trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='sdpa')
    # Device-only move preserves the original non-persistent RoPE buffer dtype.
    model.to(device=torch.device('cuda:0')).eval().requires_grad_(False)
    if any(v.device != torch.device('cuda:0') for v in list(model.parameters()) + list(model.buffers())):
        raise ValueError('model tensor on unexpected actual device')
    return model


def data(a, config):
    from transformers import AutoTokenizer
    from experiments.qwen_task_accuracy_20261019.task_data import load_tasks, token_documents, harness_sources
    marker = a.output / 'TASK_DATA.json'
    if marker.exists() or (a.output / 'tokenized').exists():
        raise FileExistsError('data preparation already exists; never overwrite a frozen/partial run')
    env = environment()
    model = model_identity(a, config)
    checkpoints = []
    for entry in config['checkpoints']:
        path = check_artifact(entry, a.home)
        checkpoints.append(dict(entry, path=str(path)))
    tokenizer = AutoTokenizer.from_pretrained(str(a.model), local_files_only=True, trust_remote_code=False)
    tasks, identities = load_tasks(a.task_data)
    tokenized, statistics = {}, {}
    for name, task in tasks.items():
        docs = token_documents(task, name, tokenizer)
        full = len(docs)
        if name == 'hellaswag':
            selected = set(random.Random(20261019).sample(range(full), 1000))
            docs = [d for index, d in enumerate(docs) if index in selected]
        ids_sha = hashlib.sha256(json.dumps([d['doc_id'] for d in docs], separators=(',', ':')).encode()).hexdigest()
        if ids_sha != TASK_IDS[name]:
            raise ValueError('frozen selected document IDs differ: ' + name)
        path = a.output / 'tokenized' / (name + '.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            for row in docs:
                stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        contexts = [len(d['context_ids']) for d in docs]
        answers = [len(c) for d in docs for c in d['choices_ids']]
        statistics[name] = dict(documents=len(docs), full_split_documents=full,
            selection='fixed Random(20261019) 1000 without replacement before inference' if name == 'hellaswag' else 'full split',
            selected_doc_ids_sha256=ids_sha, requests=len(answers), answer_targets=sum(answers),
            prompt_min=min(contexts), prompt_max=max(contexts), answer_max=max(answers),
            max_scored_context=max(len(d['context_ids']) + max(map(len, d['choices_ids'])) - 1 for d in docs))
        tokenized[name] = artifact(path)
    write_new(marker, dict(status='completed', code_commit=a.code_commit, config=artifact(a.config),
        configuration=config, source_sha256=sources(), model=model, checkpoints=checkpoints,
        tasks=identities, tokenized=tokenized, statistics=statistics,
        harness_sources=harness_sources(), num_fewshot=0, chat_template=False,
        metrics='official lm_eval0.4.8 process_results; acc_norm uses choice character length',
        environment=env, created_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(event='data_completed', task_data=artifact(marker), statistics=statistics)), flush=True)


def frozen(a, config):
    from experiments.qwen_task_accuracy_20261019.task_data import harness_sources, load_tasks
    meta = read(a.output / 'TASK_DATA.json')
    if meta.get('status') != 'completed' or meta['code_commit'] != a.code_commit:
        raise ValueError('data preparation code/version incomplete or different')
    check_artifact(meta['config'], a.home)
    if meta['configuration'] != config or meta['source_sha256'] != sources():
        raise ValueError('frozen config or execution sources changed')
    if meta['harness_sources'] != harness_sources():
        raise ValueError('installed official Harness implementation changed')
    for entry in meta['model']['files'].values():
        check_artifact(entry, a.home)
    for entry in meta['checkpoints']:
        check_artifact(entry, a.home)
    tasks, identity = load_tasks(a.task_data)
    if identity != meta['tasks']:
        raise ValueError('official task definitions or dataset identity changed')
    docs = {}
    for name, entry in meta['tokenized'].items():
        path = check_artifact(entry, a.project)
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        if len(rows) != meta['statistics'][name]['documents'] or len({r['id'] for r in rows}) != len(rows):
            raise ValueError('frozen document coverage changed')
        docs[name] = rows
    return meta, tasks, docs


def compare_choices(left, right, reverse=False):
    left = {r['id']: r['choices'] for r in left}
    right = {r['id']: r['choices'] for r in right}
    if set(left) != set(right):
        raise ValueError('smoke document coverage differs')
    maximum = 0.
    for key, choices in left.items():
        other = list(reversed(right[key])) if reverse else right[key]
        if len(choices) != len(other):
            raise ValueError('smoke choice coverage differs')
        for a, b in zip(choices, other):
            maximum = max(maximum, abs(a['logprob'] - b['logprob']))
            if a['is_greedy'] != b['is_greedy'] or a['tokens'] != b['tokens']:
                raise ValueError('smoke greedy flag or token alignment differs')
    if maximum > 1e-6:
        raise ValueError('smoke choice sum logprob difference exceeds 1e-6: ' + str(maximum))
    return dict(passed=True, max_absolute_sum_logprob_difference=maximum, tolerance=1e-6)


def naive_bf16_cached(model, documents, variant):
    """Independent BF16 prefix per choice; no sharing/deepcopy/RNG helper."""
    import torch
    from collections import defaultdict
    groups, outputs = defaultdict(list), {}
    for row in documents:
        groups[(len(row['context_ids']), len(row['choices_ids']))].append(row)
    with torch.inference_mode():
        for signature in sorted(groups):
            group = groups[signature]
            for start in range(0, len(group), variant['batch']):
                batch = group[start:start + variant['batch']]
                for choice in range(signature[1]):
                    context = torch.tensor([d['context_ids'] for d in batch], device='cuda:0')
                    cache = model.model(input_ids=context[:, :-1], use_cache=True).past_key_values
                    answers = [d['choices_ids'][choice] for d in batch]
                    scores = torch.zeros(len(batch), device='cuda:0', dtype=torch.float64)
                    greedy = torch.ones(len(batch), device='cuda:0', dtype=torch.bool)
                    for step in range(max(map(len, answers))):
                        tokens = context[:, -1:] if step == 0 else torch.tensor(
                            [[a[step-1] if step-1 < len(a) else 0] for a in answers], device='cuda:0')
                        result = model.model(input_ids=tokens, past_key_values=cache, use_cache=True)
                        cache = result.past_key_values
                        logits = model.lm_head(result.last_hidden_state[:, -1]).float()
                        target = torch.tensor([a[step] if step < len(a) else 0 for a in answers], device='cuda:0')
                        active = torch.tensor([step < len(a) for a in answers], device='cuda:0')
                        lp = logits.log_softmax(-1).gather(-1, target[:, None]).squeeze(-1).double()
                        scores += torch.where(active, lp, 0.)
                        greedy &= (~active) | (logits.argmax(-1) == target)
                    for row, answer, value, exact in zip(batch, answers, scores.tolist(), greedy.tolist()):
                        outputs.setdefault(row['id'], []).append(dict(logprob=value, is_greedy=exact, tokens=len(answer)))
    return [dict(id=key, choices=choices) for key, choices in outputs.items()]


def score_case(a, config, meta, tasks, documents, variant, scope):
    import torch
    from experiments.pdnn_task_accuracy_20261023.pdnn_score import evaluate_tasks, install_students
    from experiments.qwen_task_accuracy_20261019.task_data import metrics_for
    task = documents[0]['task']
    name = variant['name'] + '_' + task
    directory = a.output / scope
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name + '.json')
    progress_path = directory / (name + '.progress.jsonl')
    documents_path = directory / (name + '.documents.jsonl')
    if path.exists():
        result = read(path)
        if (result.get('status') != 'completed' or result['code_commit'] != a.code_commit
                or result['configuration'] != variant or result['task_data_sha256'] != sha(a.output / 'TASK_DATA.json')
                or result['n_documents'] != len(documents) or result['source_sha256'] != sources()):
            raise ValueError('existing result cannot be reused: ' + name)
        check_artifact(result['document_artifact'], a.project)
        check_artifact(result['progress_artifact'], a.project)
        verify_metrics(result, tasks, documents)
        print(json.dumps(dict(event='verified_completed_skip', case=name, scope=scope)), flush=True)
        return result
    if progress_path.exists() or documents_path.exists():
        raise FileExistsError('partial case exists; do not replay/resume automatically: ' + name)
    # Claim the case before costly GPU model loading so any interruption is visible.
    with progress_path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(dict(event='started', case=name, code_commit=a.code_commit,
            slurm_job_id=os.environ['SLURM_JOB_ID'], utc=datetime.now(timezone.utc).isoformat())) + '\n')
    model = load_model(a)
    case = {k: v for k, v in variant.items() if k != 'name'}
    checkpoint_records = []
    try:
        if variant['layers']:
            checkpoint_records = install_students(model,
                [c for c in config['checkpoints'] if c['layer'] in variant['layers']],
                variant['samples'], a.home, next(model.parameters()).device)
        torch.cuda.reset_peak_memory_stats(torch.device('cuda:0'))
        by_id = {row['id']: row for row in documents}
        def progress(update):
            with progress_path.open('a', encoding='utf-8', newline='\n') as stream:
                for item in update['documents']:
                    source = by_id[item['id']]
                    enriched = dict(source, choices=item['choices'])
                    stream.write(json.dumps(dict(id=item['id'], task=task, doc_id=source['doc_id'],
                        choices=item['choices'], metrics=metrics_for(tasks, enriched)), separators=(',', ':')) + '\n')
            print(json.dumps(dict(event='progress', case=name, completed=update['execution_audit']['completed_documents'],
                                  elapsed_seconds=update['elapsed_seconds'])), flush=True)
        result = evaluate_tasks(model, documents, case, progress=progress)
        if scope == 'smoke':
            replay = evaluate_tasks(model, documents, case)
            reversed_docs = copy.deepcopy(documents)
            for row in reversed_docs:
                row['choices_ids'].reverse()
            permuted = evaluate_tasks(model, reversed_docs, case)
            gates = dict(replay=compare_choices(result['documents'], replay['documents']),
                         option_permutation=compare_choices(result['documents'], permuted['documents'], reverse=True))
            if not variant['layers']:
                gates['independent_cached_bf16'] = compare_choices(result['documents'], naive_bf16_cached(model, documents, variant))
            result['smoke_gates'] = gates
        records = []
        for item in result.pop('documents'):
            source = by_id[item['id']]
            enriched = dict(source, choices=item['choices'])
            records.append(dict(id=item['id'], task=task, doc_id=source['doc_id'],
                                choices=item['choices'], metrics=metrics_for(tasks, enriched)))
        if len(records) != len(documents) or {r['id'] for r in records} != set(by_id):
            raise ValueError('case did not return exactly all requested documents')
        with documents_path.open('x', encoding='utf-8', newline='\n') as stream:
            for row in sorted(records, key=lambda x: x['doc_id']):
                stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        result.update(status='completed', task=task, case=name, scope=scope, code_commit=a.code_commit,
            configuration=variant, n_documents=len(records),
            metrics={key: sum(r['metrics'][key] for r in records) / len(records) for key in ('acc', 'acc_norm')},
            document_artifact=artifact(documents_path), progress_artifact=artifact(progress_path),
            task_data_sha256=sha(a.output / 'TASK_DATA.json'), config=artifact(a.config),
            source_sha256=sources(), model_identity=meta['model'], checkpoint_identities=checkpoint_records,
            environment=dict(environment(), gpu=torch.cuda.get_device_name(0)),
            slurm_job_id=os.environ['SLURM_JOB_ID'], command=sys.argv,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(torch.device('cuda:0')),
            completed_utc=datetime.now(timezone.utc).isoformat())
        if scope == 'full':
            result['ready_sha256'] = sha(a.output / 'READY.json')
        verify_metrics(result, tasks, documents)
        write_new(path, result)
        # Independent readback checks every saved official task metric again.
        verify_metrics(read(path), tasks, documents)
        print(json.dumps(dict(event='completed', case=name, scope=scope, metrics=result['metrics'])), flush=True)
        return result
    finally:
        del model
        torch.cuda.empty_cache()


def verify_metrics(result, tasks, documents):
    from experiments.qwen_task_accuracy_20261019.task_data import metrics_for
    path = Path(result['document_artifact']['path'])
    if path.stat().st_size != result['document_artifact']['bytes'] or sha(path) != result['document_artifact']['sha256']:
        raise ValueError('saved documents artifact changed')
    saved = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    requested = {r['id']: r for r in documents}
    if len(saved) != len(requested) or {r['id'] for r in saved} != set(requested):
        raise ValueError('saved official document coverage mismatch')
    for row in saved:
        source = requested[row['id']]
        if row['task'] != source['task'] or row['doc_id'] != source['doc_id']:
            raise ValueError('saved source document identity mismatch')
        if len(row['choices']) != len(source['choices_ids']) or any(
                choice['tokens'] != len(ids) for choice, ids in zip(row['choices'], source['choices_ids'])):
            raise ValueError('saved candidate token alignment mismatch')
        expected = metrics_for(tasks, dict(source, choices=row['choices']))
        if row['metrics'] != expected:
            raise ValueError('saved official process_results mismatch')
    means = {key: sum(r['metrics'][key] for r in saved) / len(saved) for key in ('acc', 'acc_norm')}
    if means != result['metrics']:
        raise ValueError('saved official aggregate differs')


def smoke(a, config):
    meta, tasks, docs = frozen(a, config)
    ready_path = a.output / 'READY.json'
    if ready_path.exists():
        verify_ready(a)
        print(json.dumps(dict(event='verified_ready_skip', ready=artifact(ready_path))), flush=True)
        return
    variants = [v for v in config['variants'] if v['seed'] == 0]
    if sorted(len(v['layers']) for v in variants) != [0, 2, 4]:
        raise ValueError('smoke requires BF16/two/four-layer seed0')
    records = []
    for task, rows in docs.items():
        selected = {rows[0]['id'], max(rows, key=lambda d: (len(d['context_ids']), d['id']))['id']}
        pilot = [row for row in rows if row['id'] in selected]
        for variant in variants:
            result = score_case(a, config, meta, tasks, pilot, variant, 'smoke')
            if not all(gate.get('passed') for gate in result['smoke_gates'].values()):
                raise ValueError('real-model smoke gate failed')
            records.append(artifact(a.output / 'smoke' / (result['case'] + '.json')))
    write_new(ready_path, dict(status='ready', code_commit=a.code_commit,
        task_data_sha256=sha(a.output / 'TASK_DATA.json'), source_sha256=sources(), config=artifact(a.config),
        cases=records, scope='first plus longest-prompt official document per task; not task accuracy',
        gates='all 24 actual decoder/FFN paths; real GPU global RNG replay and option permutation; independent BF16 cached oracle',
        environment=environment(), created_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(event='ready', ready=artifact(ready_path))), flush=True)


def verify_ready(a):
    ready = read(a.output / 'READY.json')
    if (ready['status'] != 'ready' or ready['code_commit'] != a.code_commit
            or ready['task_data_sha256'] != sha(a.output / 'TASK_DATA.json') or ready['source_sha256'] != sources()):
        raise ValueError('READY source or task-data binding changed')
    check_artifact(ready['config'], a.home)
    if len(ready['cases']) != 9:
        raise ValueError('READY must cover nine real-model smoke cases')
    for entry in ready['cases']:
        path = check_artifact(entry, a.project)
        result = read(path)
        if result.get('status') != 'completed' or not all(g.get('passed') for g in result['smoke_gates'].values()):
            raise ValueError('READY points to an incomplete/failed smoke case')
        check_artifact(result['document_artifact'], a.project)
        check_artifact(result['progress_artifact'], a.project)
    return ready


def run(a, config):
    meta, tasks, docs = frozen(a, config)
    verify_ready(a)
    cases = [(task, variant) for task in docs for variant in config['variants']]
    if a.case:
        cases = [(task, v) for task, v in cases if v['name'] + '_' + task == a.case]
        if len(cases) != 1:
            raise ValueError('unknown or ambiguous case name: ' + a.case)
    for task, variant in cases:
        score_case(a, config, meta, tasks, docs[task], variant, 'full')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('data', 'smoke', 'run'):
        p = sub.add_parser(action)
        for name in ('project-root', 'model', 'task-data', 'output', 'config', 'code-commit'):
            p.add_argument('--' + name, required=True)
        if action == 'run':
            p.add_argument('--case', help='variant-name_task, e.g. pdnn2_subset_joint4_s0_piqa')
    args = parser.parse_args()
    cfg = setup(args)
    environment()
    {'data': data, 'smoke': smoke, 'run': run}[args.action](args, cfg)


if __name__ == '__main__':
    main()
