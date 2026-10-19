"""Issue50 optional full-corpus cached confirmation; Slurm GPU execution only.

The d61 suffix preparation remains immutable. This runner rechecks input hashes,
inherits only its successful unchanged-BF16 environment gate, and measures a new
matched cached BF16 reference. Two real prefix-shape memory pilots must pass
before any batch32 full case is admitted. Import and plan tests need no Torch.
"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO))
from experiments.qwen_joint_stratified_attention_20261019 import run_joint as joint
from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.scoring import (
    full_window_plan, plan_metadata)


PRIOR_COMMIT = 'd61b2861edc91e00495268d39a738edb3599f87f'
EXPECTED_TARGETS = 299077
FULL_BATCH = 32


def cases(phase='full'):
    """The exact, preregistered 22-cell matched grid, or two memory pilots."""
    if phase not in ('full', 'memory'):
        raise ValueError('phase must be full or memory')
    rows = []

    def add(ffn, mode, seed=0, **updates):
        cfg = dict(name=f'{ffn}_{mode}_S128_s{seed}', ffn=ffn, mode=mode,
            seed=seed, samples=128, burn=16., spacing=4., selection='fixed',
            budget_blocks=8, target_fraction=.30, context=2048, decode=128,
            examples=32, batch=FULL_BATCH, protocol='full', stride=1024)
        cfg.update(updates)
        validate_case(cfg, phase)
        rows.append(cfg)

    if phase == 'memory':
        for batch in (16, FULL_BATCH):
            add('b4_t32', 'screen_ising', name=f'memory_B{batch}_b4_t32_S512_s0',
                samples=512, examples=batch, decode=4, batch=batch, protocol='suffix',
                context=2048 if batch == 16 else 1024)
    else:
        add('none', 'sdpa')
        for ffn in joint.FFNS:
            for seed in joint.SEEDS:
                add(ffn, 'sdpa', seed)
        for ffn in ('none',) + joint.FFNS:
            for seed in joint.SEEDS:
                add(ffn, 'screen_ising', seed)
        if len(rows) != 22:
            raise AssertionError('full matched grid must have 22 cases')
    if len(rows) != len({row['name'] for row in rows}):
        raise AssertionError('duplicate case name')
    return rows


def validate_case(cfg, phase):
    """Reject accidental suffix-as-full configurations before loading a model."""
    expected = {'full': 'full', 'memory': 'suffix'}
    if phase not in expected or cfg.get('protocol') != expected[phase]:
        raise ValueError('phase/protocol mismatch')
    if cfg.get('context') not in ((2048,) if phase == 'full' else (1024, 2048)) or cfg.get('stride') != 1024:
        raise ValueError('full confirmation uses the frozen 2048/1024 plan')
    if phase == 'full' and cfg.get('batch') != FULL_BATCH:
        raise ValueError('all matched full cases require the approved batch32')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _identity_fields(identity):
    # Paths can be equivalent aliases; compare exact bytes, not symlink spelling.
    return dict(model_repository=identity['model_repository'],
        model_revision=identity['model_revision'], tokens=identity['tokens'],
        files={key: {k: value[k] for k in ('bytes', 'sha256')}
               for key, value in identity['files'].items()},
        frozen_manifest_sha256=identity['frozen_manifest_sha256'],
        source_sha256=identity['source_sha256'])


def prior_gate(a, fresh):
    """Read/hash only the authorized own d61 snapshot and its original receipts."""
    project = Path(a.project_root).resolve(strict=True)
    prior = Path(a.prior_output).resolve(strict=True)
    if project not in prior.parents or prior == Path(a.output).resolve():
        raise ValueError('prior output must be a different artifact inside this project')
    paths = {name: prior / name for name in
             ('identity.json', 'suite.json', 'READY.json', 'bf16_vectorized_full.json')}
    identity, suite, ready, baseline = (_read(paths[name]) for name in paths)
    if (ready.get('code_commit') != PRIOR_COMMIT or
            identity.get('execution_commit') != PRIOR_COMMIT or
            suite.get('code_commit') != PRIOR_COMMIT or
            baseline.get('code_commit') != PRIOR_COMMIT):
        raise ValueError('prior artifacts are not the frozen d61 preparation')
    if not ready.get('baseline_gate_passed') or not ready.get('sdpa_wrapper_bitwise_passed'):
        raise ValueError('prior BF16/wrapper gate did not pass')
    if (ready['identity_sha256'] != joint.digest(paths['identity.json']) or
            ready['suite_sha256'] != joint.digest(paths['suite.json'])):
        raise ValueError('prior preparation artifacts changed')
    if (not baseline.get('baseline_gate_passed') or
            baseline.get('scored_tokens') != EXPECTED_TARGETS or
            not math.isclose(baseline['perplexity'], 11.652735047455899,
                             rel_tol=0., abs_tol=1e-8)):
        raise ValueError('prior original vectorized BF16 gate mismatch')
    if _identity_fields(identity) != _identity_fields(fresh):
        raise ValueError('new input/tokenizer/corpus/frozen dependency differs from d61')
    snapshot = (project / 'snapshots' / PRIOR_COMMIT).resolve(strict=True)
    for relative, checksum in identity['joint_sources'].items():
        path = (snapshot / relative).resolve(strict=True)
        if snapshot not in path.parents or joint.digest(path) != checksum:
            raise ValueError('prior immutable source changed: ' + relative)
    return dict(output=str(prior), code_commit=PRIOR_COMMIT,
        artifact_sha256={name: joint.digest(path) for name, path in paths.items()},
        original_vectorized_ppl=baseline['perplexity'],
        reuse='environment gate only; full matched cached BF16 is rerun in this grid')


def prepare(a):
    out = joint.output_dir(a)
    if any(out.iterdir()):
        raise FileExistsError('full preparation output must be empty; never overwrite artifacts')
    identity = joint.verify(a.model, a.data, out / 'identity.json')
    prior = prior_gate(a, identity)
    identity.update(execution_commit=a.code_commit, joint_sources=joint.sources(),
        calibration_sha256=joint.CAL_SHA, prior_preparation=prior,
        randomness='same stratified shared64 FFN and independent selector/finite CTMC domains as d61')
    joint.write_json(out / 'identity.json', identity)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='')
    check = subprocess.run([sys.executable, '-B', str(ROOT / 'test_full_plan.py')],
        cwd=REPO, env=env, text=True, capture_output=True)
    (out / 'full_plan_tests.stdout.txt').write_text(check.stdout, encoding='utf-8', newline='\n')
    (out / 'full_plan_tests.stderr.txt').write_text(check.stderr, encoding='utf-8', newline='\n')
    check.check_returncode()
    # A deliberately larger 32x2047 pilot OOMed on31.37GiB before any full job.
    # Actual full scoring batches have1023 prefix tokens; the initial long
    # window has batch1/no prefill. Cover16x2047 then the actual32x1023 shape.
    import torch
    for cfg in cases('memory'):
        result = joint.evaluate(a, cfg, identity)
        joint.write_json(out / 'memory' / (cfg['name'] + '.json'), result)
        print(json.dumps(dict(event='full_memory_pilot', name=cfg['name'],
            targets=result['scored_tokens'], seconds=result['elapsed_seconds'],
            peak_allocated_bytes=result['peak_allocated_bytes'])), flush=True)
        torch.cuda.empty_cache()
    plan = full_window_plan(identity['tokens']['test']['tokens'], 2048, 1024)
    metadata = plan_metadata(plan, identity['tokens']['test']['tokens'], 'full')
    if metadata['scored_tokens'] != EXPECTED_TARGETS or not metadata['every_full_corpus_target_once']:
        raise AssertionError('full target coverage mismatch')
    suite = dict(code_commit=a.code_commit, created_utc=datetime.now(timezone.utc).isoformat(),
        full=cases('full'), memory=cases('memory'), scoring_plan=metadata,
        prior_preparation=prior, no_training=True,
        attention_budget='S128 fixed for every query; NOT a constant per-query L/16 ratio',
        prefill='original multi-token SDPA Attention; selected FFNs remain stochastic in prefill and decode',
        seed_comparison='same batch32/window order; seed IDs matched, CTMC trajectories may diverge with logits',
        bf16='fresh full cached baseline; prior vectorized BF16 is environment gate only')
    joint.write_json(out / 'suite.json', suite)
    joint.write_json(out / 'READY.json', dict(code_commit=a.code_commit,
        baseline_gate_passed=True, sdpa_wrapper_bitwise_passed=True,
        gate_provenance='unchanged model/data/frozen dependencies plus hashed d61 successful preparation',
        prior_ready_sha256=prior['artifact_sha256']['READY.json'],
        memory_pilots_passed=True, approved_full_batch=FULL_BATCH, full_cases=22,
        identity_sha256=joint.digest(out / 'identity.json'), suite_sha256=joint.digest(out / 'suite.json')))


def worker(a):
    out = joint.output_dir(a)
    ready = _read(out / 'READY.json')
    if (ready.get('code_commit') != a.code_commit or not ready.get('memory_pilots_passed') or
            ready.get('approved_full_batch') != FULL_BATCH or
            not ready.get('baseline_gate_passed') or not ready.get('sdpa_wrapper_bitwise_passed')):
        raise ValueError('full worker preparation gates not passed')
    if (ready['identity_sha256'] != joint.digest(out / 'identity.json') or
            ready['suite_sha256'] != joint.digest(out / 'suite.json')):
        raise ValueError('full preparation artifacts changed')
    identity, suite = _read(out / 'identity.json'), _read(out / 'suite.json')
    if identity['joint_sources'] != joint.sources() or identity['source_sha256'] != joint.source_manifest():
        raise ValueError('execution sources/frozen dependencies changed')
    prior = prior_gate(a, identity)
    if prior != identity['prior_preparation'] or ready['prior_ready_sha256'] != prior['artifact_sha256']['READY.json']:
        raise ValueError('inherited environment gate changed')
    grid = cases('full')
    if suite['full'] != grid or not 0 <= a.index < len(grid):
        raise ValueError('full suite/index mismatch')
    cfg = grid[a.index]
    path = out / 'full' / (cfg['name'] + '.json')
    if path.exists():
        raise FileExistsError(path)
    result = joint.evaluate(a, cfg, identity)
    if (result['scored_tokens'] != EXPECTED_TARGETS or
            not result['scoring_plan']['every_full_corpus_target_once'] or
            result['scoring_plan']['target_positions_sha256_le_int64'] !=
            suite['scoring_plan']['target_positions_sha256_le_int64']):
        raise RuntimeError('actual full result does not match every-target scoring plan')
    result['prior_preparation'] = prior
    joint.write_json(path, result)
    print(json.dumps(dict(event='full_completed', name=cfg['name'],
        ppl=result['perplexity'], targets=result['scored_tokens'],
        seconds=result['elapsed_seconds'])), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', choices=('prepare', 'worker'), required=True)
    for key in ('model', 'data', 'calibration', 'project-root', 'output', 'code-commit', 'prior-output'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--index', type=int, default=0)
    args = parser.parse_args()
    if len(args.code_commit) != 40 or any(c not in '0123456789abcdef' for c in args.code_commit):
        parser.error('exact lowercase execution SHA required')
    {'prepare': prepare, 'worker': worker}[args.action](args)


if __name__ == '__main__':
    main()
