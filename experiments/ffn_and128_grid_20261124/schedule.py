"""Gate-dependent Slurm submission and sealed, complete-result aggregation."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import shlex
import statistics
import subprocess


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, value):
    p = Path(p);p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((json.dumps(value, indent=2, allow_nan=False) + '\n').encode())
    p.with_suffix('.sha256').write_bytes((sha(p) + '\n').encode())


def read(p):
    p = Path(p);assert sha(p) == p.with_suffix('.sha256').read_text().strip()
    return json.loads(p.read_bytes())


def collect(a, settings, gate, plan):
    specs = read(a.root / 'JOB_SPECS.json')
    grouped, tasks, errors, index = defaultdict(list), defaultdict(list), [], []
    for spec in specs:
        try:
            p = a.root / spec['output'] / 'RESULT.json';d = read(p)
            assert d['status'] == 'completed' and d['provenance'] == gate['provenance']
            assert (d['case'], d['seed'], d['shard'], d['phase']) == (spec['case'], spec['seed'], spec['shard'], spec['phase'])
            assert d['gate_sha256'] == sha(a.root / 'gate/RESULT.json')
            if spec['case'] != 'bf16':
                assert d['identity'] == gate['identity'] and d['overlay'] == gate['overlay']
                assert d['case_config'] == next(c for c in plan['cases'] if c['id'] == spec['case'])
            index.append({'path': p.relative_to(a.root).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size})
            if spec['phase'] == 'ppl':
                assert d['parts'] == list(range(0, 292, 8))[spec['shard']::plan['ppl']['shards']]
                grouped[spec['case'], spec['seed']].append(d)
            else:
                assert d['task'] == spec['task'] and d['task_protocol'] == plan['task_protocol']
                op = p.parent / 'OFFICIAL_RESULT.json'
                assert sha(op) == d['official_sha256'] == op.with_suffix('.sha256').read_text().strip()
                raw = json.loads(op.read_bytes())['samples'][spec['task']]
                assert len(raw) == d['documents'] and {int(x['doc_id']) for x in raw} == set(range(d['doc_start'], d['doc_end']))
                for key, value in d['metrics'].items():
                    assert math.isclose(sum(x[key.split(',')[0]] for x in raw) / len(raw), value, rel_tol=1e-12)
                for report in d['audit']['reports']:
                    n = report['scored_tokens_per_layer'][0]
                    assert report['scored_tokens_per_layer'] == [n] * 36
                    assert all(v['sampled_head_rows'] == n * 32 for v in report['attention']['layers'].values())
                request_raw = (json.dumps(d['audit']['requests'], separators=(',', ':')) + '\n').encode()
                assert hashlib.sha256(request_raw).hexdigest() == d['audit']['request_ledger_sha256']
                tasks[spec['case'], spec['task']].append((d, raw))
                index.append({'path': op.relative_to(a.root).as_posix(), 'sha256': sha(op), 'bytes': op.stat().st_size})
        except Exception as exc:
            errors.append({'spec': spec, 'error': type(exc).__name__ + ': ' + str(exc)})
    ppl, metrics, ledger = [], [], None
    keys = ['segment_id', 'begin', 'end', 'first_target', 'last_target_exclusive',
            'prefill_tokens', 'scored_tokens', 'target_begin', 'target_end', 'target_token_sha256']
    for (case, seed), values in sorted(grouped.items()):
        if len(values) != plan['ppl']['shards']:
            continue
        try:
            records = sorted([r for d in values for r in d['result']['records']], key=lambda x: x['segment_id'])
            assert len(records) == len({r['segment_id'] for r in records}) == 292
            assert sum(r['scored_tokens'] for r in records) == 299077
            candidate = [{k: r[k] for k in keys} for r in records]
            if ledger is None:ledger = candidate
            assert candidate == ledger
            nll = sum(r['nll_sum'] for r in records)
            for d in values:
                assert math.isclose(d['result']['nll'], sum(r['nll_sum'] for r in d['result']['records']), rel_tol=1e-12)
                assert sum(audit['scored_tokens_per_layer'][0] for audit in d['result']['audits']) == d['result']['targets']
                assert all(audit['scored_tokens_per_layer'] == [audit['scored_tokens_per_layer'][0]] * 36 for audit in d['result']['audits'])
            ppl.append({'case': case, 'seed': seed, 'targets': 299077, 'windows': 292,
                        'nll': nll, 'ppl': math.exp(nll / 299077),
                        'scoring_seconds_sum': sum(d['result']['seconds'] for d in values)})
        except Exception as exc:errors.append({'case': case, 'seed': seed, 'error': repr(exc)})
    for (case, task), values in sorted(tasks.items()):
        if len(values) != plan['task_shards']:
            continue
        try:
            samples = [s for _, rows in values for s in rows]
            total = plan['tasks'][task]['count']
            assert len(samples) == total and {int(s['doc_id']) for s in samples} == set(range(total))
            names = list(values[0][0]['metrics'])
            metrics.append({'case': case, 'task': task, 'seed': 101, 'documents': total,
                            'metrics': {key: sum(s[key.split(',')[0]] for s in samples) / total for key in names}})
        except Exception as exc:errors.append({'case': case, 'task': task, 'error': repr(exc)})
    aggregates = []
    for case in ['coarse32', 'fine128']:
        rows = [r for r in ppl if r['case'] == case]
        if {r['seed'] for r in rows} == set(plan['ppl_seeds']):
            aggregates.append({'case': case, 'seeds': plan['ppl_seeds'],
                               'ppl_from_mean_nll': math.exp(statistics.mean(r['nll'] / r['targets'] for r in rows)),
                               'ppl_arithmetic_mean': statistics.mean(r['ppl'] for r in rows),
                               'ppl_sample_SD': statistics.stdev(r['ppl'] for r in rows)})
    completed = len(ppl) == 7 and len(metrics) == 6 and not errors
    save(a.root / 'FINAL_SUMMARY.json', {'status': 'completed' if completed else 'partial',
         'full_PPL': ppl, 'ppl_aggregates': aggregates, 'tasks': metrics, 'errors': errors,
         'expected_full_PPL': 7, 'expected_task_configurations': 6,
         'source_manifest_sha256': gate['provenance']['source_manifest_sha256'],
         'gate_sha256': sha(a.root / 'gate/RESULT.json'), 'result_index': index})
    print(json.dumps({'status': 'completed' if completed else 'partial', 'PPL': len(ppl), 'tasks': len(metrics), 'errors': errors}))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=['submit', 'collect'], required=True)
    for key in ['root', 'source', 'settings']:
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args();settings = read(a.settings)
    assert a.root.resolve() == Path(settings['root']).resolve()
    assert a.source.resolve() == Path(settings['source']).resolve()
    plan = json.loads((a.source / 'PLAN.json').read_bytes())
    gate = read(a.root / 'gate/RESULT.json')
    assert gate['status'] == 'completed' and gate['native_cached_noop_bitwise']
    assert gate['coarse_repeat_logits_bitwise'] and gate['front_shared64_unchanged']
    if a.stage == 'collect':
        collect(a, settings, gate, plan);return
    receipt = a.root / 'AFTER_GATE.json'
    if receipt.exists():
        print('Receipt already exists; inspect instead of resubmitting.');return
    specs = []
    for case, seeds in [('bf16', [101]), ('coarse32', plan['ppl_seeds']), ('fine128', plan['ppl_seeds'])]:
        for seed in seeds:
            for shard in range(plan['ppl']['shards']):
                specs.append({'phase': 'ppl', 'case': case, 'seed': seed, 'shard': shard, 'task': 'piqa',
                              'output': 'ppl/%s/seed%d/shard%d' % (case, seed, shard)})
    for case in ['coarse32', 'fine128']:
        for task in plan['tasks']:
            for shard in range(plan['task_shards']):
                specs.append({'phase': 'task', 'case': case, 'seed': 101, 'shard': shard, 'task': task,
                              'output': 'task/%s/%s/seed101/shard%d' % (case, task, shard)})
    assert len(specs) == 52 and len({s['output'] for s in specs}) == 52
    spec_path = a.root / 'JOB_SPECS.json';save(spec_path, specs)
    assert sha(settings['dispatcher']) == settings['dispatcher_sha256']
    cmd = [settings['sbatch'], '--parsable', '--partition=' + settings['partition'], '--gres=gpu:1',
           '--cpus-per-task=4', '--mem=48G', '--time=1440', '--array=0-51', '--job-name=and128-263-eval',
           '--output=' + str(a.root / 'logs/eval-%A_%a.log'),
           '--wrap', shlex.join([settings['python'], settings['dispatcher'], '--settings', str(a.settings), '--specs', str(spec_path)])]
    save(receipt, {'status': 'submitting', 'specs_sha256': sha(spec_path), 'command': cmd})
    job = subprocess.check_output(cmd, text=True).strip().split(';')[0];assert job.isdigit()
    child_cmd = [settings['sbatch'], '--parsable', '--partition=' + settings['partition'], '--cpus-per-task=1',
                 '--mem=8G', '--time=30', '--dependency=afterany:' + job, '--job-name=and128-263-collect',
                 '--output=' + str(a.root / 'logs/collect-%j.log'), '--wrap', shlex.join([settings['python'],
                     str(Path(__file__).resolve()), '--stage', 'collect', '--root', str(a.root), '--source', str(a.source),
                     '--settings', str(a.settings)])]
    child = subprocess.check_output(child_cmd, text=True).strip().split(';')[0];assert child.isdigit()
    rates = {r['case']: r['seconds'] / r['targets'] for r in gate['pilots']}
    estimate = gate['native_reference']['seconds'] / gate['native_reference']['targets'] * 299077
    estimate += sum(rates[c] * 299077 * 3 for c in ['coarse32', 'fine128'])
    estimate += sum(r['seconds'] / r['documents'] * plan['tasks'][r['task']]['count'] for r in gate['task_pilots'])
    save(receipt, {'status': 'submitted', 'array_job': job, 'array_tasks': len(specs), 'collector_job': child,
                   'specs_sha256': sha(spec_path), 'settings_sha256': sha(a.settings),
                   'dispatcher_sha256': settings['dispatcher_sha256'], 'scheduler_sha256': sha(__file__),
                   'gate_sha256': sha(a.root / 'gate/RESULT.json'),
                   'pilot_based_GPU_hours': estimate / 3600,
                   'ETA_scope': 'sum of suffix-pilot service estimates; full-window grouping, concurrency and queue not guaranteed',
                   'command': cmd, 'collector_command': child_cmd})
    print(json.dumps({'status': 'submitted', 'array': job, 'tasks': len(specs), 'collector': child,
                      'pilot_based_GPU_hours': estimate / 3600}))


if __name__ == '__main__':
    main()
