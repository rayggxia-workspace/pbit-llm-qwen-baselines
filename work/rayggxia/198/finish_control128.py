"""Verify immutable EDA originals and generate the control-only comparison."""
from pathlib import Path
import hashlib,json,tarfile,statistics,re,shutil,zipfile,subprocess,sys,csv,io
R=Path(__file__).resolve().parents[3];WS=R.parents[1];W=Path(__file__).parent
P=W/'.eda_private';D=P/'control128_received'
C=R/'architecture_tlm/attention_compare_20261027/control128_20261028'
A=WS/'project_archives/attention_compare_issue198_20261027/control128_20261028'
RID='attention-control128-198-eda-20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,indent=2,ensure_ascii=False)+'\n').encode())
def main():
    receipt=read(D/'COLLECTION.json');idx=read(D/'RAW_INDEX.json')['files']
    assert sha(D/'RESULTS.json')==receipt['results_sha256'] and sha(D/'RAW_INDEX.json')==receipt['raw_index_sha256']
    assert sha(D/'EDA_REPORTS.tar.gz')==receipt['reports']['sha256']
    checked=[]
    with tarfile.open(D/'EDA_REPORTS.tar.gz') as t:
        for m in t.getmembers():
            if not m.isfile():continue
            b=t.extractfile(m).read();h=hashlib.sha256(b).hexdigest()
            if m.name=='collection_v1/RAW_INDEX.json':assert h==receipt['raw_index_sha256']
            else:assert h==idx[m.name]['sha256'] and len(b)==idx[m.name]['bytes'],m.name
            checked.append(m.name)
    ar=read(D/'TIMING_AUDIT_COLLECTION.json');assert sha(D/'timing_audit_v1.tar.gz')==ar['sha256']
    data=read(D/'RESULTS.json');tops=data['results'];audit=[]
    with tarfile.open(D/'timing_audit_v1.tar.gz') as t:
        index=json.loads(t.extractfile('timing_audit_v1/INDEX.json').read());members=0
        for name,m in index['files'].items():
            b=t.extractfile(name).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256'];members+=1
        for x in tops:
            top=x['spec']['top'];prefix='timing_audit_v1/'+top+'/'
            r=next(y for y in index['records'] if y['top']==top)
            assert r['netlist_sha256']==x['netlist_sha256'] and r['sdc_sha256']==x['sdc_sha256']
            flags=sorted(set(re.findall(r'(?:positive_unate|negative_unate|non_unate)\s+(\w)\s',t.extractfile(prefix+'disable_timing.rpt').read().decode())))
            assert flags and set(flags)<=set('pCc'),flags
            exceptions=t.extractfile(prefix+'exceptions.rpt').read().decode()
            assert not re.search(r'false_path|multicycle_path',exceptions)
            hold=t.extractfile(prefix+'hold.rpt').read().decode()
            audit.append(dict(internal=json.loads(t.extractfile(prefix+'INTERNAL_SLACK.json').read()),disabled_arc_flags=flags,
                first_hold_startpoint=re.search(r'Startpoint: (.+)',hold)[1],first_hold_endpoint=re.search(r'Endpoint: (.+)',hold)[1],user_false_multicycle_exceptions=False,**r))
    assert len(tops)==8 and sum(len(x['functional_checks']) for x in tops)==336
    assert sum(x['functional_cycles'] for x in tops)==212454
    assert sum(len(x['power_windows']) for x in tops)==56
    for name,m in read(W/'CONTROL128_SOURCE.json')['files'].items():
        p=C/name
        if p.is_file():assert sha(p)==m['sha256'],name
    # Preserve executed originals. Public clarification removes only an inherited
    # generic limitation: this run's query PT windows are all complete S128 queries.
    data['limitations'][-1]='All query power windows complete 128 outputs; idle window has zero outputs. Synthetic inputs do not establish effective independent samples or model quality.'
    data['original_results_sha256']=receipt['results_sha256']
    write(C/'RESULTS.json',data)
    write(C/'TIMING_AUDIT.json',dict(archive_sha256=ar['sha256'],verified_members=members,results=audit,limits='SS-only ideal-clock internal paths; all module input-boundary hold violations retained, not postlayout or FF hold signoff'))
    rows=[]
    for x in tops:
        p=[y for y in x['power_windows'] if y['trace'].startswith('sparse_') and not y['trace'].endswith('_stall')]
        assert len(p)==3
        rows.append(dict(top=x['spec']['top'],raw_area_um2=x['raw_cell_area_um2'],area55_mm2=x['area_55nm_equivalent_um2']/1e6,
            query_cycles_mean=statistics.mean(y['metrics']['start_to_done_cycles'] for y in p),query_energy_nJ_mean=statistics.mean(y['window_energy_J']*1e9 for y in p),
            query_energy_nJ_std=statistics.stdev(y['window_energy_J']*1e9 for y in p),query_power_uW_mean=statistics.mean(y['power']['total_W']*1e6 for y in p),
            energy_pJ_per_output_mean=statistics.mean(y['energy_per_output_J']*1e12 for y in p),setup_ns=x['setup_ns'],hold_ns=x['hold_ns']))
    write(C/'COMPARISON.json',dict(selected=rows[1]['top'],criterion='energy, full-query cycles, throughput and timing margin jointly; area secondary',sparse_probability=1/32,seeds=[17,503,1009],samples=128,burn=0,rows=rows))
    labels=['G8 融合','G16 融合（主候选）','G32 融合','G16 两级','G16 提前保持','G16 one-hot','G16 32位计数','G16 串行']
    table='\n'.join(f"|{label}|{x['raw_area_um2']/1e6:.6f}|{x['area55_mm2']:.6f}|{x['query_cycles_mean']:.2f}|{x['query_power_uW_mean']:.2f}|{x['query_energy_nJ_mean']:.6f}|{x['setup_ns']:.6f}|" for label,x in zip(labels,rows))
    report='''# 128节点赢家保持反馈／仲裁：面积、能量与时延联合评估

2026-10-28，Issue198 / PR199，rayggxia。选 **G16融合、二进制赢家反馈、10位事务计数器、弹性流水** 作为本轮主候选。选择依据是完整事务能量、周期、吞吐和时序余量共同占优；没有为了面积将反馈链串行化。全部是本次重新综合与门级活动估算，不由旧512节点数据除以4。

## 同约束比较

SS SVT 1.08 V / 125°C / 100 MHz。N=128，S=128，burn=0，候选独立置1概率1/32，三个seed=17/503/1009。功耗为三次query窗口平均；能量按每次P×实际窗口时间后再平均，包含start、配置、填充、输出、排空。原始面积保留，55nm折算仅乘0.81；功耗和时间不缩放。

|候选|原始面积 mm²|55nm折算 mm²|完整query平均周期|平均功率 μW|128输出平均能量 nJ|setup余量 ns|
|---|---:|---:|---:|---:|---:|---:|
'''+table+'''

G16融合稀疏三seed为158/161/166拍（1.58/1.61/1.66 μs），0.903602/0.906752/0.958484 nJ，平均0.922946 nJ，即7.210516 pJ/输出。这是控制能量，不是一个独立有效样本或完整Attention能量。串行平均2.246279 nJ、415.67拍，是主候选约2.43倍能量、2.57倍时间，面积反而大1.71%，排除。G32稀疏能量低约0.83%，面积高10.79%，setup余量从2.80降至1.38 ns；全1和dense输入能量还高，保留备选，不宣称0.83%超出估算误差。

G16两级在这些无外部stall输入下多1拍、稀疏能量高约20.61%、面积高12.86%，本轮无需增加级数。提前保持减少不必要fair随机字消费，在dense模式从195降至159拍、1.385085降至1.182483 nJ，全1从0.669655降至0.618849 nJ；但稀疏能量没有改善，setup余量仅0.052158 ns，暂不选。外部随机源未计，未来可能改变这一权衡。10位比32位计数器稀疏能量少约8.73%、面积少11.52%，支持总更新S+burn≤1023；这不是无限采样版本。

## 周期与接口边界

主候选从接受第一帧至首个输出3拍；无rank重取的稳定输入可每拍提交1个输出。全1压力query是133拍、0.669655 nJ，而不是机械地128×反馈延迟；旧赢家依赖在提交时解决，准备段处理独立候选帧。全1保持同一赢家只验证吞吐，不能证明128个独立样本。

稀疏额外周期来自无偏rank拒绝重取，不假定p-bit阵列本身逐个更新。故即使128个p-bit一拍更新，也不能保证任何候选图案都恰好128拍完成。rank最多64次拒绝，达到上限显式failed，失败前部分输出不能当成功query。

相同seed17输入和fair逻辑序列，外部回压测试保持完全相同输出地址：由158拍/0.903602 nJ增至263拍/1.439662 nJ。这个人为source/fair/config/output stall用于验证弹性接口，不作为概率驱动或V读取的默认调度。两级版在这条周期性回压轨迹反而255拍，说明不能把无stall排名当成所有外部调度的结论。

主候选时钟持续运行空闲功率445.9 μW，表明时钟与寄存器开销值得后续检查；本轮没有实现ICG，不把假设门控节省扣除。query功率内部/开关/泄漏已完整相加，clock引脚内部功耗已含在total，不能重复添加clock分组。

输出为候选局部7位index（0..127）。SparQ候选到原始token/KV地址的映射表、分页KV布局、V读取及累加均不含于本控制。输出index不等于HBM物理地址。未施加概率驱动、V读取串行调度，未报告这些模块PPA。

## 验证和时序限制

本机168项/106227拍；服务器同168项分别RTL、门级，共336项/212454拍（424908个pre/post端口比对）通过。覆盖三seed复位与回压、零/单/多/全1、S64/128/256/512、burn32、最大1023更新、非法配置/溢出与rank上限。S64/256/512与burn32只验证功能/周期，没有对应PT能量；seed17主候选分别82/317/625拍，S128+B32为203拍，不能简单写成固定32拍预热代价。没有新PPL，也不由此决定算法必须burn0。

8个DC、56个PT显式窗口完成。PT net/cell活动覆盖100%，仍存在PWR-981部分prefix向量映射告警及其他原始告警，全部保留；100%不证明告警无影响。零延迟门级VCD、averaged power，无SDF/SPEF/布线RC/CTS/完整延时毛刺。

所有模块整体hold为负（−0.114082至−0.031043 ns）。主候选最差−0.056977 ns，路径从cfg_ready到configured寄存器；不是只有reset路径。额外同网表/同SDC审计：主候选内部reg-reg setup +2.801410 ns、hold +0.134473 ns；8个候选内部均正。禁用弧仅常量/条件p/C/c，无loop-breaking、用户false/multicycle例外。内部SS通过不能代替接口hold修复、FF hold角与CTS后签核，不能宣称100MHz或更高频率已完成物理签核。

输入slew0.1 ns，输出load0.02 pF，IO delay0，setup uncertainty2 ns、hold0.1 ns；DC O-2018.06-SP1、VCS O-2018.09-SP2、PT O-2018.06-SP1。后续优先明确真实接口最小延迟/时钟合同并修复hold，核实PWR-981，再以真实模型候选活动和外部模块接口整合评估；不以提高允许时序或false path掩盖问题。

## 复现与原件

源码和配置由work/rayggxia/198/CONTROL128_SOURCE.json的362文件SHA及父提交5f4f5bde2051c7c646d5a790179ad37208a8b9de绑定，含独立flat-list oracle/输入原字节。执行快照v1从提交到归档不可变；额外timing_audit脚本独立冻结。RESULTS.json保留56窗口与全部功能逐项记录，COMPARISON.json提供表格数值，TIMING_AUDIT.json提供内部路径及原始报告哈希入口。

原报告/manifest/输入与STA归档已本地逐成员SHA校验；含VCD/网表的完整原始包只在授权EDA存储，未谎称本机全包重校验。CONTROL128_ARCHIVE.json定位私有原件，不公开连接凭据或工艺库；中央台账run attention-control128-198-eda-20261028记录functional=pass、synthesis=completed、sta=violations、power=calculated、postlayout=not_run。模型/语料SHA不适用：本轮为合成RTL激励，无模型调用。PR待审不等于合并或芯片实测。
'''
    (C/'RESULTS_ZH.md').write_bytes(report.encode())
    A.mkdir(exist_ok=False)
    for p in D.iterdir():
        if p.is_file():shutil.copyfile(p,A/p.name)
    write(A/'ARCHIVE_PRIVATE.json',dict(remote=receipt,root=read(D/'RAW_INDEX.json')['root'],full_raw_downloaded=False,local_report_members_verified=len(checked),audit_members_verified=members))
    ops=A/'LOCAL_OPERATIONS.zip'
    with zipfile.ZipFile(ops,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in P.rglob('*'):
            rel=p.relative_to(P)
            if p.is_file() and ('128' in str(rel)) and p.suffix!='.vvp' and 'control128_received' not in rel.parts and '__pycache__' not in rel.parts:z.write(p,rel.as_posix())
    with zipfile.ZipFile(ops) as z:assert z.testzip() is None
    artifacts=[]
    for p,role in [(C/'RESULTS.json','public_numeric'),(C/'TIMING_AUDIT.json','internal_timing_audit'),(A/'EDA_REPORTS.tar.gz','private_original_reports'),(A/'timing_audit_v1.tar.gz','private_timing_reports'),(A/'ARCHIVE_PRIVATE.json','private_full_raw_remote_index'),(ops,'private_source_vectors_operations')]:
        artifacts.append(dict(path=str(p),role=role,present_at_registration=True,required=True,bytes=p.stat().st_size,sha256=sha(p)))
    write(W/'CONTROL128_ARCHIVE.json',dict(local_artifacts=artifacts,remote_raw=dict(bytes=receipt['raw']['bytes'],sha256=receipt['raw']['sha256'],downloaded=False,access='authorized EDA storage; path in private index'),private_index_path=str(A/'ARCHIVE_PRIVATE.json')))
    write(W/'CONTROL128_COLLECTION_CHECK.json',dict(report_members_verified=len(checked),audit_members_verified=members,original_files_indexed=len(idx),reports_sha256=receipt['reports']['sha256'],results_original_sha256=receipt['results_sha256'],audit_sha256=ar['sha256'],functional_checks=336,cycles=212454,power_windows=56,source_current_matches_frozen=True))
    cases=[]
    for x in tops:
        for p in x['power_windows']:
            cases.append(dict(top=x['spec']['top'],trace=p['trace'],window=p['window'],raw_area_um2=x['raw_cell_area_um2'],area_55nm_equivalent_um2=x['area_55nm_equivalent_um2'],power_W=p['power']['total_W'],energy_J=p['window_energy_J'],duration_ns=p['duration_ns'],setup_ns=x['setup_ns'],hold_ns=x['hold_ns'],warning_codes=p['warnings'],power_report_sha256=p['power_report_sha256'],status='calculated_with_hold_violations'))
    record=dict(schema_version=1,id=RID,name='128候选赢家保持控制8top：336回放/56PT，能量时延联合选择',family='Attention/控制',registered_on='2026-10-28',owner='rayggxia',issue=198,evidence_level='DC_GATE_PT_PRELAYOUT',status='calculated_hold_violations_annotation_warnings',stages=dict(functional='pass',synthesis='completed',sta='violations',power='calculated',postlayout='not_run'),boundary='N128反馈/无偏rank/弹性流水；不含概率驱动、随机源本体、token地址映射、QK/V/SRAM/累加',conditions=dict(node_nm=65,target_equivalent_area_nm=55,area_only_scale=.81,corner='SS',voltage_V=1.08,temperature_C=125,clock_MHz=100,seeds=[17,503,1009],window_ns=None,samples=128,burn=0,count_widths=[10,32],load_pF=.02,input_transition_ns=.1,io_delay_ns=0,setup_uncertainty_ns=2,hold_uncertainty_ns=.1,sdf=False,spef=False,cts=False,activity='zero-delay gate VCD averaged PT; all query windows complete; idle no outputs; clock-pin included'),source=dict(git_commit=None,parent_commit=read(W/'CONTROL128_SOURCE.json')['parent'],source_manifest_sha256=read(W/'CONTROL128_SOURCE.json')['manifest_sha256'],binding='exact immutable v1 source/vector bytes; separate timing audit retained'),artifacts=artifacts,cases=cases,limitations=data['limitations']+['Internal SS reg-reg positive, whole module boundary hold negative; no signoff','Model/corpus not applicable: synthetic control inputs; outputs are not effective independent samples','Full raw archive remote only; local report/audit members verified'],next_action='G16融合主候选；先修真实接口hold和标注，再集成真实候选活动及外部模块，不做面积驱动串行化')
    record_path=R/'digital_circuit_simulation_registry/records'/f'{RID}.json';write(record_path,record)
    register(record_path,artifacts)
    print(json.dumps(dict(report=str(C/'RESULTS_ZH.md'),archive=str(A),report_members=len(checked),audit_members=members,comparison=rows),ensure_ascii=False))

def register(record_path,artifacts):
    reg=WS/'digital_circuit_simulation_registry';check=W/'control128_registry_check';check.mkdir(exist_ok=False)
    names=['catalog.json','archive_inventory.csv','00_总览.md','01_结果地址索引.md','runs.csv','artifact_locations.csv']
    pre={n:sha(reg/n) for n in names};old={p.name:sha(p) for p in (reg/'records').glob('*.json')}
    for n in ['registry.py','catalog.json','archive_inventory.csv']:shutil.copyfile(reg/n,check/n)
    shutil.copytree(reg/'records',check/'records')
    subprocess.run([sys.executable,str(check/'registry.py'),'add',str(record_path)],check=True)
    rows=[dict(path=x['path'],bytes=x['bytes'],sha256=x['sha256'],linked_records=RID,review_state='sha_verified_local',note='same control128 run, private original archive') for x in artifacts if x['path'].endswith(('.tar.gz','.zip'))]
    fields=['path','bytes','sha256','linked_records','review_state','note'];s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');w.writerows(rows)
    with (check/'archive_inventory.csv').open('ab') as f:f.write(s.getvalue().encode())
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows);(W/'CONTROL128_ARCHIVE_INVENTORY_APPEND.csv').write_bytes(s.getvalue().encode())
    p=subprocess.run([sys.executable,str(check/'registry.py'),'check'],capture_output=True,text=True,check=True);write(W/'CONTROL128_REGISTRY_CHECK.json',json.loads(p.stdout))
    subprocess.run([sys.executable,str(check/'registry.py'),'render'],check=True)
    assert pre=={n:sha(reg/n) for n in names} and old=={p.name:sha(p) for p in (reg/'records').glob('*.json')}
    backup=A/'reading_preimages';backup.mkdir()
    for n in names:shutil.copyfile(reg/n,backup/n)
    assert not (reg/'records'/record_path.name).exists();shutil.copyfile(record_path,reg/'records'/record_path.name)
    for n in names:shutil.copyfile(check/n,reg/n)
    assert all(sha(reg/'records'/n)==s for n,s in old.items())
    write(W/'CONTROL128_REGISTRY_SYNC.json',dict(old_records=len(old),new_records=len(old)+1,all_old_records_unchanged=True,record_sha256=sha(record_path),preimages=str(backup)))

if __name__=='__main__':main()
