"""Remove the uniform area reserve and audit, but do not activate, SRAM cuts."""
from pathlib import Path
import hashlib,json,math,subprocess

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
P=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.encode())

new=json.loads((P/'SRAM_INTAKE_20261109.json').read_bytes())
cal=json.loads((P/'SRAM_CALIBRATION_20261109.json').read_bytes())
archive=WS/'project_archives/tlm_energy225_20261108/0/RESULT.json'
r=json.loads(archive.read_bytes())
parts=[('Attention八组缓冲',384),('CIM权重驻留双缓冲',256),('激活/概率码/元数据',128),
       ('FFN跨K状态',96),('普通投影权重双缓冲',64),('Norm权重双缓冲',32)]
assert sum(v for _,v in parts)==960
assert r['sram_capacity_contract']['accessed_highwater_bytes']['activations_and_codes']==96*1024
assert r['sram_capacity_contract']['memory']['unallocated_bytes']==0
peak_gu=max(z.get('peak_owned_state_groups',0) for z in r['common_FFN_stages'] if z['mode']=='GU')
assert peak_gu==76

# A proposed 36KiB Attention address map, using the actual 16KiB coarse-score
# transfers in current N2048 actors. The old API's 32KiB reservation is not
# silently assumed to fit. Validate each phase's simultaneous live objects.
objects=dict(K=(0,32768),coarse=(16384,16384),selected_score=(32768,2048),
             V=(0,32768),output=(34816,1024))
phases=[('coarse',),('K','selected_score'),('V','selected_score'),('output',)]
for bounds in objects.values():assert bounds[0]>=0 and sum(bounds)<=36*1024
for names in phases:
    for i,a in enumerate(names):
        for b in names[i+1:]:
            aa,an=objects[a];bb,bn=objects[b]
            assert max(aa,bb)>=min(aa+an,bb+bn)
sources={str(archive):sha(archive)}
for name in ('closed250_v3','closed500_v3'):
    p=ROOT/'work/rayggxia/225/process28_whole_20261109'/name/'RESULT.json'
    z=json.loads(p.read_bytes());sources[str(p)]=sha(p)
    assert z['SRAM']['by_tag']['coarse_scores']['write_words']==z['layers']*8*1024

unit=cal['area_mm2_per4KiB'];sram_source=WS/'architecture_tlm/process_28nm/SRAM_CHARACTERIZATION_RESULTS_20261109.json'
libs=json.loads(sram_source.read_bytes())['library_records']
s2=next(x for x in libs if x['macro_id']=='S2' and x['VDD_V']==.9)
rows=[]
for c in new['cases']:
    assert c['area_placement_factor']==1 and c['added_area_placement_factor']==1
    assert math.isclose(c['area_mm2'],c['area_without_SRAM_mm2']+240*unit,abs_tol=1e-12)
    rows.append(dict(clock_MHz=c['clock_MHz'],default_capacity_KiB=960,area_mm2=c['area_mm2'],
        previous_uniform15pct_area_mm2=c['area_mm2']*1.15,
        no_reserve_area_928KiB_candidate=c['area_mm2']-8*unit,
        no_reserve_area_832KiB_candidate=c['area_mm2']-32*unit,
        no_reserve_area_704KiB_candidate=c['area_mm2']-64*unit,
        time_ms=c['time_ms'],chip_energy_mJ=c['chip_energy_mJ']))
result=dict(status='AREA_REPORTING_UPDATE_AND_LOGICAL_SRAM_CANDIDATE_AUDIT',
    decision='omit uniform placement/control percentage reserve;retain named module costs',
    area_placement_factor=1.0,default_SRAM_KiB=960,default_physical_banks=240,
    changed_SRAM_runtime=False,new_bank_timing_replay=False,new_EDA=False,
    checks=['existing960capacity_sum','activation_highwater96KiB','coarse_transfer16KiB_verified_in_two28probes',
        '36KiB_Attention_candidate_phase_live_ranges_disjoint','area_sum_no15percent'],
    sources_sha256=sources,partition_KiB=dict(parts),observed_GU_peak_state_groups=peak_gu,
    Attention_candidate_objects_bytes=objects,
    weight_only_larger_macro_scenario=dict(capacity_KiB=256,
        area_64_equivalent4KiB_mm2=64*unit,area_32_8KiB_mm2=32*s2['area_um2']/1e6,
        port_count_halved=True,requires_repartition=True,power='S2 library-only;not PT250500'),cases=rows)
