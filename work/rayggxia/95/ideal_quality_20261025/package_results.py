"""Archive one completed diagnostic run and prepare its central registry record."""
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[4]
ws = Path('C:/Users/86134/Documents/a_P_BIT')
result = root/'architecture_tlm/random_service/quality/results/ideal_20261025'
archive = ws/'project_archives/rng_ideal_quality_20261025'
work = Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def artifact(p,role):return dict(path=str(p),role=role,required=True,present_at_registration=True,sha256=sha(p),bytes=p.stat().st_size)

# Immutable snapshot; fail rather than silently replace an existing archive.
dst = archive/'results'
dst.mkdir(exist_ok=False)
for p in result.iterdir():
    if p.is_file():shutil.copyfile(p,dst/p.name)
source_files = ['architecture_tlm/random_service/quality/'+n for n in
    ('ideal_readout.py','test_ideal_readout.py','audit_ideal.py','report_ideal.py','metrics.py')]
source_files += ['architecture_tlm/random_service/'+n for n in ('model.py','backends.py','shared64_mapping.json')]
with zipfile.ZipFile(archive/'sources.zip','x',zipfile.ZIP_DEFLATED) as z:
    for name in source_files:z.write(root/name,name)
source_hashes = {name:sha(root/name) for name in source_files}
write(work/'SOURCE_PACKAGE_MANIFEST.json',source_hashes)
with zipfile.ZipFile(archive/'sources.zip') as z:
    assert all(hashlib.sha256(z.read(name)).hexdigest()==h for name,h in source_hashes.items())
summary=json.loads((result/'SUMMARY.json').read_text(encoding='utf8'))
index=dict(archive=str(archive),results=artifact(dst/'RESULTS.json','full_results'),
    source_package=artifact(archive/'sources.zip','execution_sources_plus_later_tests_analysis'),
    execution_bundle=artifact(archive/'execution.bundle','execution_commit_requires_base_d6d33995'),
    digital_npz_count=len(summary['cases']),digital_npz_bytes=sum(c['artifact']['bytes'] for c in summary['cases']),
    artifact_list='SUMMARY.json cases[].artifact',note='Stable local archive; access is not implied by GitHub publication.')
write(result/'ARCHIVE_INDEX.json',index);shutil.copyfile(result/'ARCHIVE_INDEX.json',dst/'ARCHIVE_INDEX.json')
shutil.copyfile(result/'REPORT.html',ws/'远端上传/rng_ideal_quality_20261025.html')
test=subprocess.run([sys.executable,'-m','unittest','architecture_tlm.random_service.quality.test_ideal_readout','-v'],cwd=root,capture_output=True)
(work/'tests.log').write_bytes(test.stdout+test.stderr)
assert test.returncode==0
write(work/'VALIDATION.json',dict(status='PASS',unit_tests=6,audit_checks=8956,cases=225,
    execution_commit='bdbab3e38ff56e267783af9ac327dbba67a0e169',
    independent_review='Read-only second agent: all225 NPZ,3609 assertions, no blocking findings; reviewed timing/seed/state/statistics and report scope.',
    later_test_changes='Added internal-state equality and due-boundary test after execution freeze. Initial strict report-dict equality differed only by missing/explicit zero Counter keys; final internal Counter equality passes. No model/execution source changed.',
    browser='See BROWSER_CHECK.json; first sandbox Edge launch failed, separate-profile elevated launch used for verification.',
    command=[sys.executable,'-m','architecture_tlm.random_service.quality.ideal_readout','--input',str(ws/'analog_pbit_20261016/ideal_and_old_20000_v1'),'--out',str(result),'--raw-out',str(archive/'digital')],
    test_log_sha256=sha(work/'tests.log'),report_sha256=sha(result/'REPORT.html')))
record=dict(schema_version=1,id='rng-ideal-quality-95-20261025',name='理想读出20k：有时间戳的分层随机质量',
    family='RNG质量诊断',registered_on='2026-10-25',owner='rayggxia',issue=95,evidence_level='DESIGN_PROOF',
    status='diagnostic_completed_not_quality_certified',
    stages=dict(functional='pass',synthesis='not_run',sta='not_run',power='not_run',postlayout='not_run'),
    boundary='216主案例+9重复种子故障对照，每例2端点4096帧；3条已有物理轨迹的理想/旧比较器读出及合成IID。直通/VN、定时种子分发、LFSR/GF64/Bivium、局部算术及联合探针。',
    conditions=dict(node_nm=None,corner='Physical TT; digital functional model no PVT',voltage_V=None,temperature_C=25,
        clock_MHz=100,physical_sample_us=1,seeds=[32003,32009,32027],input_bits_per_seed=20000,
        cold_boot_windows=4,window_samples=5000,frames_per_endpoint=4096,reseed_cycles=100000000,periodic_reseed_observed=False,
        source_timing='last constituent raw bit +1 idealized cycle; fresh packet per endpoint; no source looping',sdf=False,spef=False,cts=False),
    source=dict(git_commit=None,local_execution_commit='bdbab3e38ff56e267783af9ac327dbba67a0e169',
        base_git_commit='d6d33995754fcdcea99286e4ce43f91647aa231a',source_manifest_sha256=sha(result/'SOURCE_MANIFEST.json'),
        config_sha256=sha(result/'CONFIG.json'),input_manifest_sha256=sha(result/'INPUT_MANIFEST.json'),
        binding='5 exact execution files; local commit preserved in execution.bundle; later tests/audit/report source package separately bound'),
    artifacts=[artifact(dst/n,'summary') for n in ('CONFIG.json','SOURCE_MANIFEST.json','INPUT_MANIFEST.json','STAGES.json','SUMMARY.json','AUDIT.json','ARCHIVE_INDEX.json','REPORT.html')]+[index['results'],index['source_package'],index['execution_bundle']],
    cases=[dict(case_id=c['case_id'],backend=c['backend'],source=c['source'],seed=c['seed'],conditioner=c['mode'],boot=c['boot'],
        diagnostic_status=c['status'],power_W=None,area_um2=None,output_p1=c['output']['first_lane']['p1'],
        rho1=c['output']['first_lane']['rho']['1'],first_request_us=c['first_output_us']) for c in summary['cases']],
    limitations=['不是熵率认证、独立性证明、完整FFN/Attention/LLM结果或新RTL/PPA。',
        '理想阈值来自仍带旧比较器负载的核心；MID全保留；TT/noisefmin500Hz记录不覆盖慢漂移及空间相关。',
        '四冷启动来自每条轨迹的四固定段，不是12独立物理seed；本轮不触发1s周期换种。',
        'GF64前四路XOR恒0，稀疏命中偏离IID；较好种子不能修复固定映射关系。',
        '原始NPZ及完整JSON在稳定本机归档；远端读者需另获存储访问。'],
    next_action='替换后续实际比较器数据，扩展物理空间/长时间记录；按真实消费者检查联合相关，不将PRNG统计当物理熵。')
write(work/'registry_record.json',record)
print(json.dumps(dict(summary_bytes=(result/'SUMMARY.json').stat().st_size,archive=str(archive),status='PASS')))
