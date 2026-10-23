# 给 jieruiz 的 SparQ STA/PPA 实施交接（Issue157）

本交接对应用户指定的后续 EDA 工作，由 `jieruiz` 在其已授权个人环境执行。当前已有数值核、CPU 验证、参数化动作/事务账本和 GPU 测量入口；**完整 SparQ RTL 顶层、完整 dense 对照顶层及其门级网表尚未实现，本项 STA/PPA 为 `not_run`**。这不是把现有五项 FFN 编码/恢复顶层换个名字后直接综合的任务。

交付前由执行者冻结本文件所列缺项、源码提交和配置。没有完整顶层时可以先表征可复用小模块，但结果只能登记为该模块，完整 Attention 面积、延迟、能量仍为 `null`。本文件没有启动 EDA，也没有代替执行者确认工具、库或机器权限。

## 1. 固定算法与比较边界

| 项目 | 本轮合同 |
|---|---|
| 模型与形状 | `Qwen/Qwen3-4B`，revision `1cfa9a7208912126459214e8b04321603b3df60c`；每层、每次 decode，32 Q heads / 8 KV heads，group=4，d=128 |
| 主方案 | `paper-v6-gqa-probability-sum`；r=32，k_total=128，local_total=32，reallocation=False |
| 可见长度 | N=128、512、2048、8192、32768，均含当前 token；先跑 N=2048，再扩展其余长度 |
| 输入/输出 | 输入为已经过 QK-Norm/RoPE 的 BF16 Q[32,128]，外部 BF16 K/V 缓存；输出 BF16 Y[32,128]，位于 Wo 之前 |
| 算法算术 | Q/K/V 扩展到 FP32；各 Q 头独立近似/准确 QK、softmax 和 PV；BF16 只描述缓存及最终输出边界 |
| 分组选取 | 同组 sum(abs(Q)) 选共享 r 通道；每头 tau=`sqrt(d*selected_L1/total_L1)`；先缩放 Q 再点积；组内对各头近似 softmax 概率求和，再选共享 K/V 行 |
| local 与回退 | 最近32个有效 token 固定占用总k预算，含当前；N<=k 整组 dense；任一头选中通道 L1=0 整组 dense。r=d 不等于取消 k<N 的筛选 |
| 补偿 | meanV/alpha 补偿关闭；不放入免费 sumV 状态。未来开启时独立配置、功能验证和计费 |
| 不计入本轮 core | QKV 投影、QK-Norm、RoPE、Wo、残差、FFN、lm_head、主机；若另报完整 Attention，须逐项补齐，不能改用同一个 core 数字 |

数值依据为 [core.py](../../qwen3/sparq/core.py) 与 [来源审计](../../qwen3/sparq/SOURCE_AUDIT_ZH.md)。官方 tag 的 raw-score-sum、k+1/local+1 不属于本轮主合同。旧 max4 summary、小网络、Bernoulli/RNG selector 和 fixed-eight repair 不再叠加进主方案费用。不得从旧 FFN、SNG 或 Ising PPA 推算这些新模块。

FP32 数据通路不自动意味着与 Torch bitwise 相同。必须固定乘加是否融合、归约顺序、舍入、subnormal/overflow、exp/reciprocal/sqrt 实现、top-k 同分规则，以及 local 强制逻辑。现有 PWL 非线性、低位 MAC、量化分数和不同 online softmax 归约均属于候选数值实现：先用对应逐笔软件参考验证，再按相同模型/数据/完整 PPL 与任务计分协议报告差异。尚未由用户接受的质量阈值写 `null`，不能仅凭局部误差自行宣布质量达标。

## 2. 完整顶层仍缺的依赖

以下命名是待交付范围，**不是现成模块名或可运行命令**。

