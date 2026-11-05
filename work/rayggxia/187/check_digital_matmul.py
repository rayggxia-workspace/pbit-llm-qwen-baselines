"""Check literature bytes and explicitly labelled peak-bound arithmetic; no RTL run."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / 'architecture_tlm/simulator_survey_20261025'
HERE = Path(__file__).resolve().parent
LOCAL = HERE / 'source_checks/digital_matmul'
sources = json.loads((DOC / 'DIGITAL_MATMUL_SOURCES.json').read_text(encoding='utf-8'))
checks = []
for entry in sources['downloaded_files']:
    p = LOCAL / entry['local_relative_path']
    b = p.read_bytes()
    assert len(b) == entry['bytes'], p
    assert hashlib.sha256(b).hexdigest() == entry['sha256'], p
    checks.append({'path': entry['local_relative_path'], 'sha256_equal': True})
rtl = LOCAL / 'tpe_rtl'
assert 'saed32rvt_tt0p85v25c' in (rtl / 'OPT1/systolic_array_os/array_mac_based/syn/dc.tcl').read_text()
assert 'ACC_WIDTH = 32' in (rtl / 'OPT1/systolic_array_os/mac_pe/mac.v').read_text()
assert 'MIT License' in (rtl / 'LICENSE').read_text()
figures = {
    '28nm_tpu_equivalent_pj_mac_from_reported_efficiency': 2 / 8.05,
    '28nm_trapezoid_equivalent_pj_mac_from_reported_efficiency': 2 / 9.31,
    '55nm_lenet_task_equivalent_pj_mac': 2 * 0.1384 / 29.16 * 1000,
    '55nm_mobilenet_task_equivalent_pj_mac': 2 * 0.2796 / 95.23 * 1000,
    'lenet_throughput_inverse_us': 1e6 / 41851,
    'mobilenet_throughput_inverse_us': 1e6 / 1272,
}
bounds = []
for m in (1, 8, 64):
    macs = m * 64 * 64
    bounds.append({'M': m, 'K': 64, 'N': 64, 'MACs': macs,
                   '55nm_peak_lower_bound_ns': macs / (256 * 320e6) * 1e9,
                   '28nm_peak_lower_bound_ns': macs / (1024 * 1e9) * 1e9,
                   'actual_rtl_latency_ns': None})
assert [x['55nm_peak_lower_bound_ns'] for x in bounds] == [50, 400, 3200]
assert [x['28nm_peak_lower_bound_ns'] for x in bounds] == [4, 32, 256]
files = {}
for name in ('DIGITAL_MATMUL_55_28_ZH.md', 'DIGITAL_MATMUL_SOURCES.json'):
    b = (DOC / name).read_bytes()
    assert b'\r' not in b
    b.decode('utf-8')
    files[name] = hashlib.sha256(b).hexdigest()
result = {'checked_utc': datetime.now(timezone.utc).isoformat(),
          'kind': 'LITERATURE_SOURCE_AND_ARITHMETIC_CHECK_ONLY',
          'source_checks': checks, 'figures': figures, 'peak_lower_bounds': bounds,
          'document_sha256': files, 'rtl_eda_tlm_runs': 0,
          'not_verified': ['55nm port', 'RTL function', 'actual target GEMV latency',
                           'paper PPA reproduction', 'model accuracy']}
(HERE / 'DIGITAL_MATMUL_CHECK.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'verified_source_files': len(checks), 'figures': figures,
                  'actual_target_latency_verified': False}, ensure_ascii=False))
