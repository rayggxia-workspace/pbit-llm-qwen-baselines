"""Capture conservative-scheduling audit evidence; no model or circuit run."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
parser = argparse.ArgumentParser()
parser.add_argument('--source-root', required=True, type=Path)
args = parser.parse_args()
source = args.source_root.resolve()
root = Path(__file__).resolve().parents[3]
aux = Path(__file__).resolve().parent
expected = '556462dc5db37582310302ed8b916d717b4d6ceb'

def git(*argv):
    return subprocess.check_output(['git', '-C', str(source), *argv])

head = git('rev-parse', 'HEAD').decode().strip()
if head != expected:
    raise ValueError('Audit must reference the recorded PR192 head')
paths = [
    'architecture_tlm/unified_v6/core.py',
    'architecture_tlm/unified_v6/tile_pipeline.py',
    'architecture_tlm/unified_v6/memory_profiles.py',
    'architecture_tlm/ffn_local_pipeline_20261025/model.py',
    'architecture_tlm/dramsys_backend.py',
    'architecture_tlm/clock500_resource_20261026/profiles.py',
    'architecture_tlm/clock500_resource_20261026/ppa.py',
    'architecture_tlm/clock500_resource_20261026/PPA_METHOD_ZH.md',
]
provenance = []
for rel in paths:
    data = (source / rel).read_bytes()
    blob = git('show', head + ':' + rel)
    if data.replace(b'\r\n', b'\n') != blob.replace(b'\r\n', b'\n'):
        raise ValueError('Inspected source differs from recorded head: ' + rel)
    provenance.append({'path': rel, 'checkout_sha256': hashlib.sha256(data).hexdigest(),
                       'git_blob_sha256': hashlib.sha256(blob).hexdigest()})

spec = importlib.util.spec_from_file_location('audit_core', source / paths[0])
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
s = core.Scheduler()
s.reserve('future_ready', 100.0, 10.0, ('port',))
s.reserve('already_ready', 0.0, 10.0, ('port',))
if s.end() != 120.0 or s.events[1]['start_ns'] != 110.0:
    raise ValueError('Recorded FIFO reservation example no longer matches')

cases = []
for i in range(12):
    rel = 'architecture_tlm/clock500_resource_20261026/results/case_%d/RESULT_SUMMARY.json' % i
    data = (source / rel).read_bytes()
    result = json.loads(data)
    c = result['config']
    enabled = c.get('digital_shared_prefill', False)
    if enabled:
        raise ValueError('Audit assumption changed: digital prefill is enabled')
    local = c.get('local_pipeline')
    if c['ffn']['mode'] == 'sc' and local != {'overlap': True, 'weight_bypass': True}:
        raise ValueError('Audit assumption changed: SC local pipeline')
    cases.append({'case': i, 'result_sha256': hashlib.sha256(data).hexdigest(),
                  'config_sha256': hashlib.sha256(json.dumps(c, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                  'config_hash_protocol': 'UTF-8 compact JSON, sort_keys=True; derived hash, not archived input bytes',
                  'ffn': c['ffn']['mode'], 'seed': c['seed'],
                  'digital_shared_prefill_explicit': 'digital_shared_prefill' in c,
                  'digital_shared_prefill_effective': enabled,
                  'local_pipeline': local, 'elapsed_ms': result['metrics']['elapsed_ns'] / 1e6})

note = root / 'architecture_tlm/simulator_survey_20261025/CONSERVATIVE_SCHEDULING_AUDIT_ZH.md'
body = note.read_bytes()
if b'\r' in body:
    raise ValueError('New audit note must use UTF-8/LF')
result = {'date': '2026-10-27', 'kind': 'documentation_source_and_scheduler_probe',
          'status': 'passed', 'inspected_pr': 192, 'source_commit': head,
          'source_files': provenance, 'case_count': len(cases), 'cases': cases,
          'scheduler_probe': {'events': s.events, 'finish_ns': s.end(),
                              'legal_alternative_finish_ns': 110.0,
                              'full_model_impact_measured': False},
          'report_sha256': hashlib.sha256(body).hexdigest(),
          'not_run': ['full TLM', 'GPU', 'PPL', 'RTL', 'EDA', 'server jobs'],
          'model_and_corpus_hashes': 'not applicable: no numerical inference',
          'digital_registry': 'not applicable: software scheduler probe, no digital-circuit simulation'}
out = aux / 'CONSERVATIVE_CHECK.json'
out.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'status': 'passed', 'source_files': len(provenance),
                  'cases': len(cases), 'scheduler_finish_ns': s.end(),
                  'report_sha256': result['report_sha256']}))
