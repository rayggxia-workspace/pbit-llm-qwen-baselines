"""Issue151: gated preparation and evaluation of existing joint20 P-DNN weights.

The historical checkpoint bytes must be supplied by their owner. Inspect-only
preparation never creates a GPU-ready marker and never fabricates predictions.
Issue145 reference data/results are immutable read-only dependencies. Every
compute action requires a verified personal Slurm allocation.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import statistics
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
HOME = Path('/home/Weican_Chen')
PROJECT = HOME / 'projects/pbit-pdnn20-task-accuracy-issue151'
REFERENCE_PROJECT = HOME / 'projects/pbit-pdnn-task-accuracy-issue145'
REFERENCE_COMMIT = 'f4eb25e53834e06220cbfad670ae03195eba8706'
MODEL_SHA = '88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342'
LAYERS = [1, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
TASKS = {
    'piqa': (1838, '4c9f51a5292e593fe5632b28f92c8405171a0102789840f42bd949b804e3a9ab'),
    'arc_easy': (2376, '922c84ada5637d14c1d1483cf8e15c828b0c6051da9be3d2543bc5ff53a26044'),
    'hellaswag': (1000, 'b3bedbdf96e593ddb07a08f71bb7bf5906b85af0953f798e87a517097b1abed0'),
}
HISTORICAL_HASHES = {
    1: '05aec8a47bd55b14d77006c01c32820d1b14f71827b980cebecf76400b2220dc',
    4: '91de63a20e6be59187275871ac85a7542017f6b1bc64a68017b66e0839049c48',
    5: '3d06843b331e531e6d77d8c05458ba0caccd1b954d7454941759440414c8c407',
    6: 'c2ebc7601f4da029406892e70c72714b63ce0a30fb4acb48ec67fba6c4948dfb',
    7: '7eca2b87313181bacff7fbb8a784a9b1f942300fa352402c2b49af229f8f7097',
    8: '56eaa3a6552839ddd33f5f3a4583e806bcba90eedfabf03e6315e6ff3a73962e',
    9: '946a6430ea0f38681e462f0cf3afce8f1c7db126ccb2b4b44dbf4124422768aa',
    10: '9c5c01c96d1333731ad699a1086b0869e5063247bf6cf06838db65e57c14d9a7',
    11: '8e1185c221955930581b329fa99b8ed77a970ed13731c29a84fcb5954e3c8e62',
    12: 'a12cfa7e1e4542911b751fe248e11b619c73c5ce1020f6fa207c5eb958472f37',
    13: '090c117d00f3de0bc96d37bea685d66eb0858a98f3cf2492db699cd2df1a2d55',
    14: 'e609236c9a26f6a9794a916d0975ca801f03f93c8f8ccaf52879e68088a73b98',
    15: 'bcdb1a35e6bebc07cca303d49188f382ea158fcbf256f3ee0f3b9a12c2348325',
    16: 'b1b26202892fad2f6a80ca047e15b92a4b0aca64f2ef062fcbfa08e6844e62ff',
    17: 'f79f82208c61e294ed1ae06d8a5da0e8bf04dc785dd394409a79ae4046c3179b',
    18: '5598e6fe432f45f1dc40d19ac3258d99a152550a4674f43eca5b51c225dbf2d4',
    19: 'e61dc4a5c394ad3c948a5b236568c756342ad4d8ad15fbf1bbe6cef6086528fa',
    20: '798ebae6a9d01711277e31cbb11c189dacd5676b14cf1fe972940ca036689da1',
    21: '0d983aea00541ff24b07af8179440c244c59290c75da501ed56133f6583097e7',
    22: '4b838e81086abf14932738ecbf895d5e76f7ab6a15e4c0e43b5dc502d86fe4fc',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def jsonlines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def artifact(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def personal(path, root=HOME, exists=True):
    """Resolve before use; ownership of the nearest existing parent is required."""
    path, root = Path(path).resolve(strict=exists), Path(root).resolve(strict=True)
    require(path.is_relative_to(root) and path != root, 'path leaves approved personal root: ' + str(path))
    parent = path
    while not parent.exists():
        parent = parent.parent
    require(hasattr(os, 'getuid') and parent.stat().st_uid == os.getuid(), 'personal ownership not verified: ' + str(parent))
    return path


def checked_artifact(entry, root=HOME):
    path = personal(entry['path'], root)
    require(path.is_file() and path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'],
            'artifact byte identity changed: ' + str(path))
    return path


def validate_config(config):
    expected = dict(protocol_version=1, model_weight_sha256=MODEL_SHA, layers=LAYERS,
                    samples=4, seeds=[0, 1, 2], batch=16, context=2048,
                    expected_checkpoint_manifest='checkpoints.expected.json')
    require(config == expected, 'Issue151 requires the exact historical joint20 configuration')
    return config


def validate_expected(entries):
    require(isinstance(entries, list) and len(entries) == 20 and [e['layer'] for e in entries] == LAYERS,
            'expected manifest must list exactly the twenty historical layers in order')
    for entry in entries:
        i = entry['layer']
        expected = dict(layer=i, bytes=34893765 if i < 10 else 34893775, sha256=HISTORICAL_HASHES[i],
                        relative_path=f'results/joint_full_path_pdnn_layers1_22_twenty_v1/best_layer{i}.pt',
                        student_type='full_path_bipolar_pdnn_v1', phase='joint_end_to_end_distillation', step=1000)
        require(entry == expected, 'expected manifest is not historical joint20: layer ' + str(i))
    return entries


def checkpoint_entries(expected, directory):
    return [dict(layer=e['layer'], path=str(Path(directory) / PurePosixPath(e['relative_path']).name),
                 bytes=e['bytes'], sha256=e['sha256'], phase=e['phase'], step=e['step'],
                 student_type=e['student_type']) for e in expected]


def checkpoint_inventory(entries, strict=False):
    missing, present, loaded = [], [], []
    for entry in entries:
        path = personal(entry['path'], PROJECT, exists=False)
        if not path.exists():
            missing.append(dict(layer=entry['layer'], path=str(path), expected_sha256=entry['sha256']))
            continue
        checked_artifact(entry, PROJECT)
        present.append(dict(entry))
    if strict and not missing:
        from dataclasses import asdict
        import torch
        from experiments.pdnn_ffn.full_path_pdnn_ffn import FullPathPBitFFN, FullPathPBitFFNConfig
        for entry in present:
            payload = torch.load(entry['path'], map_location='cpu', weights_only=True)
            require(payload.get('student_type') == entry['student_type']
                    and payload.get('phase') == entry['phase'] and payload.get('step') == entry['step']
                    and payload.get('training_args', {}).get('layer') == entry['layer'],
                    'checkpoint training identity differs: ' + str(entry['layer']))
            cfg = dict(payload['student_config'])
            cfg['hidden_sizes'] = tuple(cfg['hidden_sizes'])
            cfg = FullPathPBitFFNConfig(**cfg)
            effective = asdict(cfg)
            require(cfg.input_size == cfg.output_size == 896 and cfg.hidden_sizes == (4864,)
                    and cfg.input_temperature == .25 and cfg.hidden_temperature == 1.
                    and cfg.coding == 'bipolar' and cfg.architecture == 'serial' and cfg.input_encoding == 'sigmoid'
                    and cfg.input_bits == 1 and cfg.learnable_encoding is False,
                    'historical serial bipolar two-matrix architecture required')
            state = payload['student_state_dict']
            require(isinstance(state, dict) and all(isinstance(v, torch.Tensor) and v.is_floating_point()
                    and torch.isfinite(v).all().item() for v in state.values()), 'nonfinite or nonfloating checkpoint state')
            student = FullPathPBitFFN(cfg)
            student.load_state_dict(state, strict=True)
            require(sum(v.numel() for v in student.parameters()) == 8722048, 'checkpoint parameter count differs')
            checked_artifact(entry, PROJECT)
            loaded.append(dict(entry, strict_state_loaded=True, source_student_config=payload['student_config'],
                               effective_student_config=effective, parameters=8722048, inspection_device='cpu'))
            del payload, student
    return dict(expected=20, present=len(present), missing=missing, entries=present, inspected=loaded,
                all_checkpoint_bytes_present=len(present) == 20,
                all_strict_states_loaded=len(loaded) == 20)


def preparation_state(inventory, missing_baselines, inspect_only):
    ready = (not inspect_only and inventory['all_checkpoint_bytes_present']
             and inventory['all_strict_states_loaded'] and not missing_baselines)
    waiting = []
    if inventory['missing']:
        waiting.append('twenty historical checkpoint files have not all been supplied')
    if missing_baselines:
        waiting.append('the three matching Issue145 BF16 task cases are not all completed')
    if inspect_only:
        waiting.append('inspect-only cannot establish CPU readiness or authorize a GPU stage')
    return dict(status='ready' if ready else 'awaiting_external_inputs', gpu_allowed=ready, waiting=waiting)


def sources():
    areas = [HERE, REPO / 'experiments/pdnn_ffn',
             REPO / 'experiments/pdnn_task_accuracy_20261023/pdnn_score.py',
             REPO / 'experiments/pdnn_task_accuracy_20261023/runner.py',
             REPO / 'experiments/qwen_task_accuracy_20261019/task_data.py']
    paths = set()
    for area in areas:
        paths.update([area] if area.is_file() else [p for p in area.rglob('*') if p.is_file()
                     and p.suffix in ('.py', '.json', '.md', '.sbatch', '.sh') and '__pycache__' not in p.parts])
    return {p.relative_to(REPO).as_posix(): sha(p) for p in sorted(paths)}


def environment():
    import torch
    import transformers
    require(importlib.metadata.version('lm_eval') == '0.4.8' and transformers.__version__ == '4.45.2',
            'Issue145-matched lm_eval0.4.8 and Transformers4.45.2 required')
    return dict(python=sys.version, executable=sys.executable, torch=torch.__version__,
                transformers=transformers.__version__, lm_eval=importlib.metadata.version('lm_eval'),
                cuda=torch.version.cuda, slurm_job_id=os.environ['SLURM_JOB_ID'],
                cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES', ''), hostname=os.uname().nodename)


def setup(a):
    import pwd
    account = pwd.getpwuid(os.getuid())
    require(account.pw_name == getpass.getuser() == 'Weican_Chen'
            and Path(account.pw_dir).resolve(strict=True) == HOME and Path.home().resolve(strict=True) == HOME,
            'verified Weican_Chen canonical personal home required')
    require(os.environ.get('SLURM_JOB_ID'), 'computation requires an explicit Slurm allocation')
    cpu = a.action in ('preflight', 'summarize')
    visible = os.environ.get('CUDA_VISIBLE_DEVICES', '')
    require(visible == '' if cpu else visible not in ('', '-1', 'NoDevFiles'), 'CPU/GPU allocation visibility mismatch')
    a.project = personal(a.project_root)
    require(a.project == PROJECT and REPO.resolve(strict=True).is_relative_to(a.project), 'execute an immutable Issue151 snapshot')
    a.model = personal(a.model)
    a.task_data = personal(a.task_data, REFERENCE_PROJECT)
    a.reference_run = personal(a.reference_run, REFERENCE_PROJECT / 'runs')
    a.checkpoint_dir = personal(a.checkpoint_dir, a.project, exists=False)
    require(a.checkpoint_dir == a.project / 'checkpoints/joint20', 'explicit Issue151 personal checkpoint staging path required')
    a.config = personal(a.config, a.project)
    a.output = personal(a.output, a.project, exists=False)
    require(a.output.is_relative_to(a.project / 'runs') and a.output != a.project / 'runs'
            and not a.output.is_relative_to(REPO), 'outputs require a separate personal Issue151 run directory')
    require(re.fullmatch('[0-9a-f]{40}', a.code_commit), 'exact execution code commit required')
    config = validate_config(read(a.config))
    a.expected_path = personal(a.config.parent / config['expected_checkpoint_manifest'], a.project)
    a.expected = validate_expected(read(a.expected_path))
    # All paths and ownership are checked before these personal writes.
    for key, suffix in {'HF_HOME': 'cache/hf', 'HF_HUB_CACHE': 'cache/hf/hub',
            'HF_DATASETS_CACHE': 'cache/hf/datasets', 'HF_MODULES_CACHE': 'cache/hf/modules',
            'XDG_CACHE_HOME': 'cache/xdg', 'TORCH_HOME': 'cache/torch',
            'PYTORCH_KERNEL_CACHE_PATH': 'cache/torch/kernels', 'TMPDIR': 'tmp'}.items():
        value = personal(a.project / suffix, a.project, exists=False)
        value.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(value)
    os.environ.update(HF_HUB_OFFLINE='1', HF_DATASETS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    a.output.mkdir(parents=True, exist_ok=True)
    return config


def model_identity(a):
    from experiments.pdnn_task_accuracy_20261023.runner import model_identity as identity
    a.home = HOME
    return identity(a, dict(model_weight_sha256=MODEL_SHA))


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def verify_execution(result, documents, selected):
    audit = result['execution_audit']
    targets = sum(len(c) for r in documents for c in r['choices_ids'])
    require(audit['completed_documents'] == len(documents)
            and audit['scored_choice_tokens'] == audit['original_tokenized_requests'] == targets
            and audit['replaced_layers'] == selected
            and audit['shared_first_query_rows'] == len(documents)
            and audit['every_scored_target_used_24_decoder_ffn_layers'] is True,
            'scored request/replacement/decode coverage differs')
    for phase in ('prefill', 'decode'):
        calls = audit[f'actual_{phase}_calls']
        require(type(calls) is int and calls > 0, 'missing actual model execution')
        for module in ('decoder', 'ffn'):
            require(audit[f'{module}_{phase}_calls_per_layer'] == [calls] * 24, 'not all 24 layers executed')
        require(audit[f'replaced_{phase}_calls'] == {str(i): calls for i in selected}, 'P-DNN module execution missing')
    require(audit['actual_decode_query_rows'] == audit['shared_first_query_rows'] + audit['branch_query_rows']
            + audit['dummy_query_rows'], 'decode row arithmetic differs')


def verify_saved_metrics(result, documents, read_artifact, metric_function):
    """Audit immutable final/progress originals against the official requests."""
    rows = jsonlines(read_artifact(result['document_artifact']))
    expected = {r['id']: r for r in documents}
    require(len(rows) == result['n_documents'] == len(expected) and len({r['id'] for r in rows}) == len(rows)
            and {r['id'] for r in rows} == set(expected), 'saved document count/identity differs')
    for row in rows:
        source = expected[row['id']]
        require(row['task'] == source['task'] and row['doc_id'] == source['doc_id'], 'official document/gold alignment differs')
        require(len(row['choices']) == len(source['choices_ids']), 'choice count differs')
        for choice, ids in zip(row['choices'], source['choices_ids']):
            require(type(choice['tokens']) is int and choice['tokens'] == len(ids)
                    and type(choice['is_greedy']) is bool and finite(choice['logprob']) and choice['logprob'] <= 1e-5,
                    'choice score/token alignment differs')
        require(set(row['metrics']) == {'acc', 'acc_norm'} and all(type(v) in (int, float) and v in (0, 1)
                for v in row['metrics'].values()), 'saved metrics must be binary official outcomes')
        require(row['metrics'] == metric_function(dict(source, choices=row['choices'])), 'official process_results readback differs')
    means = {k: sum(r['metrics'][k] for r in rows) / len(rows) for k in ('acc', 'acc_norm')}
    require(means == result['metrics'], 'saved aggregate differs from per-document outcomes')
    progress = jsonlines(read_artifact(result['progress_artifact']))
    require(progress and progress[0].get('event') == 'started' and progress[0]['case'] == result['case']
            and progress[0]['code_commit'] == result['code_commit'], 'missing started progress claim')
    completed = progress[1:]
    require(len(completed) == len(rows) and len({r['id'] for r in completed}) == len(rows)
            and {r['id']: r for r in completed} == {r['id']: r for r in rows}, 'progress/final per-document evidence differs')
    return means


class ProgressRecorder:
    """Persist stable IDs and official outcomes without assuming scorer stats."""
    def __init__(self, path, documents, metric_function, case):
        self.path, self.by_id = Path(path), {r['id']: r for r in documents}
        self.metric_function, self.case, self.completed = metric_function, case, 0

    def __call__(self, update):
        with self.path.open('a', encoding='utf-8', newline='\n') as stream:
            for row in update['documents']:
                source = self.by_id[row['id']]
                stream.write(json.dumps(dict(id=row['id'], task=source['task'], doc_id=source['doc_id'],
                    choices=row['choices'], metrics=self.metric_function(dict(source, choices=row['choices']))),
                    separators=(',', ':')) + '\n')
        self.completed += len(update['documents'])
        print(json.dumps(dict(event='progress', case=self.case, completed=self.completed,
                              elapsed_seconds=update['elapsed_seconds'])), flush=True)


def reference_inputs(a, current_model):
    from experiments.qwen_task_accuracy_20261019.task_data import load_tasks, harness_sources, metrics_for
    meta_path = personal(a.reference_run / 'TASK_DATA.json', REFERENCE_PROJECT)
    meta = read(meta_path)
    require(meta['status'] == 'completed' and meta['code_commit'] == REFERENCE_COMMIT
            and set(meta['tokenized']) == set(TASKS) and meta['num_fewshot'] == 0 and meta['chat_template'] is False,
            'Issue145 reference run/version/protocol differs')
    checked_artifact(meta['config'], REFERENCE_PROJECT)
    require(meta['model'] == current_model, 'current model/tokenizer differs from reference BF16')
    current_environment = environment()
    require(all(meta['environment'].get(key) == current_environment[key]
                for key in ('python', 'torch', 'transformers', 'lm_eval', 'cuda')),
            'execution runtime differs from the matching Issue145 BF16 environment')
    require(meta['harness_sources'] == harness_sources(), 'installed official Harness sources differ from Issue145')
    tasks, identity = load_tasks(a.task_data)
    require(identity == meta['tasks'], 'official task/parquet identities differ from Issue145')
    for entry in identity.values():
        path = personal(entry['dataset_path'], REFERENCE_PROJECT)
        require(path.stat().st_size == entry['dataset_bytes'] and sha(path) == entry['dataset_sha256'], 'dataset parquet changed')
    ref_snapshot = Path(meta['config']['path']).parents[2]
    for relative, checksum in meta['source_sha256'].items():
        rel = PurePosixPath(relative)
        require(not rel.is_absolute() and '..' not in rel.parts and '\\' not in relative, 'unsafe reference source path')
        path = personal(ref_snapshot.joinpath(*rel.parts), REFERENCE_PROJECT)
        require(sha(path) == checksum, 'frozen Issue145 execution source changed: ' + relative)
    docs = {}
    for task, (count, ids_sha) in TASKS.items():
        rows = jsonlines(checked_artifact(meta['tokenized'][task], a.reference_run))
        ids = [r['doc_id'] for r in rows]
        require(len(rows) == count and len({r['id'] for r in rows}) == count
                and hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest() == ids_sha
                == meta['statistics'][task]['selected_doc_ids_sha256'], 'frozen task document IDs differ')
        require(all(r['id'] == f"{task}:{r['doc_id']}" and r['task'] == task for r in rows), 'task request identity differs')
        docs[task] = rows
    ready_path = a.reference_run / 'READY.json'
    missing, baselines, bindings = [], {}, [artifact(meta_path), meta['config'], *meta['tokenized'].values()]
    ready = None
    if ready_path.exists():
        ready = read(ready_path)
        require(ready['status'] == 'ready' and ready['code_commit'] == REFERENCE_COMMIT
                and ready['task_data_sha256'] == sha(meta_path) and ready['source_sha256'] == meta['source_sha256']
                and len(ready['cases']) == 9, 'reference real-GPU READY binding differs')
        bindings.append(artifact(ready_path))
        smoke_names = set()
        for item in ready['cases']:
            path = checked_artifact(item, a.reference_run)
            result = read(path)
            require(result['status'] == 'completed' and result['code_commit'] == REFERENCE_COMMIT
                    and result['task_data_sha256'] == sha(meta_path)
                    and all(g['passed'] for g in result['smoke_gates'].values()), 'reference smoke gate incomplete')
            require(result['case'] not in smoke_names, 'duplicate reference smoke case')
            smoke_names.add(result['case'])
            checked_artifact(result['document_artifact'], a.reference_run)
            checked_artifact(result['progress_artifact'], a.reference_run)
            bindings += [item, result['document_artifact'], result['progress_artifact']]
    else:
        missing.append('reference READY.json')
    for task, rows in docs.items():
        path = a.reference_run / 'full' / ('bf16_' + task + '.json')
        if not path.exists():
            missing.append('bf16_' + task)
            continue
        require(ready is not None, 'completed reference BF16 without READY')
        result = read(path)
        expected_variant = dict(name='bf16', layers=[], samples=4, seed=0, batch=16, context=2048)
        require(result['status'] == 'completed' and result['scope'] == 'full' and result['task'] == task
                and result['case'] == 'bf16_' + task and result['configuration'] == expected_variant
                and result['code_commit'] == REFERENCE_COMMIT and result['source_sha256'] == meta['source_sha256']
                and result['config'] == meta['config'] and result['task_data_sha256'] == sha(meta_path)
                and result['ready_sha256'] == sha(ready_path) and result['checkpoint_identities'] == []
                and result['model_identity'] == current_model and result['training'] is False,
                'reference BF16 configuration/model/data/source differs')
        means = verify_saved_metrics(result, rows, lambda e: checked_artifact(e, a.reference_run),
                                     lambda r: metrics_for(tasks, r))
        verify_execution(result, rows, [])
        baselines[task] = dict(case='bf16_' + task, n_documents=len(rows), metrics=means, result=artifact(path),
                               document_artifact=result['document_artifact'], progress_artifact=result['progress_artifact'])
        bindings += [artifact(path), result['document_artifact'], result['progress_artifact']]
    return dict(reference_task_data=artifact(meta_path), reference_code_commit=REFERENCE_COMMIT,
                reference_run=str(a.reference_run), reference_ready=artifact(ready_path) if ready else None,
                tasks=identity, tokenized=meta['tokenized'], statistics=meta['statistics'],
                harness_sources=meta['harness_sources'], baselines=baselines,
                missing_baselines=missing, bound_artifacts=bindings), tasks, docs


def preflight(a, config):
    marker = a.output / ('PREPARATION_ONLY.json' if a.inspect_only else 'PREFLIGHT_READY.json')
    require(not marker.exists(), 'preflight evidence already exists; use a new output tag or verify the strict frozen marker')
    model = model_identity(a)
    reference, _, _ = reference_inputs(a, model)
    entries = checkpoint_entries(a.expected, a.checkpoint_dir)
    inventory = checkpoint_inventory(entries, strict=not a.inspect_only)
    state = preparation_state(inventory, reference['missing_baselines'], a.inspect_only)
    result = dict(state, issue=151, action='preflight', inspect_only=a.inspect_only,
                  code_commit=a.code_commit, config=artifact(a.config), configuration=config,
                  expected_checkpoint_manifest=artifact(a.expected_path), source_sha256=sources(),
                  model_identity=model, reference=reference, checkpoint_inventory=inventory,
                  checkpoints=entries, environment=environment(), training=False,
                  raw_data_copied=False, reference_data_modified=False,
                  created_utc=datetime.now(timezone.utc).isoformat())
    if state['gpu_allowed']:
        write_new(a.output / 'PREFLIGHT_READY.json', result)
    else:
        write_new(a.output / 'PREPARATION_ONLY.json', result)
    print(json.dumps(dict(event='preflight', status=state['status'], gpu_allowed=state['gpu_allowed'],
                          missing_checkpoint_layers=[e['layer'] for e in inventory['missing']],
                          waiting=state['waiting']), ensure_ascii=False), flush=True)
    return state['gpu_allowed'] or a.inspect_only


def frozen(a, config):
    path = a.output / 'PREFLIGHT_READY.json'
    require(path.exists(), 'strict PREFLIGHT_READY.json required; PREPARATION_ONLY never enables GPU evaluation')
    meta = read(path)
    require(meta['status'] == 'ready' and meta['gpu_allowed'] is True and meta['inspect_only'] is False
            and meta['code_commit'] == a.code_commit and meta['configuration'] == config
            and meta['source_sha256'] == sources(), 'strict preparation/config/execution sources changed')
    require(meta['checkpoint_inventory']['all_strict_states_loaded'] is True
            and len(meta['checkpoint_inventory']['inspected']) == 20, 'all twenty CPU strict-state gates required')
    checked_artifact(meta['config'], a.project)
    checked_artifact(meta['expected_checkpoint_manifest'], a.project)
    require(meta['checkpoints'] == checkpoint_entries(a.expected, a.checkpoint_dir), 'checkpoint staging directory changed')
    for entry in meta['checkpoints']:
        checked_artifact(entry, a.project)
    model = model_identity(a)
    require(model == meta['model_identity'], 'base model/tokenizer changed after preflight')
    for entry in meta['reference']['bound_artifacts']:
        checked_artifact(entry, REFERENCE_PROJECT)
    reference, tasks, docs = reference_inputs(a, model)
    require(not reference['missing_baselines'] and reference == meta['reference'], 'reference baselines/input freeze changed')
    return meta, tasks, docs


def variant(seed, baseline=False):
    return dict(name='bf16' if baseline else f'pdnn20_joint1000_s{seed}',
                layers=[] if baseline else LAYERS, samples=4, seed=seed, batch=16, context=2048)


def validate_case(a, result, documents, case, scope, tasks, meta):
    from experiments.qwen_task_accuracy_20261019.task_data import metrics_for
    name = case['name'] + '_' + documents[0]['task']
    require(result['status'] == 'completed' and result['scope'] == scope and result['case'] == name
            and result['configuration'] == case and result['variant'] == {k: v for k, v in case.items() if k != 'name'}
            and result['code_commit'] == a.code_commit and result['source_sha256'] == meta['source_sha256']
            and result['preflight_sha256'] == sha(a.output / 'PREFLIGHT_READY.json')
            and result['model_identity'] == meta['model_identity'] and result['training'] is False,
            'existing case does not match frozen execution')
    verify_saved_metrics(result, documents, lambda e: checked_artifact(e, a.output), lambda r: metrics_for(tasks, r))
    verify_execution(result, documents, case['layers'])
    actual = result['checkpoint_identities']
    require([e['layer'] for e in actual] == case['layers'], 'runtime checkpoint coverage differs')
    expected = {e['layer']: e for e in meta['checkpoints']}
    for entry in actual:
        original = expected[entry['layer']]
        require(all(entry[k] == original[k] for k in ('layer', 'path', 'bytes', 'sha256', 'phase', 'step', 'student_type'))
                and entry['samples'] == 4 and entry['parameters'] == 8722048 and entry['dtype'] == 'torch.bfloat16',
                'runtime P-DNN identities differ from frozen historical checkpoints')
    if scope == 'full':
        require(result['smoke_ready_sha256'] == sha(a.output / 'SMOKE_READY.json'), 'case not bound to strict smoke gate')


def score_case(a, config, meta, tasks, documents, case, scope):
    import torch
    from experiments.pdnn_task_accuracy_20261023.pdnn_score import evaluate_tasks, install_students
    from experiments.pdnn_task_accuracy_20261023.runner import load_model, compare_choices, naive_bf16_cached
    from experiments.qwen_task_accuracy_20261019.task_data import metrics_for
    task = documents[0]['task']
    name = case['name'] + '_' + task
    directory = a.output / scope
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name + '.json')
    progress_path = directory / (name + '.progress.jsonl')
    document_path = directory / (name + '.documents.jsonl')
    if path.exists():
        result = read(path)
        validate_case(a, result, documents, case, scope, tasks, meta)
        print(json.dumps(dict(event='verified_completed_skip', case=name, scope=scope)), flush=True)
        return result
    require(not progress_path.exists() and not document_path.exists(), 'partial case exists; never automatically replay/overwrite: ' + name)
    with progress_path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(dict(event='started', case=name, code_commit=a.code_commit,
                                    slurm_job_id=os.environ['SLURM_JOB_ID'], utc=datetime.now(timezone.utc).isoformat())) + '\n')
    model = load_model(a)
    bare = {k: v for k, v in case.items() if k != 'name'}
    identities = []
    try:
        if case['layers']:
            identities = install_students(model, meta['checkpoints'], case['samples'], HOME, next(model.parameters()).device)
        by_id = {r['id']: r for r in documents}
        progress = ProgressRecorder(progress_path, documents, lambda row: metrics_for(tasks, row), name)
        torch.cuda.reset_peak_memory_stats(torch.device('cuda:0'))
        result = evaluate_tasks(model, documents, bare, progress=progress)
        if scope == 'smoke':
            replay = evaluate_tasks(model, documents, bare)
            permuted_documents = copy.deepcopy(documents)
            for row in permuted_documents:
                row['choices_ids'].reverse()
            permutation = evaluate_tasks(model, permuted_documents, bare)
            gates = dict(replay=compare_choices(result['documents'], replay['documents']),
                         option_permutation=compare_choices(result['documents'], permutation['documents'], reverse=True))
            if not case['layers']:
                gates['independent_cached_bf16'] = compare_choices(result['documents'], naive_bf16_cached(model, documents, bare))
            result['smoke_gates'] = gates
        records = []
        for item in result.pop('documents'):
            source = by_id[item['id']]
            records.append(dict(id=item['id'], task=task, doc_id=source['doc_id'], choices=item['choices'],
                                metrics=metrics_for(tasks, dict(source, choices=item['choices']))))
        with document_path.open('x', encoding='utf-8', newline='\n') as stream:
            for row in sorted(records, key=lambda r: r['doc_id']):
                stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        result.update(status='completed', task=task, case=name, scope=scope, code_commit=a.code_commit,
            configuration=case, n_documents=len(records), metrics={k: sum(r['metrics'][k] for r in records) / len(records)
            for k in ('acc', 'acc_norm')}, document_artifact=artifact(document_path), progress_artifact=artifact(progress_path),
            preflight_sha256=sha(a.output / 'PREFLIGHT_READY.json'), config=artifact(a.config), source_sha256=sources(),
            model_identity=meta['model_identity'], checkpoint_identities=identities,
            reference_task_data=meta['reference']['reference_task_data'], environment=dict(environment(), gpu=torch.cuda.get_device_name(0)),
            peak_allocated_bytes=torch.cuda.max_memory_allocated(torch.device('cuda:0')),
            command=sys.argv, slurm_job_id=os.environ['SLURM_JOB_ID'], completed_utc=datetime.now(timezone.utc).isoformat())
        if scope == 'full':
            result['smoke_ready_sha256'] = sha(a.output / 'SMOKE_READY.json')
        validate_case(a, result, documents, case, scope, tasks, meta)
        write_new(path, result)
        validate_case(a, read(path), documents, case, scope, tasks, meta)
        print(json.dumps(dict(event='completed', case=name, scope=scope, metrics=result['metrics'])), flush=True)
        return result
    finally:
        del model
        torch.cuda.empty_cache()


def verify_smoke(a, config, meta, tasks, docs):
    path = a.output / 'SMOKE_READY.json'
    require(path.exists(), 'six real-model smoke cases must pass before any full evaluation')
    ready = read(path)
    require(ready['status'] == 'ready' and ready['code_commit'] == a.code_commit
            and ready['source_sha256'] == meta['source_sha256'] and ready['configuration'] == config
            and ready['preflight_sha256'] == sha(a.output / 'PREFLIGHT_READY.json') and len(ready['cases']) == 6,
            'strict smoke marker binding/coverage differs')
    seen = set()
    for entry in ready['cases']:
        path = checked_artifact(entry, a.output)
        value = read(path)
        task, case = value['task'], value['configuration']
        require(task in TASKS and case in (variant(0, True), variant(0)), 'unexpected smoke case')
        key = (task, case['name'])
        require(key not in seen, 'duplicate smoke case')
        seen.add(key)
        requested = smoke_documents(docs[task])
        validate_case(a, value, requested, case, 'smoke', tasks, meta)
        gates = value['smoke_gates']
        require(set(gates) == ({'replay', 'option_permutation', 'independent_cached_bf16'} if not case['layers']
                              else {'replay', 'option_permutation'}) and all(g['passed'] for g in gates.values()),
                'required real-model replay/permutation/oracle gate failed')
    require(len(seen) == 6, 'three BF16 plus three P-DNN real-model smoke cases required')
    return ready


def smoke_documents(rows):
    selected = {rows[0]['id'], max(rows, key=lambda r: (len(r['context_ids']), r['id']))['id']}
    return [r for r in rows if r['id'] in selected]


def smoke(a, config):
    meta, tasks, docs = frozen(a, config)
    if (a.output / 'SMOKE_READY.json').exists():
        verify_smoke(a, config, meta, tasks, docs)
        print(json.dumps(dict(event='verified_smoke_ready_skip')), flush=True)
        return
    records = []
    for task, rows in docs.items():
        for case in (variant(0, True), variant(0)):
            value = score_case(a, config, meta, tasks, smoke_documents(rows), case, 'smoke')
            require(all(g['passed'] for g in value['smoke_gates'].values()), 'real-model smoke gate failed')
            records.append(artifact(a.output / 'smoke' / (value['case'] + '.json')))
    write_new(a.output / 'SMOKE_READY.json', dict(status='ready', code_commit=a.code_commit, configuration=config,
        source_sha256=meta['source_sha256'], preflight_sha256=sha(a.output / 'PREFLIGHT_READY.json'), cases=records,
        scope='first plus longest prompt per task; six smoke cases are not task accuracy', environment=environment(),
        created_utc=datetime.now(timezone.utc).isoformat()))
    verify_smoke(a, config, meta, tasks, docs)
    print(json.dumps(dict(event='smoke_ready', cases=6)), flush=True)


def run(a, config):
    meta, tasks, docs = frozen(a, config)
    verify_smoke(a, config, meta, tasks, docs)
    cases = [(task, variant(seed)) for task in TASKS for seed in config['seeds']]
    if a.case:
        cases = [(task, v) for task, v in cases if v['name'] + '_' + task == a.case]
        require(len(cases) == 1, 'unknown full-case name')
    for task, case in cases:
        score_case(a, config, meta, tasks, docs[task], case, 'full')


def summarize(a, config):
    meta, tasks, docs = frozen(a, config)
    verify_smoke(a, config, meta, tasks, docs)
    results, metrics = [], {}
    for task in TASKS:
        values = []
        for seed in config['seeds']:
            case = variant(seed)
            path = a.output / 'full' / (case['name'] + '_' + task + '.json')
            require(path.exists(), 'all nine full cases must finish before summarizing')
            value = read(path)
            validate_case(a, value, docs[task], case, 'full', tasks, meta)
            values.append(value)
            results.append(dict(case=value['case'], result=artifact(path), metrics=value['metrics'],
                                elapsed_seconds=value['elapsed_seconds'], peak_allocated_bytes=value['peak_allocated_bytes']))
        base = meta['reference']['baselines'][task]
        metrics[task] = dict(documents=len(docs[task]), baseline=base,
            metrics={key: dict(seeds=[v['metrics'][key] for v in values],
                mean=statistics.mean(v['metrics'][key] for v in values),
                inference_seed_sample_std=statistics.stdev(v['metrics'][key] for v in values),
                delta_vs_reference_bf16_percentage_points=100 * (statistics.mean(v['metrics'][key] for v in values)
                                                               - base['metrics'][key])) for key in ('acc', 'acc_norm')})
    summary = dict(status='completed', issue=151, code_commit=a.code_commit, configuration=config,
        preflight=artifact(a.output / 'PREFLIGHT_READY.json'), smoke_ready=artifact(a.output / 'SMOKE_READY.json'),
        source_sha256=meta['source_sha256'], checkpoint_manifest=meta['expected_checkpoint_manifest'],
        checkpoints=meta['checkpoints'], tasks=metrics, cases=results, n_full_cases=9,
        uncertainty='Sample standard deviation across three inference seeds, not document sampling error or training-seed variation.',
        limitations=['HellaSwag is the fixed 1000/10042 subset, not the full split.',
                     'No training or W8 quantization; original Attention is unchanged.',
                     'Software inference time/VRAM is not physical p-bit latency, energy, power or area.',
                     'Historical WT2 PPL is not rerun or assumed for these task results.'],
        cross_task_average=None, completed_utc=datetime.now(timezone.utc).isoformat())
    write_new(a.output / 'SUMMARY.json', summary)
    files = [p for p in a.output.rglob('*') if p.is_file() and p.name != 'ARTIFACT_MANIFEST.json']
    write_new(a.output / 'ARTIFACT_MANIFEST.json', dict(code_commit=a.code_commit,
        files={p.relative_to(a.output).as_posix(): artifact(p) for p in sorted(files)},
        immutable_read_only_reference_artifacts=meta['reference']['bound_artifacts']))
    print(json.dumps(dict(event='summary_completed', full_cases=9, tasks=metrics)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('preflight', 'smoke', 'run', 'summarize'):
        p = sub.add_parser(action)
        for name in ('project-root', 'model', 'task-data', 'reference-run', 'checkpoint-dir', 'output', 'config', 'code-commit'):
            p.add_argument('--' + name, required=True)
        if action == 'preflight':
            p.add_argument('--inspect-only', action='store_true')
        if action == 'run':
            p.add_argument('--case')
    args = parser.parse_args()
    config = setup(args)
    environment()
    outcome = {'preflight': preflight, 'smoke': smoke, 'run': run, 'summarize': summarize}[args.action](args, config)
    if outcome is False:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
