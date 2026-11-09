"""Use completed832 probes and macro geometry to screen port reductions."""
from pathlib import Path
import hashlib,json,math,subprocess

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
P=ROOT/'architecture_tlm/process_28nm';BASE=ROOT/'work/rayggxia/225/sram832_validation_20261109'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.encode())
def dump(p,x):write(p,json.dumps(x,ensure_ascii=False,indent=2)+'\n')

source=WS/'architecture_tlm/process_28nm/SRAM_CHARACTERIZATION_RESULTS_20261109.json'
lib=json.loads(source.read_bytes());macros={r['macro_id']:r for r in lib['library_records'] if r['VDD_V']==.9}
a4=macros['S0']['area_um2']/1e6;a8=macros['S2']['area_um2']/1e6
rows=[];identities={str(source):sha(source)}
for mhz in (250,500):
    folder=BASE/f'p{mhz}_832';seal=json.loads((folder/'SEAL.json').read_bytes())
    for n,v in seal['files_sha256'].items():assert sha(folder/n)==v
    r=json.loads((folder/'RESULT.json').read_bytes());tags=r['SRAM']['by_tag']
    gu=next(z for z in r['common_FFN_stages'] if z['mode']=='GU')
    wd=next(z for z in r['common_FFN_stages'] if z['mode']=='Wd')
    remaining=gu['frames']*8192-gu.get('prefetch_hits',0)*8192
    state=sum(sum(v.values())*16 for k,v in tags.items() if k.startswith('common_') and '_state_' in k)
    phases={name:sum(z['duration_ns'] for z in r['phases'] if z['stage']==name) for name in ('QKV','O','lm_head')}
    bytes_per_port_GBs=16*mhz/1000
    rows.append(dict(clock_MHz=mhz,one128bit_port_GBs=bytes_per_port_GBs,
        nominal_external_GBs=136.4606,ideal_ports_to_cover_external=math.ceil(136.4606/bytes_per_port_GBs),
        CIM_32x8KiB_write_ceiling_GBs=32*bytes_per_port_GBs,
        CIM_GU_stage_payload_GBs_after_recorded_prefetch=remaining/gu['elapsed_ns'],
        CIM_Wd_stage_payload_GBs=wd['frames']*8192/wd['elapsed_ns'],
        state_read_plus_write_GBs=state/sum(z['elapsed_ns'] for z in r['common_FFN_stages']),
        state_12x8KiB_combined_port_ceiling_GBs=12*bytes_per_port_GBs,
        ordinary_weight_read_GBs=tags['ordinary_weight_FIFO']['read_words']*16/sum(phases.values()),
        digital_peak_weight_read_ports=256*2//16,
        digital_peak_weight_GBs=256*2*mhz/1000,
        metadata_read_bytes=sum(tags.get(k,{}).get('read_words',0)*16 for k in
            ('GU_weight_scale_metadata','Wd_weight_scale_metadata','NL_gu_scale')),
        probe_layers=r['layers'],basis='actual completed small probe;averages are not peak guarantees'))
    identities[str(folder/'RESULT.json')]=sha(folder/'RESULT.json')
scenarios=[]
for n8,n4 in ((0,64),(32,0),(29,6),(24,16)):
    assert 8*n8+4*n4==256
    scenarios.append(dict(eightKiB=n8,fourKiB=n4,total_KiB=256,ports=n8+n4,
        area_mm2=n8*a8+n4*a4,write_GBs250=(n8+n4)*4,write_GBs500=(n8+n4)*8))
result=dict(status='PORT_BUDGET_SCREENING_NOT_NEW_LAYOUT_TIMING',scope='current28Qwen3_4B_B1_N2048_K128_S64_832KiB',
    rows=rows,CIM_256KiB_capacity_scenarios=scenarios,source_sha256=identities,
    current_front='136shared_interleaved4KiB_banks;logical_partitions_not_exclusive_banks',
    CIM_contract='parallel resident-weight presentation;no per-sample ordinary SRAM reads;programming writes remain',
    new_PPA=False,new_timing_replay=False,default_changed=False)
