"""Verify delivered CSVs against binary source matrices, and preserved old results."""
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path
import numpy as np

root=Path(__file__).resolve().parents[4]
ws=Path('C:/Users/86134/Documents/a_P_BIT')
r=root/'architecture_tlm/random_service/quality/results/correlation_20261025'
arc=ws/'project_archives/rng_correlation_20261025'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert (ws/'PROJECT_MEMORY_ZH.md').read_bytes()==(ws/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md').read_bytes()
assert (r/'REPORT.html').read_bytes()==(ws/'远端上传/rng_correlation_20261025.html').read_bytes()
assert sha(arc/'rng_correlation_20261025_tables.zip')==sha(ws/'远端上传/rng_correlation_20261025_tables.zip')
assert not subprocess.check_output(['git','diff','3b878c15ddb56179815c5afa8193ea816a96037a','--','architecture_tlm/random_service/quality/results/ideal_20261025'],cwd=root)
summary=json.loads((r/'SUMMARY.json').read_text(encoding='utf8'))
checks=0
with zipfile.ZipFile(arc/'rng_correlation_20261025_tables.zip') as z:
    for c in summary['cases']:
        if c['source']!='physical':continue
        path=next(Path(x['path']) for x in c['artifacts'] if Path(x['path']).name=='matrices.npz')
        with np.load(path) as arrays:
            for feature in ['word','q4','q128','bit0','bit7']:
                for name,key in [(feature+'_temporal.csv',feature+'_acf'),(feature+'_space_lag0.csv',feature+'_cross')]:
                    text=z.read(c['case_id']+'/'+name).decode('utf8')
                    observed=np.loadtxt(io.StringIO(text),delimiter=',',skiprows=1)[:,1:]
                    expected=arrays[key] if name.endswith('temporal.csv') else arrays[key][0]
                    np.testing.assert_allclose(observed,expected,rtol=1e-10,atol=1e-11,equal_nan=True)
                    checks+=1
for reg in [root/'digital_circuit_simulation_registry',ws/'digital_circuit_simulation_registry']:
    record=json.loads((reg/'records/rng-correlation-95-20261025.json').read_text(encoding='utf8'))
    assert sum(x['role']=='portable_execution_recovery' for x in record['artifacts'])==1
    subprocess.run(['python',str(reg/'registry.py'),'check'],check=True)
result=dict(status='PASS',csv_matrices_checked=checks,delivery_html_identical=True,delivery_zip_identical=True,old_225_results_unchanged=True,memory_mirror_identical=True)
(Path(__file__).parent/'DELIVERY_CHECK.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf8'))
print(json.dumps(result))
