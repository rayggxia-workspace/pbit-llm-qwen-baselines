"""Offline evidence/plan checks only; no Torch, network or GPU required."""
from pathlib import Path
import ast
import hashlib
import json

HERE = Path(__file__).resolve().parent
plan = json.loads((HERE/'PLAN.json').read_bytes())
index = json.loads((HERE/'SOURCE_INDEX.json').read_bytes())
assert plan['identity'] == index['execution_identity']
assert plan['source_files_sha256'] == index['source_files_sha256']
assert plan['targets'] == 299077 and plan['full_WT2'] and not plan['training']
assert plan['FFN'] == 'original exact BF16' and plan['weight'] == 'K_WH64'
assert plan['gates_passed'] == {'cpu.json': True, '2k/gate.json': True, '8k/gate.json': True}
assert sum(len(g['cases']) for g in plan['groups'].values()) == 14
assert [c['seed'] for c in plan['groups']['2k']['cases'][1:3]] == [1, 2]
for name, context, windows in [('2k', 2048, 292), ('8k', 8192, 286)]:
    group = plan['groups'][name]
    assert group['context'] == context and group['windows'] == windows
    previous_end, total, rows = 0, 0, 0
    for start in range(0, 299078, 1024):
        end = min(start + context, 299078)
        first = max(previous_end, start + 1)
        if first < end:
            total += end - first
            rows += 1
        previous_end = end
        if end == 299078:
            break
    assert (total, rows) == (299077, windows)
    for case in group['cases'][1:]:
        assert case['overlay'] == 'k_wh64' and case['r'] == 32
        assert case['samples'] in (None, 64)
for path, digest in index['public_patch_sha256'].items():
    content = (HERE/path).read_bytes()
    assert hashlib.sha256(content).hexdigest() == digest
    assert digest == index['source_files_sha256']['experiments/attention_followup_20261110/'+Path(path).name]
    ast.parse(content.decode('utf-8'))
print('PASS:14 planned full evaluations, both target plans,3 sealed gates,2 public patch byte hashes')
