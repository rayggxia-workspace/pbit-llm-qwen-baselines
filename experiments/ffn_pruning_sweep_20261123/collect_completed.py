"""Read-only audit/collection of the sealed full sweep; no model execution."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tarfile


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p, states=('completed',)):
    p = Path(p)
    assert p.with_suffix('.sha256').read_text().strip() == sha(p), str(p)
    d = json.loads(p.read_bytes())
    assert d['status'] in states, str(p)
    return d


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12), (a, b)


def ledger(d):
    fields = ['window_index', 'start', 'end', 'first_target', 'targets', 'target_token_sha256']
    return [{k: w[k] for k in fields} for w in d['result']['window_ledger']]


def addresses(d, calls, tokens):
    assert set(d['per_layer']) == {str(i) for i in range(36)}
    assert d['original_wd_calls'] == 36 * calls
    for v in d['per_layer'].values():
        assert v['calls'] == calls and v['tokens'] == tokens
        assert v['possible_addresses'] == tokens * 2560
        assert v['selected_weight_bytes'] == v['unique_addresses'] * 19456
        assert v['full_weight_bytes'] == v['possible_addresses'] * 19456
    close(d['unique_address_ratio'], d['unique_addresses'] / d['possible_addresses'])


def main():
    ap = argparse.ArgumentParser()
    for key in ['root', 'prior-root', 'source', 'out']:
        ap.add_argument('--' + key, type=Path, required=True)
    a = ap.parse_args()
    assert not a.out.exists(), 'Preserve earlier readbacks; use a new directory.'
    manifest = a.source / 'EXECUTION_MANIFEST.json'
    assert sha(manifest) == '7917ba46c29d21e226db94da8410560404761143e8e10ca9c70cffb4d542ec81'
    for name, digest in json.loads(manifest.read_bytes())['files'].items():
        assert sha(a.source / name) == digest
    plan = json.loads((a.source / 'PLAN.json').read_bytes())
    gate = read(a.root / 'gate/RESULT.json')
    cal = read(a.root / 'gate/CALIBRATION.json')
    assert sha(a.root / 'gate/CALIBRATION.json') == gate['calibration_sha256']
    assert cal['no_test_set_fit'] and gate['full2048_noop_logits_bitwise'] and gate['weights_unchanged']
    old_full = a.prior_root / 'full-f3e89e2bfc02'
    old_tasks = a.prior_root / 'tasks-5df53bac765c'
    base = read(old_full / 'original_strat64/RESULT.json')
    assert sha(old_full / 'original_strat64/RESULT.json') == 'cb3361f32bf5f76820d6ae0600397982cec1a2dc81cf1b41d3c520810385bbb5'
    full_selection = read(a.root / 'FULL_SELECTION.json')
    task_summary = read(a.root / 'TASK_SUMMARY.json')
    after_full = read(a.root / 'AFTER_FULL.json', ('submitted',))
    after_tasks = read(a.root / 'AFTER_TASKS.json')
    assert not full_selection['errors'] and not task_summary['errors'] and not after_tasks['errors']
    assert full_selection['selected_task_cases'] == ['input_p30']
    assert len(after_full['jobs']) == task_summary['expected'] == after_tasks['rows'] == 3
    files = []
    def remember(p):
        files.extend([p, p.with_suffix('.sha256')])
    def checked(p):
        d = read(p)
        assert d['provenance'] == gate['provenance'] and d['identity'] == gate['identity']
        expected_protocol = plan['task_protocol'] if d['phase'] == 'tasks' else gate['protocol']
        assert d['protocol'] == expected_protocol and d['seed'] == 101
        remember(p)
        return d
    full_rows, task_rows, pairs = [], [], []
    refs = []
    for case in ['original_strat64', 'input_p20']:
        p = old_full / case / 'RESULT.json'; d = read(p)
        refs.append({'case': case, 'result_sha256': sha(p), 'ppl': d['result']['ppl'],
                     'unique_address_ratio': d['result']['addresses']['unique_address_ratio']})
    for case in ['input_p30', 'band20_40_half']:
        p = a.root / 'full' / case / 'RESULT.json'; d = checked(p); r = d['result']
        assert d['full_corpus'] and d['phase'] == 'full' and d['case']['id'] == case
        assert d['calibration_sha256'] == gate['calibration_sha256']
        assert r['windows'] == len(r['window_ledger']) == 292 and r['targets'] == 299077
        assert ledger(d) == ledger(base)
        close(r['nll'], sum(w['nll'] for w in r['window_ledger']))
        close(r['mean_nll'], r['nll'] / r['targets']); close(r['ppl'], math.exp(r['mean_nll']))
        tokens = sum(w['end'] - w['start'] for w in r['window_ledger'])
        addresses(r['addresses'], 292, tokens)
        selected = next(x for x in full_selection['rows'] if x['case'] == case)
        assert selected['result_sha256'] == sha(p)
        close(selected['ppl'], r['ppl'])
        full_rows.append(dict(selected, windows=292, targets=299077,
                              scoring_seconds=r['seconds'], service_seconds=d['seconds']))
    for job in after_full['jobs']:
        case, task = job['case'], job['task']
        assert case == 'input_p30' and task in ['piqa', 'arc_challenge', 'winogrande']
        p = a.root / 'tasks' / case / task / 'RESULT.json'; d = checked(p)
        assert d['phase'] == 'tasks' and d['task'] == task and d['full_split']
        expected = {'piqa': 1838, 'arc_challenge': 1172, 'winogrande': 1267}[task]
        assert d['documents'] == expected and d['task_info'] == gate['task_info']
        audit = d['audit']
        assert audit['layers'] == 36 and audit['all_prompt_and_answer_positions_covered'] and not audit['prefix_exception']
        addresses(d['addresses'], audit['model_calls'], audit['input_tokens_per_layer'])
        op = p.parent / 'OFFICIAL_RESULT.json'; assert sha(op) == d['official_result_sha256']
        assert sha(op) == op.with_suffix('.sha256').read_text().strip(); remember(op)
        official = json.loads(op.read_bytes()); samples = official['samples'][task]
        assert len(samples) == len({s['doc_id'] for s in samples}) == expected
        selected = next(x for x in task_summary['rows'] if x['case'] == case and x['task'] == task)
        assert selected['result_sha256'] == sha(p) and selected['official_sha256'] == sha(op)
        for name, value in d['metrics'].items():
            close(sum(s[name.split(',')[0]] for s in samples) / expected, value)
            close(official['results'][task][name], value)
        baseline_metrics = {}
        for old_case in ['bf16', 'original_strat64', 'input_p20']:
            bp = old_tasks / old_case / task / 'RESULT.json'; old = read(bp)
            assert old['protocol'] == d['protocol']
            bop = bp.parent / 'OFFICIAL_RESULT.json'
            assert sha(bop) == old['official_result_sha256']
            assert old['audit']['input_batch_ledger_sha256'] == audit['input_batch_ledger_sha256']
            baseline_metrics[old_case] = old['metrics']
            aa = {str(v['doc_id']): v for v in json.loads(bop.read_bytes())['samples'][task]}
            bb = {str(v['doc_id']): v for v in samples}
            assert set(aa) == set(bb)
            for key in aa:
                for field in ['doc_hash', 'prompt_hash', 'target_hash']:
                    assert aa[key][field] == bb[key][field]
            for metric in [k.split(',')[0] for k in d['metrics']]:
                loss = sum(bool(aa[k][metric]) and not bool(bb[k][metric]) for k in aa)
                gain = sum(not bool(aa[k][metric]) and bool(bb[k][metric]) for k in aa)
                pairs.append({'baseline': old_case, 'case': case, 'task': task, 'metric': metric,
                              'documents': expected, 'correct_to_wrong': loss, 'wrong_to_correct': gain,
                              'delta_pp': 100 * (gain - loss) / expected})
        task_rows.append({'case': case, 'task': task, 'documents': expected, 'job': job['job'],
                          'metrics': d['metrics'], 'baseline_metrics': baseline_metrics,
                          'service_seconds': d['seconds'], 'result_sha256': sha(p),
                          'official_result_sha256': sha(op)})
    for name in ['FULL_SELECTION', 'TASK_SUMMARY', 'AFTER_FULL', 'AFTER_TASKS']:
        remember(a.root / (name + '.json'))
    for name in ['RESULT', 'CALIBRATION']:
        remember(a.root / 'gate' / (name + '.json'))
    assert len(files) == len(set(files)) == 28
    a.out.mkdir(parents=True)
    summary = {'status': 'completed_and_audited', 'scope': 'two full WT2 and three full tasks; single deployment seed101, accurate SDPA',
               'references': refs, 'full_PPL': full_rows, 'tasks': task_rows,
               'provenance': gate['provenance'], 'calibration_sha256': gate['calibration_sha256']}
    for name, value in [('SUMMARY.json', summary), ('PAIRED_OUTCOMES.json', pairs)]:
        (a.out / name).write_bytes((json.dumps(value, indent=2) + '\n').encode())
    archive = a.out / 'COMPLETED_RAW.tar.gz'
    with tarfile.open(archive, 'w:gz') as t:
        for p in files:
            t.add(p, arcname=p.relative_to(a.root).as_posix(), recursive=False)
    index = {'status': 'completed_and_audited', 'collector_sha256': sha(__file__),
             'archive': archive.name, 'archive_sha256': sha(archive), 'archive_bytes': archive.stat().st_size,
             'members': [{'path': p.relative_to(a.root).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in files],
             'outputs': {n: sha(a.out / n) for n in ['SUMMARY.json', 'PAIRED_OUTCOMES.json']}}
    (a.out / 'RESULT_INDEX.json').write_bytes((json.dumps(index, indent=2) + '\n').encode())
    print(json.dumps({k: v for k, v in index.items() if k not in ['members']}))


if __name__ == '__main__':
    main()
