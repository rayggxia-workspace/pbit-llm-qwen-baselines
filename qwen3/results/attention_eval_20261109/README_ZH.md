# Attention与FFN联合评测归档（2026-11-09）

Issue #198。本批归档81项已核验结果：58项完整WT2、23项后缀短测。首批76项公开后，追加5项FFN均值诊断。含参考与重复控制，并非81种算法；预算扫描另复用的4条结果不重复计数。未启动最终任务集推理，也没有新训练。论文质量验收仍需最终方案的匹配控制和多seed确认。

## 阅读与复验

- `CASES.csv`：每条配置、协议、PPL与mean NLL。
- `INDEX.json`：八批索引与公开载荷SHA；各批`*_index.json`保留分组摘要、原始制品字节SHA。
- `*.json.gz`：无文本/token内容的逐窗口NLL与结果元数据；标准gzip，可直接解压查看JSON。
- `TRAINING_SCOPE_SUMMARY_ZH.md`：与联合评测直接相关的训练范围结论；内部详细审计不公开。
- `python verify_results.py`：仅标准库，重建全部窗口/目标范围，核验载荷SHA、36层覆盖字段、NLL归约与PPL。它是离线结果复验，不是GPU重新运行。
- `python compare_mean_control.py`：从均值消融载荷独立复算QKVO替换的mean-NLL代价、分段差与FFN模式交互；报告见`MEAN_CONTROL_RESULT_ZH.md`。

公开JSON是去除私有机器路径的规范化派生文件。原始密封结果、分块和执行环境保留在既有授权存储；索引中的原件SHA不能当成公开派生文件的SHA。执行identity是冻结源码manifest的SHA-256，不是Git提交号。复跑GPU还需要索引绑定的原始运行时、模型、语料和配置，本包不声称脱离这些依赖即可重新计算PPL。

## 统一口径

Qwen/Qwen3-4B后训练模型revision `1cfa9a7208912126459214e8b04321603b3df60c`；BF16权重、FP32部分归约。teacher-forced原文PPL，不套chat/thinking模板。WT2 raw test SHA-256 `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`；299078输入token。完整2K为292窗，8K为286窗，stride1024，均计299077目标；缓存前缀计分与向量化BF16 anchor不保证逐bit相同。所有新环境均保留未改BF16参考。

Attention默认：FP32 SparQ r32/recent32，四Q头共享候选集；精确候选QK分数先RNE/clamp signed12/F4，再整数max-gap、饱和U8/F4、floor-P8阈值；winner-hold初始slot0/burn0/spacing1。算法随机性由独立Philox模拟，不是GF64或物理p-bit逐bit回放。短测前端对照同时保留FP32先max-gap路径。

| 批次 | 项数 | 范围 |
|---|---:|---|
| trained_cross | 13 | 准确FFN，三种Attention权重及准确PV控制，完整2K |
| trained_budget | 21 | K/S三seed补扫，另复用4条cross结果，完整2K |
| trained_front_pair | 14 | S12先量化/FP32先求差，8×1024目标短测 |
| trained_context8k | 13 | 旧K_WH128权重，完整8K |
| trained_newweights | 6 | 新权重seed0筛查及未改BF16复验，完整2K |
| joint_ffn16_32_attention | 5 | T64导出、前16/后32 FFN，seed101，完整2K |
| joint_qkvo_short | 4 | 固定T64 FFN/公共参数，仅替换QKVO，8×256目标短测 |
| joint_mean_diagnostic | 5 | 固定T64 FFN/公共参数，QKVO来源×FFN抽样/均值2×2及原BF16控制，8×256目标短测 |

## 可支持的结论

准确FFN下，K_WH64的K128/S64、K256/S64分别8.521529、8.505082，略优于旧K_WH128同seed0的8.560371、8.530862。但新权重未补多seed、8K或完整联合验证，不能称15套权重的全局最优。K128/S64效率候选、K128/S128质量候选、K256/S64备选仍保留；三seed/8K确认来自旧K_WH128。

完整联合控制（同seed101）：T64自身QKVO＋准确Attention为10.745272；替入K_WH128 QKVO＋准确Attention为12.289623；进一步SparQ＋Ising K128/S64为13.255076，K256/S64为13.055043。顺序mean-NLL增量分别为0.134289、0.075625/0.060419；前一项说明单独权重替换已产生损失，不能把全部差异归因PV抽样。缺少同权重、同SparQ、准确PV联合控制，后一项仍混合筛选、数制和采样影响。

固定T64公共参数、两边均采样的2048目标短测：T64 QKVO 13.977852，K_WH64 16.488681，K_WH128 16.505126，前者8/8段胜出。这支持T64作为联合适配的暂定起点，尚未证明机制或完整WT2质量。

审计发现：T64 FFN训练实际为full-model，FFN学习率1e-5、其他2.5e-6，144/144 QKVO均变化；其Attention算术保持准确。Attention训练只更新QKVO，FFN及公共参数固定为原BF16模型。两套权重的训练环境不同，直接拼接的输入分布与参数协同变化值得独立消融，不能据此认定联合训练必然无效。

追加均值诊断已完成：FFN抽样时T64/K_WH64 QKVO分别13.977852/16.488681；保留W8、幅度/P8编码和sigmoid LUT，用编码概率均值后分别10.548144/10.205462，排序反转。替换QKVO的mean-NLL代价从+0.165200变成−0.033027。三条重复控制的PPL与全部分段NLL均与上一轮相同；57份源码、68份制品密封/SHA核验通过；均值组36层实际输入/AND抽样帧数均0。该结果支持优先查随机前向与模块组合交互，不能简单判定两套静态权重不兼容。仍是单seed2048目标短测，均值逐级穿过非线性不等于完整随机网络的精确期望，且down的FP32归约与抽样整数归约有差异；尚不能归因某一级噪声或升级完整WT2验收。

S12/FP32前端的8192目标三seed短测暂未显示额外损失，不能升级成完整WT2严格无损。逻辑唯一V统计不是DRAM burst、物理能量或独立样本数。

恢复记录：联合末项因磁盘满退出后沿用原冻结源恢复，已有分块SHA未变；QKVO短测首轮因关闭的控制器仍持有模型导致内存门禁失败，释放引用后完成，前后已有T64结果逐记录相同。失败不计为新成功结果，保留原件SHA。单seed联合结果仍用于诊断，不作为最终质量验收。
