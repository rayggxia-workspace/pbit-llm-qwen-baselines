"""Portable personal-account Slurm profile: fresh BF16 plus joint20 P-DNN.

No Issue145 server path is required. Reuse its frozen model/tokenizer, official
tasks, byte-identical requests and scoring protocol, but recompute three BF16
cases on the recipient's allocated GPU. Missing weights never enable GPU work.
All filesystem writes stay inside the actual login user's canonical home.
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
import statistics
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from experiments.pdnn20_task_accuracy_20261023.runner import (
    LAYERS, MODEL_SHA, TASKS, ProgressRecorder, artifact, jsonlines, read, require,
    sha, smoke_documents, validate_config, validate_expected, variant,
    verify_execution, verify_saved_metrics, write_new,
)

PROFILE = 'portable_fresh_bf16_v1'


def own_path(path, home, exists=True):
    home = Path(home).resolve(strict=True)
    value = Path(path).resolve(strict=exists)
    require(value != home and value.is_relative_to(home), 'path must stay within actual canonical home: ' + str(value))
    parent = value
    while not parent.exists():
        parent = parent.parent
    require(hasattr(os, 'getuid') and parent.stat().st_uid == os.getuid(), 'path ownership differs from login UID: ' + str(parent))
    return value


def checked(entry, home, root=None):
    path = own_path(entry['path'], home)
    require(root is None or path.is_relative_to(Path(root).resolve(strict=True)), 'artifact leaves its frozen project/run root')
    require(path.is_file() and path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'],
            'artifact size/SHA differs: ' + str(path))
    return path


def normalized_harness(mapping):
    result = {}
    for path, digest in mapping.items():
        require('/site-packages/' in path, 'unrecognized installed Harness source path')
        role = path.split('/site-packages/', 1)[1]
        require(role.startswith('lm_eval/') and role not in result, 'duplicate/unexpected Harness source role')
        result[role] = digest
    return result


def check_pin(pin):
    require(re.fullmatch('[0-9a-f]{40}', pin['source_commit']) and re.fullmatch('[0-9a-f]{64}', pin['source_task_data_sha256']),
            'portable reference requires exact original source/TASK_DATA identity')
    require(set(pin['tasks']) == set(pin['tokenized']) == set(pin['statistics']) == set(TASKS), 'portable task pin coverage differs')
    require(pin['environment_versions'] == dict(torch='2.7.1+cu128', transformers='4.45.2', lm_eval='0.4.8', cuda='12.8'),
            'unsupported portable reference environment')
    require(pin['model_files']['model.safetensors']['sha256'] == MODEL_SHA, 'portable base model pin differs')
    for task, (count, ids_sha) in TASKS.items():
        require(pin['statistics'][task]['documents'] == count
                and pin['statistics'][task]['selected_doc_ids_sha256'] == ids_sha,
                'portable reference task selection differs')
    return pin


def verify_model_pin(model, pin):
    files = {name: {k: entry[k] for k in ('bytes', 'sha256')} for name, entry in model['files'].items()}
    require(files == pin['model_files'], 'model/tokenizer files differ from the portable reference pin')


def environment(pin):
    import torch
    import transformers
    versions = dict(torch=torch.__version__, transformers=transformers.__version__,
                    lm_eval=importlib.metadata.version('lm_eval'), cuda=torch.version.cuda)
    require(versions == pin['environment_versions'], 'environment mismatch; require the exact pinned software/CUDA runtime')
    return dict(versions, python=sys.version, executable=sys.executable,
                slurm_job_id=os.environ['SLURM_JOB_ID'], cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES', ''),
                hostname=os.uname().nodename)


def setup(a):
    import pwd
    account = pwd.getpwuid(os.getuid())
    home = Path(account.pw_dir).resolve(strict=True)
    require(account.pw_name == getpass.getuser() and Path.home().resolve(strict=True) == home
            and home.stat().st_uid == os.getuid(), 'actual login account/canonical home/UID must agree')
    own_path(sys.prefix, home)
    require(os.environ.get('SLURM_JOB_ID'), 'compute requires an explicit Slurm allocation')
    cpu = a.action in ('preflight', 'summarize')
    visible = os.environ.get('CUDA_VISIBLE_DEVICES', '')
    require(visible == '' if cpu else visible not in ('', '-1', 'NoDevFiles'), 'CPU/GPU allocation visibility differs')
    a.home = home
    a.actor = dict(username=account.pw_name, uid=os.getuid(), canonical_home=str(home))
    a.project = own_path(a.project_root, home)
    source = own_path(REPO, home)
    require(source.is_relative_to(a.project), 'extract the supplied source package under this personal project root')
    a.model, a.task_data, a.config = (own_path(p, home) for p in (a.model, a.task_data, a.config))
    a.checkpoint_dir, a.output = (own_path(p, home, exists=False) for p in (a.checkpoint_dir, a.output))
    require(a.config.is_relative_to(source) and a.output.is_relative_to(a.project)
            and a.output != a.project and not any(a.output.is_relative_to(p)
                for p in (source, a.model, a.task_data, a.checkpoint_dir)),
            'config must be packaged source; separate run output must be outside all immutable inputs')
    require(re.fullmatch('[0-9a-f]{40}', a.code_commit), 'exact package/execution commit identity required')
    config = validate_config(read(a.config))
    a.expected_path = own_path(a.config.parent / config['expected_checkpoint_manifest'], home)
    a.expected = validate_expected(read(a.expected_path))
    a.pin_path = own_path(a.config.parent / 'portable_reference.expected.json', home)
    require(a.expected_path.is_relative_to(source) and a.pin_path.is_relative_to(source), 'reference manifests must stay inside packaged source')
    a.pin = check_pin(read(a.pin_path))
    # Validate every target before writing user-local caches and run directories.
    for key, suffix in {'HF_HOME': 'cache/hf', 'HF_HUB_CACHE': 'cache/hf/hub',
            'HF_DATASETS_CACHE': 'cache/hf/datasets', 'HF_MODULES_CACHE': 'cache/hf/modules',
            'XDG_CACHE_HOME': 'cache/xdg', 'TORCH_HOME': 'cache/torch',
            'PYTORCH_KERNEL_CACHE_PATH': 'cache/torch/kernels', 'TMPDIR': 'tmp'}.items():
        value = own_path(a.project / suffix, home, exists=False)
        value.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(value)
    os.environ.update(HF_HUB_OFFLINE='1', HF_DATASETS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    a.output.mkdir(parents=True, exist_ok=True)
    return config


def sources():
    areas = [HERE, REPO / 'experiments/pdnn_ffn',
             REPO / 'experiments/pdnn_task_accuracy_20261023/pdnn_score.py',
             REPO / 'experiments/pdnn_task_accuracy_20261023/runner.py',
             REPO / 'experiments/qwen_task_accuracy_20261019/task_data.py']
    files = set()
    for area in areas:
        files.update([area] if area.is_file() else [p for p in area.rglob('*') if p.is_file()
                     and p.suffix in ('.py', '.md', '.json', '.sh', '.sbatch', '.expected') and '__pycache__' not in p.parts])
    return {p.relative_to(REPO).as_posix(): sha(p) for p in sorted(files)}


def model_identity(a):
    from experiments.pdnn_task_accuracy_20261023.runner import model_identity as original_identity
    model = original_identity(a, dict(model_weight_sha256=MODEL_SHA))
    for entry in model['files'].values():
        own_path(entry['path'], a.home)
    verify_model_pin(model, a.pin)
    return model


def checkpoint_inventory(a, inspect_only):
    """Explicit own-home filenames only; no auto-search, copying or rewriting."""
    from dataclasses import asdict
    entries, missing, inspected = [], [], []
    for expected in a.expected:
        path = own_path(a.checkpoint_dir / PurePosixPath(expected['relative_path']).name, a.home, exists=False)
        entry = {k: expected[k] for k in ('layer', 'bytes', 'sha256', 'student_type', 'phase', 'step')}
        entry['path'] = str(path)
        if not path.exists():
            missing.append(dict(entry))
            continue
        checked(entry, a.home, a.checkpoint_dir)
        entries.append(entry)
    if len(entries) == 20 and not inspect_only:
        import torch
        from experiments.pdnn_ffn.full_path_pdnn_ffn import FullPathPBitFFN, FullPathPBitFFNConfig
        for entry in entries:
            payload = torch.load(entry['path'], map_location='cpu', weights_only=True)
            require(payload.get('student_type') == entry['student_type'] and payload.get('phase') == entry['phase']
                    and payload.get('step') == entry['step'] and payload.get('training_args', {}).get('layer') == entry['layer'],
                    'checkpoint payload differs from historical joint20 manifest')
            cfg = dict(payload['student_config'])
            cfg['hidden_sizes'] = tuple(cfg['hidden_sizes'])
            cfg = FullPathPBitFFNConfig(**cfg)
            require(cfg.input_size == cfg.output_size == 896 and cfg.hidden_sizes == (4864,)
                    and cfg.input_temperature == .25 and cfg.hidden_temperature == 1. and cfg.coding == 'bipolar'
                    and cfg.architecture == 'serial' and cfg.input_encoding == 'sigmoid' and cfg.input_bits == 1
                    and cfg.learnable_encoding is False, 'not the historical serial bipolar two-matrix joint20 operator')
            state = payload['student_state_dict']
            require(isinstance(state, dict) and all(isinstance(v, torch.Tensor) and v.is_floating_point()
                    and torch.isfinite(v).all().item() for v in state.values()), 'checkpoint state must be finite floating point')
            student = FullPathPBitFFN(cfg)
            student.load_state_dict(state, strict=True)
            require(sum(v.numel() for v in student.parameters()) == 8722048, 'checkpoint parameter count differs')
            checked(entry, a.home, a.checkpoint_dir)
            inspected.append(dict(entry, strict_state_loaded=True, source_student_config=payload['student_config'],
                                  effective_student_config=asdict(cfg), parameters=8722048, inspection_device='cpu'))
            del student, payload
    return dict(expected=20, entries=entries, missing=missing, inspected=inspected,
                all_checkpoint_bytes_present=len(entries) == 20, all_strict_states_loaded=len(inspected) == 20)


def tasks_and_identity(a):
    from experiments.qwen_task_accuracy_20261019.task_data import load_tasks, harness_sources
    # Resolve and authorize each input before the original loader reads it.
    for task, expected in a.pin['tasks'].items():
        path = own_path(a.task_data / task / '0000.parquet', a.home)
        require(path.is_relative_to(a.task_data) and path.stat().st_size == expected['dataset_bytes']
                and sha(path) == expected['dataset_sha256'], 'dataset bytes/ownership differ before task loading')
    tasks, actual = load_tasks(a.task_data)
    normalized = {name: {k: row[k] for k in ('split', 'documents', 'dataset_sha256', 'dataset_bytes', 'task_yaml_sha256')}
                  for name, row in actual.items()}
    require(normalized == a.pin['tasks'], 'task YAML/split/parquet identity differs from the reference')
    harness = harness_sources()
    require(normalized_harness(harness) == a.pin['harness_sources'], 'installed official Harness code differs from reference')
    for entry in actual.values():
        path = own_path(entry['dataset_path'], a.home)
        require(path.is_relative_to(a.task_data) and path.stat().st_size == entry['dataset_bytes']
                and sha(path) == entry['dataset_sha256'], 'dataset bytes/ownership differ')
        own_path(entry['task_yaml'], a.home)
    for path in harness:
        own_path(path, a.home)
    return tasks, actual, harness


def write_tokenized(a, tasks):
    from transformers import AutoTokenizer
    from experiments.qwen_task_accuracy_20261019.task_data import token_documents
    require(not (a.output / 'tokenized').exists(), 'tokenized originals already exist; use a new run tag')
    tokenizer = AutoTokenizer.from_pretrained(str(a.model), local_files_only=True, trust_remote_code=False)
    paths, statistics_by_task = {}, {}
    for name, task in tasks.items():
        docs = token_documents(task, name, tokenizer)
        full = len(docs)
        if name == 'hellaswag':
            selected = set(random.Random(20261019).sample(range(full), 1000))
            docs = [d for index, d in enumerate(docs) if index in selected]
        ids = [d['doc_id'] for d in docs]
        digest = hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()
        require(len(docs) == TASKS[name][0] and digest == TASKS[name][1], 'predeclared document selection differs')
        path = a.output / 'tokenized' / (name + '.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            for row in docs:
                stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        pinned = a.pin['tokenized'][name]
        require(path.stat().st_size == pinned['bytes'] and sha(path) == pinned['sha256'],
                'tokenized requests differ from original Issue145 bytes: ' + name)
        contexts = [len(r['context_ids']) for r in docs]
        answers = [len(c) for r in docs for c in r['choices_ids']]
        stats = dict(documents=len(docs), full_split_documents=full,
            selection='fixed Random(20261019) 1000 without replacement before inference' if name == 'hellaswag' else 'full split',
            selected_doc_ids_sha256=digest, requests=len(answers), answer_targets=sum(answers),
            prompt_min=min(contexts), prompt_max=max(contexts), answer_max=max(answers),
            max_scored_context=max(len(r['context_ids']) + max(map(len, r['choices_ids'])) - 1 for r in docs))
        require(stats == a.pin['statistics'][name], 'tokenized statistics differ from the frozen reference')
        paths[name], statistics_by_task[name] = artifact(path), stats
    return paths, statistics_by_task


def cpu_ready(inventory, inspect_only):
    return (not inspect_only and inventory['all_checkpoint_bytes_present']
            and inventory['all_strict_states_loaded'] and not inventory['missing']
            and len(inventory['entries']) == len(inventory['inspected']) == 20)


def preflight(a, config):
    require(not any((a.output / name).exists() for name in ('TASK_DATA.json', 'PREFLIGHT_READY.json', 'PREPARATION_ONLY.json')),
            'preflight/partial data already exists; preserve it and choose a new run tag')
    env = environment(a.pin)
    model = model_identity(a)
    tasks, identities, harness = tasks_and_identity(a)
    inventory = checkpoint_inventory(a, a.inspect_only)
    tokenized, stats = write_tokenized(a, tasks)
    data = dict(profile=PROFILE, status='completed', actor=a.actor, code_commit=a.code_commit,
        config=artifact(a.config), configuration=config, identity_reference=artifact(a.pin_path),
        reference_source_commit=a.pin['source_commit'], reference_task_data_sha256=a.pin['source_task_data_sha256'],
        expected_checkpoint_manifest=artifact(a.expected_path), model_identity=model, tasks=identities,
        harness_sources=harness, tokenized=tokenized, statistics=stats, source_sha256=sources(),
        environment=env, num_fewshot=0, chat_template=False, training=False,
        baseline='fresh BF16 per task on this account/GPU; existing Issue145 numerical results are not reused',
        created_utc=datetime.now(timezone.utc).isoformat())
    write_new(a.output / 'TASK_DATA.json', data)
    ready = cpu_ready(inventory, a.inspect_only)
    marker = dict(profile=PROFILE, status='ready' if ready else 'awaiting_external_inputs',
        gpu_allowed=ready, inspect_only=a.inspect_only, actor=a.actor, code_commit=a.code_commit,
        task_data=artifact(a.output / 'TASK_DATA.json'), config=data['config'], configuration=config,
        identity_reference=data['identity_reference'], expected_checkpoint_manifest=data['expected_checkpoint_manifest'],
        source_sha256=data['source_sha256'], checkpoint_inventory=inventory, environment=env, training=False,
        waiting=[] if ready else ['strict CPU validation of all twenty historical checkpoint files is required; inspect-only never authorizes GPU'],
        created_utc=datetime.now(timezone.utc).isoformat())
    write_new(a.output / ('PREFLIGHT_READY.json' if ready else 'PREPARATION_ONLY.json'), marker)
    print(json.dumps(dict(event='portable_preflight', status=marker['status'], gpu_allowed=ready,
        missing_layers=[e['layer'] for e in inventory['missing']], profile=PROFILE)), flush=True)
    return ready or a.inspect_only


def frozen(a, config):
    environment(a.pin)
    path = a.output / 'PREFLIGHT_READY.json'
    require(path.exists(), 'strict CPU PREFLIGHT_READY required; PREPARATION_ONLY cannot enable GPU')
    marker = read(path)
    require(marker['profile'] == PROFILE and marker['status'] == 'ready' and marker['gpu_allowed'] is True
            and marker['inspect_only'] is False and marker['actor'] == a.actor and marker['code_commit'] == a.code_commit
            and marker['configuration'] == config and marker['source_sha256'] == sources()
            and marker['checkpoint_inventory']['all_strict_states_loaded'] is True
            and len(marker['checkpoint_inventory']['inspected']) == 20, 'strict CPU/source/profile/actor binding differs')
    for entry in (marker['config'], marker['identity_reference'], marker['expected_checkpoint_manifest']):
        checked(entry, a.home, REPO)
    data = read(checked(marker['task_data'], a.home, a.output))
    require(data['profile'] == PROFILE and data['status'] == 'completed' and data['actor'] == a.actor
            and data['code_commit'] == a.code_commit and data['configuration'] == config
            and data['source_sha256'] == marker['source_sha256'], 'TASK_DATA profile/source binding differs')
    require(model_identity(a) == data['model_identity'], 'base model/tokenizer changed after preflight')
    expected_paths = {e['layer']: str(a.checkpoint_dir / PurePosixPath(e['relative_path']).name) for e in a.expected}
    entries = marker['checkpoint_inventory']['entries']
    require([e['layer'] for e in entries] == LAYERS, 'strict checkpoint coverage differs')
    for entry in entries:
        require(str(Path(entry['path'])) == expected_paths[entry['layer']], 'checkpoint directory changed after preflight')
        checked(entry, a.home, a.checkpoint_dir)
    tasks, identities, harness = tasks_and_identity(a)
    require(identities == data['tasks'] and harness == data['harness_sources'], 'official task identity changed')
    docs = {}
    for task, entry in data['tokenized'].items():
        rows = jsonlines(checked(entry, a.home, a.output))
        ids = [r['doc_id'] for r in rows]
        require(len(rows) == TASKS[task][0] and len({r['id'] for r in rows}) == len(rows)
                and hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest() == TASKS[task][1],
                'frozen per-task ID coverage changed')
        docs[task] = rows
    return marker, data, tasks, docs


def validate_case(a, result, documents, case, scope, tasks, marker, data):
    from experiments.qwen_task_accuracy_20261019.task_data import metrics_for
    require(result['profile'] == PROFILE and result['status'] == 'completed' and result['scope'] == scope
            and result['case'] == case['name'] + '_' + documents[0]['task'] and result['configuration'] == case
            and result['variant'] == {k: v for k, v in case.items() if k != 'name'}
            and result['code_commit'] == a.code_commit and result['source_sha256'] == marker['source_sha256']
            and result['preflight_sha256'] == sha(a.output / 'PREFLIGHT_READY.json')
            and result['task_data_sha256'] == sha(a.output / 'TASK_DATA.json')
            and result['model_identity'] == data['model_identity'] and result['training'] is False,
            'case differs from frozen portable execution')
    verify_saved_metrics(result, documents, lambda e: checked(e, a.home, a.output), lambda r: metrics_for(tasks, r))
    verify_execution(result, documents, case['layers'])
    actual = result['checkpoint_identities']
    require([e['layer'] for e in actual] == case['layers'], 'runtime checkpoint coverage differs')
    expected = {e['layer']: e for e in marker['checkpoint_inventory']['entries']}
    for entry in actual:
        require(all(entry[k] == expected[entry['layer']][k] for k in
                    ('layer', 'path', 'bytes', 'sha256', 'student_type', 'phase', 'step'))
                and entry['samples'] == 4 and entry['parameters'] == 8722048 and entry['dtype'] == 'torch.bfloat16',
                'runtime operator/checkpoint differs from historical joint20')
    if scope == 'full':
        require(result['smoke_ready_sha256'] == sha(a.output / 'SMOKE_READY.json'), 'full case not bound to real-model smoke')


def score_case(a, config, marker, data, tasks, documents, case, scope):
    import torch
    from experiments.pdnn_task_accuracy_20261023.pdnn_score import evaluate_tasks, install_students
    from experiments.pdnn_task_accuracy_20261023.runner import load_model, compare_choices, naive_bf16_cached
    from experiments.qwen_task_accuracy_20261019.task_data import metrics_for
    task = documents[0]['task']
    name = case['name'] + '_' + task
    folder = a.output / scope
    folder.mkdir(parents=True, exist_ok=True)
    path, progress_path, docs_path = (folder / (name + suffix) for suffix in ('.json', '.progress.jsonl', '.documents.jsonl'))
    if path.exists():
        result = read(path)
        validate_case(a, result, documents, case, scope, tasks, marker, data)
        print(json.dumps(dict(event='verified_completed_skip', case=name, scope=scope)), flush=True)
        return result
    require(not progress_path.exists() and not docs_path.exists(), 'partial case exists; do not automatically replay/overwrite: ' + name)
    with progress_path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(dict(event='started', case=name, code_commit=a.code_commit,
            slurm_job_id=os.environ['SLURM_JOB_ID'], utc=datetime.now(timezone.utc).isoformat())) + '\n')
    model = load_model(a)
    bare = {k: v for k, v in case.items() if k != 'name'}
    try:
        identities = install_students(model, marker['checkpoint_inventory']['entries'], 4, a.home,
                                       next(model.parameters()).device) if case['layers'] else []
        recorder = ProgressRecorder(progress_path, documents, lambda r: metrics_for(tasks, r), name)
        torch.cuda.reset_peak_memory_stats(torch.device('cuda:0'))
        result = evaluate_tasks(model, documents, bare, progress=recorder)
        if scope == 'smoke':
            replay = evaluate_tasks(model, documents, bare)
            reversed_docs = copy.deepcopy(documents)
            for row in reversed_docs:
                row['choices_ids'].reverse()
            reversed_scores = evaluate_tasks(model, reversed_docs, bare)
            gates = dict(replay=compare_choices(result['documents'], replay['documents']),
                         option_permutation=compare_choices(result['documents'], reversed_scores['documents'], reverse=True))
            if not case['layers']:
                gates['independent_cached_bf16'] = compare_choices(result['documents'], naive_bf16_cached(model, documents, bare))
            result['smoke_gates'] = gates
        by_id = {r['id']: r for r in documents}
        records = []
        for row in result.pop('documents'):
            original = by_id[row['id']]
            records.append(dict(id=row['id'], task=task, doc_id=original['doc_id'], choices=row['choices'],
                metrics=metrics_for(tasks, dict(original, choices=row['choices']))))
        with docs_path.open('x', encoding='utf-8', newline='\n') as stream:
            for row in sorted(records, key=lambda r: r['doc_id']):
                stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        result.update(profile=PROFILE, status='completed', task=task, case=name, scope=scope, code_commit=a.code_commit,
            configuration=case, n_documents=len(records), metrics={k: sum(r['metrics'][k] for r in records) / len(records)
            for k in ('acc', 'acc_norm')}, document_artifact=artifact(docs_path), progress_artifact=artifact(progress_path),
            preflight_sha256=sha(a.output / 'PREFLIGHT_READY.json'), task_data_sha256=sha(a.output / 'TASK_DATA.json'),
            source_sha256=marker['source_sha256'], model_identity=data['model_identity'], checkpoint_identities=identities,
            environment=dict(environment(a.pin), gpu=torch.cuda.get_device_name(0)), actor=a.actor,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(torch.device('cuda:0')),
            slurm_job_id=os.environ['SLURM_JOB_ID'], command=sys.argv, completed_utc=datetime.now(timezone.utc).isoformat())
        if scope == 'full':
            result['smoke_ready_sha256'] = sha(a.output / 'SMOKE_READY.json')
        validate_case(a, result, documents, case, scope, tasks, marker, data)
        write_new(path, result)
        validate_case(a, read(path), documents, case, scope, tasks, marker, data)
        print(json.dumps(dict(event='completed', case=name, scope=scope, metrics=result['metrics'])), flush=True)
        return result
    finally:
        del model
        torch.cuda.empty_cache()


def verify_smoke(a, config, marker, data, tasks, docs):
    path = a.output / 'SMOKE_READY.json'
    require(path.exists(), 'six actual model smoke cases must pass before full scoring')
    ready = read(path)
    require(ready['profile'] == PROFILE and ready['status'] == 'ready' and ready['code_commit'] == a.code_commit
            and ready['configuration'] == config and ready['source_sha256'] == marker['source_sha256']
            and ready['preflight_sha256'] == sha(a.output / 'PREFLIGHT_READY.json') and len(ready['cases']) == 6,
            'portable smoke identity/coverage differs')
    expected = {(task, kind) for task in TASKS for kind in ('bf16', 'pdnn20_joint1000_s0')}
    seen = set()
    for entry in ready['cases']:
        value = read(checked(entry, a.home, a.output))
        key = (value['task'], value['configuration']['name'])
        require(key in expected and key not in seen, 'unexpected or duplicate smoke case')
        seen.add(key)
        case = variant(0, baseline=key[1] == 'bf16')
        validate_case(a, value, smoke_documents(docs[key[0]]), case, 'smoke', tasks, marker, data)
        gates = value['smoke_gates']
        require(set(gates) == ({'replay', 'option_permutation', 'independent_cached_bf16'} if key[1] == 'bf16'
                              else {'replay', 'option_permutation'}) and all(g['passed'] is True for g in gates.values()),
                'smoke replay/permutation/oracle gate failed')
    require(seen == expected, 'missing real-model smoke case')
    return ready


def smoke(a, config):
    marker, data, tasks, docs = frozen(a, config)
    if (a.output / 'SMOKE_READY.json').exists():
        verify_smoke(a, config, marker, data, tasks, docs)
        return
    artifacts = []
    for task, rows in docs.items():
        for case in (variant(0, True), variant(0)):
            value = score_case(a, config, marker, data, tasks, smoke_documents(rows), case, 'smoke')
            require(all(g['passed'] for g in value['smoke_gates'].values()), 'real-model smoke failed')
            artifacts.append(artifact(a.output / 'smoke' / (value['case'] + '.json')))
    write_new(a.output / 'SMOKE_READY.json', dict(profile=PROFILE, status='ready', code_commit=a.code_commit,
        configuration=config, source_sha256=marker['source_sha256'], preflight_sha256=sha(a.output / 'PREFLIGHT_READY.json'),
        cases=artifacts, scope='six first/longest-document cases are smoke, not task accuracy',
        actor=a.actor, environment=environment(a.pin), created_utc=datetime.now(timezone.utc).isoformat()))
    verify_smoke(a, config, marker, data, tasks, docs)
    print(json.dumps(dict(event='portable_smoke_ready', cases=6)), flush=True)


def full_matrix(config):
    return [(task, case) for task in TASKS for case in [variant(0, True), *[variant(s) for s in config['seeds']]]]


def run(a, config):
    marker, data, tasks, docs = frozen(a, config)
    verify_smoke(a, config, marker, data, tasks, docs)
    matrix = full_matrix(config)
    if a.case:
        matrix = [(task, case) for task, case in matrix if case['name'] + '_' + task == a.case]
        require(len(matrix) == 1, 'unknown portable full-case name')
    for task, case in matrix:
        score_case(a, config, marker, data, tasks, docs[task], case, 'full')


def summarize(a, config):
    marker, data, tasks, docs = frozen(a, config)
    verify_smoke(a, config, marker, data, tasks, docs)
    cases, values = [], {}
    for task, case in full_matrix(config):
        path = a.output / 'full' / (case['name'] + '_' + task + '.json')
        require(path.exists(), 'all twelve complete fresh-BF16/P-DNN cases are required')
        result = read(path)
        validate_case(a, result, docs[task], case, 'full', tasks, marker, data)
        values[(task, case['name'])] = result
        cases.append(dict(case=result['case'], result=artifact(path), metrics=result['metrics'],
            elapsed_seconds=result['elapsed_seconds'], peak_allocated_bytes=result['peak_allocated_bytes']))
    tasks_summary = {}
    for task in TASKS:
        baseline = values[(task, 'bf16')]
        sampled = [values[(task, variant(s)['name'])] for s in config['seeds']]
        tasks_summary[task] = dict(documents=len(docs[task]), fresh_bf16=baseline['metrics'],
            pdnn20={k: dict(seeds=[v['metrics'][k] for v in sampled],
                mean=statistics.mean(v['metrics'][k] for v in sampled),
                inference_seed_sample_std=statistics.stdev(v['metrics'][k] for v in sampled),
                delta_vs_fresh_bf16_percentage_points=100 * (statistics.mean(v['metrics'][k] for v in sampled)
                                                            - baseline['metrics'][k])) for k in ('acc', 'acc_norm')})
    summary = dict(profile=PROFILE, status='completed', code_commit=a.code_commit, configuration=config,
        actor=a.actor, tasks=tasks_summary, cases=cases, full_cases=12, checkpoints=marker['checkpoint_inventory']['entries'],
        identity_reference=artifact(a.pin_path), task_data=artifact(a.output / 'TASK_DATA.json'),
        preflight=artifact(a.output / 'PREFLIGHT_READY.json'), smoke_ready=artifact(a.output / 'SMOKE_READY.json'),
        source_sha256=marker['source_sha256'],
        baseline_scope='Three newly computed BF16 cases; no Issue145 numerical result or server-private file is reused.',
        reference_relation='Model/tokenizer, official task/Harness sources, exact tokenized bytes, subset and MC scoring follow the Issue145 pin. Hardware/software batch arithmetic may differ; compare this fresh baseline.',
        uncertainty='Sample standard deviation of three inference seeds; not a document confidence interval or training-seed variation.',
        limitations=['HellaSwag is the fixed 1000/10042 subset.', 'No training, W8 quantization or sampled Attention.',
                     'GPU software timing/VRAM are not physical p-bit latency, energy, power or area.',
                     'Historical WT2 PPL is not rerun or assumed.'], cross_task_average=None,
        completed_utc=datetime.now(timezone.utc).isoformat())
    write_new(a.output / 'SUMMARY.json', summary)
    files = [p for p in a.output.rglob('*') if p.is_file() and p.name != 'ARTIFACT_MANIFEST.json']
    write_new(a.output / 'ARTIFACT_MANIFEST.json', dict(profile=PROFILE, code_commit=a.code_commit,
        files={p.relative_to(a.output).as_posix(): artifact(p) for p in sorted(files)}))
    print(json.dumps(dict(event='portable_summary_completed', full_cases=12, tasks=tasks_summary)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    for action in ('preflight', 'smoke', 'run', 'summarize'):
        p = commands.add_parser(action)
        for field in ('project-root', 'model', 'task-data', 'checkpoint-dir', 'output', 'config', 'code-commit'):
            p.add_argument('--' + field, required=True)
        if action == 'preflight':
            p.add_argument('--inspect-only', action='store_true')
        if action == 'run':
            p.add_argument('--case')
    args = parser.parse_args()
    config = setup(args)
    outcome = {'preflight': preflight, 'smoke': smoke, 'run': run, 'summarize': summarize}[args.action](args, config)
    if outcome is False:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
