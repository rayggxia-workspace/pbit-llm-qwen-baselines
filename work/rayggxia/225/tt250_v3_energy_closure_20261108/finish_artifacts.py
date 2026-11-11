"""Small public receipts and profile metadata; never edit the submitted snapshot."""
from pathlib import Path
import copy, hashlib, json, shutil, zipfile

HERE=Path(__file__).resolve().parent
WD=HERE.parents[3]
PROJECT=Path('C:/Users/86134/Documents/a_P_BIT')
REL='architecture_tlm/module_refresh_20261107/FFN_PROFILE.json'

def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())

with zipfile.ZipFile(HERE/'snapshot.zip') as z:
    original=z.read(REL)
manifest=json.loads((HERE/'MANIFEST.json').read_bytes())
assert sha(original)==manifest['files_sha256'][REL]
executed=HERE/'EXECUTED_FFN_PROFILE.json'
if executed.exists():assert executed.read_bytes()==original
else:executed.write_bytes(original)
prior=json.loads(original);profile=copy.deepcopy(prior)
v=profile['versions']['250MHz'];core=v['core']
v['superseded_failed_jobs']={'functional_job':v['functional_job'],'ppa_job':v['ppa_job']}
v['functional_job']='38625462';v['ppa_job']='38625468'
for mode in ('GU','Wd'):
    m=core['modes'][mode]
    m['incremental_pJ_per_frame_over_seed17_waiting']=m['gross_pJ_per_frame']-core['waiting_total_W']*m['frame_ns']*1000
    assert abs(m['incremental_pJ_per_frame_over_seed17_waiting']/128-m['incremental_pJ_per_DOT64_over_seed17_waiting'])<1e-10
profile['historical_source_status']=profile['source_status']
profile['source_status']='SS100_READY_TT250_V3_ACCEPTED_PRELAYOUT'
profile['counted']='completeM128 includingGF64,caches,nonlinear,weightedtree,C19,dualresults; ICG518 SS100 and582 TT250v3'
profile['version_sources']={'100MHz':profile['source_profile_sha256'],'250MHz':v['source_handoff_sha256']}
profile['metadata_normalization']={
    'executed_profile_sha256':sha(original),
    'executed_profile_receipt':'work/rayggxia/225/tt250_v3_energy_closure_20261108/EXECUTED_FFN_PROFILE.json',
    'changes':'Current job IDs and ICG/status labels corrected; derived incremental/frame alias restores earlier schema. Used timing, gross, waiting, area inputs unchanged.',
    'submitted_snapshot_modified':False}
assert profile['versions']['100MHz']==prior['versions']['100MHz']
for mode in ('GU','Wd'):
    for k,value in prior['versions']['250MHz']['core']['modes'][mode].items():assert profile['versions']['250MHz']['core']['modes'][mode][k]==value
current=WD/REL;before=current.read_bytes()
target=(json.dumps(profile,ensure_ascii=False,indent=2)+'\n').encode()
if before!=target:assert before==original,'unexpected concurrent profile edit'
current.write_bytes(target)
root=PROJECT/REL
assert root.read_bytes() in (before,target),'root profile changed elsewhere'
root.write_bytes(target)
save(HERE/'PROFILE_NORMALIZATION.json',dict(executed_profile_sha256=sha(original),current_profile_sha256=sha(target),
    used_numeric_inputs_unchanged=True,SS100_semantic_object_unchanged=True,snapshot_unchanged=True,
    compatibility_incremental_frame_pJ={n:core['modes'][n]['incremental_pJ_per_frame_over_seed17_waiting'] for n in ('GU','Wd')}))

status_path=WD/'architecture_tlm/sram1216_20261106/250MHz/ASSEMBLY_STATUS.json'
s=json.loads(status_path.read_bytes())
if s.get('update_date')!='2026-11-08':
    s['prior_assembly_metadata']={k:s[k] for k in ('status','SRAM_KiB','physical_banks','native_job','calibrated_coverage_area55_proxy_mm2','shortT_C19_measured_PPA')}
