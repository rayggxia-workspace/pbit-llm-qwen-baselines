"""Freeze private raw bytes, portable sources, and incremental registry evidence."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
WS=ROOT.parents[1]
W=Path(__file__).parent
A=ROOT/'architecture_tlm/attention_compare_20261027'
C=A/'control_v2'
ARCH=WS/'project_archives/attention_compare_issue198_20261027'
RID='attention-control-198-v2-20261027'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))
def text(p,s):p.write_bytes(s.encode('utf-8'))
def freeze_zip(target,entries):
    assert not target.exists(),target
    target.parent.mkdir(parents=True,exist_ok=True)
    members={name:dict(sha256=sha(p),bytes=p.stat().st_size) for name,p in entries.items()}
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in entries.items():z.write(p,name)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name,m in members.items():
            b=z.read(name)
            assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
    return dict(path=str(target),sha256=sha(target),bytes=target.stat().st_size,members=members)

def main():
    e=read(C/'EVALUATION.json')
    assert len(e['gate_checks'])==3 and all(g['status']=='pass' for g in e['gate_checks'])
    assert e['winner_cases']==104 and e['rejection_cases']==20
    assert len(e['mapped'])==8 and all(not m['unmapped_types'] for m in e['mapped'])
    # Git contains small exact summaries; all raw artifacts remain recoverable.
    evidence=C/'evidence';evidence.mkdir(exist_ok=True)
    paths=['winner_release2/SOURCE.json','winner_release2/VALIDATION.json',
           'rejection_v1/SOURCE.json','rejection_v1/VALIDATION.json',
           'map_ss047_v1/SUMMARY.json','map_ss_matrix/SUMMARY.json',
           'ppa_bundle_final/CASES.json']
    paths += [str(p.relative_to(C/'results')).replace('\\','/') for p in (C/'results').glob('gate_final_*/VALIDATION.json')]
    for rel in paths:
        dest=evidence/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(C/'results'/rel,dest)
    tops=C/'tops';tops.mkdir(exist_ok=True)
    for p in (C/'results/ppa_bundle_final/rtl').glob('*.sv'):
        if p.stem.startswith(('win512_','rej512_')):shutil.copyfile(p,tops/p.name)
    text(C/'.gitignore','results/\n__pycache__/\n')
    ig=(W/'.gitignore').read_text()
    for line in ['.tools_yosys047/','.yosys_tmp/','control_registry_check/','portable_check/']:
        if line not in ig:ig+=line+'\n'
    text(W/'.gitignore',ig)
    # Keep private library-derived netlists/models and every failure local only.
    entries={'results/'+str(p.relative_to(C/'results')).replace('\\','/'):p
             for p in (C/'results').rglob('*') if p.is_file() and p.suffix!='.vvp'}
    for p in W.glob('YOSYS*PROBE.log'):entries['probes/'+p.name]=p
    raw=freeze_zip(ARCH/'raw_control_v2.zip',entries)
    raw.update(access='authorized local archive only; contains private library-derived netlists/models; never publish',
       excluded='regenerable .vvp binaries; original private Liberty/LEF not copied',
       failures_preserved=['finishing state priority bug','overstrict serial coverage assertion',
          'Windows sandbox ABC temp directory','initial cap8 oracle vs cap64 mapped top mismatch; corrected matched cap64 tests pass'])
    write(W/'CONTROL_RAW_ARCHIVE.json',raw)
    # Freeze current public source closure. Functional execution snapshots in raw
    # archive remain authoritative where the helper subsequently gained options.
    public=[p for p in C.rglob('*') if p.is_file() and 'results' not in p.relative_to(C).parts
            and '__pycache__' not in p.relative_to(C).parts]
    source={str(p.relative_to(ROOT)).replace('\\','/'):dict(sha256=sha(p),bytes=p.stat().st_size) for p in public}
    write(W/'CONTROL_SOURCE_MANIFEST.json',dict(parent_commit='0fc3969004433056e3074c0bc37a8626df3aabb0',
        files=source,python=sys.version,rtl_tool='Icarus10.1',mapping_tool='Yosys0.47/ABC via YoWASP',
        executed_snapshots='CONTROL_RAW_ARCHIVE.json members results/*/SOURCE.json and SOURCE_FILES.zip',
        source_caveat='validate.generate gained optional rankcap argument after winner_release2; default unchanged. No RTL changed after final sweep. Gate tests explicitly cap64.'))
    packet={str(p.relative_to(ROOT)).replace('\\','/'):p for p in public}
    for p in [A/'__init__.py',A/'rtl/nr_singleton_tree.sv',W/'CONTROL_SOURCE_MANIFEST.json',W/'CONTROL_AREA_UNITS.json']:
        packet[str(p.relative_to(ROOT)).replace('\\','/')]=p
    portable=freeze_zip(WS/'output/attention_control_issue198_20261027/attention_control_v2.zip',packet)
    portable.update(access='public-safe source packet; no library, mapped netlist, cell models or private paths content beyond indexes')
    write(W/'CONTROL_PORTABLE.json',portable)
    # Record once per circuit assessment; variants are cases, not new run IDs.
    artifacts=[]
    for p,role in [(C/'EVALUATION.json','aggregate_rtl_mapping_gate_results'),
                   (W/'CONTROL_SOURCE_MANIFEST.json','source_manifest'),
                   (W/'CONTROL_AREA_UNITS.json','area_units_lef_crosscheck'),
                   (Path(raw['path']),'private_raw_logs_vectors_netlists_failures'),
                   (Path(portable['path']),'portable_public_sources')]:
        artifacts.append(dict(path=str(p),role=role,present_at_registration=True,required=True,
                              sha256=sha(p),bytes=p.stat().st_size))
    cases=[]
    for c in e['mapped']:
        cases.append(dict(top=c['top'],functional='pass',synthesis='completed',area_um2=c['area_um2'],
                          cells=c['cells'],gate_functional=c.get('gate_functional','not_run'),
                          sta='not_run',power='not_run',frequency_constraint_MHz=None))
    record=dict(schema_version=1,id=RID,name='Attention完整赢家/拒绝反馈仲裁：124RTL案例与8个55nm库映射',
        family='Attention/控制',registered_on='2026-10-27',owner='rayggxia',issue=198,
        evidence_level='PARTIAL_FLOW',status='rtl_and_mapping_pass_sta_power_pending',
        stages=dict(functional='pass',synthesis='completed',sta='not_run',power='not_run',postlayout='not_run'),
        boundary='N512固定top；赢家分组popcount/scan/无偏rank/保持反馈/有限弹性流水，拒绝m反馈与公平位预取；不含RNG/比较器/阈值重编码/QK/V/SRAM/输出累加',
        conditions=dict(node_nm=55,corner='SS',voltage_V=1.08,temperature_C=125,clock_MHz=None,
            testbench_clock_MHz=100,seeds=[17,503,1009],window_ns=None,load_pF=None,sdf=False,spef=False,cts=False,
            activity='synthetic held valid/ready bits; 104winner/332800cycles,20rejection/90000cycles,3zero-delay gate/1920cycles; mapping unconstrained frequency'),
        source=dict(git_commit=None,source_manifest_sha256=sha(W/'CONTROL_SOURCE_MANIFEST.json'),
             binding='parent 0fc3969 plus exact current manifest; executed SOURCE_FILES snapshots and PPA bundle frozen in private raw archive'),
        artifacts=artifacts,cases=cases,
        limitations=['映射面积不是STA通过/DC/PT/布局/实测功耗；debug计数器从PPA顶层断开',
          'cap8压力RTL与cap64部署top分开；最终门级三top已用匹配cap64',
          '公平位独立与概率源/配置稳定由上游保证；有限cap失败显式上报，不能当成功query',
          '原始私有网表/库导出模型仅本机授权ZIP；公开包不含私有资料',
          '后训练真实QKV/PPL、完整V链/GQA/源时序仍待验证'],
        next_action='SS100MHz实际STA后比较融合/两级准备/G32候选，再门级活动PT；不自动启动昂贵服务器/模型重跑')
    record_path=ROOT/'digital_circuit_simulation_registry/records'/f'{RID}.json'
    write(record_path,record)
    # Union the current shared reading mirror without copying other worktrees.
    reg=WS/'digital_circuit_simulation_registry';check=W/'control_registry_check'
    check.mkdir(exist_ok=False)
    tracked=['catalog.json','archive_inventory.csv','00_总览.md','01_结果地址索引.md','runs.csv','artifact_locations.csv']
    pre={n:sha(reg/n) for n in tracked}
    pre_records={p.name:sha(p) for p in (reg/'records').glob('*.json')}
    for n in ['registry.py','catalog.json','archive_inventory.csv']:shutil.copyfile(reg/n,check/n)
    shutil.copytree(reg/'records',check/'records')
    subprocess.run([sys.executable,str(check/'registry.py'),'add',str(record_path)],check=True)
    # Preserve inventory original bytes, append only previously unindexed archives.
    rows=list(csv.DictReader((check/'archive_inventory.csv').open(encoding='utf-8',newline='')))
    known={r['path'] for r in rows}
    additions=[]
    for archive,run in [(ARCH/'raw_runs_v1.zip','attention-rejection-198-20261027'),(Path(raw['path']),RID)]:
        if str(archive) not in known:
            additions.append(dict(path=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),linked_records=run,
                review_state='sha_verified_local',note='original archive bytes and members verified; authorized local access'))
    out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=list(rows[0]))
    writer.writerows(additions)
    with (check/'archive_inventory.csv').open('ab') as f:f.write(out.getvalue().encode('utf-8'))
    result=subprocess.run([sys.executable,str(check/'registry.py'),'check'],capture_output=True,text=True,check=True)
    write(W/'CONTROL_REGISTRY_CHECK.json',json.loads(result.stdout))
    subprocess.run([sys.executable,str(check/'registry.py'),'render'],check=True)
    # Guard every old run and generated preimage before incremental synchronization.
    assert pre=={n:sha(reg/n) for n in tracked}
    assert pre_records=={p.name:sha(p) for p in (reg/'records').glob('*.json')}
    backup=ARCH/'control_reading_preimages';backup.mkdir(exist_ok=False)
    for n in tracked:shutil.copyfile(reg/n,backup/n)
    assert not (reg/'records'/record_path.name).exists()
    shutil.copyfile(record_path,reg/'records'/record_path.name)
    for n in tracked:shutil.copyfile(check/n,reg/n)
    subprocess.run([sys.executable,str(reg/'registry.py'),'check'],check=True)
    assert all(sha(reg/'records'/n)==s for n,s in pre_records.items())
    write(W/'CONTROL_REGISTRY_SYNC.json',dict(old_records=len(pre_records),new_records=len(pre_records)+1,
       old_records_unchanged=True,inventory_appended=additions,preimages=str(backup),record_sha256=sha(record_path)))
    prefix=('## 2026-10-27 Issue198：完整采样反馈/仲裁电路v2\n\n'
      '沿用rayggxia/task198/草稿PR199。实现分组popcount/平衡scan/无偏按秩选择、真实赢家有序提交、有限弹性流水、burn/回压/rank cap，'
      '以及拒绝路径公平位预取消融。3精确数学测试、104赢家332800拍、20拒绝90000拍通过；3个匹配cap64固定top零延迟门级共1920拍通过。'
      'N512/S128+burn16全1控制轨迹串行577拍→融合147/两级148；这是控制供数理想压力例，不是Attention整机提速。\n\n'
      '本地55nm SS1.08V125C Yosys0.47/ABC八top完成映射，LEF核单位。赢家0.040823–0.056112mm²，拒绝0.018058/0.018223mm²。'
      '无频率约束、STA/PT/功耗/布局未跑；G16融合面积最小、两级及G32待时序选择，未称全局最优。拒绝预取同地址SHA省64拍但fair64→128，'
      '提前保持省fair却增加组合依赖；一热面积增加。源/比较器/配置重编码/QK/V/累加/存储在边界外。\n\n'
      '正式control_v2/README_ZH.md和EVALUATION.json，公开源码ZIP及私有原字节ZIP/失败保留/SHA见work/rayggxia/198/CONTROL_*。'
      '统一台账新增attention-control-198-v2-20261027，增量union/check/render；旧记录不改。'
      '当前本地完成，准确远端状态看CONTROL_PUBLICATION.json；PR待审不关闭Issue。无GPU/Slurm/许可EDA/模型PPL，旧v1不变。'
      '两记忆各前置同段并保留已有不同旧字节。\n\n---\n\n').encode('utf-8')
    memories=[]
    for i,p in enumerate([WS/'PROJECT_MEMORY_ZH.md',WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md']):
        b=p.read_bytes();(backup/f'memory_{i}.bin').write_bytes(b)
        assert b'Issue198\xef\xbc\x9a\xe5\xae\x8c\xe6\x95\xb4\xe9\x87\x87\xe6\xa0\xb7' not in b[:3000]
        p.write_bytes(prefix+b);assert p.read_bytes()[len(prefix):]==b
        memories.append(dict(path=str(p),old_sha256=hashlib.sha256(b).hexdigest(),new_sha256=sha(p)))
    write(W/'CONTROL_MEMORY_SYNC.json',dict(memories=memories,preimages=str(backup),old_bytes_preserved=True))
    stage=('2026-10-27 控制v2本地完成，上传状态见CONTROL_PUBLICATION.json（尚未生成即未确认发布）。'
      '完整赢家/拒绝反馈仲裁RTL、8固定PPA top、独立oracle/数学检查、DC/PT脚本在control_v2。'
      '124RTL项422800拍及3个cap64零延迟门级1920拍通过，8个55nm SS映射0.018058–0.056112mm²；'
      'STA/功耗未跑，不把TB100MHz当时序通过。源码/原字节/公开包/台账/记忆同步见CONTROL_*。'
      '保留G16融合/两级及G32候选待STA；源供给/完整V链/后训练QKV/GQA/D1仍待补。'
      '无运行中GPU/Slurm/许可EDA作业；PR199草稿、未合并。\n\n')
    for p in [ROOT/'progress/rayggxia/STATUS.md',W/'HANDOFF.md']:
        b=p.read_bytes();p.write_bytes(stage.encode()+b)
    with (A/'README_ZH.md').open('ab') as f:f.write(('\n\n## 2026-10-27 完整反馈与仲裁电路v2\n\n'
       '新增[专门报告](control_v2/README_ZH.md)：124RTL项、3门级回放、8个55nm库映射面积。'
       '这是控制边界的新证据，STA/PT/完整Attention能耗仍未知；上述v1冻结结果保持原标注。\n').encode())
    write(W/'CONTROL_DELIVERY.json',dict(local_stage='complete; publication pending',rtl_cases=124,rtl_cycles=422800,
       mathematical_tests=3,gate_cases=3,gate_cycles=1920,mapped_cases=8,sta='not_run',power='not_run',
       raw_sha256=raw['sha256'],portable_sha256=portable['sha256'],registry=read(W/'CONTROL_REGISTRY_CHECK.json')))
    print(json.dumps(dict(raw_bytes=raw['bytes'],raw_members=len(raw['members']),portable_bytes=portable['bytes'],
                         registry=read(W/'CONTROL_REGISTRY_CHECK.json'))))

if __name__=='__main__':main()
