"""CPU allocation: verify personal artifacts, copy bound inputs, load P-DNN state."""
from pathlib import Path
import argparse
from dataclasses import asdict
import json
import os
import pwd
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from experiments.pdnn_task_accuracy_20261023.pdnn_score import file_sha256
from experiments.pdnn_ffn.full_path_pdnn_ffn import FullPathPBitFFN, FullPathPBitFFNConfig

PERSONAL = Path('/home/Weican_Chen')
SOURCES = {
    'piqa': ('piqa__None__validation.parquet', '40e1677bba609c8801deacc171d76f3e24c083f365c95a1cbda7520c923dfea2'),
    'arc_easy': ('allenai__ai2_arc__ARC-Easy__test.parquet', '4160597d618ae851c7eb04e281574f3f654776216ac6b6641588d64527b47177'),
    'hellaswag': ('hellaswag__None__validation.parquet', '899813071e1e95efafec90f856e1987d2150fa4d020fc005df6962c259f660cd'),
}


def personal(path, exists=True):
    value = Path(path).resolve(strict=exists)
    if not value.is_relative_to(PERSONAL) or value == PERSONAL:
        raise ValueError('path outside verified personal home: '+str(value))
    existing = value if value.exists() else value.parent
    if not existing.exists() or existing.stat().st_uid != os.getuid():
        raise ValueError('personal owner required: '+str(existing))
    return value


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--project-root', required=True)
    p.add_argument('--config', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise RuntimeError('CPU-only Slurm job with CUDA hidden required')
    account = pwd.getpwuid(os.getuid())
    if account.pw_name != 'Weican_Chen' or Path(account.pw_dir).resolve() != PERSONAL:
        raise ValueError('unexpected account/home')
    project = personal(a.project_root)
    output = personal(a.output, False)
    if project not in output.parents or REPO in output.parents or output.exists():
        raise ValueError('new output outside immutable source required')
    config = json.loads(Path(a.config).read_text(encoding='utf-8'))
    report = dict(slurm_job_id=os.environ['SLURM_JOB_ID'], user=account.pw_name,
                  cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES'], training=False,
                  data={}, checkpoints=[])
    inputs = project/'data'
    if inputs.exists():
        personal(inputs)
    else:
        inputs.mkdir()
    old_data = personal(PERSONAL/'projects/apple-sigmoid-7b-eval-20261019/data/parquet')
    for task, (filename, expected) in SOURCES.items():
        source = personal(old_data/filename)
        if file_sha256(source) != expected:
            raise ValueError('source parquet changed: '+task)
        target_dir = inputs/task
        if target_dir.exists():
            personal(target_dir)
        else:
            target_dir.mkdir()
        target = personal(target_dir/'0000.parquet', False)
        if target.exists():
            if file_sha256(target) != expected:
                raise ValueError('existing task copy changed')
        else:
            with source.open('rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)
        if file_sha256(target) != expected:
            raise ValueError('task copy mismatch')
        report['data'][task] = dict(source=str(source), target=str(target),
                                   bytes=target.stat().st_size, sha256=expected)
    import torch
    for entry in config['checkpoints']:
        path = personal(entry['path'])
        if path.stat().st_size != entry['bytes'] or file_sha256(path) != entry['sha256']:
            raise ValueError('checkpoint byte identity changed')
        payload = torch.load(path, map_location='cpu', weights_only=True)
        if payload['training_args']['layer'] != entry['layer']:
            raise ValueError('checkpoint layer mismatch')
        if payload['phase'] != entry['phase'] or payload['step'] != entry['step']:
            raise ValueError('checkpoint training metadata mismatch')
        if payload['student_type'] != 'full_path_bipolar_pdnn_v1':
            raise ValueError('original serial bipolar P-DNN required')
        config_args = dict(payload['student_config'])
        config_args['hidden_sizes'] = tuple(config_args['hidden_sizes'])
        cfg = FullPathPBitFFNConfig(**config_args)
        student = FullPathPBitFFN(cfg)
        student.load_state_dict(payload['student_state_dict'], strict=True)
        if not all(torch.isfinite(t).all().item() for t in student.state_dict().values()):
            raise ValueError('nonfinite checkpoint state')
        report['checkpoints'].append(dict(entry, student_type=payload['student_type'],
            source_student_config=payload['student_config'], effective_student_config=asdict(cfg),
            parameters=sum(p.numel() for p in student.parameters()), strict_state_loaded=True))
        del student, payload
    with output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(dict(event='cpu_artifact_preflight_passed', checkpoints=len(report['checkpoints']),
                          dataset_copies=len(report['data']), output=str(output))), flush=True)


if __name__ == '__main__':
    main()
