"""Adopt exactly the already-tested832 configs, without altering run archives."""
from pathlib import Path
import ast,hashlib,json,math,subprocess

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
P=ROOT/'architecture_tlm/process_28nm'
TEST=ROOT/'work/rayggxia/225/sram832_validation_20261109'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.encode())
def dump(p,x):write(p,json.dumps(x,ensure_ascii=False,indent=2)+'\n')

plan=json.loads((TEST/'PLAN.json').read_bytes());execution=Path(plan['execution'])
summary=json.loads((P/'SRAM832_VALIDATION_20261109.json').read_bytes())
old=json.loads((P/'SRAM_INTAKE_20261109.json').read_bytes())
guardfiles=[ROOT/'architecture_tlm/sram1216_20261106/250MHz'/n for n in ('model.py','pricing.py','sram_layout.py')]
before55={str(p):sha(p) for p in guardfiles}
rows=[]
for mhz in (250,500):
    probe=next(x for x in plan['cases'] if x['clock_MHz']==mhz and x['capacity_KiB']==832)
    reference=next(x for x in plan['cases'] if x['clock_MHz']==mhz and x['capacity_KiB']==960)
    passed=json.loads((TEST/probe['name']/'SEAL.json').read_bytes())
    assert passed['status']=='completed'
    for n,v in passed['files_sha256'].items():assert sha(TEST/probe['name']/n)==v
    tested=Path(probe['command'][probe['command'].index('--macros')+1])
    assert sha(tested)==probe['config_sha256']
    cfg=json.loads(tested.read_bytes());s=cfg['SRAM']
    assert (s['capacity_KiB'],s['bank_count'],s['layout_profile'])==(832,208,'activation96_attention36')
    # Copy exact bytes: the active default is the configuration actually tested.
    target=P/f'{mhz}MHz/WHOLE_CONFIG.json';target.write_bytes(tested.read_bytes())
    assert sha(target)==probe['config_sha256']
    ref=Path(reference['command'][reference['command'].index('--macros')+1])
    (P/f'{mhz}MHz/WHOLE_CONFIG_960_REFERENCE.json').write_bytes(ref.read_bytes())
    evidence=next(x for x in summary['rows'] if x['clock_MHz']==mhz and x['capacity_KiB']==832)
    previous=next(x for x in old['cases'] if x['clock_MHz']==mhz)
    area=previous['area_without_SRAM_mm2']+208*s['area_mm2_per4KiB']
    expected=6.758446623979165 if mhz==250 else 6.784987237074602
    assert math.isclose(area,expected,abs_tol=1e-12)
    rows.append(dict(clock_MHz=mhz,capacity_KiB=832,physical_banks=208,
        front_banks=136,attention_banks=72,activation_KiB=96,attention_group_KiB=36,
        SRAM_macro_area_mm2=208*s['area_mm2_per4KiB'],conditional_subsystem_area_mm2=area,
        area_factor=1,default_config_sha256=sha(target),tested_config_sha256=probe['config_sha256'],
        paired_partial_time_ms=evidence['time_ms'],paired_partial_time_change_pct=evidence['time_change_pct'],
        full_default36_time_ms=None,full_default36_energy_mJ=None,
        historical960_full_time_reference_ms=previous['time_ms'],
        full_reference_is_not_new832_run=True))
    for name in ('whole_model.py','run_whole.py','whole_pricing.py','sram_characterization.py'):
        assert sha(P/name)==sha(execution/name),name
    current=ast.parse((P/'candidate_sram.py').read_text())
    frozen=ast.parse((execution/'candidate_sram.py').read_text())
    fn=lambda x:next(n for n in x.body if isinstance(n,ast.FunctionDef) and n.name=='install')
    assert ast.dump(fn(current))==ast.dump(fn(frozen))
assert before55=={str(p):sha(p) for p in guardfiles}
data=dict(status='USER_ACCEPTED_DEFAULT832_BOTH_28NM_CLOCKS',date='2026-11-09',issue=225,PR=249,
    owner='rayggxia',model='Qwen3-4B',context=2048,candidates=128,samples=64,GU_samples=16,Wd_samples=32,
    scope='28nm250/500 only;55nm unchanged',default_changed=True,rows=rows,
    partition_KiB=dict(ordinary_weight_double_buffer=64,CIM_weight_slots=256,
        activation_codes_metadata=96,norm_double_buffer=32,attention8groups=288,crossK_state=96),
    tests=['defaults_byte_SHA_equal_passed832_configs','all_original_SEAL_bytes_unchanged',
        'runtime_semantics_equal_passed_snapshot','208real_banks_partition_sum','55nm_sources_unchanged'],
    no_new_timing_replay=True,new_PPA=False,whole_default832_performance_not_yet_run=True)
