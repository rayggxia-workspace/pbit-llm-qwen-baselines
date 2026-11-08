"""Evidence-backed handoff;no RTL changes,simulation or new PPA measurements."""
from pathlib import Path
import hashlib,json,math
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
OWNER=PROJECT/'tmp/attention-compare-issue198-20261027'
OUT=ROOT/'architecture_tlm/module_handoff/attention_score_front_compare_20261108'
assert not OUT.exists();OUT.mkdir(parents=True)
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
sources={
 'S12_RTL':OWNER/'architecture_tlm/attention_compare_20261027/quant_front_20261104/quant_front.sv',
 'S12_results':OWNER/'architecture_tlm/attention_compare_20261027/quant_front_20261104/RESULTS.json',
 'S12_report':OWNER/'architecture_tlm/attention_compare_20261027/quant_front_20261104/REPORT_ZH.md',
 'S12_execution_manifest':OWNER/'architecture_tlm/attention_compare_20261027/quant_front_20261104/EXECUTION_MANIFEST.json',
 'FP32_front_macro':OWNER/'architecture_tlm/attention_supply_front_20261107/score_front.py',
 'module_cost_adapter':OWNER/'architecture_tlm/attention_supply_front_20261107/costing.py',
 'module_base_price':OWNER/'architecture_tlm/attention_unified250_v2_20261107/pricing.py',
 'module_proxy_prices':OWNER/'architecture_tlm/attention_unified250_v2_20261107/OTHER_PRICES.json',
 'module_handoff':PROJECT/'architecture_tlm/module_handoff/attention_supply_front_20261107/HANDOFF_ZH.md',
 'cross_model_price':PROJECT/'tmp/cross-model245-20261106/architecture_tlm/model_scaling_20261106/current_pricing.py',
 'short_PPL_report':OWNER/'experiments/attention_gap_accuracy_20261102/results/REPORT_ZH.md',
 'distribution_report':OWNER/'experiments/attention_distribution_20261107/REPORT_ZH.md',
 'registry':PROJECT/'digital_circuit_simulation_registry/records/attention-score-quant-front-198-20261104.json'}
index={k:dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for k,p in sources.items()}
old=next(x for x in load(sources['S12_results'])['rows'] if x['q']==12)
other=load(sources['module_proxy_prices'])
area=4*other['fp32_add_area55_mm2']+.008+64*other['holding_area55_per_byte']
energy128=128*(2*other['fp32_add_incremental_pJ']+other['fp32_to_bf16_pJ'])/1000
assert abs(old['area55_mm2']-old['raw_area_um2']*.81/1e6)<1e-12
assert abs(old['query_nJ']-old['work_mW']*650/1000)<1e-10
facts=dict(status='SOURCE_AUDIT_NOT_NEW_SIMULATION',issue=225,related_issue=198,
 old_S12=dict(source='S12_results',PVT='SS1.08V125C',MHz=100,candidates=128,lanes=4,
  area55_mm2=old['area55_mm2'],gross_query_nJ=old['query_nJ'],dynamic_query_nJ=old['dynamic_query_nJ'],
  mean_cycles=old['mean_cycles'],power_work_mW=old['work_mW'],idle_openclock_mW=old['idle_mW'],
  slacks_ns=old['slacks_ns'],area_by_cell_group=old['area_by_cell_group'],buffer_bits=1536),
 new_FP32=dict(status='TIMING_AND_COST_MACRO_NOT_NEW_RTL_PPA',uncontended_cycles=73,
  score_SRAM_read_bytes_per_query=1024,macro_area_per_instance_mm2=area,
  proxy_arithmetic_only_query_nJ=energy128,
  proxy_warning='11/7 moduleprice composition only,not actual FP32 front cost nor a universal whole-model price'),
 same_short_protocol=dict(targets=1024,seeds=3,S12_PPL=13.954596,FP32gap_PPL=13.739371,complete_WT2=False),
 numerical_checks=dict(S12_range=[-128,127.9375],gap_signed_bits=13,U8F4_max=15.9375,
  logical_FP32_row_bytes=512,S12_DFF_row_bytes=192,S12_padded16_SRAM_row_bytes=256,
  shared_threshold_row_bytes=128,quantization_not_repeated_per_sampling_update=True),
 no_new_RTL_PT=True,no_new_GPU_PPL=True,no_default_or_running_snapshot_changed=True)