dump(P/'AREA_SRAM_REVIEW_20261109.json',result)
doc='''# 取消统一面积预留与SRAM缩减空间

2026-11-09，Issue225 / PR249；用户要求暂不考虑15%布局/控制统一预留。

## 当前面积

统一面积系数改为1，保留已有具名逻辑、控制、寄存器与SRAM宏的面积。历史带15%的数字保留在Git版本，不再作为当前默认中心。只改变面积报告，时间、能量、计算资源与SRAM默认容量都不变。

|28nm版本|此前含15%|现在模块直接相加|
|---|---:|---:|
'''
for x in rows:doc+=f"|{x['clock_MHz']}MHz|{x['previous_uniform15pct_area_mm2']:.6f}mm²|{x['area_mm2']:.6f}mm²|\n"
doc+='''
这里仍是原条件整机估计，包含此前具名平台宏，并非新完成的物理芯片布局。55nm原先按模块直接相加，本次不改其结果。历史`rough_estimate.py`用于复现此前估计；当前真实SRAM/无统一预留入口为`intake_sram.py`。

## SRAM还有哪里可缩

当前960KiB完全分配，未分配空间为0。可以优化的是已分区中的余量与缓冲深度。

|分区|当前|建议候选|节省|依据与代价|
|---|---:|---:|---:|---|
|激活/概率码/尺度元数据|128KiB|96KiB|32KiB|现有映射范围与完整55nm轨迹最高96KiB；减少8个bank后仍需验证供数|
|八组Attention缓冲|8×48KiB|8×36KiB|96KiB|保留32KiB K/V缓存、2KiB分数和1KiB输出；输出由47KiB移至34KiB。实际粗分数每组16KiB，已有两频探针核对。通过逻辑生命周期范围检查，尚未做9bank/组回放|
|CIM权重驻留槽|32×8KiB|16×8KiB|128KiB|下一阶段候选；会减少预取深度，不能直接宣称原吞吐不变|
|FFN跨K状态|96KiB|80KiB或64KiB|16或32KiB|当前GU最大观测76组、Wd20组；需改变状态槽映射/输出批次。不能按3核就只保留3份跨K状态|
|Norm双缓冲|2×16KiB|Qwen专用2×12KiB|8KiB|每层10752B可装入12KiB；需要重排槽步长，其他更宽模型仍可能需要16KiB|
|普通投影权重双缓冲|2×32KiB|先保留|—|每个实际tile需要32KiB；缩小要调整分块和供数|

先做激活＋Attention的**960→832KiB**候选：保留采样数、精度、候选数、V缓存项数与计算核。布局逻辑具备缩减条件，尚未验证bank减少后的周期；不自动切换默认。

|容量情景|4KiB宏数|SRAM宏面积|250MHz子系统面积，仅容量计价|
|---|---:|---:|---:|
'''
for kib in (960,928,832,704):
    area=kib/4*unit;total=rows[0]['area_mm2']-(960-kib)/4*unit
    doc+=f'|{kib}KiB|{kib//4}|{area:.6f}mm²|{total:.6f}mm²|\n'
doc+='''
704KiB还包含CIM驻留槽减半，属于更激进的后续候选。以上候选面积不是已验证的性能工作点，功耗也未按容量同比缩减。减少bank会改变端口、DMA落地、QK供数和部分和冲突，需要有限bank回放；不能只改容量价格。

另有“容量不变但减少宏外围”的方向：为256KiB CIM权重单独划区，按真实宏库计，64个4KiB等效容量份额为0.760328mm²，32个8KiB为0.555413mm²，约省27%。当前前端是交错共享bank，实施时必须重划区并验证装载端口；这不是现成64个独占CIM bank直接换名字，8KiB当前仅库提取价。

当前执行默认仍960KiB/240bank。建议先验证832KiB，再考虑CIM16槽；已有低采样计算速度足够，优先守住外存供数和普通投影吞吐。
'''
write(P/'AREA_SRAM_REVIEW_20261109_ZH.md',doc)

# Regenerate the current intake explanation without modifying archived results.
p=P/'SRAM_INTAKE_20261109_ZH.md';text=p.read_text(encoding='utf8')
text=text.replace('覆盖子系统面积，含原15%布局预留','覆盖子系统面积，无统一布局预留')
for x in rows:text=text.replace(f"|{x['clock_MHz']}MHz|{x['previous_uniform15pct_area_mm2']:.3f}mm²|",f"|{x['clock_MHz']}MHz|{x['area_mm2']:.3f}mm²|")
text=text.replace('面积中心比旧值各增加约1.354mm²（实际宏差额×既有1.15布局系数）。',
    '用户决定暂不考虑统一15%布局/控制预留；当前模块面积直接相加，已有具名控制与寄存器保留。')