assert sum(data['partition_KiB'].values())==832
dump(P/'DEFAULT_SRAM832_20261109.json',data)
doc='''# 28nm默认SRAM采用832KiB

2026-11-09用户确认；Issue225 / PR249。250MHz与500MHz的`WHOLE_CONFIG.json`均已切换为**832KiB、208个4KiB/128bit/1RW宏**。默认配置字节SHA与已通过的小配对832配置完全相同，执行算法/服务代码保持相同语义；旧960KiB可通过同目录`WHOLE_CONFIG_960_REFERENCE.json`显式恢复。55nm设置不变。

|分区|KiB|
|---|---:|
|普通投影权重双缓冲|64|
|CIM权重32个驻留槽|256|
|激活/概率码/元数据|96|
|Norm双缓冲|32|
|八组Attention，每组36KiB|288|
|FFN跨K状态|96|
|合计|832|

前端136bank、Attention72bank；输出地址为每组34KiB。保持GU16/Wd32、K128/S64、128项V缓存、FFN核数、FMA与PV资源、16KiB返回保持及外存参数。

|版本|SRAM宏面积|子系统面积预算，无统一15%预留|已完成小配对时延变化|
|---|---:|---:|---:|
'''
for r in rows:doc+=f"|{r['clock_MHz']}MHz|{r['SRAM_macro_area_mm2']:.6f}mm²|{r['conditional_subsystem_area_mm2']:.6f}mm²|+{r['paired_partial_time_change_pct']:.4f}%|\n"
doc+='''
面积预算减少0.380164mm²。局部配对已核源/配置SHA、实际208bank、边界/排空、矩阵/采样/转换及外存字节/地址摘要。[配对证据](SRAM832_VALIDATION_20261109_ZH.md)中的“默认尚未切换”是验证创建时状态，本次用户接受后以上述新默认为准。

完整36层/151936词表的832KiB时延与能量尚未重新执行；旧45.901/40.991ms等仅保留为960KiB参考，不静默改名为832结果，也不把局部百分比直接乘到整机。新完整运行省略`--macros`时会自动使用832配置；新输出按208个真实宏计面积、访问与泄漏。SRAM宏功耗卡沿原实测值，不新增PPA或重跑健康任务。

适用当前Qwen3-4B/B1/2K/K128/S64。其他模型、上下文或更激进CIM槽缩减按[对接清单](../module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md)处理。
'''
write(P/'DEFAULT_SRAM832_20261109_ZH.md',doc)
header='> **2026-11-09用户已接受：28nm250/500MHz默认832KiB/208bank。** 当前面积预算6.758447/6.784987mm²，无统一15%预留；55nm保持。960KiB及原全token时间为历史参考。见[新默认说明](DEFAULT_SRAM832_20261109_ZH.md)。\n\n'
docs=[P/n for n in ('README_ZH.md','WHOLE_MODEL_ZH.md','SRAM_INTAKE_20261109_ZH.md',
    'AREA_SRAM_REVIEW_20261109_ZH.md','SRAM832_VALIDATION_20261109_ZH.md')]
docs+=[ROOT/'architecture_tlm/module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md']
for p in docs:
    t=p.read_text(encoding='utf8')
    # Keep historical measurements; remove contradictory current-default prose.
    t=t.replace('默认960KiB保持','此前默认960KiB，现已接受832KiB')
    t=t.replace('SRAM默认仍960KiB，832KiB已完成两频小配对，仍为候选','SRAM已默认832KiB，两频小配对已完成')
    t=t.replace('容量默认仍960KiB','容量已按用户决定改为832KiB')
    t=t.replace('当前执行默认仍960KiB/240bank','当前执行默认832KiB/208bank')
    t=t.replace('当前960KiB完全分配','原960KiB布局完全分配')
    t=t.replace('建议先验证832KiB，再考虑CIM16槽','832KiB已完成两频小配对；下一步才考虑CIM16槽')
    t=t.replace('默认仍960KiB，832作为有执行证据的候选；是否改变默认由后续整机评估口径决定',
        '用户已接受832KiB为28nm两频默认；完整整机性能另行评估')
    t=t.replace('默认仍960KiB，候选不覆盖既有结果','28nm两频默认已改832KiB，既有验证结果保留')
    t=t.replace('SRAM每bank1RW、240bank/960KiB、访问延迟1拍，**28nm SRAM的该周期尚未库确认**',
        'SRAM每bank1RW、208bank/832KiB、访问延迟1拍；S0宏TT时序已确认，bank互连沿有限执行模型')
    if p.name=='README_ZH.md':
        t=t.replace('## 2026-11-09 SRAM校准待办','## 历史：最初SRAM校准需求（S0现已完成）')
        t=t.replace('：目前没有接入真实28nm宏数据，粗估来自CACTI＋55nm残差迁移',
            '：最初未接入真实28nm宏数据，初估来自CACTI＋55nm残差迁移；当前已采用真实S0结果')
    own_header=header if p.parent==P else header.replace('](DEFAULT_SRAM832_','](../process_28nm/DEFAULT_SRAM832_')
    if own_header!=header and t.startswith(header):t=t[len(header):]
    if not t.startswith(own_header):write(p,own_header+t)
    else:write(p,t)
