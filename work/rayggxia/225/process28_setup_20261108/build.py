"""Create an isolated28nm component staging folder;no full-system estimator."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
OUT=ROOT/'architecture_tlm/process_28nm'
if OUT.exists():raise RuntimeError('Inspect existing28nm stage before replacing anything')
OUT.mkdir(parents=True);(OUT/'250MHz').mkdir();(OUT/'500MHz').mkdir()
def load(p):return json.loads(p.read_bytes())
def save(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
def text(p,x):p.write_bytes(x.encode())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source_paths={
 'original6_measurements':'architecture_tlm/module_handoff/ffn_tsmc28_three_classes_20261107/POWER_RESULTS_20261108.json',
 'current_owner_entry':'architecture_tlm/module_handoff/ffn_tsmc28_three_classes_20261107/README_CURRENT_ZH.md',
 'A9_synchronous_reset':'architecture_tlm/module_handoff/a9_sync_reset_28nm_20261108/profile.json',
 'zero_uncertainty_review':'architecture_tlm/module_handoff/ffn_tsmc28_three_classes_20261107/ZERO_UNCERTAINTY_REVIEW.json'}
sources={k:dict(local_path=str(PROJECT/v),repository_path=v,sha256=digest(PROJECT/v)) for k,v in source_paths.items()}
p=load(PROJECT/source_paths['original6_measurements']);sync=load(PROJECT/source_paths['A9_synchronous_reset'])
qualified=p['qualified_pre_layout_prices'];ffn=qualified['ffn_250'];bf=qualified['bf16_250'];a9=sync['core']
assert ffn['frequency_MHz']==bf['frequency_MHz']==a9['clock_MHz']==250
assert ffn['area_multiplier']==bf['area_multiplier']==a9['area_multiplier']==1
assert sync['status']=='COMPLETE_QUALIFIED_PRELAYOUT'
assert all(x>0 for x in (a9['setup_slack_ns'],a9['hold_slack_ns'],ffn['data_setup_ns'],ffn['data_hold_ns']))
components=dict(status='COMPONENT_STAGING_NOT_FULL_TLM',process='TSMC28HPC+',PVT='TT0.9V25C',frequency_MHz=250,
 area_multiplier=1.0,default_enabled=False,full_system_ready=False,
 FFN=dict(area_mm2=ffn['area_mm2'],variant='original_threshold_cache_C19_518ICG_not55nm_delta_v3',
  physical_K=64,physical_M=128,sampling=dict(GU=16,Wd=32),service_cycles=dict(GU=18,Wd=34),
  modes=ffn['modes'],timing=dict(data_setup_ns=ffn['data_setup_ns'],data_hold_ns=ffn['data_hold_ns'],
   gate_setup_ns=ffn['gate_setup_ns'],gate_hold_ns=ffn['gate_hold_ns']),source='original6_measurements'),
 BF16=dict(measurement=bf,source='original6_measurements',
  interpretation='FMA16/C4 continuous window;DOT64 tariff is window throughput,not a1-cycle DOT64 latency'),
 A9W8=dict(measurement=a9,source='A9_synchronous_reset',reset_contract=sync['reset_contract']),
 unavailable_power=dict(constant_TIE_W=None),
 excluded=['operandSRAM/CIM','globalCTS/NoC/PHY','production_quantization_and_crossK_storage',
  'wholeAttention','wholechip_area_energy_time','numerical_model_quality'])
save(OUT/'250MHz/COMPONENTS.json',components)
review=load(PROJECT/source_paths['zero_uncertainty_review'])
save(OUT/'500MHz/STATUS.json',dict(status='DIAGNOSTIC_AND_CONDITIONAL_ONLY',default_enabled=False,
 full_system_ready=False,qualified_price=None,original_constraints_timing_pass=False,
 conditional_review=review,source='zero_uncertainty_review',
 note='Ignoring setup uncertainty is an arithmetic sensitivity,not a newSTA or full-chip500MHz approval'))
missing=[dict(id=k,status='NOT_BOUND_FOR28NM',required=v) for k,v in [
 ('SRAM','28nm organization/ports/capacity/access time/read/write/leakage calibration'),
 ('Attention_scalar_and_sampler','sameprocess arithmetic,front,max-gap/LUT/P8,Ising/Vcontrol and state costs'),
 ('DMA_vector_conversion','sameprocess DMA/FIFO,format/scale,Norm/RoPE/residual and clockgating costs'),
 ('CIM_and_interconnect','weight storage/CIMinterface,loading,localrouting and distribution boundary'),
 ('allocation_and_scheduling','28nm pool/FFN counts and equalarea controls;realbandwidth/queues/backpressure'),
 ('full_system_validation','future matching Qwen anchors andfullcases,closedstate/activity ledger')]]
save(OUT/'PROCESS_PROFILE.json',dict(status='DIRECTORY_AND_COMPONENT_STAGING_ONLY',process='TSMC28HPC+',
 default_enabled=False,full_system_ready=False,area_multiplier=1.0,automatic_55nm_scaling=False,
 selected_system_frequency_MHz=None,wholechip_area_mm2=None,wholechip_energy_mJ_token=None,wholechip_time_ms_token=None,
 component_profiles={'250MHz':'250MHz/COMPONENTS.json','500MHz':'500MHz/STATUS.json'},missing_bindings=missing,
 external_memory_policy='May reuse independentlydeclared LPDDR model;offchip rates do not scale withlogicprocess',
 existing55nm100_250_defaults_unchanged=True,no_new_TLM_or_EDA_jobs=True))
save(OUT/'SOURCE_INDEX.json',dict(status='local_sources_SHA_verified_no_raw_reports_copied',issue=225,
 owner_circuit_issue=204,sources=sources,PDK_or_netlist_included=False))
text(OUT/'README_ZH.md','''# 28nm 工艺 TLM 准备目录

2026-11-08，Issue225 / PR249，维护人 rayggxia。用户要求先建立独立28nm目录，暂不提供完整TLM。本目录目前只登记已测组件、来源和缺项，没有整机运行入口、整机面积/能量/速度，也不改变55nm的100/250MHz默认或正在运行的三模型任务。

|目录/文件|用途|
|---|---|
|250MHz/COMPONENTS.json|已通过前布局检查的28nm组件，包括最新A9同步复位版|
|500MHz/STATUS.json|原约束时序失败及零setup不确定度条件分析；不作为已合格500MHz价格|
|PROCESS_PROFILE.json|未来接入状态与尚缺模块；整机值保持null|
|SOURCE_INDEX.json|原交接位置和准确SHA；不复制工艺库、网表或大原始报告|

## 当前可以使用的250MHz组件

TSMC28HPC+、TT0.9V25℃。28nm面积按原值×1.0，不能再乘本项目55等效的0.81。

|组件|整核面积mm²|标定能量pJ/DOT64|服务说明|
|---|---:|---:|---|
|随机FFN公共核|0.373801302|GU10.162500；Wd9.254021|M128/K64；GU16/Wd32，18/34拍；两模式共享一份面积|
|BF16 FMA16/C4|0.062453790|211.495833|连续窗口吞吐；不是一次DOT64的单拍延迟|
|准确A9×W8同步复位核|0.010242414|peak10.901333|K64、1拍延迟/II1；复位至少覆盖两个上升沿|

DOT64指64项点积。三个核的规模、精度、输入活动及接口不同，不能直接按整核面积或功率宣布等吞吐胜负；gross价含该工作窗口的已建模驻留功耗，后续接入不得再叠加整段idle。完整mode、等待/漏电及三seed变化保留在JSON。

原始六配置88窗＋同步复位版21窗均有交接；本目录复用其索引，不是新做109次仿真。FFN是28nm原门限缓存/C19/518ICG版本，不能套用55nm新delta_v3的19/35拍。TIE功耗未知仍为null，面积已计；模型/库表告警和前布局范围保留。

## 500MHz与待接入项

原约束下FFN、A9、BF16的500MHz都有时序失败。去掉预设setup uncertainty后的条件分析中FFN/A9 setup可能满足2ns，BF16仍不满足；A9旧异步复位hold问题也未由此消失。这不是新的STA或全片500MHz验收，250MHz价格不外推为500MHz价格。

后续优先补SRAM组织/读写/漏电、Attention标量与采样器、DMA/转换/向量、CIM接口及互连，再确定计算核数和等面积数字对照，最后才接整机调度与闭合账本。外存LPDDR是独立边界，可以明确复用原模型，不随28nm或片上时钟自动加速。

当前不把55nm剩余模块直接缩放后包装成“28nm完整结果”，不新启动TLM、RTL或EDA作业。源组件交接仍由Issue204维护，本目录只是Issue225的消费端准备层。
''')
assert all(load(OUT/n)['full_system_ready'] is False for n in ('PROCESS_PROFILE.json','250MHz/COMPONENTS.json','500MHz/STATUS.json'))
assert load(OUT/'PROCESS_PROFILE.json')['wholechip_time_ms_token'] is None
for row in sources.values():assert digest(Path(row['local_path']))==row['sha256']
save(OUT/'VALIDATION.json',dict(status='PASS_COMPONENT_STAGING_CHECKS',source_SHA_count=len(sources),
 process_isolation=True,area_factor_1_once=True,qualified_A9_sync_selected=True,whole_system_outputs_absent=True,
 new_circuit_measurement=False,new_full_TLM=False))
for f in OUT.rglob('*'):
 if f.is_file():
  target=PROJECT/f.relative_to(ROOT);assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
print(json.dumps(dict(status='created',folder=str(OUT),files=len([x for x in OUT.rglob('*') if x.is_file()]),whole_system_ready=False)))