s.update(status='accepted_v3_native_layer_verified_full_pending',update_date='2026-11-08',
    SRAM_KiB=960,physical_banks=240,native_job='38629485',native_gate_job='38629484',
    calibrated_coverage_area55_proxy_mm2=22.086073419488095,
    shortT_C19_measured_PPA='delta_pipeline_v3 accepted prelayout; reported table flags retained',
    GU_frame_cycles=19,Wd_frame_cycles=35,GU_frame_ns=76,Wd_frame_ns=140,
    modeled_energy_ledger='CLOSED_WITHIN_DECLARED_MODEL_BOUNDARY',physical_chip_coverage_complete=False,
    current_report='ENERGY_CLOSURE_ZH.md')
save(status_path,s)

readme=WD/'architecture_tlm/module_refresh_20261107/README_ZH.md'
prefix='''> 2026-11-08：250MHz现已接受FFN delta_pipeline_v3，GU/Wd为19/35拍、76/140ns；3核、960KiB、16KiB入口保持。单层原生LPDDR门禁已通过，覆盖面积22.086073mm²、片上0.550405mJ；完整36层含head三seed运行中。新增逐资源能量对账，FFN旧计费本就未重复加idle。详见[当前能量对账](../sram1216_20261106/250MHz/ENERGY_CLOSURE_ZH.md)。下方表格为2026-11-07历史接合，不能覆盖本条当前状态；100MHz不变。

'''
if not readme.read_text(encoding='utf-8').startswith(prefix):readme.write_bytes(prefix.encode()+readme.read_bytes())

archive=PROJECT/'project_archives/tlm_energy225_20261108/gate'
collection=json.loads((HERE/'COLLECTION.json').read_bytes())
row=next(x for x in collection['rows'] if x['case']=='gate')
for name,h in row['files_sha256'].items():assert sha((archive/name).read_bytes())==h
budget=json.loads((archive/'BUDGET.json').read_bytes())
ledger=json.loads((archive/'ENERGY_LEDGER.json').read_bytes())
result=json.loads((archive/'RESULT.json').read_bytes())
summary=dict(status='VERIFIED_NATIVE_COLD_LAYER_NOT_FULL_TOKEN',model='Qwen3-4B',batch=1,context=2048,
    clock_MHz=250,SRAM_KiB=960,FFN_cores=3,GU_samples=16,Wd_samples=32,GU_frame_cycles=19,Wd_frame_cycles=35,
    FP32_reduction_lanes=16,SparQ_dimensions=32,scope='cold layer0 with embedding; no lm_head;36layer address allocation',
    time_ms=row['time_ms'],totals=row['totals'],FFN_core=budget['FFN_core_calibration'],
    ledger_status=ledger['status'],component_count=len(ledger['components']),
    configuration_sha256=row['configuration_sha256'],files_sha256=row['files_sha256'],
    archive=str(archive),remote=row['remote'],source_manifest_sha256=sha((HERE/'MANIFEST.json').read_bytes()),
    snapshot_sha256=sha((HERE/'snapshot.zip').read_bytes()),
    full_token=dict(status='RUNNING_PENDING',array_job='38629485',seeds=[17,503,1009],layers=36,includes_lm_head=True),
    exact_executed_profile_sha256=sha(original),metadata_normalization='PROFILE_NORMALIZATION.json',
    no_new_RTL_or_PT=True,physical_chip_measurement=False)
save(HERE/'VERIFIED_GATE.json',summary)
shutil.copyfile(archive/'ENERGY_LEDGER.csv',HERE/'VERIFIED_GATE_LEDGER.csv')
shutil.copyfile(archive/'VALIDATION.json',HERE/'VERIFIED_GATE_VALIDATION.json')
print(json.dumps(dict(summary=True,profile_compatible=True,SS100_unchanged=True,ledger_rows=len(ledger['components']))))
