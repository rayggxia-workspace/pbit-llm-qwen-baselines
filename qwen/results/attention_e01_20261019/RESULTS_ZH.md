# Attention E0/E1 实际结果（2026-10-19）

负责人 `amlink1219`；[Issue35](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/35)。本轮已在本人Slurm服务器完成原BF16参考、真实Attention捕获、12项pilot和465项有限微基准。**尚未证明物理p-bit的面积、能耗或速度优势。**

## 本次完成范围

| 阶段 | Slurm | 实际结果 |
|---|---|---|
| 首次预检 | 2159 | FAILED/1:0：输入SHA通过，测试config漏入归档，未开始模型推理；原快照保留 |
| CPU修正预检 | 2160 | COMPLETED/0:0；8输入文件SHA匹配，39/39测试通过 |
| BF16与捕获 | 2161 | COMPLETED/0:0；完整WT2 PPL **11.652735047455899**，299077计分目标；捕获前后完整模型logits逐bit相同 |
| 微基准pilot | 2162 | COMPLETED/0:0；12/12，无错误/超时 |
| 正式微基准 | 2163 | COMPLETED/0:0；465/465，无错误/超时 |

执行源 `879050031ac1cc7757e3b7f54e19c25dc40faf72`；默认window2048/stride1024、seed0、Qwen2.5-0.5B Base、原BF16 FFN/SDPA。tokenizer为本人旧项目中保存的**原始upstream字节版本**，与近期save_pretrained快照分别登记；权重和raw test相同，完整token序列299078及int64 SHA也匹配原协议。模型revision、每文件SHA、环境/配置/命令及各制品SHA见[原始记录](raw/COLLECTION_MANIFEST.json)与[源清单](raw/execution_source_manifest.json)。

## 数字参考的数值结果

60项数值对照含3个M×5个profile×4种方法；数学参考为相同logits上的稳定FP64 Softmax。FP32稳定Softmax最大TV为 **2.65216e-07**；64段exp2 PWL数值模型最大TV **2.49565e-06**；FP32归一化后BF16概率RNE cast最大TV **0.00090263**。BF16输出不再偷偷重归一化。online FP32 PV最大NMSE **1.89191e-12**，含running-max改变时的重缩放。

这些是软件数值准确度。PWL没有固定完整有限字长、RTL流水线、资源共享、库/工艺或功耗测量；不能由其Python耗时推断数字电路成本。online方法输出最终V，不强制物化概率向量，三种输出契约分别列账。

## 同预算采样：M2048、S128

以下是相同logits/V下最终V向量的 **NMSE（三种子均值±样本标准差）**，越小越好；不是模型PPL，也不是准确率下降百分点。

| 固定真实输入行 | 数字IID | 数字systematic（单随机相位） | 串行Ising参考 |
|---|---|---|---|
| layer0/head0 | 1.845% ± 1.206% | 0.139% ± 0.088% | 0.977% ± 0.473% |
| layer12/head13 | 2.489% ± 0.328% | 0.827% ± 0.258% | 3.016% ± 0.918% |
| layer23/head13 | 10.040% ± 2.378% | 5.171% ± 1.627% | 12.644% ± 3.695% |

在这三个预选输入上，systematic均值均低于当前串行Ising参考，支持将其作为后续硬件对照。样本量和输入覆盖有限，不能推广成所有Attention头、语料或物理Ising架构的普遍排序，也不能宣称三seed均值差已证明统计显著。Ising相对IID在不同输入上有好有坏；没有统一精度优势。

本轮Ising为既有**离散串行随机扫描、硬抑制heat-bath参考**，burn16 sweeps、spacing4 sweeps；M2048/S128实际账本为 **1,080,816次逻辑尝试更新**。几何事件压缩只节省软件空更新；上述次数不是硬件周期，也不等于1,080,816个独立样本。未以理想IID宏替代有限Ising；没有物理随机源比特流回放。原生异步类别器件仍需独立器件模型及混合验证。

## 覆盖与限制

- M64/512/2048、S32/128/512、seed0/1/2。135项数字IID、135项systematic、135项串行Ising；另60项数值参考。逐项指标及索引数组的服务器位置/SHA见raw中的case日志与stage_summary。
- 真实输入只来自test起点0、2048token **prefill的最后query**，三个层/头为0/0、12/13、23/13；不是KV-cache decode计时，不代表全部模型。小M取对应候选前缀后重新归一化；不是实际QK筛选器质量。另uniform/peaked为合成logits诊断，V沿用相同源行。
- S最大512，低于预设ESS诊断最小1024；因此本轮ESS为insufficient_samples，不能宣称已充分混合或独立。uniform经验TV的支持集下限单列；短S直方图不能当完整概率精确实现。
- 未替换整模型Attention，未做随机方案全WT2、概率QK筛选调参、RTL/DC/PT、TLM、器件/电路PPA或能量实测。
- 原始attention_rows.npz和每case数组继续留本人服务器，Git只保存小型汇总、记录和SHA。回收归档SHA及逐文件检查已通过；477项是12pilot+465full，不是Issue33全部623行计划完成。

后续应先扩展真实输入覆盖及长链诊断，再对满足相同输出误差目标的数字/原生方案进行同资源RTL或器件级PPA比较。当前结果支持数字systematic作为必要强对照，尚不足以判断物理p-bit模块最终是否划算。

## 交付状态

本地已提交代码并完成服务器实验，GitHub账号amlink1219对正式workspace仍push=false，任务分支未上传、PR未创建。Issue35实际结果已同步并回读，保持open；Projects本次查询返回INSUFFICIENT_SCOPES（缺read:project），待权限同步。不使用其他账号或历史个人仓库替代。实际远端与交接见[HANDOFF](../../../work/amlink1219/35/HANDOFF.md)。
