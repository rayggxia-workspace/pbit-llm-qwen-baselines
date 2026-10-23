"""Separate, pinned benchmark supplement; never rewrites a quality snapshot.

The freeze/validation helpers are standard-library only. GPU execution delegates
to benchmark.run_benchmark unchanged and requires an existing Slurm allocation.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys

MODEL = 'Qwen/Qwen3-4B'
REVISION = '1cfa9a7208912126459214e8b04321603b3df60c'
CONFIG = dict(r=32, k_total=128, local_total=32, reallocation=False,
              selection='probability_sum', validate_finite=False)
SHAPE = dict(num_hidden_layers=36, hidden_size=2560, num_attention_heads=32,
             num_key_value_heads=8, head_dim=128, intermediate_size=9728)
SCHEDULE = dict(contexts=[128, 512, 2048], decode_lengths=[64, 128],
                modes=['native', 'dense', 'sparq'], warmup=1, repeats=3, power_interval_s=.02)
MODEL_FILES = {'config.json', 'generation_config.json', 'merges.txt',
    'model-00001-of-00003.safetensors', 'model-00002-of-00003.safetensors',
    'model-00003-of-00003.safetensors', 'model.safetensors.index.json',
    'tokenizer.json', 'tokenizer_config.json', 'vocab.json'}
REQUIRED = {'qwen3/sparq/' + name for name in (
    'bench_only.py', 'benchmark.py', 'core.py', 'adapter.py', 'run.py', 'scoring.py',
    'task_data.py', 'batch_scoring.py', 'SOURCES.json', 'model_identity.json')}
REQUIRED.add('qwen3/stochastic/vendor/scoring.py')
BUNDLE_FILES = REQUIRED | {'qwen3/sparq/test_bench_only.py', 'qwen3/sparq/BENCH_ONLY_ZH.md'}
UNCHANGED_NUMERICS = {'qwen3/sparq/core.py', 'qwen3/sparq/adapter.py',
                      'qwen3/stochastic/vendor/scoring.py'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def inside(path, root, *, exists=True):
    root = Path(root).resolve(strict=True)
    target = Path(path).resolve(strict=exists)
    if not target.is_relative_to(root):
        raise ValueError('path escapes its declared root: ' + str(path))
    return target


def validate_manifest(tree, manifest):
    files = manifest.get('files', {})
    if manifest.get('purpose') != 'benchmark_supplement' or set(files) != BUNDLE_FILES:
        raise ValueError('supplement source manifest has missing/unexpected dependencies')
    if not re.fullmatch('[0-9a-f]{40}', manifest.get('commit', '')):
        raise ValueError('full source commit required')
    for name, digest in files.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name:
            raise ValueError('noncanonical source path')
        target = inside(Path(tree) / name, tree)
        if not target.is_file() or sha(target) != digest:
            raise ValueError('source digest differs: ' + name)
    return manifest


def freeze(repo, output):
    """Export only committed fixed dependencies; no model/data/logs/credentials."""
    repo, output = Path(repo).resolve(strict=True), Path(output).resolve()
    if output.exists():
        raise ValueError('bundle destination already exists')
    def git(*args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout
    commit = git('rev-parse', 'HEAD').decode().strip()
    if git('status', '--porcelain', '--untracked-files=all', '--', *sorted(BUNDLE_FILES)).strip():
        raise ValueError('commit the supplement and its dependencies before freezing')
    blobs = {name: git('show', commit + ':' + name) for name in sorted(BUNDLE_FILES)}
    manifest = dict(schema=1, purpose='benchmark_supplement', commit=commit,
                    repo='rayggxia-workspace/pbit-llm-qwen-baselines',
                    files={name: hashlib.sha256(blob).hexdigest() for name, blob in blobs.items()})
    # Only create the new destination after every committed blob was readable.
    output.mkdir(parents=True)
    for name, blob in blobs.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(blob)
    with (output / 'EXECUTION.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write('\n')
    validate_manifest(output, manifest)
    return manifest


def envelope(path, identity):
    value = read_json(path)
    if (value.get('experiment') != fingerprint(identity)
            or value.get('result_sha256') != fingerprint(value.get('result'))):
        raise ValueError('parent artifact integrity failure: ' + str(path))
    return value['result']


def validate_benchmark(result):
    for key in ('contexts', 'decode_lengths', 'modes'):
        if result.get(key) != SCHEDULE[key]:
            raise ValueError('benchmark schedule differs: ' + key)
    if (result.get('measured_repeats') != 3 or result.get('warmup_trials_per_case_mode') != 1
            or result.get('attention_config') != CONFIG or result.get('original_ffn_guard_passed') is not True):
        raise ValueError('benchmark configuration/original FFN differs')
    expected = {(c, d, m, r) for c in SCHEDULE['contexts'] for d in SCHEDULE['decode_lengths']
                for m in SCHEDULE['modes'] for r in range(3)}
    rows = result.get('trials', [])
    actual = [(r['context_tokens'], r['decode_steps'], r['mode'], r['repeat']) for r in rows]
    if len(rows) != 54 or len(set(actual)) != 54 or set(actual) != expected:
        raise ValueError('benchmark is missing/duplicating a planned trial')
    if any(r.get('batch') != 1 or r.get('last_decode_logits_finite') is not True for r in rows):
        raise ValueError('benchmark batch/finite gate differs')


def validate_parent(root, parent_results, expected_identity_sha, execution):
    results_root = inside(Path(root) / 'results', root)
    parent_results = inside(parent_results, results_root)
    path = inside(parent_results / 'IDENTITY.json', parent_results)
    if not re.fullmatch('[0-9a-f]{64}', expected_identity_sha) or sha(path) != expected_identity_sha:
        raise ValueError('parent IDENTITY bytes differ from explicitly pinned SHA')
    parent = read_json(path)
    if (parent.get('model') != MODEL or parent.get('revision') != REVISION
            or parent.get('config') != CONFIG or parent.get('seed') != 0
            or parent.get('original_ffn') is not True):
        raise ValueError('parent model/config/FFN protocol differs')
    for name in UNCHANGED_NUMERICS:
        if execution['files'][name] != parent['execution']['files'].get(name):
            raise ValueError('numerical dependency changed; cannot call this a measurement supplement: ' + name)
    preflight_path = inside(parent_results / 'preflight.json', parent_results)
    benchmark_path = inside(parent_results / 'benchmark.json', parent_results)
    preflight = envelope(preflight_path, parent)
    if preflight.get('passed') is not True:
        raise ValueError('parent preflight did not pass')
    benchmark = envelope(benchmark_path, parent)
    validate_benchmark(benchmark)
    for name in ('benchmark.py', 'adapter.py', 'core.py'):
        key = 'qwen3/sparq/' + name
        if benchmark.get('source_files_sha256', {}).get(key) != parent['execution']['files'].get(key):
            raise ValueError('parent benchmark source provenance differs')
    return parent, benchmark, dict(identity_sha256=expected_identity_sha,
        identity_fingerprint=fingerprint(parent), quality_source_commit=parent['execution']['commit'],
        benchmark_artifact_sha256=sha(benchmark_path),
        preflight_artifact_sha256=sha(preflight_path), path=str(parent_results))


def verify_assets(root, parent, owner_uid=None):
    root = Path(root).resolve(strict=True)
    ready_path = inside(root / 'prepared/READY.json', root)
    def owned(path):
        if owner_uid is not None and path.stat().st_uid != owner_uid:
            raise ValueError('foreign-owned model/data input')
    owned(ready_path)
    if sha(ready_path) != parent['ready_sha256']:
        raise ValueError('READY differs from the original identity')
    ready = read_json(ready_path)
    if ready.get('model') != MODEL or ready.get('revision') != REVISION or ready.get('shape') != SHAPE:
        raise ValueError('staged model revision/shape differs')
    rows = ready.get('files', [])
    if len(rows) != 10 or {row['name'] for row in rows} != MODEL_FILES:
        raise ValueError('exactly the 10 pinned model/tokenizer files are required')
    model_root = inside(root / 'model', root)
    for row in rows:
        path = inside(model_root / row['name'], model_root)
        owned(path)
        if type(row['bytes']) is not int or row['bytes'] < 1 or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('model/tokenizer bytes changed: ' + row['name'])
    corpus = inside(root / 'data/wikitext-2/wiki.test.raw', root)
    owned(corpus)
    matches = [row for row in ready.get('data', []) if Path(row['path']).resolve() == corpus]
    if len(matches) != 1 or corpus.stat().st_size != matches[0]['bytes'] or sha(corpus) != matches[0]['sha256']:
        raise ValueError('original WikiText test bytes changed or are not uniquely declared')
    return ready, corpus


def validate_tokens(ids, parent, original_benchmark):
    # Reuse exactly the paired scorer's little-endian int64 corpus digest.
    from ..stochastic.vendor.scoring import ids_sha256
    if ids.ndim != 1 or ids.numel() < 2176 or ids_sha256(ids.tolist()) != parent['tokens_sha256']:
        raise ValueError('tokenization differs from the original full corpus')
    import struct
    h = hashlib.sha256(struct.pack('<QQ', 1, ids.numel()))
    for token in ids.tolist():
        h.update(struct.pack('<q', token))
    if (original_benchmark.get('token_ids_shape') != [1, ids.numel()]
            or original_benchmark.get('token_ids_shape_and_le_int64_sha256') != h.hexdigest()):
        raise ValueError('original benchmark consumed different token IDs')


def output_path(root, execution, parent, job):
    if not re.fullmatch('[0-9]+', str(job)):
        raise ValueError('numeric Slurm job identity required')
    directory = Path(root) / 'benchmark_supplements' / (execution['commit'][:12] + '_' + fingerprint(parent)[:12]) / str(job)
    target = inside(directory, root, exists=False)
    if target.is_relative_to(inside(Path(root) / 'results', root)):
        raise ValueError('supplement destination aliases original quality results')
    return target


def write_report(destination, identity, completed, save):
    """Repeatable report repair after an already committed benchmark; no GPU."""
    destination = Path(destination)
    benchmark = completed['benchmark']
    artifacts = {}
    for name in ('IDENTITY.json', 'INVOCATION.json', 'benchmark_supplement.json', 'progress.jsonl', 'FAILED.json'):
        path = destination / name
        if path.is_file():
            path = inside(path, destination)
            artifacts[name] = dict(bytes=path.stat().st_size, sha256=sha(path))
    report = dict(kind='benchmark_supplement_report', measurement_complete=True,
        quality_evaluation_complete=False, original_quality_results_inherited=False,
        parent=identity['parent'], model=identity['model'], revision=identity['revision'],
        measuring_execution=identity['measuring_execution'], job=identity['job'],
        gpu_uuid=identity['gpu_uuid'], gpu_name=identity['gpu_name'], environment=identity['environment'],
        config=CONFIG, schedule=SCHEDULE, original_ffn=True,
        ready_sha256=identity['ready_sha256'], verified_corpus_sha256=identity['verified_corpus_sha256'],
        verified_model_files=identity['verified_model_files'], tokens_sha256=identity['tokens_sha256'],
        power_status=completed['power_status'], power_windows_available=completed['power_windows_available'],
        phase_energy_attribution_validated=False, physical_asic_ppa=None,
        timing_protocol=benchmark['timing_protocol'], scope=benchmark['scope'],
        nvml_gpu_uuid=benchmark['nvml_gpu_uuid'], nvml_unavailable_reason=benchmark['nvml_unavailable_reason'],
        summaries=benchmark['summaries'], trial_count=len(benchmark['trials']),
        transfer_artifacts=artifacts)
    save(destination / 'report.json', report)
    save(destination / 'report.sha256.json', dict(file='report.json', sha256=sha(destination / 'report.json')))
    return report


def run(args):
    # Guard BEFORE importing Torch or touching CUDA. Unix ownership applies only
    # to this remote execution entry, not portable local freeze/helper tests.
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('explicit GPU Slurm allocation required; no job is submitted here')
    import pwd
    home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
    root = inside(args.root, home)
    parent_path = inside(args.parent_results, inside(root / 'results', root))
    tree = inside(Path(__file__).resolve().parents[2], home)
    for path in (home, root, parent_path, tree):
        if path.stat().st_uid != os.getuid():
            raise ValueError('foreign-owned personal input/source root')
    execution = validate_manifest(tree, read_json(tree / 'EXECUTION.json'))
    parent, original_benchmark, parent_link = validate_parent(root, parent_path, args.parent_identity_sha256, execution)
    ready, corpus = verify_assets(root, parent, owner_uid=os.getuid())
    environment = {name: importlib.metadata.version(name) for name in parent['environment']}
    if environment != parent['environment'] or environment.get('transformers') != '4.51.3':
        raise ValueError('runtime packages differ from original experiment')
    import torch
    if torch.cuda.device_count() != 1 or not torch.cuda.is_bf16_supported():
        raise RuntimeError('exactly one allocated BF16 GPU required')
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from .benchmark import run_benchmark
    from .core import SparQConfig
    from .run import Artifacts, save
    torch.manual_seed(0)
    torch.cuda.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(root / 'model', local_files_only=True, trust_remote_code=False)
    ids = tokenizer(corpus.read_bytes().decode('utf-8'), return_tensors='pt', add_special_tokens=False).input_ids[0]
    validate_tokens(ids, parent, original_benchmark)
    gpu = torch.cuda.get_device_properties(0)
    job = os.environ['SLURM_JOB_ID']
    identity = dict(kind='benchmark_supplement', parent=parent_link, measuring_execution=execution,
        ready_sha256=parent['ready_sha256'], model=MODEL, revision=REVISION,
        verified_model_files=ready['files'], verified_corpus_sha256=sha(corpus),
        tokens_sha256=parent['tokens_sha256'], config=CONFIG, benchmark_schedule=SCHEDULE,
        original_ffn=True, seed=0, environment=environment, gpu_name=gpu.name,
        gpu_uuid=str(gpu.uuid), job=job, original_quality_results_inherited=False,
        quality_evaluation_performed=False, task_datasets_revalidated=False)
    destination = output_path(root, execution, parent, job)
    out = Artifacts(destination, identity)
    completed = out.existing('benchmark_supplement')
    if completed is not None:
        write_report(destination, identity, completed, save)
        print(json.dumps(dict(status='already_completed_verified', output=str(destination))))
        return 0
    save(destination / 'INVOCATION.json', dict(argv=sys.argv, host=platform.node(), python=platform.python_version(),
        job=job, visible_devices=os.environ['CUDA_VISIBLE_DEVICES'], cuda_build=torch.version.cuda))
    try:
        model = AutoModelForCausalLM.from_pretrained(root / 'model', local_files_only=True,
            trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0').eval()
        if any(getattr(model.config, key) != value for key, value in SHAPE.items()):
            raise ValueError('loaded model shape differs')
        result = run_benchmark(model, ids, config=SparQConfig(**CONFIG), **SCHEDULE,
            power_gpu_uuid=str(gpu.uuid), model_provenance=dict(model=MODEL, revision=REVISION,
                measuring_source_commit=execution['commit'], parent_quality_source_commit=parent_link['quality_source_commit'],
                parent_identity_sha256=parent_link['identity_sha256'], job=job, role='measurement_supplement'),
            progress=out.progress('benchmark_supplement'))
        validate_benchmark(result)
        for name, digest in result['source_files_sha256'].items():
            if execution['files'].get(name) != digest:
                raise ValueError('measured benchmark source differs from frozen bundle')
        power_windows = sum(row[phase]['power'] is not None for row in result['trials'] for phase in ('prefill', 'decode'))
        completed = dict(measurement_complete=True, quality_evaluation_complete=False,
            parent=parent_link, measuring_source_commit=execution['commit'], benchmark=result,
            power_windows_available=power_windows, total_phase_windows=108,
            power_status='sampled_board_estimates' if power_windows else 'unavailable', physical_asic_ppa=None)
        out.put('benchmark_supplement', completed)
        write_report(destination, identity, completed, save)
        print(json.dumps(dict(status='measurement_completed', output=str(destination), power_windows_available=power_windows)))
        return 0
    except BaseException as error:
        save(destination / 'FAILED.json', dict(error=repr(error), job=job,
            measurement_complete=False, quality_evaluation_complete=False))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('freeze', help='new committed-source bundle; local CPU, no model/GPU')
    prepare.add_argument('--out', type=Path, required=True)
    execute = commands.add_parser('run', help='existing GPU allocation only; separate supplement artifacts')
    execute.add_argument('--root', type=Path, required=True)
    execute.add_argument('--parent-results', type=Path, required=True)
    execute.add_argument('--parent-identity-sha256', required=True)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        result = freeze(Path(__file__).resolve().parents[2], args.out)
        print(json.dumps(dict(status='frozen_not_run', commit=result['commit'], files=len(result['files']), output=str(args.out))))
        return 0
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
