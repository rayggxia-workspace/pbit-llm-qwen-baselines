"""Independent local recomputation from new and earlier sealed raw archives."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tarfile


def digest(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--readback', type=Path, required=True)
    ap.add_argument('--prior-archive', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    index = json.loads((a.readback / 'RESULT_INDEX.json').read_bytes())
    arc = a.readback / index['archive']
    assert digest(arc.read_bytes()) == index['archive_sha256']
    assert digest(a.prior_archive.read_bytes()) == '85396a156a8f58a1da1cca49c12a4ed54fbe3d3b196219d875b23a12e39642fb'
    with tarfile.open(arc, 'r:gz') as t:
        raw = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
    assert len(raw) == len(index['members']) == 28
    for e in index['members']:
        assert len(raw[e['path']]) == e['bytes'] and digest(raw[e['path']]) == e['sha256']
    for name, checksum in index['outputs'].items():
        assert digest((a.readback / name).read_bytes()) == checksum
    with tarfile.open(a.prior_archive, 'r:gz') as t:
        old = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
    def load(data, name):
        assert digest(data[name]) == data[str(Path(name).with_suffix('.sha256')).replace('\\', '/')].decode().strip()
        value = json.loads(data[name]); assert value['status'] == 'completed'
        return value
    summary = json.loads((a.readback / 'SUMMARY.json').read_bytes())
    recorded_pairs = json.loads((a.readback / 'PAIRED_OUTCOMES.json').read_bytes())
    base = load(old, 'full-f3e89e2bfc02/original_strat64/RESULT.json')
    for row in summary['full_PPL']:
        d = load(raw, 'full/' + row['case'] + '/RESULT.json'); r = d['result']
        nll = sum(x['nll'] for x in r['window_ledger']); targets = sum(x['targets'] for x in r['window_ledger'])
        assert len(r['window_ledger']) == 292 and targets == 299077
        assert math.isclose(nll, r['nll'], rel_tol=1e-12)
        assert math.isclose(math.exp(nll / targets), row['ppl'], rel_tol=1e-12)
        for x, y in zip(r['window_ledger'], base['result']['window_ledger']):
            for key in ['window_index', 'start', 'end', 'first_target', 'targets', 'target_token_sha256']:
                assert x[key] == y[key]
    for row in summary['tasks']:
        task = row['task']; prefix = 'tasks/input_p30/' + task + '/'
        d = load(raw, prefix + 'RESULT.json')
        assert digest(raw[prefix + 'OFFICIAL_RESULT.json']) == d['official_result_sha256']
        samples = json.loads(raw[prefix + 'OFFICIAL_RESULT.json'])['samples'][task]
        b = {str(v['doc_id']): v for v in samples}
        assert len(b) == len(samples) == row['documents']
        audit = d['audit']; ledger_bytes = (json.dumps(audit['input_batch_ledger'], separators=(',', ':')) + '\n').encode()
        assert digest(ledger_bytes) == audit['input_batch_ledger_sha256']
        for metric, score in row['metrics'].items():
            assert math.isclose(sum(v[metric.split(',')[0]] for v in samples) / len(samples), score, rel_tol=1e-12)
        for case in ['bf16', 'original_strat64', 'input_p20']:
            op = 'tasks-5df53bac765c/' + case + '/' + task + '/'
            prev = load(old, op + 'RESULT.json')
            assert digest(old[op + 'OFFICIAL_RESULT.json']) == prev['official_result_sha256']
            aa = {str(v['doc_id']): v for v in json.loads(old[op + 'OFFICIAL_RESULT.json'])['samples'][task]}
            assert aa.keys() == b.keys() and prev['audit']['input_batch_ledger'] == audit['input_batch_ledger']
            for key in b:
                assert all(aa[key][f] == b[key][f] for f in ['doc_hash', 'prompt_hash', 'target_hash'])
            for metric in row['metrics']:
                m = metric.split(',')[0]
                loss = sum(aa[k][m] and not b[k][m] for k in b)
                gain = sum(not aa[k][m] and b[k][m] for k in b)
                pair = next(p for p in recorded_pairs if p['baseline'] == case and p['task'] == task and p['metric'] == m)
                assert loss == pair['correct_to_wrong'] and gain == pair['wrong_to_correct']
    validation = {'status': 'passed', 'new_archive_sha256': index['archive_sha256'],
                  'archive_members': 28, 'complete_full_PPL': 2, 'complete_tasks': 3,
                  'PPL_windows_each': 292, 'PPL_targets_each': 299077,
                  'task_documents': {r['task']: r['documents'] for r in summary['tasks']},
                  'checks': ['member and output SHA256', 'full target ledger equality', 'NLL and PPL recomputation',
                             'official document identity', 'input batch ledger equality and SHA',
                             'per-document metric means', 'paired outcome transitions against three prior cases'],
                  'auditor_sha256': digest(Path(__file__).read_bytes())}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes((json.dumps(validation, indent=2) + '\n').encode())
    print(json.dumps(validation))


if __name__ == '__main__':
    main()
