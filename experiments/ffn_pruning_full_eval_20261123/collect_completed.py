"""Read-only collection of completed results; never changes execution snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import tarfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--inspector', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    ppl = a.root / 'full-f3e89e2bfc02'
    tasks = a.root / 'tasks-5df53bac765c'
    result = runpy.run_path(str(a.inspector))['inspect'](ppl, tasks)
    assert result['status'] == 'completed'
    assert result['ppl_completed'] == 4 and result['tasks_completed'] == 9
    paired, diagnostics, files, identities = [], [], [], []
    full = {}
    for base in [ppl, tasks]:
        for p in sorted(base.rglob('RESULT.json')):
            d = json.loads(p.read_bytes())
            assert d['status'] == 'completed' and d['seed'] == 101
            assert sha(p.read_bytes()) == p.with_suffix('.sha256').read_text().strip()
            files.extend([p, p.with_suffix('.sha256')])
            provenance = d.get('provenance', d)
            assert provenance['inputs_sha256'] == '84302bdff04a6bd78216dc03df24ebec309c666207879e2f3a468b057111bc5a'
            assert provenance['calibration_sha256'] == 'e627eb746affbcfdb6b8f9927207a3edaa3755aa53ef23c16be7d455759557a4'
            if d['case']['id'] != 'bf16':
                identities.append(d['identity'])
            if base == tasks:
                op = p.parent / 'OFFICIAL_RESULT.json'
                assert sha(op.read_bytes()) == d['official_result_sha256']
                assert sha(op.read_bytes()) == op.with_suffix('.sha256').read_text().strip()
                files.extend([op, op.with_suffix('.sha256')])
                full[d['case']['id'], d['task']] = json.loads(op.read_bytes())['samples'][d['task']]
            elif d['case']['id'] != 'bf16':
                for layer, v in d['result']['addresses']['pruning']['per_layer'].items():
                    diagnostics.append({'case': d['case']['id'], 'layer': int(layer),
                        'pruned_fraction': v['pruned'] / v['possible'],
                        'removed_input_absolute_mass_fraction': v['removed_input_mass'] / v['input_mass'],
                        'removed_score_square_fraction': v['removed_score_square_mass'] / v['score_square_mass']})
    assert len(identities) == 9 and all(x == identities[0] for x in identities)
    for task in ['piqa', 'arc_challenge', 'winogrande']:
        x = {str(v['doc_id']): v for v in full['original_strat64', task]}
        y = {str(v['doc_id']): v for v in full['input_p20', task]}
        assert set(x) == set(y)
        for metric in ['acc', 'acc_norm']:
            if metric not in next(iter(x.values())):
                continue
            counts = [0, 0, 0, 0]
            for key in x:
                assert x[key]['doc_hash'] == y[key]['doc_hash']
                xv, yv = bool(x[key][metric]), bool(y[key][metric])
                counts[0 if xv and yv else 1 if xv else 2 if yv else 3] += 1
            paired.append({'task': task, 'metric': metric, 'documents': len(x),
                'both_correct': counts[0], 'base_correct_pruned_wrong': counts[1],
                'base_wrong_pruned_correct': counts[2], 'both_wrong': counts[3],
                'delta_pp': 100 * (counts[2] - counts[1]) / len(x)})
    assert len(files) == 44 and len(set(files)) == 44
    a.out.mkdir(parents=True, exist_ok=True)
    for name, value in [('SUMMARY.json', result), ('PAIRED_OUTCOMES.json', paired),
                        ('PRUNING_DIAGNOSTICS.json', diagnostics)]:
        p = a.out / name
        assert not p.exists(), 'Use a fresh collection directory; preserve prior receipts.'
        p.write_bytes((json.dumps(value, indent=2) + '\n').encode())
    archive = a.out / 'COMPLETED_RAW.tar.gz'
    assert not archive.exists()
    with tarfile.open(archive, 'w:gz') as t:
        for p in files:
            t.add(p, arcname=p.relative_to(a.root), recursive=False)
    index = {'status': 'completed_and_audited', 'collector_sha256': sha(Path(__file__).read_bytes()),
        'inspector_sha256': sha(a.inspector.read_bytes()), 'archive': archive.name,
        'archive_sha256': sha(archive.read_bytes()), 'archive_bytes': archive.stat().st_size,
        'scope': '4 full WT2 and 9 full tasks, single deployment seed 101, exact SDPA',
        'identity': identities[0], 'members': [{'path': p.relative_to(a.root).as_posix(),
            'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size} for p in files],
        'outputs': {name: sha((a.out / name).read_bytes()) for name in
            ['SUMMARY.json', 'PAIRED_OUTCOMES.json', 'PRUNING_DIAGNOSTICS.json']}}
    (a.out / 'RESULT_INDEX.json').write_bytes((json.dumps(index, indent=2) + '\n').encode())
    print(json.dumps({k: v for k, v in index.items() if k not in ['identity', 'members']}))


if __name__ == '__main__':
    main()
