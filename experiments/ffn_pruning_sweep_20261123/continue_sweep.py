"""Slurm CPU continuations: screen -> qualified full WT2 -> qualified tasks."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import shlex
import subprocess
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + '\n').encode())
    path.with_suffix('.sha256').write_bytes((sha(path) + '\n').encode())


def read(path, states=('completed',)):
    path = Path(path)
    assert path.with_suffix('.sha256').read_text().strip() == sha(path), str(path)
    value = json.loads(path.read_bytes())
    assert value['status'] in states, str(path)
    return value


def ledger(result):
    keys = ['window_index', 'start', 'end', 'first_target', 'targets', 'target_token_sha256']
    return [{k: w[k] for k in keys} for w in result['window_ledger']]


def qualifies(result, reference, settings):
    ppl = result['ppl']
    ratio = None if ppl is None or not math.isfinite(ppl) else ppl / reference['ppl']
    reduction = 1 - result['addresses']['unique_address_ratio'] / reference['addresses']['unique_address_ratio']
    accepted = ratio is not None and ratio <= settings['max_ppl_ratio'] and reduction >= settings['minimum_relative_unique_address_reduction']
    return {'ppl': ppl, 'ppl_ratio': ratio, 'relative_unique_address_reduction': reduction,
            'unique_address_ratio': result['addresses']['unique_address_ratio'], 'qualified': accepted}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['screen', 'full', 'tasks'], required=True)
    for name in ['root', 'source', 'job-script', 'prior-root']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--sbatch', required=True)
    ap.add_argument('--partition', default='gpu5090')
    a = ap.parse_args()
    root, source = a.root.resolve(), a.source.resolve()
    assert source.parent == root and a.job_script.resolve().parent == root
    receipt = root / ('AFTER_' + a.phase.upper() + '.json')
    if receipt.exists():
        print('Existing continuation receipt; review it instead of resubmitting:', receipt)
        return
    own = json.loads((source / 'EXECUTION_MANIFEST.json').read_bytes())
    for name, digest in own['files'].items():
        assert sha(source / name) == digest
    plan = json.loads((source / 'PLAN.json').read_bytes())
    gate_path = root / 'gate/RESULT.json'
    gate = read(gate_path)
    assert gate['provenance']['source_manifest_sha256'] == sha(source / 'EXECUTION_MANIFEST.json')
    assert gate['full2048_noop_logits_bitwise'] and gate['weights_unchanged']
    prior_path = a.prior_root / 'full-f3e89e2bfc02/original_strat64/RESULT.json'
    prior = read(prior_path)
    assert sha(prior_path) == plan['prior_full_PPL_sha256']

    def checked(path):
        d = read(path)
        assert d['provenance'] == gate['provenance'] and d['identity'] == gate['identity']
        assert d['seed'] == plan['seed']
        return d

    def submit(command):
        out = subprocess.check_output([a.sbatch, '--parsable'] + command, text=True).strip().split(';')[0]
        assert out.isdigit()
        return out

    def gpu(phase, case, task=''):
        command = ['--partition=' + a.partition, '--gres=gpu:1', '--cpus-per-task=4', '--mem=48G',
            '--time=180', '--chdir=' + str(source), '--job-name=prunesweep261-' + phase,
            '--output=' + str(root / 'logs' / (phase + '-' + case + '-' + task + '-%j.log')),
            '--wrap', shlex.join(['bash', str(a.job_script), phase, case, task])]
        return {'job': submit(command), 'case': case, 'task': task, 'command': command}

    def follow(phase, jobs):
        command = ['--partition=' + a.partition, '--cpus-per-task=1', '--mem=4G', '--time=15',
            '--dependency=afterany:' + ':'.join(j['job'] for j in jobs),
            '--job-name=prunesweep261-' + phase + '-select',
            '--output=' + str(root / 'logs' / ('select-' + phase + '-%j.log')),
            '--wrap', shlex.join([sys.executable, str(source / 'continue_sweep.py'),
                '--phase', phase, '--root', str(root), '--source', str(source),
                '--job-script', str(a.job_script), '--prior-root', str(a.prior_root),
                '--sbatch', a.sbatch, '--partition', a.partition])]
        return {'job': submit(command), 'command': command}

    rows, chosen, errors, jobs = [], [], [], []
    if a.phase == 'screen':
        base = checked(root / 'screen/original_strat64/RESULT.json')
        anchor = checked(root / 'screen/input_p20/RESULT.json')
        assert base['phase'] == anchor['phase'] == 'screen' and base['result']['windows'] == 8
        assert ledger(base['result']) == ledger(anchor['result'])
        assert [w['window_index'] for w in base['result']['window_ledger']] == plan['screen_window_indices']
        for case in plan['candidates']:
            try:
                path = root / 'screen' / case / 'RESULT.json'
                d = checked(path)
                assert d['case']['id'] == case and d['phase'] == 'screen'
                assert ledger(d['result']) == ledger(base['result'])
                row = dict(case=case, result_sha256=sha(path), **qualifies(d['result'], base['result'], plan['promotion']))
                rows.append(row)
                if row['qualified']:
                    chosen.append(case)
            except Exception as exc:
                errors.append({'case': case, 'error': type(exc).__name__ + ': ' + str(exc)})
        save(root / 'SCREEN_SELECTION.json', dict(status='completed', seed=101, rows=rows,
            selected_cases=chosen, errors=errors, settings=plan['promotion'],
            anchor_SHA256=sha(root / 'screen/input_p20/RESULT.json'),
            baseline_SHA256=sha(root / 'screen/original_strat64/RESULT.json'),
            source_manifest_sha256=sha(source / 'EXECUTION_MANIFEST.json')))
        save(receipt, dict(status='submitting', selected_cases=chosen, jobs=jobs))
        for case in chosen:
            jobs.append(gpu('full', case))
            save(receipt, dict(status='submitting', selected_cases=chosen, jobs=jobs))
        child = follow('full', jobs) if jobs else None
    elif a.phase == 'full':
        previous = read(root / 'AFTER_SCREEN.json', states=('submitted',))
        for case in previous['selected_cases']:
            try:
                path = root / 'full' / case / 'RESULT.json'
                d = checked(path)
                assert d['phase'] == 'full' and d['full_corpus']
                assert d['result']['windows'] == 292 and d['result']['targets'] == 299077
                assert ledger(d['result']) == ledger(prior['result'])
                assert set(d['result']['addresses']['per_layer']) == {str(i) for i in range(36)}
                assert d['result']['addresses']['original_wd_calls'] == 36 * 292
                row = dict(case=case, result_sha256=sha(path), **qualifies(d['result'], prior['result'], plan['promotion']))
                rows.append(row)
                if row['qualified']:
                    chosen.append(case)
            except Exception as exc:
                errors.append({'case': case, 'error': type(exc).__name__ + ': ' + str(exc)})
        save(root / 'FULL_SELECTION.json', dict(status='completed', seed=101, rows=rows,
            selected_task_cases=chosen, errors=errors, settings=plan['promotion'],
            baseline_full_SHA256=sha(prior_path), source_manifest_sha256=sha(source / 'EXECUTION_MANIFEST.json')))
        save(receipt, dict(status='submitting', selected_cases=chosen, jobs=jobs))
        for case in chosen:
            for task in plan['tasks']:
                jobs.append(gpu('tasks', case, task))
                save(receipt, dict(status='submitting', selected_cases=chosen, jobs=jobs))
        child = follow('tasks', jobs) if jobs else None
    else:
        previous = read(root / 'AFTER_FULL.json', states=('submitted',))
        for job in previous['jobs']:
            case, task = job['case'], job['task']
            try:
                path = root / 'tasks' / case / task / 'RESULT.json'
                d = checked(path)
                assert d['phase'] == 'tasks' and d['full_split'] and d['documents'] == plan['tasks'][task]['count']
                assert d['audit']['layers'] == 36 and not d['audit']['prefix_exception']
                assert d['addresses']['original_wd_calls'] == 36 * d['audit']['model_calls']
                old = read(a.prior_root / 'tasks-5df53bac765c/original_strat64' / task / 'RESULT.json')
                assert d['audit']['input_batch_ledger_sha256'] == old['audit']['input_batch_ledger_sha256']
                op = path.parent / 'OFFICIAL_RESULT.json'
                assert sha(op) == d['official_result_sha256']
                samples = json.loads(op.read_bytes())['samples'][task]
                assert len(samples) == len({s['doc_id'] for s in samples}) == d['documents']
                for name, value in d['metrics'].items():
                    assert math.isclose(sum(s[name.split(',')[0]] for s in samples) / len(samples), value, rel_tol=1e-12)
                rows.append({'case': case, 'task': task, 'documents': d['documents'],
                    'metrics': d['metrics'], 'result_sha256': sha(path), 'official_sha256': sha(op),
                    'old_T64_metrics': old['metrics'], 'old_T64_result_sha256': sha(a.prior_root / 'tasks-5df53bac765c/original_strat64' / task / 'RESULT.json')})
            except Exception as exc:
                errors.append({'case': case, 'task': task, 'error': type(exc).__name__ + ': ' + str(exc)})
        save(root / 'TASK_SUMMARY.json', dict(status='completed' if not errors else 'partial',
            rows=rows, errors=errors, expected=len(previous['jobs']), seed=101,
            source_manifest_sha256=sha(source / 'EXECUTION_MANIFEST.json')))
        save(receipt, dict(status='completed' if not errors else 'partial', rows=len(rows), errors=errors))
        print(json.dumps({'phase': 'tasks', 'completed': len(rows), 'errors': errors}))
        return
    value = dict(status='submitted' if jobs else 'completed_no_qualified_candidate',
        selected_cases=chosen, jobs=jobs, continuation=child, errors=errors,
        gate_sha256=sha(gate_path), source_manifest_sha256=sha(source / 'EXECUTION_MANIFEST.json'),
        job_script_sha256=sha(a.job_script))
    save(receipt, value)
    print(json.dumps({'phase': a.phase, 'selected': chosen, 'jobs': [j['job'] for j in jobs], 'errors': errors}))


if __name__ == '__main__':
    main()
