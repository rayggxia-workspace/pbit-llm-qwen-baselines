2026-10-28更新：已完成服务器DC/VCS/PT，见[结果](eda_20261028/RESULTS_ZH.md)。下文为2026-10-27冻结阶段，STA/PT未跑的说法仅指当时；本轮有hold违例和PWR-981，未签核。

# 完整采样反馈与仲裁：电路候选评估（Issue198 / PR199）

2026-10-27；负责人rayggxia。接续用户要求，在现有任务分支增加完整赢家控制、拒绝校正预取消融和55nm库映射面积，不修改此前冻结的v1电路与原结果。

**建议先以G16、二进制赢家状态为主候选，保留融合准备与两级准备两版，待STA后选择。** 当前面积最小的是融合准备，但不能据此认定它在目标频率下最优；G32两级准备也是有竞争力的候选。提前保持判断节省随机服务，却增加组合依赖；一热赢家增加面积，尚无实测时序收益支持采用。

## 1 规则正确，才谈优化

赢家规则为：每帧独立产生候选bit；旧赢家bit=1或全零则保持，否则在所有活跃位置均匀选一位。多1是正常情况。固定优先、随机旋转后首1、round-robin或树上等概率左右选择，都不能直接替代均匀仲裁。

反例：4个位置中活跃{0,1,3}，起点均匀旋转再选首1，输出概率是{1/4,1/4,1/2}，而不是{1/3,1/3,1/3}。本轮精确枚举小N全部bitmap和全部接受rank，并检查预选后保持的完整转移核，不只靠Monte Carlo直方图。

主方案：M=popcount(mask&bits)，k=ceil(log2 M)，从k个公平bit得到r；r>=M则重抽，r<M就选第r个活跃位。M0/1不消耗fair word；M为2幂时无rank重试。无需除法或通用乘法器。对于独立公平位、M>1，每次成功概率大于1/2；实际RANK_CAP=64，失败显式终止query，不补IID或固定优先。功能压力测试用cap8并强制越界，和部署cap64区分。

## 2 数据流与反馈环

```text
固定驱动、带valid/ready的N路bit帧
  → G路局部popcount（可寄存）
  → 平衡exclusive scan：各组prefix、完整M
  → 无偏rank拒绝 → 并行选组与组内rank
  → 小G局部scan/选址 + 当前真实赢家bit测试
  → 按输入帧次序更新赢家 → burn过滤 → 单输出寄存/ready
```

- 固定驱动的bitmap与旧赢家无关，可先做计数和均匀选址。最后提交时再读实际旧赢家，不能使用过期/预测赢家；本轮按位轨迹与独立平坦列表oracle逐周期核对。
- 三个有限弹性处理级（融合准备版少一级）和一个输出寄存；不存无限帧，也不保存全部V。输出阻塞会逐级回压源；burn期间保持帧也计更新，不能删除以制造独立样本。
- G=8/16/32分组，global scan为平衡upsweep/downsweep，避免逐元素线性前缀长链。组内select只处理G位；两级准备版多保存一份bitmap/局部计数，换更短组合级。
- 二进制winner查bit与一热winner的AND/OR归约均实现；后者额外保留N位状态，并不保证真实工艺更快。
- 普通流水版会预选一些最终保持的帧，额外fair服务已计。EARLY_HOLD版在前帧本拍提交结果确定时，对下一bitmap做精确保持判断，能免掉不必要rank；代价是跨两个级的组合依赖，必须STA验证。串行消融自然可用已知旧赢家跳过仲裁。
- 控制接口可以达到1帧/拍，不代表整个Attention或随机源达到1更新/拍。若用R8数字比较器，N512一帧对应512个R8而非512个公平bit；源供给/比较/稳定/去相关、驱动与重配置成本在边界外。

## 3 实际RTL周期

以下N512、128输出+16 burn，共144帧，100MHz只是TB时钟；从首帧接受到末输出消费，含首尾边沿。输入和公平词采用独立保持式源，分组/流水版本对同输入帧及输出SHA严格配对。全1是无rank拒绝的吞吐压力用例，不是实际Attention分布。

|设计|全1帧耗时/拍|M=3压力耗时/拍|全1公平bit|
|---|---:|---:|---:|
|串行调度|577|620|0|
|融合准备|147|190|1296|
|普通流水|148|191|1296|
|提前保持|148|191|0|

M=3包含实际越界重试，额外等待未省略。不同是否跳过保持轮仲裁的政策会消费不同fair词；不声称所有候选具有相同随机轨迹。本次时序只为数字控制，尚未替换PR88的源/配置宏或主unified_v6默认。

## 4 拒绝路径：预取未必最划算

拒绝法m变化会改变下一帧概率，不能像固定驱动赢家一样无条件流水后续提议。本轮保留串行反馈与明确cfg_ready，代表当前驱动已经稳定；没有把重编码/写阈值删除。

优化项只将m个公平校正bit与proposal一起捕获，在singleton树归约时并行算出空态校正。非空帧预取的fair bit也收费；源不足时必须同时等proposal与fair有效，不能凭空补0。

|N512，256提议/128接受|按需公平校正|预取公平校正|
|---|---:|---:|
|配置等待1拍：总拍|1857|1793|
|配置等待8拍：总拍|2753|2689|
|公平bit|64|128|