| 缺项 | 必须交付的实现与验收证据 |
|---|---|
| shared-channel selector | 4头 abs/sum、128选32、索引排序/保存、同分和零覆盖检测；真实 compare-exchange 数、共享单元数、II/latency。账本的 padded bitonic 是候选参考，不是已综合网络 |
| 近似评分链 | tau 的全/选中 L1、倒数/开方；共享通道 K 读取、4头 FP32 点积与 N 长度 softmax；有限保持及回读次数 |
| token selector | 组内概率汇总、local32 独立强制、其余位置选足96、N<=128和零覆盖回退；索引不重复、不越界，不依赖仿真器事先给候选 |
| 准确计算链 | 候选 K/V 获取、各头准确 QK、候选 softmax/PV及 BF16 收窄；与 dense 相同算术单元和共享协议 |
| memory/DMA | token-major 与 channel-major K 地址、初始转置构建、每token追加、有限响应/操作数/索引buffer、mask/有效长度、bank仲裁、CDC及反压 |
| 完整控制包装 | descriptor/tag、in/out valid-ready、容量/credit、复位flush、异常输入、重复/丢失事务检测；由请求/返回/消费轨迹证明 read-before-use |
| dense 对照 | 同32Q/8KV复用、BF16缓存、FP32计算；分块在线/融合 softmax + PV，保留max/sum/output重标定状态，不能强制物化完整N概率矩阵 |
| 验证/活动 | 模块与完整顶层TB、可重放真实Q/K/V片段、独立参考结果与候选ID、随机stall/reset及极端用例；固定窗口/完成数和源SHA |
| 工艺包装 | 新顶层全源码filelist、固定参数、SDC、库/宏清单、端口驱动/负载、映射/活动/STA/PT脚本；原FFN driver不能直接接受尚不存在的SparQ顶层 |

源与功能门禁通过后才冻结顶层名、端口和 netlist SHA。需要覆盖 N128 dense fallback、zero-L1 fallback、正负/零值、相同分数、local边界、单布局散布通道、双K读写冲突、输出反压和复位中断。功能失败或未知值未解释时不进入“可用于TLM的PPA”状态。

## 3. 存储边界：片外容量与片上实现分列

以每层、batch1、固定 capacity 为边界：

- dense 与单布局：片外 BF16 `K[8,capacity,128]`、`V[8,capacity,128]`。
- dual K：额外 BF16 `K_channels[8,128,capacity]`，持久容量为 dense 的1.5倍；capacity32768时 dense128MiB、dual K192MiB，不含元数据/对齐。不得把这部分片外容量当成已实现的片上 SRAM。
- 片上 Q、partial/output、softmax max/sum、candidate score/index、K/V response、read-hold、DMA、CDC、transpose/write-combine 状态分别列容量、位宽、bank数、端口和实现（flop/SRAM宏）。只共享实际可复用的数据；四Q共享一次 K/V 读取，四Q算术仍逐头计费。
- 片外接口参数必须冻结：burst、每拍字节/有效带宽、读返回延迟、最大outstanding、请求粒度、写mask/RMW、page/对齐与容量。账本的64B仅是**事务模型假设**，不是实测DRAM总线。
- 当前 token 的 K/V 及其所需副本写入完成后才可消费；有写合并时明确未落地行的转发/回读、buffer占用与flush开销。容量增长不得隐含免费转置或复制整个缓存。

必须单列三类工作：①prefill后初始额外 K 读取/转置写入；②稳态 routing及候选 K/V 读取；③每token K/V和额外K副本追加。默认64B立即masked写的账本中，dual K每token转置副本逻辑2048B可对应65536B事务写入；需要RMW的接口还应补读，采用write-combining则必须提供真实buffer和调度证据。初始化只有在明确生成长度和完成数后才能作另列摊销，不能藏进稳态指标。

读取事务的黄金检查复用 [ledger.py](ledger.py)，允许导入真实每KV候选与通道索引；fallback通道可为空、候选须完整N。账本不代替bank时序/返回valid/有限buffer验证，也不提供DRAM能耗。片外控制器/PHY是否计入芯片面积必须明确；外部DRAM器件能量没有匹配证据则为 `null`，不能乘一个旧FFN每字节系数补全。