note='''## 2026-11-09 用户接受28nm默认832KiB

Issue225/PR249；28nm250/500的WHOLE_CONFIG已逐字节换为通过配对的832配置：208个4KiB/1RW宏，前端136/Attention72、激活96KiB/8×36KiB Attention，其余资源/采样/外存不变。两频默认SHA与冻结测试文件相同，运行函数AST一致，四SEAL保持，55源SHA不变。960参考另存WHOLE_CONFIG_960_REFERENCE。

无15%统一预留的28nm250/500面积预算6.758447/6.784987mm²，SRAM2.471065mm²。已测局部时延+0.159069%/+0.094963%；完整832的36层/full-vocab时延与能量尚未重跑，旧45.901/40.991ms只作960参考，不能改标签。新完整命令默认会实际执行208bank；当前不启动新长任务或PPA，不动冻结运行/55设置。

正式process_28nm/DEFAULT_SRAM832_20261109_ZH.md/json与两频WHOLE_CONFIG；intake_sram.py修复当前默认不能套给历史960结果的容量标签，历史重计仍显式960。旧小配对创建时default_changed=false保留，当前默认状态以新接受文件为准。发布看本work/PUBLICATION.json；PR待审未合并，Projects待同步。
'''
status=ROOT/'progress/rayggxia/STATUS.md';old=status.read_text(encoding='utf8')
if not old.startswith(note):write(status,note+'\n---\n\n'+old)
write(HERE/'HANDOFF.md',note+'\n下一步完整token评估用默认832并新建结果目录，960对照显式传--macros WHOLE_CONFIG_960_REFERENCE.json；不要重标签旧报告或覆盖封存。\n')
a=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';b=WS/'PROJECT_MEMORY_ZH.md'
prior=a.read_bytes();assert prior==b.read_bytes()
after=prior if prior.startswith(note.encode()) else (note+'\n---\n\n').encode()+prior
assert a.read_bytes()==b.read_bytes()==prior;a.write_bytes(after);b.write_bytes(after)
files=['architecture_tlm/process_28nm/'+n for n in ('250MHz/WHOLE_CONFIG.json','500MHz/WHOLE_CONFIG.json',
    '250MHz/WHOLE_CONFIG_960_REFERENCE.json','500MHz/WHOLE_CONFIG_960_REFERENCE.json',
    'DEFAULT_SRAM832_20261109.json','DEFAULT_SRAM832_20261109_ZH.md','candidate_sram.py','intake_sram.py',
    'README_ZH.md','WHOLE_MODEL_ZH.md','SRAM_INTAKE_20261109_ZH.md','AREA_SRAM_REVIEW_20261109_ZH.md','SRAM832_VALIDATION_20261109_ZH.md')]
files+=['architecture_tlm/module_handoff/SRAM_REDUCTION_COORDINATION_ZH_20261109.md',
    'work/rayggxia/225/adopt832_20261109/adopt.py','work/rayggxia/225/adopt832_20261109/HANDOFF.md','progress/rayggxia/STATUS.md']
for n in files:
    if n.startswith('architecture_tlm/'):
        dest=WS/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/n).read_bytes())
dump(HERE/'PUBLIC_FILES.json',dict(files=[dict(path=n,sha256=sha(ROOT/n),content=(ROOT/n).read_text(encoding='utf8')) for n in files]))
subprocess.run(['git','-c','core.autocrlf=false','add','--sparse','--',*files],cwd=ROOT,check=True)
subprocess.run(['git','-c','core.whitespace=cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*files],cwd=ROOT,check=True)
for n in files:assert hashlib.sha256(subprocess.check_output(['git','show',':'+n],cwd=ROOT)).hexdigest()==sha(ROOT/n)
print(json.dumps(dict(status=data['status'],files=len(files),rows=rows)))