两版对照使用相同逻辑proposal与校正硬币，128个输出地址SHA完全一致。该合成轨迹预取只省64拍，不能直接宣称能量更低；建议以按需版本为保守面积/熵候选，预取作为显式选项。

## 5 已完成的55nm映射面积

本机SS/1.08V/125°C Liberty，Yosys0.47/ABC完整映射，全部8top无残留generic cell。Liberty面积与同名单元LEF SIZE乘积核对8点，比例均1，单位为µm²。只读本地库，未上传库、库导出的模型或映射网表。

**这是无频率约束的映射单元面积，不是DC/PT、STA通过、布局面积或功耗。** 调试统计输出在固定top中断开，综合可删除相关观测计数器；必要的帧数/重试/反馈状态仍保留。没有额外包一圈输入输出寄存器抬高或掩盖core边界。

|固定top|单元数|面积 mm²|
|---|---:|---:|
|win512_g16_p2_o0_e0|13991|0.048195|
|win512_g8_p2_o0_e0|16062|0.056112|
|win512_g16_p1_o0_e0|11392|0.040823|
|win512_g32_p2_o0_e0|13204|0.044541|
|win512_g16_p2_o1_e0|15867|0.053829|
|win512_g16_p2_o0_e1|13985|0.049701|
|rej512_pref0|5851|0.018058|
|rej512_pref1|5963|0.018223|

逻辑门级回放已完成3个top，使用私有Liberty导出的零延迟逻辑模型；没有SDF/厂商时序检查，具体top/周期/网表SHA见EVALUATION.json。STA及动态/空闲/漏电功率仍为not_run，不能以面积最小认定能量最优或500MHz可达。

## 6 可复现评估与下一步

- 精确数学测试3项；最终赢家104项/332800拍，拒绝20项/90000拍逐周期全等。含mask、零/单/多、burn、保持/切换、重试cap、连续query、复位与回压；同帧/输出SHA配对在最终winner_release2。
- 源文件和输入原字节在执行SOURCE、SOURCE_FILES及manifest；旧finishing覆盖新query的RTL错误、过强的串行source_wait覆盖要求，以及Windows沙箱ABC临时目录失败均保留。首次门级回放误用cap8的RTL golden对照cap64固定top，失败日志保留；最终3项改用相同cap64重新生成激励/oracle后通过，未放宽逐周期比较。
- prepare包包含8固定top、必要RTL、TB/向量生成和DC/PT脚本；SS100MHz先STA，TT补充，再按实际关键路径决定250/500MHz是否需增加流水。run中私有库仅由环境变量指定。
- PT须用同一映射网表的门级活动并核对覆盖，分别报continuous、hold、switch、rank retry、zero、multi/empty reject、重配置等待、输出阻塞与idle窗口。CE不是ICG；有效/空闲功耗、漏电和每次完成输出能量分别报告。
- 没有运行模型/PPL、GPU/Slurm或许可EDA；本轮控制优化不改采样数学，也不继承旧Base或合成初筛为后训练模型验收。
- 正式交付仍为Issue198/PR199。接续在本目录，不重开全量checkout；数字台账新增v2记录并保留v1。原始VCD/私有映射与失败日志按SHA归档，公开只放源、聚合、索引。

复现命令（均使用新的输出目录）：

```sh
python -B -m unittest architecture_tlm.attention_compare_20261027.control_v2.test_math -v
python -B -m architecture_tlm.attention_compare_20261027.control_v2.validate --iverilog /path/iverilog --vvp /path/vvp --ivl-lib /path/lib/ivl --output NEW_WINNER
python -B -m architecture_tlm.attention_compare_20261027.control_v2.rejection --iverilog /path/iverilog --vvp /path/vvp --ivl-lib /path/lib/ivl --output NEW_REJECTION
python -B -m architecture_tlm.attention_compare_20261027.control_v2.make_ppa --output NEW_PPA_BUNDLE
```

## 7 一手参考与采用边界

- [Blelloch, Prefix Sums and Their Applications](https://www.cs.cmu.edu/afs/cs.cmu.edu/project/scandal/public/papers/CMU-CS-90-190.html)：balanced upsweep/downsweep scan; our own RTL, no claim of published Attention controller
- [Lemire, Fast Random Integer Generation in an Interval](https://arxiv.org/abs/1805.10941v4)：unbiased bounded integers and modulo/multiply bias. We use bitmask/reject for small <=512 bounds, not his multiply-high circuit
- [CPython random.py v3.13.0](https://github.com/python/cpython/blob/v3.13.0/Lib/random.py)：getrandbits/reject reference. Ours uses ceil(log2 M)=(M-1).bit_length, no random word at M0/1; power-of-two bounds have no rejection
- [PULP common_cells rr_arb_tree](https://github.com/pulp-platform/common_cells/blob/dc555643226419b7a602f0aa39d449545ea4c1f2/src/rr_arb_tree.sv)：tree/ready-valid/stall reference; throughput fairness is not IID uniform active-address selection; no code vendored
- [YoWASP](https://yowasp.org/)：open-source Yosys WASM runtime; local Liberty only, no private library publication

选择理由是本设计的推导与当前有限评估，不宣称已有论文证明本Attention硬件全局最优。