## 4. 同预算 digital 对照

冻结一个共享资源配置 `R0` 后，dense与SparQ都使用该配置：FP32 MAC/add/mul实例数、vector单元、exp/reciprocal/sqrt单元、格式转换数、时钟、片外端口及片上总容量/端口预算相同。选择器和新buffer的面积必须计入SparQ，不能一边把4头算术复用、一边又按4头免费并行。允许相同物理单元在阶段间复用，但须报告其仲裁、控制、寄存状态与II。

`Rates()` 的64 MAC/拍、16 vector/拍等只是敏感性示例，不能自动作为已实现资源。执行者须在首个综合配置中填入 `R0` 的具体实例数、各单元latency/II及供数限制；这些字段未冻结时不得发布匹配PPA比较。

若另做等面积优化，建立独立 `R_area` 配置并分别综合，展示选择器/SRAM占用如何减少可用算术资源；不要将它与固定资源 `R0` 的结果混排。dense采用GQA复用和融合/在线softmax，其归约重标定、保持和控制照实计费；两边都不要求存下整个N×32概率矩阵。

## 5. 可复用代码与授权环境

| 可复用入口 | 允许复用与需要重新验证 |
|---|---|
| [nr_fp32_mul.sv](../digital_ppa_v1/rtl/nr_fp32_mul.sv)、[nr_vector_math.sv](../digital_ppa_v1/rtl/nr_vector_math.sv)、[格式转换](../../format_conversion_rtl_20261016/) | 标量算术、compare-exchange和格式转换原语；重新确认语义/位宽、实际流水和共享供数，不继承“组合功能一拍=100MHz” |
| [nr_unary_lut.sv](../digital_ppa_v1/rtl/nr_unary_lut.sv)、[nr_array_probes.sv](../digital_ppa_v1/rtl/nr_array_probes.sv) | 非线性/数组原型；PWL和BF16原语不能直接冒充主合同FP32算术 |
| [nr_memory_control.sv](../digital_ppa_v1/rtl/nr_memory_control.sv)、[nr_attention_control.sv](../digital_ppa_v1/rtl/nr_attention_control.sv) | FIFO/信用/控制构件；不是完整SparQ DMA、top-k或双K接口 |
| [Issue123 EDA交接](../encoding_restore_contract/ppa/HANDOFF_JIERUI_ZH.md)与该目录driver/Tcl/parser | 环境预检、源SHA、固定top/约束、报告单位/活动/STA门禁；原五项编码恢复配置不运行SparQ |
| Issue107 digital_ppa_v1/ppa8；Issue146/PR148 | 与已有负责人协调复用其已核实库、流程/模块证据，避免重复作业；SNG/W8门阵列不等于SparQ选择器。沿用原始来源和状态，不继承完整PPA |

由 `jieruiz` 现场填写实际登录身份、canonical个人根、CPU allocation、DC/VCS/PT工具绝对路径、许可可用性、标准单元DB/Verilog模型、SRAM DB/行为模型/LEF及各自SHA。所有输出位于核实过的个人根；CPU作业显式 `CUDA_VISIBLE_DEVICES=''`，不在共享登录节点跑综合/仿真。路径、工具版本、授权库来源未核实即停在环境预检，不能照抄他人的 `/public3` 或猜测安装路径。

本项目55nm流程可作为目标候选；TT1.2V25℃、SS1.08V125℃仅在**实际获授权库的report_lib/operating_conditions与宏角支持一致**时采用。若现场库电压、温度或工艺不同，保留真实条件并新建配置，不重命名成55nm/TT/SS。standard cell与SRAM每个角都分别核验时间、电容、功率、面积单位；无物理面积单位依据时保留library units，`area_um2=null`。