write(p,text)
for name in ('README_ZH.md','WHOLE_MODEL_ZH.md'):
    p=P/name;old=p.read_text(encoding='utf8')
    heading='> 用户2026-11-09决定：取消统一15%面积预留；当前250/500MHz中心7.139/7.165mm²。SRAM默认仍960KiB，832KiB仅逻辑候选。见[面积和SRAM审查](AREA_SRAM_REVIEW_20261109_ZH.md)。\n\n'
    if not old.startswith(heading):write(p,heading+old)
note='''## 2026-11-09 用户决定取消15%统一面积预留，SRAM继续缩减审查

Issue225/PR249。28nm当前面积汇总系数1，具名模块成本保留；250/500中心7.138610/7.165151mm²，时间45.900576/40.990565ms、片上15.012937/15.050444mJ不变。55nm原为模块加和，本轮不改。intake_sram.py与派生结果/说明已同步，旧带15%估计留Git历史。

SRAM默认仍960KiB/240bank，未分配0。逻辑候选：激活128→96KiB（完整旧轨迹高水位96KiB）；八组Attention48→36KiB（保留32KiB缓存/2KiB分数/1KiB输出，输出地址移47→34KiB；两28探针实际粗分数16KiB，生命周期无重叠检查通过），合计832KiB，容量计价250面积6.758446mm²。尚未做缩bank时序，不当已验收默认。后续CIM32→16槽可到704KiB，需验证预取供数；跨K状态观测GU76/Wd20，缩80/64另调映射，不能直接按核数砍状态。Qwen Norm每层10752B可考虑双12KiB，普通投影双32KiB先保留。

8KiB权重宏分区可另减外围面积，但原前端交错共享，端口/划区需回放，不能只换价格。正式process_28nm/AREA_SRAM_REVIEW_20261109_ZH.md/json。只取消统一预留并做逻辑审查，无新长时序/EDA/PPL或容量默认改变。发布状态看本work/PUBLICATION.json；PR待审未合并，Projects待同步。
'''
status=ROOT/'progress/rayggxia/STATUS.md';old=status.read_text(encoding='utf8')
if not old.startswith(note):write(status,note+'\n---\n\n'+old)
write(HERE/'HANDOFF.md',note+'\n下一步如批准缩容测试，先激活96KiB与Attention36KiB/组配对bank回放，再决定是否切默认；不改冻结任务。\n')
a=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';b=WS/'PROJECT_MEMORY_ZH.md'
old=a.read_bytes();assert old==b.read_bytes()
new_bytes=old if old.startswith(note.encode()) else (note+'\n---\n\n').encode()+old
assert a.read_bytes()==b.read_bytes()==old;a.write_bytes(new_bytes);b.write_bytes(new_bytes)

files=['architecture_tlm/process_28nm/'+n for n in ('intake_sram.py','SRAM_INTAKE_20261109.json',
    'SRAM_INTAKE_20261109_ZH.md','AREA_SRAM_REVIEW_20261109_ZH.md','AREA_SRAM_REVIEW_20261109.json','README_ZH.md','WHOLE_MODEL_ZH.md')]
files+=['work/rayggxia/225/sram28_intake_20261109/finalize.py','work/rayggxia/225/area_sram_review_20261109/review.py',
    'work/rayggxia/225/area_sram_review_20261109/HANDOFF.md','progress/rayggxia/STATUS.md']
for name in files:
    if name.startswith('architecture_tlm/'):
        p=WS/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
dump(HERE/'PUBLIC_FILES.json',dict(files=[dict(path=n,sha256=sha(ROOT/n),content=(ROOT/n).read_text(encoding='utf8')) for n in files]))
subprocess.run(['git','-c','core.autocrlf=false','add','--sparse','--',*files],cwd=ROOT,check=True)
subprocess.run(['git','-c','core.whitespace=cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*files],cwd=ROOT,check=True)
for n in files:assert hashlib.sha256(subprocess.check_output(['git','show',':'+n],cwd=ROOT)).hexdigest()==sha(ROOT/n)
print(json.dumps(dict(status='PASS_AREA_AND_LOGICAL_SCOPE_ONLY',files=len(files),cases=rows),ensure_ascii=False))
