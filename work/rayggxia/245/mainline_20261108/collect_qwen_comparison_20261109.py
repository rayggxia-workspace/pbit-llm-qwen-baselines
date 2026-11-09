"""Read the completed Qwen subset only; never relax the36-case final aggregate."""
from pathlib import Path
import hashlib,json,ops
HERE=Path(__file__).resolve().parent/'qwen_comparison_20261109';HERE.mkdir(exist_ok=True)
D=json.loads((HERE.parent/'revision2/SUBMISSION.json').read_bytes())
x=ops.remote('D='+repr(D)+'\n'+r'''
from pathlib import Path
import datetime,hashlib,json
r=Path(D['root']);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(r/'SNAPSHOT_MANIFEST.json')==D['manifest_sha256']
plan=json.loads((r/'PLAN.json').read_bytes());rows=[]
for i,c in enumerate(plan):
 if c['model']!='qwen3_4b':continue
 folder=r/'results/full'/('%02d_%s_%s_%s_s%s'%(i,c['model'],c['clock'],c['scheme'],c['seed']))
 seal=json.loads((folder/'SEAL.json').read_bytes());assert seal['status']=='completed'
 for n,h in seal['files_sha256'].items():assert sha(folder/n)==h,(i,n)
 a=json.loads((folder/'RESULT.json').read_bytes());b=json.loads((folder/'BUDGET.json').read_bytes());v=json.loads((folder/'VALIDATION.json').read_bytes())
 assert a['status']=='completed' and v['status']=='PASS' and b['energy_sum_closed']
 assert a['snapshot_manifest_sha256']==D['manifest_sha256'] and a['backend']=='native'
 assert a['includes_head'] and a['layers']==36 and a['shape']['vocab']==151936
 assert a['actions']['digital_BF16_MAC']==36*26214400+151936*2560
 n=b['excluding_lm_head_stage']
 assert abs(a['time_without_lm_head_stage_ms']-n['time_ms'])<1e-10
 assert abs(a['time_ms']-n['time_ms']-a['lm_head_stage_ms'])<1e-10
 assert n['time_ms']>0 and n['onchip_mJ']<=b['onchip_mJ']
 rows.append(dict(index=i,model=a['model'],clock_MHz=a['clock_MHz'],scheme=a['scheme'],seed=a['seed'],
   area55_mm2=b['area55_mm2'],area_allocation=b['area_allocation'],
   including_head=dict(time_ms=a['time_ms'],onchip_mJ=b['onchip_mJ'],external_mJ_by_pJbit=b['external_mJ_by_pJbit'],
       system_mJ_by_pJbit=b['system_mJ_by_pJbit'],average_W_by_pJbit=b['average_W_by_pJbit']),
   excluding_head=n,lm_head_stage_ms=a['lm_head_stage_ms'],phase_totals_ns=a['phase_totals_ns'],
   components=b['components'],boundary=b['boundary'],backend=a['backend'],
   source_manifest_sha256=a['snapshot_manifest_sha256'],remote_folder=str(folder),
   files_sha256=dict(seal['files_sha256'],**{'SEAL.json':sha(folder/'SEAL.json')})))
assert len(rows)==12 and {x['index'] for x in rows}==set(range(12))
print(json.dumps(dict(status='QWEN12_FULL_CASES_SEALED_AND_VERIFIED',UTC=datetime.datetime.utcnow().isoformat(),rows=rows,
 input_snapshot_manifest_sha256=D['manifest_sha256'],shape=dict(model='Qwen/Qwen3-4B',batch=1,context=2048,layers=36,vocab=151936),
 not_all36_complete=True,no_new_TLM_or_PPL=True)))
''')
(HERE/'DERIVED_INPUT.json').write_bytes((json.dumps(x,indent=2)+'\n').encode())
print(json.dumps(dict(status=x['status'],rows=len(x['rows']),input_sha256=hashlib.sha256((HERE/'DERIVED_INPUT.json').read_bytes()).hexdigest(),
 preview=[dict(clock=r['clock_MHz'],scheme=r['scheme'],seed=r['seed'],area=r['area55_mm2'],with_ms=r['including_head']['time_ms'],without_ms=r['excluding_head']['time_ms'],without_mJ=r['excluding_head']['system_mJ_by_pJbit']['4.0']) for r in x['rows']])))