dump(P/'SRAM_PORT_REDUCTION_20261109.json',result)
doc='''# 哪些SRAM可以减少端口：按当前832KiB流程分析

2026-11-09，Issue225 / PR249。默认仍为已接受的832KiB/208个4KiB宏，本轮只分析端口预算，不替换默认或新增仿真。

## 结论

最适合先减端口的是Norm权重、尺度/控制元数据和阶段边界的残差/输出存储。CIM则必须分开看：**采样时对普通读端口需求很低，但换权重块时写入带宽很高，不能只保容量。** 数字投影权重、热K/V及跨K部分和都要保留足够吞吐，不能统一按“容量够就行”。

当前前端136个bank由普通权重、CIM、激活、Norm和状态条带共享。容量份额÷4KiB不是各区域独占端口数；例如256KiB CIM不等于现有64个专属bank。下面的8KiB独立分区是待评估的新组织，不能直接在现有账本换宏名后保留旧带宽。

|区域|能否减少端口|判断|
|---|---|---|
|Norm权重32KiB|最优先|每层权重10752B，有跨层预取和双缓冲；阶段内gamma读取会变慢一些，但占整机时间很小。保留双槽的读/写隔离|
|尺度/控制元数据|优先|虽然每tile读取，但实际字数少；可少bank或预取到现有局部接口。不能把元数据误当每层只读一次|
|残差/等待消费的输出|较适合|主要在阶段边界读写；容量和生命周期比高持续带宽更重要，仍保留必要的向量突发带宽|
|CIM权重256KiB|采样读端口可少，装载写端口敏感|沿当前并行供权重假设，采样GU16/Wd32不逐拍读SRAM；每次换8KiB tile仍要通过DMA写入|
|激活/概率码区域整体96KiB|可减一部分|g/u码、x码在帧前加载，且有Norm/残差突发；不宜全并成单端口。将冷元数据与热接口分开更合理|
|FFN跨K状态96KiB|中等敏感|实际读写合计约33GB/s，包含读-改-写依赖。较少bank可能够平均量，但两state端口的突发和返回延迟必须回放|
|普通QKV/O/lm_head权重64KiB|最敏感之一|256路BF16 FMA满速需要每拍512B权重，即32个128bit读端口；还要接收下一块DMA写入。不能按容量孤立成少量宏|
|Attention热K/V和转置|敏感，按通路评估|同时涉及DMA填充、K复用/转置和V选择读取；分数/输出小区域可以少端口，热K/V区需单独验证|

## CIM为什么不能认为只要容量够

当前每层GU有6080个8KiB帧、Wd有3040帧。GU权重约49.81MB，Wd约24.90MB。输入流并没有因为采样复用而消除每token换权重的装载。

一条128bit/1RW端口，每拍16B，在250/500MHz分别是4/8GB/s。若256KiB权重区独立使用32个8KiB宏：

|频率|32端口理论写上限|原完成回放中的GU/Wd装载速率|判断|
|---|---:|---:|---|
'''
for r in rows:
    judgement='128GB/s不足以覆盖当前约135GB/s写入，可能形成新瓶颈' if r['clock_MHz']==250 else '256GB/s高于外存峰值，写端口有明显余量，值得优先试'
    doc+=f"|{r['clock_MHz']}MHz|{r['CIM_32x8KiB_write_ceiling_GBs']:.0f}GB/s|{r['CIM_GU_stage_payload_GBs_after_recorded_prefetch']:.2f}/{r['CIM_Wd_stage_payload_GBs']:.2f}GB/s|{judgement}|\n"
doc+='''
GU速率已扣记录中的32个预取tile；是按完成帧字节/阶段时间计算的阶段平均量，不是逐周期峰值。外存名义136.4606GB/s对应至少35个250MHz或18个500MHz端口的理想写预算。还未考虑bank冲突、突发和仲裁，达到这个整数下限不等于已经验证同速。

因此建议：500MHz先试32个8KiB宏的独立权重区；250MHz使用混合宏保留更多写端口。例如容量仍256KiB：

|组织|端口数|250MHz写上限|宏面积|
|---|---:|---:|---:|
'''
for r in scenarios:
    doc+=f"|{r['eightKiB']}×8KiB＋{r['fourKiB']}×4KiB|{r['ports']}|{r['write_GBs250']:.0f}GB/s|{r['area_mm2']:.6f}mm²|\n"
