"""Freeze reports and indices for the completed long-correlation run."""
import csv
import hashlib
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4];WS=Path('C:/Users/86134/Documents/a_P_BIT')
WORK=Path(__file__).resolve().parent;RESULT=ROOT/'architecture_tlm/random_service/quality/results/correlation_20261025'
ARC=WS/'project_archives/rng_correlation_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def artifact(p,role='summary'):return dict(path=str(p),role=role,required=True,present_at_registration=True,bytes=p.stat().st_size,sha256=sha(p))

dst=ARC/'results';dst.mkdir(exist_ok=False)
for p in RESULT.iterdir():
    if p.is_file():shutil.copyfile(p,dst/p.name)
subprocess.run(['git','bundle','create',str(ARC/'execution.bundle'),'task/95-ideal-quality-20261025','^3b878c15'],cwd=ROOT,check=True)
subprocess.run(['git','bundle','verify',str(ARC/'execution.bundle')],cwd=ROOT,check=True)
manifest=json.loads((RESULT/'SOURCE_MANIFEST.json').read_text(encoding='utf8'))
for name,h in manifest.items():
    blob=subprocess.check_output(['git','show','2dd9ec33fa321174f3891b0cd684bc5aac4b589a:'+name],cwd=ROOT)
    assert hashlib.sha256(blob).hexdigest()==h
sources=list(manifest)+['architecture_tlm/random_service/quality/'+f for f in ['test_long_correlation.py','audit_correlation.py','report_correlation.py']]
with zipfile.ZipFile(ARC/'sources.zip','x',zipfile.ZIP_DEFLATED) as z:
    for name in sources:z.write(ROOT/name,name)
write(WORK/'SOURCE_PACKAGE_MANIFEST.json',{name:sha(ROOT/name) for name in sources})
summary=json.loads((RESULT/'SUMMARY.json').read_text(encoding='utf8'))['cases']
rawfiles=[f for c in summary for f in c['artifacts']]
for f in rawfiles:assert sha(Path(f['path']))==f['sha256']
index=dict(root=str(ARC),execution_commit='2dd9ec33fa321174f3891b0cd684bc5aac4b589a',
    execution_bundle=artifact(ARC/'execution.bundle','execution_commit_requires_local_parent_3b878c15'),
    sources=artifact(ARC/'sources.zip','execution_and_postprocessing_sources'),
    executable=artifact(ARC/'build/correlation_native.exe','validated_native_accelerator'),
    tables=artifact(ARC/'rng_correlation_20261025_tables.zip','full_physical_case_CSV'),
    summary=artifact(dst/'SUMMARY.json'),raw_artifact_count=len(rawfiles),raw_artifact_bytes=sum(f['bytes'] for f in rawfiles),
    raw_artifact_list='SUMMARY.json cases[].artifacts',access='local workspace; GitHub link does not grant archive access')
write(RESULT/'ARCHIVE_INDEX.json',index);shutil.copyfile(RESULT/'ARCHIVE_INDEX.json',dst/'ARCHIVE_INDEX.json')
shutil.copyfile(RESULT/'REPORT.html',WS/'远端上传/rng_correlation_20261025.html')
shutil.copyfile(ARC/'rng_correlation_20261025_tables.zip',WS/'远端上传/rng_correlation_20261025_tables.zip')
write(WORK/'VALIDATION.json',dict(status='PASS',native_unit_tests=5,runtime_checks=22524,post_audit_checks=6122,
    matrix_elements=17124432,physical_cases=18,shape_matched_iid_controls=18,frames_per_lane=131072,
    source_git_blobs_checked=len(manifest),raw_artifacts_sha_checked=len(rawfiles),
    compiler='MinGW.org GCC6.3.0-1; -O3 -std=c++11 -mpopcnt -static-libgcc -static-libstdc++',
    executable_sha256=sha(ARC/'build/correlation_native.exe'),
    execution_command='python -m architecture_tlm.random_service.quality.long_correlation --input <ideal_and_old_20000_v1> --out <new-results> --archive <new-archive> --exe <compiled-native-exe>',
    environment='OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1; Python3.12.14 NumPy2.3.5; report Python3.8/matplotlib3.7.5',
    limitations='Not EDA/RTL/PPA; native bulk flow verified against Python reference; single boot per physical seed/mode/backend; no 1s reseed',
    tool_issue='32bit MinGW cannot launch inside sandbox due DLL relocation; approved outside-sandbox compilation/execution succeeded; no data or algorithm workaround'))
