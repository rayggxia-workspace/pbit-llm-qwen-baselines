"""Small reviewable delivery;never publishes private execution snapshot contents."""
from pathlib import Path
import ast,hashlib,importlib.util,json,tempfile
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
FORMAL=ROOT/'architecture_tlm/model_scaling_20261106';R2=HERE/'revision2'
def dump(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_bytes(s.encode())
for n in ('current_mainline.py','current_run.py','current_pricing.py','prepare_current.py','aggregate_current.py'):
    ast.parse((FORMAL/n).read_text(),filename=n)
spec=importlib.util.spec_from_file_location('aggregate_current',FORMAL/'aggregate_current.py')
aggregate=importlib.util.module_from_spec(spec);spec.loader.exec_module(aggregate)
with tempfile.TemporaryDirectory(dir=HERE,prefix='aggregate_guard_') as t:
    t=Path(t);(t/'PLAN.json').write_bytes((R2/'snapshot/PLAN.json').read_bytes())
    try:aggregate.aggregate(t,t/'summary')
    except AssertionError as e:assert len(e.args[0]['missing'])==36
    else:raise AssertionError('Incomplete full runs must not emit completed report')
    assert not (t/'summary').exists()
status=json.loads((R2/'STATUS_CURRENT.json').read_bytes());sub=json.loads((R2/'SUBMISSION.json').read_bytes())
dispatch=json.loads((R2/'DISPATCH.json').read_bytes());final=json.loads((R2/'FINALIZER_SUBMISSION.json').read_bytes())
pub=HERE/'delivery';pub.mkdir(exist_ok=True)
for folder,n in [(R2,'SUBMISSION.json'),(R2,'DISPATCH.json'),(R2,'FINALIZER_SUBMISSION.json'),(R2,'STATUS_CURRENT.json'),
                 (HERE,'LOCAL_CHECKS.json'),(HERE,'RETIRED_DISPATCH.json')]:
    source=folder/n
    if source.exists():(pub/n).write_bytes(source.read_bytes())
dump(pub/'CHECKS.json',dict(status='PASS',AST_sources=5,incomplete36guard='rejected_without_report',
    prior_local_cases=5,current_remote_pilot_gates=len(status['pilot_gates']),new_GPU=False,new_RTL_PT=False,
    aggregate_source_sha256=sha(FORMAL/'aggregate_current.py'),
    current_execution_source_sha256={n:sha(FORMAL/n) for n in ('current_mainline.py','current_run.py','current_pricing.py')},
    frozen_manifest_sha256=sub['manifest_sha256'],snapshot_sha256=sub['snapshot_sha256']))
plan=json.loads((R2/'snapshot/PLAN.json').read_bytes());dump(pub/'PLAN.json',plan)
snapshot=json.loads((R2/'snapshot/SNAPSHOT_MANIFEST.json').read_bytes())
dump(pub/'SOURCE_INDEX.json',dict(source_manifest_sha256=sub['manifest_sha256'],snapshot_sha256=sub['snapshot_sha256'],
    exact_sources=snapshot['sources'],publication='hashes/locations only;private owner source/fixtures/archive excluded'))
text='''# 三模型当前主线 TLM：完整评估执行入口

2026-11-08，Issue245 / PR247，负责人 rayggxia。已把跨模型适配接回当前100/250MHz执行主线；旧24项串行试接pilot及解析预算保留作历史，不能作为本轮整机结果。

## 评估什么

|模型|层数|隐藏/FFN宽度|Q/KV头|映射到8个物理KV组|
|---|---:|---:|---:|---|
|Qwen/Qwen3-4B|36|2560/9728|32/8|1波，每组4个Q|
|Llama-3.2-3B-Instruct|28|3072/8192|24/8|1波，每组3个有效Q|
|DeepSeek-LLM-7B-Chat|30|4096/11008|32/32|4波，每组1个有效Q|

模型revision、config来源和SHA仍见CURRENT_WORKLOAD_PLAN.json及evidence。Llama配置为官方SKU派生。只做硬件工作量及执行评估，无须下载权重；不推断这三个模型的PPL、精度或真实文本开关活动。

|芯片版本|片上SRAM|随机FFN核|概率硬件覆盖面积|
|---|---:|---:|---:|
|55等效100MHz|1088KiB|6|33.284710mm²|
|55等效250MHz|960KiB|3|22.086073mm²|

100MHz采用SS1.08V125C；250MHz FFN采用已验收TT1.2V25C delta_pipeline_v3，而非旧失败STA价格。两者角点不同，不能把能量差全部解释为频率变化。原流程面积按用户规定乘0.81一次；功耗、时间不套0.81。28nm组件候选不混入本表。

每种芯片跑全部三个模型，不随模型放大物理SRAM或随机核。数字对照在相同总面积上限、相同外存、相同物理SRAM容量下分配合法FMA16切片与有限FIFO；SC专用核和采样器不再向数字侧收费。切片离散造成的小面积缺口在每个结果中原样列出，不称面积逐位相等。

每模型/频率有SC_ising、BF16_dense、W8_dense、W8_screen四路径；SC三部署参考seed17/503/1009，数字各seed17，共24配置、36完整模型执行。B1、上下文2048；筛选r32/K128，SC赢家保持S64。FFN使用当前已标定GU16/Wd32（100MHz18/34拍、250MHz19/35拍）；不把算法上另测GU8的结果冒充这套已标定硬件。W8只指FFN权重，Q/K/V/O与lm_head仍BF16，W8数字非线性保持确定性。

## 保留的执行机制和新适配

- 保留主线普通投影有限FIFO、提前补货、公共FFN后端、PV地址生产/读取/累加的重叠，未回退为旧试接的串行算子相加。
- 数字投影、FFN与Attention实际申请同一个共享FMA池，释放后才能复用；原CIM权重SRAM区在数字阶段用作普通SRAM，没有免费添加计算阵列或权重缓存。
- W8数字GU四个K64合为一个DMA包，仍逐K64计算；有限双包FIFO和SRAM端口实际计入。非线性为5级有限流水、II1，不把5拍延迟当每块5拍启动间隔。
- DeepSeek权重尺度元数据33024B，向上分配到36KiB；重新安排GU尺度偏移，避免旧固定20000与权重尺度重叠。Norm每槽16KiB，按实际宽度/是否QK norm搬运。
- KV复用使用逻辑头地址；Q/K/V输入、输出、转置、残差、Norm、尺度码和部分和的读写仍经过真实物理bank/端口，DMA/队列/回压/等待/排空均参与时间。没有把外存当无限带宽数组。
- Llama/DeepSeek保留物理4Q槽的QK及确定性PV填充成本；SC无效Q的采样关闭。这是当前硬件映射，未宣称针对MHA或3Q组的最优专用电路。

外存时序沿当前LPDDR-derived8533 Ramulator桥和有限DMA，名义136.4606GB/s；属于LPDDR5时序派生情景，不能写成已取得厂商8533完整模型。外存能量独立用4/6.6/8pJ/bit三情景，不把时序模型误称为已校准DRAMPower。权重、KV及其它请求都计字节。

## 校验、作业和输出

本地5项前驱单层检查通过，包括Qwen100/250解析锚点1.206150/1.085720ms；不能乘层数作整机结果。当前执行revision2修正后，EDA Qwen锚点为1.206270/1.085720ms：100MHz差12拍、约0.010%，记录原差，不伪称逐周期一致。跨环境细微差异原因未单独归因；门禁允许0.1%时间偏差，同时字节/MAC/帧/样本及容量守恒要求精确。

主快照SHA3a7dd5e0679ed56cdb60e37ef54c3c787d62e4470a7436e414f6348a63ab0bbf；manifest SHA982f9303785c364ed7c7ac5384927f0a12f98388433708306878e5f14fbae925。冻结后不修改执行源。

- 8项单层校验数组38631497，最多4并发。
- 门禁全部成功后，协调作业38631505提交8个worker；每个顺序执行4或5个完整case，共36项。不是36项此刻已运行。原36元素直接数组提交触及AssocMaxSubmitJobLimit，没有生成full任务；改用8worker，不取消其它成员任务。
- 独立汇总协调38631640，在full worker全部成功后提交汇总；未改执行快照。汇总强制36项唯一完整层数、含head、原生后端、SHA/守恒/PPA账本均通过，缺项不会产生“完成”报告。
- 每case1逻辑线程、12GiB、0GPU；当前分区按内存授予3 CPU，以Slurm实际分配记录成本。worker上限48小时，非预计耗时。

实际状态以同目录work交付的STATUS_CURRENT.json时间戳、driver门禁回执与sacct退出码为准，不能只看SEAL文件就判作业通过。完整worker/最终汇总ID由FULL_SUBMISSION/AGGREGATE_JOB回执补充。服务器连接、恢复与不可变索引见work/rayggxia/245/HANDOFF.md。

最终SUMMARY.csv/JSON给出每token时间、token/s、能量、平均功率、面积、三seed SD及相对三个数字对照；同时给出不含lm_head阶段的数据。后者保留final norm及已与前层重叠发出的head预取，不是另一套删除head硬件的独立重跑。COMPONENT_ENERGY.csv、PHASE_TIME.csv、AREA_ALLOCATIONS.json展开部件能量、独占阶段时间和面积分配；重叠时间不能把所有局部服务时间直接相加。

## 仍是估计的边界

已校准电路价格与实际动作/驻留相乘，gross服务能量加剩余等待，不加一遍全时idle；SRAM动态及全容量漏电只计一次，共享FMA只计一次。FFN随机前端/非线性已在公共核价内，不另收一遍。

SS100 V控制仍有10%组合储备；数制/尺度转换、向量宏采用现有ADD/转换/保持标定组成的代理价；部分SS标量价格在250MHz保留代理。CIM接口、PHY、完整CTS/NoC及后布局未全片表征，面积是已声明模块覆盖面积，非完整die。合成Q/K、筛选轨迹及Ising参考地址只能支持条件硬件评估，不能替代真实三模型精度/文本依赖功耗验证。

更正历史口径：旧文中“r32需对齐r16”不正确。r16后缀指16路FP32归约加法器；SparQ特征维数始终r32。旧250空价与旧总面积也已被本轮有效v3配置取代，历史原件不重写。
'''
write(FORMAL/'CURRENT_MAINLINE_ZH.md',text)
old=FORMAL/'EXECUTION_STATUS_ZH.md';original=old.read_text(encoding='utf-8')
if not original.startswith('> 当前执行入口'):
    original='> 当前执行入口已更新为 [CURRENT_MAINLINE_ZH.md](CURRENT_MAINLINE_ZH.md)：已接主线、有效250v3价格和36项完整任务DAG。下文为旧适配阶段历史；r16是归约器路数，SparQ始终r32，旧空价/串行项不代表本轮状态。\n\n'+original
write(old,original)
status_text='''## 2026-11-08 Issue245：接回100/250主线，36完整case DAG已安排

负责人rayggxia；task/245-cross-model-estimate / PR247 base main；工作目录tmp/cross-model245-20261106。新入口CURRENT_MAINLINE_ZH.md，完整模型Qwen3-4B/Llama3.2-3B-Instruct/DeepSeek7BChat ×100/250 ×SC/BF16dense/W8dense/W8screen，共24配置、36case。SC3seed，数字单seed；含/不含head阶段。当前6核1088KiB/3核960KiB，250用有效delta_v3价格/面积22.086073mm²；不混28nm。

保留有限FIFO、早补货、PV生产消费重叠；数字共享FMA真租约、GU四K64合包、有限NL流水。逻辑KV地址/元数据36KiB/Norm及动态数制访存已适配。r16指归约器，不是SparQ维数。SS100控制/转换及250部分代理成本显式保留，非全片物理验收。

冻结revision2 manifest982f9303785c364ed7c7ac5384927f0a12f98388433708306878e5f14fbae925。pilot38631497，成功后协调38631505提交8worker共36case；汇总协调38631640再afterok全worker。提交回执及最新状态见work/rayggxia/245/mainline_20261108/delivery/。旧直接36数组因提交配额未建立，已保留失败回执，无重复full提交；revision1原始结果保留作诊断，不作为最终结果。5项本地前驱预检；revision2远端门禁数量看STATUS时间戳和退出码。

阶段：完整执行已安排，尚未收齐36个完整结果，不宣布整机PPA完成，不将单层乘层数；不新开GPU/训练/PT，不改变默认，不合并PR。发布以PUBLICATION_CURRENT.json为准；Projects无写接口，待维护者同步。下一步检查revision2门禁、full worker和汇总；失败在独立新快照修复，禁止改已提交源/重跑健康case。

---

'''
p=ROOT/'progress/rayggxia/STATUS.md';write(p,status_text+p.read_text(encoding='utf-8'))
handoff='''## 2026-11-08 当前主线完整评估恢复

本节优先于下方旧阶段。Issue245/PR247，rayggxia，task/245-cross-model-estimate；未合并。完整说明architecture_tlm/model_scaling_20261106/CURRENT_MAINLINE_ZH.md。正式新源码current_mainline.py/current_run.py/current_pricing.py/prepare_current.py/aggregate_current.py；执行源SHA在delivery/SOURCE_INDEX与CHECKS。

本地：C:/Users/86134/Documents/a_P_BIT/tmp/cross-model245-20261106。网络操作用Codex附带Python，系统3.8 SSH依赖不兼容。只执行读状态，不再次prepare/dispatch/finalize_submit：

`python -X utf8 -B work/rayggxia/245/mainline_20261108/launcher_r2.py status`

主root `/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm245_current_3a7dd5e0679e`，manifest982f9303785c364ed7c7ac5384927f0a12f98388433708306878e5f14fbae925，zip3a7dd5e0679ed56cdb60e37ef54c3c787d62e4470a7436e414f6348a63ab0bbf。详细8门禁/36full计划、源码SHA与执行环境来自冻结manifest；私有源/fixture仅本地和EDA保留，Git只小索引和本任务胶合，不发布整个快照。

pilot38631497；coordinator38631505及`_dispatch_v3/FULL_SUBMISSION.json`；8worker%8每人4/5case，1逻辑线程12GiB48h，实际CPU看sacct。聚合协调38631640，root`_aggregate_2fe4732df6`，`AGGREGATE_JOB.json`记录依赖full worker的最终汇总ID。full目录sealed JSON+VALIDATION+退出码齐全才计完成。聚合仅接受36个唯一全层含head原生case。绝不能重复提交已健康/完成的case。

revision1 root`tlm245_current_0af9dd179a3c`/pilot38631345保留：100MHz锚点严格相等门禁失败12拍，且后续查出逻辑KV输入偏移/显式输入读取待修。其SEAL不等于driver门禁通过；不用作最终版。旧pending协调38631395已在确认pending/名称后取消，RETIRED_DISPATCH有回执；未启动full。revision2独立修正源并记录锚点0.1%容差，工作量仍严格。原始36数组因AssocMaxSubmitJobLimit未创建，不能当full_job。恢复先看SUBMISSION+DISPATCH+FINALIZER+STATUS，再读各root回执，不重执行prepare。

校验：5项前驱本地冷层；5源AST和36缺项拒绝汇总通过；当前门禁成功数看delivery/STATUS_CURRENT。Qwen解析锚点100MHz实际1.206270 vs本地1.206150（12拍，不归因未验证原因）、2501.085720一致。模型PPL不在范围。100SS/250TT角点不同；SS100控制/格式宏及250标量代理未全片测量；28nm保持候选。

交付/待做：本轮代码、状态、交接已本地整理；上传SHA以PUBLICATION_CURRENT.json为准，未写该回执前不能称远端已完成。收齐full后下载封存小JSON/summary，逐SHA核对，发布同一PR247/Issue245、更新STATUS/HANDOFF及长期备忘录；不合并。Projects待维护者同步。未改owner和默认100/250，不重跑225健康Qwen任务。

---

'''
p=ROOT/'work/rayggxia/245/HANDOFF.md';write(p,handoff+p.read_text(encoding='utf-8'))
files=[FORMAL/n for n in ('current_mainline.py','current_run.py','current_pricing.py','prepare_current.py','aggregate_current.py','CURRENT_MAINLINE_ZH.md','EXECUTION_STATUS_ZH.md')]
files+=[ROOT/'progress/rayggxia/STATUS.md',ROOT/'work/rayggxia/245/HANDOFF.md']+list(pub.glob('*.json'))
files+=[HERE/n for n in ('ops.py','launcher_r2.py','poll.py','dispatch_v2.py','finalize_submit.py','recover.py','retire_old_dispatch.py','build_delivery.py')]
dump(HERE/'PUBLIC_FILES.json',[dict(path=p.relative_to(ROOT).as_posix(),content=p.read_bytes().decode('utf-8'),sha256=sha(p)) for p in files])
print(json.dumps(dict(status='prepared',files=len(files),remote_pilot_gates=len(status['pilot_gates']),full_job=status['full'])))