建议首个目标clock为100MHz/10ns，标签只能为 `requested_clock`。若SRAM使用独立80MHz域，须提供该宏最坏周期/访问检查、CDC及约束；既有宏表提取不是接口STA通过。10ns失败须保留WNS/TNS/失败路径，后续降频或加流水是新配置并重新功能验证。不得通过不当false-path/multicycle-path删除真实数据依赖。

## 6. 最小执行矩阵与阶段门禁

| 阶段 | 最小矩阵/工作 | 输出与放行条件 |
|---|---|---|
| A：先冻结 | SparQ dual K、SparQ token-major、dense fused/online；共同R0和端口边界 | 新顶层/资源/数值/存储合同及完整源码manifest；缺项明确owner和状态 |
| B：功能 | 先N2048，再5种N；每方案相同真实QKV与合成边界/反压输入 | 逐笔输出/索引、顺序、信用、读返回/消费、fallback与活动窗口；独立参考PASS |
| C：综合/STA小闭环 | 先N2048、SS与TT（若现场支持）、100MHz请求；三方案各1个固定top | 每个实际distinct top/config/角独立DC；mapped网表、SDC、面积及setup/hold/check_timing，无未知blackbox/漏约束 |
| D：活动/功率 | 每个已验证网表：真实QKV active、idle、stall、append、initial-transpose；至少三套输入/seed | 门级功能先过；有效VCD/SAIF窗口、X/Z/注释覆盖、接受/完成/字节计数，再PT功率 |
| E：扩展 | 同一参数化最大N顶层运行五种N；若N改变硬件结构则分别综合 | 不因换N重算一遍同一网表面积；区分动态N与独立设计，逐项完整结果 |

“三方案×两角=6份网表”只适用于每方案一个固定资源/最大N顶层；若双/单布局共用一份可配置网表，应记录实际共享关系，不能重复计为独立面积。若未实现所有方案，保留缺项，不以小模块面积相加冒充全核完成。

活动窗口须覆盖同一边界的足够多完整输入/输出：稳态窗口开始/结束时在途数、buffer占用应相同；否则保留fill/drain并明确分母。单token首次延迟与稳态II分开测量。记录每层每token完成一次32头输出，不能把一个head、一个候选或一个tile当成完整token。

## 7. 执行顺序与可检查的交付文件

当前可直接运行的仅为本目录CPU账本检查；命令在准确提交的仓库根执行：

```bash
python3 -B -m unittest architecture_tlm.sparq_baseline.test_ledger -v
python3 -B -m architecture_tlm.sparq_baseline.run \
  --tokens 128 512 2048 8192 32768 --layouts dual_k token_major \
  --capacity-tokens 32768 --out /verified/personal/new-run/LEDGER.json
```

后续 EDA 执行入口应随顶层实现一起提交，禁止提供一个实际综合旧FFN top的“成功”命令。每阶段保存完整命令、退出码和工具版本；只有已完成的阶段可按源/配置/库/约束/激励SHA恢复，失败或修改用新run目录。

1. `PREFLIGHT.json`：个人根与allocation回执，工具/许可、源闭包/库/宏/SDC/配置SHA，实际PVT/单位；不上传库本体。
2. `FUNCTIONAL.json`：参考版本、数值实现、激励SHA、N/布局、接受/完成/fallback、数值/握手/信用断言；失败保留首个反例。
3. `DC/STA`：完整mapped面积和分层面积、寄存器/组合单元、SRAM边界、critical paths、clock、WNS/TNS、hold、未约束路径及全部warning；block timing失败照实登记。
4. `ACTIVITY.json`：mapped netlist/TB/model SHA、是否SDF、窗口起止/时长、输入/输出/读写事务/完成token数、时钟与电源状态、VCD/SAIF SHA、X/Z与注释覆盖、idle/stall/active分类。
5. `POWER.json`：标准单元internal/switching/leakage、SRAM、controller/PHY及片外DRAM分项；没有证据的部分为null，列总和是否完整。
6. `RESULT.json`与公开摘要：每个方案/配置/PVT的性能、面积、能量及证据链接；更新 `digital_circuit_simulation_registry`，保留旧失败/来源，不把新包装登记为新的独立原语测量。

