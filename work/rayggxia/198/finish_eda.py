"""Verify received originals, register the run, and preserve private provenance."""
from pathlib import Path
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import zipfile

R=Path(__file__).resolve().parents[3];WS=R.parents[1]
W=Path(__file__).parent;P=W/'.eda_private'
C=R/'architecture_tlm/attention_compare_20261027/control_v2'
E=C/'eda_20261028'
ARCH=WS/'project_archives/attention_compare_issue198_20261027/eda_20261028'
RID='attention-control-198-eda-20261028'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,indent=2,ensure_ascii=False)+'\n').encode())

def main():
    receipt=read(P/'COLLECTION.json')
    for local,meta in [(P/'EDA_REPORTS.tar.gz',receipt['reports'])]:
        assert local.stat().st_size==meta['bytes'] and sha(local)==meta['sha256']
    assert sha(P/'RESULTS_ORIGINAL.json')==receipt['results_sha256']
    assert sha(P/'RAW_INDEX.json')==receipt['raw_index_sha256']
    index=read(P/'RAW_INDEX.json')['files'];checked=[]
    with tarfile.open(P/'EDA_REPORTS.tar.gz') as t:
        for member in t.getmembers():
            if not member.isfile():continue
            b=t.extractfile(member).read()
            if member.name=='collection_v1/RAW_INDEX.json':
                assert hashlib.sha256(b).hexdigest()==receipt['raw_index_sha256']
            else:
                m=index[member.name];assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256'],member.name
            checked.append(member.name)
        evidence=E/'evidence';evidence.mkdir(exist_ok=True)
        for version in ['v1','v2','v3','collect_v1']:
            b=t.extractfile('snapshots/'+version+'/SOURCE.json').read()
            (evidence/(version+'_SOURCE.json')).write_bytes(b)
    assert len(checked)>1000
    audit=P/'timing_audit_v1.tar.gz'
    assert sha(audit)=='4d92ac5c8a7fe64ea384c5e9bb9de921ffdd2ecccf8eaf40fafbf29c03ad8bb3'
    data=read(E/'RESULTS.json');assert len(data['results'])==8
    assert sum(len(x['power_windows']) for x in data['results'])==66
    assert all(x['hold_ns']<0 for x in data['results'])
    ARCH.mkdir(parents=True,exist_ok=False)
    for name in ['EDA_REPORTS.tar.gz','timing_audit_v1.tar.gz','RESULTS_ORIGINAL.json','RAW_INDEX.json','COLLECTION.json']:
        shutil.copyfile(P/name,ARCH/name)
    # Preserve internal paths/commands locally, publish only their byte hashes.
    write(ARCH/'ARCHIVE_PRIVATE.json',dict(remote=receipt,remote_root=read(P/'RAW_INDEX.json')['root'],
        full_raw_archive_local=False,full_raw_archive_member_recheck_local=False,
        small_report_members_verified=len(checked),audit_members_verified=read(E/'TIMING_AUDIT.json')['verified_members']))
    operations=ARCH/'LOCAL_OPERATIONS.zip'
    with zipfile.ZipFile(operations,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in P.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(P).as_posix())
        # Local compatibility regression is not another server PPA run.
        for p in (C/'results/rejection_dc_compat').glob('*'):
            if p.is_file() and p.suffix!='.vvp':z.write(p,'rejection_dc_compat/'+p.name)
    with zipfile.ZipFile(operations) as z:assert z.testzip() is None
    artifacts=[]
    for p,role in [(E/'RESULTS.json','public_numeric_results'),(E/'TIMING_AUDIT.json','timing_arc_and_hold_audit'),
        (ARCH/'EDA_REPORTS.tar.gz','private_original_reports_and_source_snapshots'),
        (ARCH/'timing_audit_v1.tar.gz','private_additional_sta_reports'),
        (ARCH/'ARCHIVE_PRIVATE.json','private_remote_full_raw_archive_location_and_sha'),
        (operations,'private_local_commands_snapshots_and_regression')]:
        artifacts.append(dict(path=str(p),role=role,present_at_registration=True,required=True,
                              bytes=p.stat().st_size,sha256=sha(p)))
    write(W/'EDA_ARCHIVE.json',dict(local_artifacts=artifacts,remote_raw=dict(bytes=receipt['raw']['bytes'],sha256=receipt['raw']['sha256'],
        access='authorized EDA server only; exact path in private local archive index',downloaded=False),
        private_index_path=str(ARCH/'ARCHIVE_PRIVATE.json'),no_private_library_or_models_published=True))
    write(W/'EDA_COLLECTION_CHECK.json',dict(report_archive_sha256=receipt['reports']['sha256'],
        report_members_sha_verified=len(checked),original_files_indexed=len(index),
        original_results_sha256=receipt['results_sha256'],raw_index_sha256=receipt['raw_index_sha256'],
        audit_archive_sha256=sha(audit),audit_members_verified=read(E/'TIMING_AUDIT.json')['verified_members'],
        all_116_functional_checks_pass=True,power_windows=66,sta='violations',remote_full_raw_not_downloaded=True))
    write(W/'EDA_SOURCE.json',dict(parent_commit='157e19c6823b2cd3434ed6cd99ff1786e07824f0',
        executed_manifests={p.name:sha(p) for p in (E/'evidence').glob('*SOURCE.json')},
        current_source={p.relative_to(R).as_posix():sha(p) for p in list((E).rglob('*'))+[C/'rtl/ac_rejection.sv'] if p.is_file() and '__pycache__' not in p.parts},
        notes='exact executed snapshots retained; report/audit helpers added after original source_v3 freeze; no circuit equations changed'))
    cases=[]
    for top in data['results']:
        for p in top['power_windows']:
            cases.append(dict(top=top['spec']['top'],trace=p['trace'],window=p['window'],
                raw_area_um2=top['raw_cell_area_um2'],area_55nm_equivalent_um2=top['area_55nm_equivalent_um2'],
                power_W=p['power']['total_W'],internal_W=p['power']['internal_W'],switching_W=p['power']['switching_W'],leakage_W=p['power']['leakage_W'],
                setup_ns=top['setup_ns'],hold_ns=top['hold_ns'],warning_codes=p['warning_codes'],
                power_report_sha256=p['power_report_sha256'],status='calculated_with_hold_violations'))
    record=dict(schema_version=1,id=RID,name='Attention反馈/仲裁8top服务器DC/VCS/PT：66窗口，保留hold违例',
        family='Attention/控制',registered_on='2026-10-28',owner='rayggxia',issue=198,
        evidence_level='DC_GATE_PT_PRELAYOUT',status='calculated_hold_violations_annotation_warnings',
        stages=dict(functional='pass',synthesis='completed',sta='violations',power='calculated',postlayout='not_run'),
        boundary='N512赢家无偏rank/反馈弹性流水与拒绝公平校正；debug统计断开；不含RNG/概率比较及重编码/QK/V/SRAM/输出累加',
        conditions=dict(node_nm=65,target_equivalent_area_nm=55,area_only_scale=.81,raw_geometry='user-confirmed SHARK unshrunk; library retains original ICsprout55 label',
            corner='SS',voltage_V=1.08,temperature_C=125,clock_MHz=100,seeds=[17,503,1009],
            window_ns=None,load_pF=.02,input_transition_ns=.1,setup_uncertainty_ns=2,hold_uncertainty_ns=.1,
            sdf=False,spef=False,cts=False,activity='same mapped-netlist zero-delay VCS VCD; explicit 66 averaged PT windows; ideal clock, clock-pin power included'),
        source=dict(git_commit=None,source_manifest_sha256=sha(W/'EDA_SOURCE.json'),binding='parent157e19c plus exact v1/v2/v3/collect/audit SOURCE manifests and current source index; source SHA not inferred from HEAD'),
        artifacts=artifacts,cases=cases,limitations=['所有top hold<0；多数最短路径从rst_n输入，0最小IO delay/0.1ns hold uncertainty；不能称签核',
          '100% net/cell标注仍有PWR-981；额外时序审计确认无loop-breaking/user false/multicycle例外，p/C禁用保留',
          '零延迟平均活动，未含完整毛刺/布线RC/CTS；面积×0.81不缩放功耗/时序',
          '合成压力能量/输出不代表独立有效样本或真实Attention质量；模型/完整通路未测',
          '私有完整大包仅服务器；本机已核小报告和72成员时序审计，不虚报完整大包下载'],
        next_action='G16融合为主候选，明确reset/配置IO合同、修hold和PWR-981后同约束STA，再决定更高频率/ICG；非自动模型重跑')
    record_path=R/'digital_circuit_simulation_registry/records'/f'{RID}.json';write(record_path,record)
    reg=WS/'digital_circuit_simulation_registry';check=W/'eda_registry_check';check.mkdir(exist_ok=False)
    names=['catalog.json','archive_inventory.csv','00_总览.md','01_结果地址索引.md','runs.csv','artifact_locations.csv']
    pre={n:sha(reg/n) for n in names};old={p.name:sha(p) for p in (reg/'records').glob('*.json')}
    for n in ['registry.py','catalog.json','archive_inventory.csv']:shutil.copyfile(reg/n,check/n)
    shutil.copytree(reg/'records',check/'records')
    subprocess.run([sys.executable,str(check/'registry.py'),'add',str(record_path)],check=True)
    rows=[]
    for p in [ARCH/'EDA_REPORTS.tar.gz',ARCH/'timing_audit_v1.tar.gz',operations]:
        rows.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p),linked_records=RID,review_state='sha_verified_local',note='authorized private archive; same circuit run, not another experiment'))
    fields=['path','bytes','sha256','linked_records','review_state','note'];out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=fields,lineterminator='\n');writer.writerows(rows)
    with (check/'archive_inventory.csv').open('ab') as f:f.write(out.getvalue().encode())
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    (W/'EDA_ARCHIVE_INVENTORY_APPEND.csv').write_bytes(out.getvalue().encode())
    result=subprocess.run([sys.executable,str(check/'registry.py'),'check'],capture_output=True,text=True,check=True)
    write(W/'EDA_REGISTRY_CHECK.json',json.loads(result.stdout));subprocess.run([sys.executable,str(check/'registry.py'),'render'],check=True)
    assert pre=={n:sha(reg/n) for n in names} and old=={p.name:sha(p) for p in (reg/'records').glob('*.json')}
    backup=ARCH/'reading_preimages';backup.mkdir()
    for n in names:shutil.copyfile(reg/n,backup/n)
    assert not (reg/'records'/record_path.name).exists();shutil.copyfile(record_path,reg/'records'/record_path.name)
    for n in names:shutil.copyfile(check/n,reg/n)
    assert all(sha(reg/'records'/n)==s for n,s in old.items())
    write(W/'EDA_REGISTRY_SYNC.json',dict(old_records=len(old),new_records=len(old)+1,all_old_records_unchanged=True,
        record_sha256=sha(record_path),preimages=str(backup)))
    # Keep old reports as dated evidence, point current readers to new results.
    for p in [C/'README_ZH.md',C.parent/'README_ZH.md']:
        b=p.read_bytes();p.write_bytes(('2026-10-28更新：已完成服务器DC/VCS/PT，见[结果](eda_20261028/RESULTS_ZH.md)。'
             '下文为2026-10-27冻结阶段，STA/PT未跑的说法仅指当时；本轮有hold违例和PWR-981，未签核。\n\n' if p==C/'README_ZH.md' else
             '2026-10-28更新：服务器采样控制评估见[最新结果](control_v2/eda_20261028/RESULTS_ZH.md)，其余旧阶段保留原始日期和限制。\n\n').encode()+b)
    with (R/'digital_circuit_simulation_registry/ATTENTION_198_INTEGRATION_ZH.md').open('ab') as f:f.write(('\n2026-10-28：另新增'+RID+'，8top/116回放/66PT窗口，STA=violations、power=calculated。合并独立record并按EDA_ARCHIVE_INVENTORY_APPEND.csv增量追加，check/render结果见EDA_REGISTRY_CHECK.json；不能覆盖其他分支catalog。\n').encode())
    log=R/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md'
    if not log.exists():log.write_bytes(subprocess.check_output(['git','show','HEAD:architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md']))
    with log.open('ab') as f:f.write(('\n\n## 2026-10-28 Issue198：完整采样反馈/仲裁服务器电路评估\n\n'
      '沿用PR199，8固定控制top同SS100约束DC/VCS/PT，116回放230400拍、66功耗窗口，额外8top时序审计。G16融合折算面积0.035969mm²，较G16两级小14.2%；全1吞吐压力每输出17.17pJ，低21.8%，非独立有效样本/完整Attention。所有hold为负、PWR-981保留；最短路径rst_n，禁用弧仅p/C、无loop-breaking或用户false/multicycle。按需/预取拒绝控制微收益2%–3%未计额外公平位。原面积×0.81另列，不缩功耗/时序。入口attention_compare_20261027/control_v2/eda_20261028/RESULTS_ZH.md，统一run attention-control-198-eda-20261028。无模型/PPL/布线；下一步IO/reset合同/hold/标注。\n').encode())
    prefix=('## 2026-10-28 Issue198：服务器采样控制PPA首轮完成\n\n'
      '用户授权EDA；rayggxia/task198/草稿PR199。DC8top；VCS RTL+门级116项230400拍逐周期oracle通过；PT66显式窗口计算、net/cell标注均100%。'
      'SS1.08V125C100MHz，core IO delay0/slew.1ns/load.02pF/setup uncertainty2ns/hold.1ns；无SDF/SPEF/CTS。'
      'G16融合原面积0.044406mm²→按SHARK×.81折算0.035969mm²，较G16两级面积−14.2%；全1吞吐压力17.17pJ/输出、−21.8%，不代表独立有效样本/完整Attention。\n\n'
      '全部候选hold−.0219..−.1141ns，setup报告非负但提前保持仅.000527ns。额外38437962静态审计：最短hold从rst_n开始，禁用弧p/C，无loop-breaking或用户false/multicycle，常量禁用checks保留；PWR-981部分向量映射告警仍待专项闭合。'
      '功耗calculated但STA violations，不称签核/500MHz/物理实测。内部时钟引脚功耗已在总功率、不重复加clock组；无ICG。拒绝预取控制能量仅省2%–3%，外供fair64→128仍未计。\n\n'
      '预检38437604的声明顺序失败保留，coin_mask先声明后引用，20项90000拍复核通过；DC38437625/38437668，回放PT38437709/38437736，归档38437848。'
      '正式control_v2/eda_20261028/RESULTS_ZH.md及JSON；源/配置/归档SHA与私有原件入口work/rayggxia/198/EDA_*。原始大包仅服务器，本地小报告逐成员及72时序审计成员已核，不公开连接/库/模型/网表。'
      '中央台账新增attention-control-198-eda-20261028，增量check/render保留旧记录；无模型/GPU/PPL，后续明确IO/reset合同、修hold/标注后再提频。准确上传看EDA_PUBLICATION.json；PR待审未合并。两备忘录旧字节分别保留。\n\n---\n\n').encode()
    memories=[]
    for i,p in enumerate([WS/'PROJECT_MEMORY_ZH.md',WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md']):
        b=p.read_bytes();(backup/('memory_'+str(i)+'.bin')).write_bytes(b);assert p.read_bytes()==b;p.write_bytes(prefix+b)
        memories.append(dict(path=str(p),old_sha256=hashlib.sha256(b).hexdigest(),new_sha256=sha(p)))
    write(W/'EDA_MEMORY_SYNC.json',dict(memories=memories,preimages=str(backup),old_bytes_preserved=True))
    stage=('2026-10-28服务器评估已完成：8DC/116VCS回放230400拍/66PT窗口及8top时序审计，所有hold违例，PWR-981保留；无签核/模型结论。'
      '主候选G16融合折算0.035969mm²、全1控制17.17pJ/输出。准确结果RESULTS_ZH.md，源/作业/原件EDA_*；原始私有大包仅服务器。'
      '本地报告包逐成员SHA与72诊断成员已核；上传见EDA_PUBLICATION.json，PR199待审。下一步IO/reset合同/hold/标注，无需重跑健康原任务。\n\n').encode()
    for p in [R/'progress/rayggxia/STATUS.md',W/'HANDOFF.md']:
        b=p.read_bytes();p.write_bytes(stage+b)
    d=read(W/'EDA_SUBMISSION_INDEX.json');d['status']='all requested first-stage circuit tests and audits completed; publication pending';d['jobs'].update(collection=38437848,timing_audit=38437962);write(W/'EDA_SUBMISSION_INDEX.json',d)
    print(json.dumps(dict(local_archive=str(ARCH),report_members=len(checked),registry=json.loads(result.stdout))))

if __name__=='__main__':main()