record=dict(schema_version=1,id='rng-correlation-95-20261025',name='物理理想读出到三后端：全路时间空间相关长流',family='RNG质量诊断',
    registered_on='2026-10-25',owner='rayggxia',issue=95,evidence_level='DESIGN_PROOF',status='completed_diagnostic_not_certified',
    stages=dict(functional='pass',synthesis='not_run',sta='not_run',power='not_run',postlayout='not_run'),
    boundary='18物理播种+18同形状IID对照；两个实例，每路131072帧；R8/五阈值/八bitplane，全路131个时间lag和R8/阈值九个空间lag。',
    conditions=dict(node_nm=None,corner='physical input TT; functional digital model',voltage_V=None,temperature_C=25,clock_MHz=100,
        seeds=[32003,32009,32027],physical_interval_us=1,physical_samples_per_seed=20000,frames_per_lane=131072,
        reseed_cycles=100000000,periodic_reseed_observed=False,modes=['raw','vn'],sdf=False,spef=False,cts=False),
    source=dict(git_commit=None,local_execution_commit='2dd9ec33fa321174f3891b0cd684bc5aac4b589a',
        parent_local_commit='3b878c15',parent_remote_commit='057629881fcbf0704c87b70393bce1437edacae2',
        source_manifest_sha256=sha(RESULT/'SOURCE_MANIFEST.json'),config_sha256=sha(RESULT/'CONFIG.json'),
        binding='7 exact execution blobs, executable SHA, compiler command; Python/C++ exact tests and4096-frame golden prefix checks for18 cases'),
    artifacts=[artifact(dst/n) for n in ['CONFIG.json','SOURCE_MANIFEST.json','INPUT_MANIFEST.json','LAYERS.json','SUMMARY.json','AUDIT.json','POST_AUDIT.json','PEAKS.csv','REPORT.html','ARCHIVE_INDEX.json']]+[index['tables'],index['sources'],index['execution_bundle'],index['executable']],
    cases=[dict(case_id=c['case_id'],source=c['source'],backend=c['backend'],seed=c['physical_seed'],mode=c['mode'],frames_per_lane=c['frames'],
        q128_temporal_max_abs=c['stats']['q128']['temporal']['abs'],power_W=None,area_um2=None) for c in summary],
    limitations=['只有一个物理通道，物理空间相关无数据；三个noise seed不是并行物理lane。',
        '默认1s换种未触发；只有请求的种子前缀进入PRNG，全20k输入统计不意味着全20k驱动本次输出。',
        '不同后端路数不同，不能按最大相关直接排名；同形状软件IID对照不构成熵认证。',
        'GF64联合XOR/稀疏事件关系仍在；两两相关小不代表联合IID。',
        '无新Spectre/RTL/综合/STA/PT/LLM。无停顿操作数按固定动作累计，不冒称完整逐拍RTL仿真。'],
    next_action='复用本协议替换实际读出数据；按消费者的时间/空间相关合同验收，补真实多物理通道及重播种窗口。')
write(WORK/'registry_record.json',record)
for reg in [ROOT/'digital_circuit_simulation_registry',WS/'digital_circuit_simulation_registry']:
    subprocess.run([__import__('sys').executable,str(reg/'registry.py'),'add',str(WORK/'registry_record.json')],check=True)
    p=reg/'archive_inventory.csv';rows=list(csv.DictReader(p.open(encoding='utf8',newline='')))
    for f in [ARC/'sources.zip',ARC/'execution.bundle',ARC/'rng_correlation_20261025_tables.zip']:
        assert not any(r['path']==f.as_posix() for r in rows)
        buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n')
        w.writerow(dict(path=f.as_posix(),bytes=f.stat().st_size,sha256=sha(f),linked_records=record['id'],review_state='sha_verified_functional_only',note='长流质量仿真源/CSV，非PPA；不重复计实验'))
        with p.open('ab') as out:out.write(buf.getvalue().encode('utf8'))
    subprocess.run([__import__('sys').executable,str(reg/'registry.py'),'check'],check=True)
    subprocess.run([__import__('sys').executable,str(reg/'registry.py'),'render'],check=True)
print(json.dumps(dict(status='PASS',artifacts=len(rawfiles),bytes=index['raw_artifact_bytes'])))