功率放行还须检查每类实际使用单元的timing/power表齐全、单位一致、活动注释的分子/分母与排除网清单、未注释网和X/Z原因。缺表、未解释blackbox/未约束路径、时序违例或未关闭的相关warning保持 `accepted_for_tlm=false`；可以保留原始估值，但不能把它升级为该频率可执行的完整结果。

建议采用以下回填结构，**此处所有数值空值都表示尚未测得**：

```json
{
  "issue": 157,
  "status": "not_run_missing_complete_rtl",
  "source_commit": null,
  "source_manifest_sha256": null,
  "top": null,
  "config_sha256": null,
  "scheme": "sparq_dual_k",
  "shape": {"query_heads": 32, "kv_heads": 8, "head_dim": 128, "r": 32, "k_total": 128, "local_total": 32},
  "numeric_implementation": null,
  "quality_protocol_sha256": null,
  "quality_acceptance_budget": null,
  "shared_resource_budget": null,
  "memory_boundary": {"offchip_capacity_tokens": 32768, "onchip_buffers": null, "ports_and_rates": null},
  "process": null,
  "pvt": null,
  "library_and_macro_sha256": null,
  "requested_clock_hz": 100000000,
  "achieved_clock_hz": null,
  "setup_wns_ns": null,
  "setup_tns_ns": null,
  "hold_wns_ns": null,
  "unconstrained_paths": null,
  "area_um2": {"selector": null, "approx_qk_softmax": null, "exact_qk_softmax_pv": null, "format_control_fifo": null, "sram_macros": null, "controller_phy": null, "complete_core": null},
  "sram": {"instances": null, "capacity_bits": null, "ports": null, "power_source": null},
  "activity": {"scenario": null, "sha256": null, "window_seconds": null, "completed_layer_tokens": null, "completed_append_tokens": null, "constructed_cache_tokens": null, "annotation_coverage": null, "xz_status": null},
  "power_W": {"cell_internal": null, "cell_switching": null, "cell_leakage": null, "sram": null, "controller_phy": null, "offchip_dram": null},
  "energy_J_per_layer_token": null,
  "energy_total_scope_complete": false,
  "first_token_latency_ns": null,
  "steady_state_ii_cycles": null,
  "initial_transpose_energy_J": null,
  "append_energy_J_per_token": null,
  "warnings": [],
  "accepted_for_tlm": false,
  "raw_reports_location_and_sha256": null
}
```

面积分项须注明是否包含子层级，不能把parent与child相加。power分项在各自唯一边界相加；若完整core功率本身已经包含append或SRAM，不再重复加一次。core能量按真实活动窗口 `P[W]×duration[s]/completed_layer_tokens` 计算；仅追加窗口改用完成全部8KV组及所需副本写入的 `completed_append_tokens` 作分母，初始转置报告整个已构建缓存的总能量及 `constructed_cache_tokens`。分母为0/未知、idle-only或不完整窗口不填每token能量，保留窗口总能量/功率；初始化能量独立。缺少SRAM/片外项时只能报告已测部分能量和未覆盖列表，`energy_total_scope_complete=false`，不能将null视为0。

公开GitHub只交付可公开源码、配置、摘要、状态及散列索引；工艺库、受限工艺模型/报告、大波形和网表保留在已授权个人存储并登记可恢复位置。前布局mapped cell area不等于die/core面积，未做CTS/SPEF/后布局不得称物理实现；GPU板卡功率与本轮ASIC PPA分别报告。待文件发布后由任务负责人在原Issue/PR中通知 `jieruiz`，避免对未就绪顶层重复提交EDA作业。
