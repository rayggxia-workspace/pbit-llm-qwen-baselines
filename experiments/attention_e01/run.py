"""Issue35 Slurm-stage driver. No downloads, installation, or job submission.

Paths and expected model identities are supplied after read-only server discovery.
Only writes below the verified personal root; snapshots are immutable once staged.
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inside(path, personal_root, exists=True):
    target = Path(path).resolve(strict=exists)
    if target == personal_root or personal_root not in target.parents:
        raise ValueError('Path must be below verified personal root: '+str(target))
    return target


def environment_python(path, personal_root):
    """Preserve the venv executable path; its base Python symlink is read-only.

    Resolving bin/python to /usr/bin/python would discard the virtual environment.
    Validate the personal venv directory separately from the base executable.
    """
    executable = Path(path)
    if not executable.is_absolute():
        raise ValueError('Python environment path must be absolute')
    bin_dir = inside(executable.parent, personal_root)
    venv_root = inside(bin_dir.parent, personal_root)
    if not (venv_root/'pyvenv.cfg').is_file():
        raise ValueError('An explicit personal virtual environment is required')
    base = executable.resolve(strict=True)
    if personal_root not in base.parents and not (base.parent==Path('/usr/bin') and base.name.startswith('python')):
        raise ValueError('Python base resolves outside the personal root or system interpreter')
    return executable


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def check_source(manifest_path, commit):
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    if manifest.get('code_commit') != commit:
        raise ValueError('Source manifest does not identify requested commit')
    entries = manifest.get('files', [])
    required = {
        'baselines/common.py', 'baselines/perplexity.py',
        'architecture_tlm/attention_reference_v3.py',
        'config/qwen2.5-0.5b-config.json',
        *('experiments/attention_e01/'+name for name in [
            'run.py', 'capture.py', 'verify_inputs.py', 'microbench.py',
            'test_capture_contract.py', 'test_microbench.py', 'test_driver.py',
            'microbench_config.json', 'run.sbatch', 'prepare_inputs.py', 'expected_identity.json']),
    }
    declared = {entry['path'] for entry in entries}
    if not required.issubset(declared) or len(declared) != len(entries):
        raise ValueError('Source manifest has missing or duplicate execution files')
    for entry in entries:
        path = (SOURCE/entry['path']).resolve(strict=True)
        if SOURCE not in path.parents or digest(path) != entry['sha256']:
            raise ValueError('Snapshot source hash/path mismatch: '+entry['path'])
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=['preflight','baseline_capture','micro_pilot','micro_full'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--source-manifest', required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Computation requires an explicit Slurm allocation')
    gpu_stage = args.stage == 'baseline_capture'
    if not gpu_stage:
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
    elif not os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('GPU stage requires scheduler-provided CUDA_VISIBLE_DEVICES')
    import pwd
    user = pwd.getpwuid(os.getuid())
    if user.pw_name != 'Weican_Chen' or Path(user.pw_dir).resolve() != Path('/home/Weican_Chen'):
        raise RuntimeError('Server identity/home changed; rediscover and review before running')
    personal_root = Path(user.pw_dir).resolve(strict=True)
    inside(SOURCE, personal_root)
    config_path = inside(args.config, personal_root)
    source_manifest_path = inside(args.source_manifest, personal_root)
    source = check_source(source_manifest_path, args.source_commit)
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if config.get('schema') != 'attention-e01-run-v1' or config.get('ready') is not True:
        raise ValueError('Supply a reviewed ready=true server configuration')
    paths = {key:inside(config[key], personal_root) for key in ['model','text','expected_manifest']}
    paths['python'] = environment_python(config['python'], personal_root)
    output_root = inside(config['output_root'], personal_root, exists=False)
    output_root.mkdir(parents=True, exist_ok=True)
    stage_output = output_root/(args.stage+'-'+os.environ['SLURM_JOB_ID'])
    stage_output.mkdir(exist_ok=False)
    summary = {
        'stage':args.stage, 'state':'running', 'job_id':os.environ['SLURM_JOB_ID'],
        'node':os.environ.get('SLURMD_NODENAME'), 'source_commit':args.source_commit,
        'source_manifest_sha256':digest(source_manifest_path),
        'config_sha256':digest(config_path), 'commands':[],
        'hardware_measurement':False, 'random_attention_full_ppl_run':False,
        'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    save(stage_output/'stage_summary.json', summary)
    python = str(paths['python'])

    def run(arguments):
        command = [python, '-u', *map(str,arguments)]
        record = {'argv':command,'started_at':dt.datetime.now(dt.timezone.utc).isoformat()}
        summary['commands'].append(record)
        save(stage_output/'stage_summary.json', summary)
        start = time.monotonic()
        completed = subprocess.run(command, cwd=SOURCE)
        record.update(returncode=completed.returncode, elapsed_seconds=time.monotonic()-start)
        save(stage_output/'stage_summary.json', summary)
        completed.check_returncode()

    phase_output = None
    try:
        if args.stage=='preflight':
            run([HERE/'verify_inputs.py','--model',paths['model'],'--text',paths['text'],
                 '--expected-manifest',paths['expected_manifest'],'--output',stage_output/'verified_inputs.json'])
            run(['-m','unittest','discover','-s',HERE,'-p','test_*.py'])
            summary['preflight_passed']=True
        elif gpu_stage:
            verification = stage_output/'verified_inputs.json'
            run([HERE/'verify_inputs.py','--model',paths['model'],'--text',paths['text'],
                 '--expected-manifest',paths['expected_manifest'],'--output',verification])
            run(['-m','unittest','discover','-s',HERE,'-p','test_*.py'])
            common = ['--model',paths['model'],'--text-file',paths['text'],
                      '--max-length','2048','--stride','1024','--seed','0']
            # The original baseline scripts and model are used unchanged.
            run([SOURCE/'baselines/perplexity.py',*common,'--max-tokens','128',
                 '--output',stage_output/'bf16_prefix128.json'])
            prefix = json.loads((stage_output/'bf16_prefix128.json').read_text(encoding='utf-8'))
            if not math.isfinite(prefix['perplexity']):
                raise RuntimeError('BF16 smoke produced nonfinite PPL')
            run([HERE/'capture.py','--model',paths['model'],'--text',paths['text'],
                 '--verification',verification,'--output-dir',stage_output/'capture_smoke',
                 '--tokens','128','--source-commit',args.source_commit])
            run([SOURCE/'baselines/perplexity.py',*common,
                 '--output',stage_output/'bf16_full_wt2.json'])
            result = json.loads((stage_output/'bf16_full_wt2.json').read_text(encoding='utf-8'))
            if (result['scored_tokens'] != 299077 or
                abs(result['perplexity']-11.652735047455899) > 1e-4):
                raise RuntimeError('Full BF16 reference drift: stop before comparative microbenchmarks')
            run([HERE/'capture.py','--model',paths['model'],'--text',paths['text'],
                 '--verification',verification,'--output-dir',stage_output/'capture_real',
                 '--tokens','2048','--source-commit',args.source_commit])
            summary['bf16_reference_match'] = True
            summary['capture_root'] = str(stage_output/'capture_real')
        else:
            trace = inside(config['trace'], personal_root)
            capture_report_path = inside(config['capture_report'], personal_root)
            upstream = json.loads(capture_report_path.read_text(encoding='utf-8'))
            if upstream.get('stage') != 'baseline_capture' or upstream.get('state') != 'complete' or upstream.get('bf16_reference_match') is not True:
                raise ValueError('A completed fresh BF16/capture stage is required')
            if trace.parent != Path(upstream['capture_root']).resolve():
                raise ValueError('Trace must come from the completed capture stage')
            expected_trace_sha = config.get('trace_sha256')
            if not expected_trace_sha or digest(trace) != expected_trace_sha:
                raise ValueError('Trace SHA must be verified before microbenchmark submission')
            phase = 'pilot' if args.stage=='micro_pilot' else 'full'
            phase_output = output_root/'microbench'/phase
            run([HERE/'microbench.py','--trace',trace,'--output',output_root/'microbench',
                 '--phase',phase,'--config',HERE/'microbench_config.json',
                 '--source-manifest-sha256',digest(source_manifest_path)])
            summary['trace_sha256'] = expected_trace_sha
        summary['state'] = 'complete'
    except BaseException as error:
        summary.update(state='failed',error=type(error).__name__+': '+str(error))
        raise
    finally:
        summary['ended_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        artifact_paths = list(stage_output.rglob('*'))
        if phase_output is not None and phase_output.is_dir():
            artifact_paths.extend(phase_output.rglob('*'))
        summary['files'] = [
            {'path':str(p.relative_to(output_root)), 'bytes':p.stat().st_size,'sha256':digest(p)}
            for p in sorted(set(artifact_paths)) if p.is_file() and p.name!='stage_summary.json'
        ]
        save(stage_output/'stage_summary.json', summary)


if __name__ == '__main__':
    main()
