"""Read-only verification of three native Slurm gates and sealed bytes."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ops import remote,save
H=Path(__file__).resolve().parent;plan=json.loads((H/'UPLOAD_PLAN.json').read_bytes())
code='ROOT='+repr(plan['root'])+'\n'+r'''
from pathlib import Path
import hashlib,json,datetime
r=Path(ROOT);rows=[]
for scheme in ('BF16_dense','W8_dense','W8_screen'):
    case='pilot_'+scheme;d=r/'outputs'/case;w=r/'work'/case
    seal=json.loads((d/'SEAL.json').read_text());ex=json.loads((w/'EXIT.json').read_text())
    assert seal['status']=='completed' and ex['exit_code']==0
    for n,v in seal['files_sha256'].items():assert hashlib.sha256((d/n).read_bytes()).hexdigest()==v
    x=json.loads((d/'RESULT.json').read_text());b=json.loads((d/'BUDGET.json').read_text())
    assert x['status']=='completed' and x['scope']=='layer_or_partial' and x['layers']==1
    assert x['backend']=='native' and x['head_probe_rows']==384
    assert json.loads((d/'VALIDATION.json').read_text())['status']=='PASS'
    rows.append(dict(scheme=scheme,job_id=ex['job_id'],time_ms=x['time_ms'],wall_seconds=x['wall_seconds'],
        area_mm2=b['conditional_subsystem_area_mm2'],core_mJ=b['conditional_subsystem_energy_mJ'],
        files_sha256=seal['files_sha256'],seal_sha256=hashlib.sha256((d/'SEAL.json').read_bytes()).hexdigest()))
print(json.dumps(dict(status='THREE_NATIVE_GATES_SEALED_SHA_VERIFIED',observed_UTC=datetime.datetime.utcnow().isoformat(),
    scope='native1layer384head,notcomplete36layers',rows=rows)))
'''
x=remote(code);save('NATIVE_GATES.json',x);print(json.dumps(x))