save(OUT/'AUDIT_FACTS.json',facts);save(OUT/'SOURCE_INDEX.json',dict(sources=index,raw_reports_or_owner_source_copied=False))
doc='''# Attention分数前端：S12先量化与FP32先求差的电路成本交接

2026-11-08｜Issue225 / PR249，关联Attention Issue198 / PR199｜整理：rayggxia。

**给接手对话的结论：这两种前端的电路成本还没有被公平地拆清。S12路径并不是做两次浮点量化；第二步只是整数饱和裁剪。S12已有独立PPA，新FP32前端仍是时序／成本宏。现有TLM前后面积和能量相近，不能证明两种电路成本相同。** 本文只交接审计，不改变默认、不改冻结运行、不启动新仿真。

## 1. 先固定同一个输入、输出和比较范围

每次查询：一个Q头、128个有效候选、4路并行。共同输入为已做QK缩放的FP32分数；共同输出为U8/F4差值地址，再经同一个256×8bit sigmoid表得到P8阈值。mask、RNE舍入、饱和、ready/valid及回压规则一致。

|阶段|A：S12先量化，已有RTL/PPL路径|B：FP32先求差，最新TLM宏|
|---|---|---|
|首次处理|`q=clip(RNE(score×16),−2048,2047)`|直接比较FP32分数并求max|
|最大值|12位有符号比较＋选择|有限FP32比较＋选择；不是一次浮点加法|
|求差|13位有符号减法，确保最大4095不回绕|FP32减法，包括对阶、相减、规格化和舍入等实现成本|
|转U8地址|`address=min(max(q)−q,255)`|`address=clip(RNE((max−score)×16),0,255)`|
|后续共同部分|同一P8 LUT、阈值保持、随机比较、赢家保持、V读取累加|同左，但阈值不同可能改变实际采样轨迹|

**A的整数差本来就带4位小数，转U8没有再做一次浮点转换或小数舍入，只需检查高位、超限选255，否则取低8位。** FP32→S12的首次转换也可由指数判断、尾数取位／移位、RNE和饱和实现，不应按一套通用FPU计价。FP32比较同样不能机械套用完整ADD能量。B需要处理浮点差值规则及流水状态，其物理实现方式尚未确定。

**也不能反过来认定B必须是一套通用FP32减法器加转换器。** 最后只要U8/F4时，可以设计对阶／相减／舍入／饱和融合的专用单元，避免写出完整FP32中间差；截断范围也可能用于提前判定。但必须保持足够的保护位／粘滞位和抵消精度，不能先把两输入各自砍到F4后还称为B。当前宏显式有“FP32减法舍入，再转F4”的顺序；若专用实现改成精确差后只舍入一次，需要证明输出等价或单列为第三种数值路径。因此ADD代理价既可能高估，也可能漏掉控制／流水成本，不能预先断言B一定大几倍。

S12/F4为总12位、4位小数；地址U8/F4为总8位、4位小数；概率P8也是8位。旧RTL中的5位wp/rp是32个四分数组的地址指针，不是5位分数或概率。

## 2. 已有数字能说明什么

|项目|已有证据|不能推导的结论|
|---|---|---|
|A独立前端|55nm等效SS1.08V125C、100MHz；面积0.015050059mm²；128分数查询gross0.166291667nJ，工作功率0.255833mW；65拍|不是250MHz/28nm数据，不含LUT、阈值、随机源、仲裁、QK、KV/PV或输入SRAM|
|A面积构成|寄存器0.009159156、ICG0.000644728、组合逻辑0.005246176mm²；1536bit分数DFF|约61%面积在寄存器，但不能因此免费删掉分数的后续保存需求|
|A时序|setup约+0.006119ns、hold+0.252494ns；前布局，有活动／库表告警|不能把65拍直接改为250MHz并称已经STA通过|
|B宏|4路、两遍SRAM读、32B输入FIFO、4个FP32部分max；无争用73拍|没有这个完整新前端的对应RTL/DC/PT，73拍是宏假设|
|同协议短PPL|A13.954596±0.170664，B13.739371±0.084208；1024个后缀目标、三seed|不是完整WT2；S12当轮分数截断率为0，不能说S12已被证明显著不够|

A为原作业38559861的独立四路前端，面积原18580.32µm²单次乘0.81；gross已含工作窗漏电。其65拍＝32拍流式转换／维护max＋32拍读回／输出＋1拍start，没有第三遍max扫描。不能在每一次S64采样更新中再重复65拍或重复收转换能量。

B在11月7日模块脚本中的面积占位是`4×FP32_ADD面积＋0.008mm²控制＋64B保持`，约**0.0481955mm²/实例**；算术动作占位为每元素`2×FP32_ADD增量＋FP32→BF16转换代理`，128元素约**1.61985nJ**，尚不含该前端额外SRAM等项。**这些是旧代理价的组合，不是B实测，也不是所有整机版本统一使用的单价；不能拿它与A宣布3.2倍面积或某个能耗倍率。** FP32→BF16价格不能自动等同专用FP32→U8/F4价格。

## 3. 存储和调度是另一个变量，必须分开比较

|对象/动作，每128分数查询|A当前RTL组织|B当前宏组织|
|---|---|---|
|从既有FP32分数SRAM取数|若以这个边界开始，读一遍512B，随后存本地S12|两遍各512B，共1024B读取|
|查询期间需要保留的分数|1536bit＝192B本地DFF|原FP32分数512B驻留在SRAM，外加FIFO、部分max和未知流水寄存器|
|若A改用SRAM保存S12|紧凑位数192B；16位对齐通常为256B，物理端口字节另算|不能按12/32直接缩小任意16B SRAM事务|
|P8阈值保持|128B，共同成本，装入后跨多个采样更新复用|同左，不是每个S样本复制一份阈值阵列|

上表的512/1024B是逻辑连续布局下的输入读量；最终按实际16B字、地址、填充和bank事件计费。本地DFF读写不是SRAM读写，不能把两者字节简单相加后套同一个pJ/bit。

还要明确三件事：

1. FP32分数写入是否已在QK生产端计过；若已计，前端不再加一份写入。即使容量已分配，其驻留生命周期、端口占用和读能量仍需统计。
2. B可以在QK流式输出时维护max，随后只读一次FP32分数；A也可以边输出边转换／维护max。要分别比较“数制顺序”和“流式融合／缓存组织”，不能只给一边这项优化。当前B宏的两遍读不是理论最低读量。
3. A的192B DFF不能按SRAM位密度计面积；B删去该DFF后仍有FP32缓存和流水状态。若借用现有SRAM，须说明容量/端口/生存期是否确实可复用，而不是默认免费。先做好每查询的动作数，再按实际实例数计面积；不是每层新建一套前端。

## 4. 目前TLM账本里没有拆清的地方

- **旧／新模块预算都保留了同一条`wide_score_front_reserve`。** 显式前端通过`FP32_to_S12=wide_score_quantize`复用旧计数入口，名字已经不能代表数制。因此“总面积没变”有预算沿用的原因，不能当电路证据。
- 前端面积用4个FP32 ADD类单元代理，max比较、FP32减法、专用定点转换、流水寄存器／输入隔离尚未分别标定。面积共享与并发阶段也未用新网表核验。
- 旧采样器gross价格里含未单独切窗的准备阶段；时间中删除旧65拍，并不等于能量／面积中也已经精确扣除对应逻辑。保留整块旧sampler再加新前端可能高估，直接减去整块旧sampler又会漏掉共同随机／赢家逻辑。这个边界重叠问题不能冒称整机所有gross/idle都重复计算。
- SRAM新前端已有真实读事件时，应移除旧额外读预算；反之不能删除物理事件。旧sampler准备的寄存器捕获、阈值装载、时钟与漏电，各自只计一次。
- 跨模型整机`current_pricing.py`又以ADD/转换动作组成前端代理；需要与模块版统一边界和价卡，而不是仅凭同一模块名称认定同价。
- 新TLM前端配旧S12参考采样轨迹，只能支持固定负载的条件时序回放。量化顺序改变P8阈值后，赢家切换、仲裁、缓存命中、唯一V数和回压也可能变化；端到端比较应使用各自阈值驱动的地址轨迹。

历史250MHz局部前缀配对592.824→593.236µs；片上能量393.972→393.938～393.974µJ，覆盖面积前后14.01214mm²。其范围为从embedding到O的模块前缀、含共享池和672KiB归属SRAM，**不是当前整机，也不是S12实物与FP32实物的配对PPA**。面积预算复用、准备费用重叠区间及代理成本存在，不能据这些很小的差值宣称B免费。

## 5. 给Attention／电路对话的建议工作

**先保留A为已有证据参考，B单列候选；本交接不擅自修改任何运行或默认。** 如果决定继续比较，优先完成下面三件事，不必重做整个LLM电路。

1. **统一接口与数据流。** 一个query＝128个FP32分数，4路、相同握手／mask／输出地址／目标PVT频率。明确采用同样的输入SRAM还是同样的QK流式输入，各自中间存储写清。A直接复用现有RTL；只在改组织／流水／时钟时重测A。
2. **补B的小前端与配对表征。** 实现有限FP32 max、FP32差值、专用RNE U8/F4饱和。对有限极值导致的减法溢出，要明确饱和255及状态处理，不能依赖Python先用更宽精度减再夹紧；NaN/Inf／全mask规则也要一致。RNE半整数边界、S12饱和、mask、回压、复位、输入保持用同一oracle核对。记录延迟、II、气泡、服务窗口；流水寄存器、ICG、负载都算入。
3. **交付可直接接TLM的差额。** 每实例面积与组件边界；每query活动gross和等待／漏电；每元素比较／减法／转换与每字SRAM读写次数；时延／II；保留／删去哪些旧准备资源。用独立work/hold/gated-idle窗口，避免gross服务再叠全时idle。新电路run登记统一台账，保留PVT、激励、频率和原件SHA；模块profile与数值前向同时标`frontend_kind=s12_max_gap`或`fp32_max_gap`。

100MHz SS是现有可用起点；250MHz或28nm用各自结果或显式代理，不能静默跨角点外推。p-bit/RNG、P8 LUT、赢家及V路径先保持共同边界；完整链条再用各自阈值与同协议随机源跑轨迹/PPL，不能由短测均值宣布精度无损。

## 6. 交付与证据入口

本目录`AUDIT_FACTS.json`保存可机读数字，`SOURCE_INDEX.json`保存准确本地文件位置／SHA。未复制私有owner源码、波形、网表或工艺库，也没有新增RTL/PT/GPU/PPL/TLM作业。

主要源：已有`quant_front_20261104/REPORT_ZH.md`与`RESULTS.json`、`score_front.py`、`costing.py`、`attention_unified250_v2_20261107/pricing.py`和`OTHER_PRICES.json`；统一台账run为`attention-score-quant-front-198-20261104`。此前完整PPL数制仍按各冻结执行manifest核对，本交接不改写历史结果。
'''
(OUT/'HANDOFF_ZH.md').write_bytes(doc.encode())
assert len(index)==13
assert all(sha(Path(row['path']))==row['sha256'] for row in index.values())
save(OUT/'VALIDATION.json',dict(status='PASS_SOURCE_AND_UNIT_AUDIT',sources_verified=13,
 checks=['rawarea_times0.81_once','gross_mW_times650ns_equalsnJ','S12_second_conversion_is_integerclip',
  'physical_SRAM_and_DFF_boundaries_explicit','FP32_price_proxy_labeled','old_sampler_preparation_overlap_explicit'],
 new_functional_or_PPA_test=False,no_defaults_changed=True))
for p in OUT.iterdir():
 target=PROJECT/p.relative_to(ROOT);assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
print(json.dumps(dict(files=4,report=str(PROJECT/OUT.relative_to(ROOT)/'HANDOFF_ZH.md'),old_S12_nJ=old['query_nJ'],
 new_area_proxy_mm2=area,new_arithmetic_proxy_nJ=energy128,source_checks=13,new_simulations=0)))