doc+='''
250MHz可优先试24×8KiB＋16×4KiB，40端口/160GB/s留一些写带宽余量，宏面积份额比64个4KiB等效容量少约20%。29×8KiB＋6×4KiB虽有35端口/140GB/s，但余量较小。不将这些独立划区面积直接冒充当前已完成的整机结果。

CIM的这一结论沿用“驻留权重在本地参与并行计算”的设计假设；标准1RW宏本身并不会自动提供全部权重同时输出。普通SRAM等效读能量是当前接受的能量代理，不应把它误当逐采样真实端口事务，再给出错误带宽需求。

## 其他区域的量级与下一步

在完成回放中，部分和读写约33.2/33.5GB/s。若96KiB状态独立用12个8KiB宏，其250/500MHz读写合计上限48/96GB/s。平均带宽有余量，但读-改-写依赖和突发要验证，因此优先级低于Norm/元数据。

普通数字权重回放的阶段平均读取约117/135GB/s，满速计算瞬时需求128/256GB/s。数字权重双缓冲即使总容量只有64KiB，也不能随意削成8个专用8KiB端口（250MHz仅32GB/s）。可以继续共享条带或增加bank数并减深度，重点是满足每拍权重供给。

建议顺序：先整理Norm和冷元数据的少端口分区；并行评估500MHz的CIM8KiB组织与250MHz混合宏；最后依据实际bank回放调整状态和热K/V端口。无需新训练/PPL。已有4KiB宏不重测，8KiB可先用已有库与校准估计，只有需要更准功耗时补代表性PT。

功耗不能按端口数或宏面积同比缩小；本轮没有声称新的能耗、完整token时间或改默认。机器表含来源SHA与实际速率。
'''
write(P/'SRAM_PORT_REDUCTION_20261109_ZH.md',doc)
note='''## 2026-11-09 SRAM端口削减分析：CIM分计算与装载两阶段

Issue225/PR249。832默认不变，无新时序/PPA。前端136bank条带共享，容量份额不等于专属端口。Norm/冷元数据/残差最适合先减端口；CIM采样驻留不逐拍读，但GU/Wd装载实际约135GB/s。独立256KiB用32×8KiB端口在250MHz只有128GB/s，低于当前需求；500MHz256GB/s有余量。250建议试24×8K＋16×4K=256K/40端口160GB/s，宏面积份额.606642mm²；500可试32×8K=.555413mm²。不是已完成新整机结果。

FFN状态实际读写约33GB/s，12×8K独立区250/500上限48/96GB/s，但RMW突发需回放。256BF16FMA满速权重512B/拍=32个128bit读端口，数字权重/热K-V不按容量随意砍端口。CIM静态并行呈现仍为当前假设，普通SRAM能量代理不代表标准宏天然全权重输出。

正式process_28nm/SRAM_PORT_REDUCTION_20261109_ZH.md/json；来源为两832已封存小流程与真实宏库。无需新训练/重跑S0。发布看本work/PUBLICATION，PR待审未合并，Projects待同步。
'''
status=ROOT/'progress/rayggxia/STATUS.md';prior=status.read_text(encoding='utf8')
if not prior.startswith(note):write(status,note+'\n---\n\n'+prior)
write(HERE/'HANDOFF.md',note+'\n下一步按分析做少端口独立分区/混合宏实际回放；先不改单价替代端口模型或将CIM热装载当容量问题。\n')
a=WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';b=WS/'PROJECT_MEMORY_ZH.md'
prior=a.read_bytes();assert prior==b.read_bytes()
value=prior if prior.startswith(note.encode()) else (note+'\n---\n\n').encode()+prior
assert a.read_bytes()==b.read_bytes()==prior;a.write_bytes(value);b.write_bytes(value)
files=['architecture_tlm/process_28nm/SRAM_PORT_REDUCTION_20261109_ZH.md','architecture_tlm/process_28nm/SRAM_PORT_REDUCTION_20261109.json',
    'work/rayggxia/225/sram_port_analysis_20261109/analyze.py','work/rayggxia/225/sram_port_analysis_20261109/HANDOFF.md','progress/rayggxia/STATUS.md']
for n in files[:2]:p=WS/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/n).read_bytes())
dump(HERE/'PUBLIC_FILES.json',dict(files=[dict(path=n,sha256=sha(ROOT/n),content=(ROOT/n).read_text(encoding='utf8')) for n in files]))
subprocess.run(['git','-c','core.autocrlf=false','add','--sparse','--',*files],cwd=ROOT,check=True)
subprocess.run(['git','-c','core.whitespace=cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*files],cwd=ROOT,check=True)
for n in files:assert hashlib.sha256(subprocess.check_output(['git','show',':'+n],cwd=ROOT)).hexdigest()==sha(ROOT/n)
print(json.dumps(dict(status=result['status'],files=len(files),rows=rows)))
