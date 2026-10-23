# Qwen3-4B 后训练版 SparQ 基线（Issue157）

本任务入口是 `python -m qwen3.sparq.run`。用户已明确选择 **Qwen/Qwen3-4B 后训练版**，固定 revision `1cfa9a7208912126459214e8b04321603b3df60c`；另建原 BF16 对照，不能沿用 PR147 的 Qwen3-4B-Base 数值。

默认配置为论文版 GQA：r32、总候选128、最近32（含当前 token），无均值补偿，组内概率求和。这里已替换整个旧筛选路径：不计算 max4 摘要、不加载小网络权重、不叠加 Bernoulli 选块和固定八块修复。选出候选后使用准确 QK/softmax/PV，原 FFN 保持完整。`SparQ + sampled attention` 和 `SparQ + B4/T32 FFN` 应作为另列实验；不能将纯 SparQ 的结果称为联合方案结果。

## 原方案核对与替换范围

| 已核对入口 | 既有行为 | 本任务处理 |
|---|---|---|
| PR147，`qwen3/stochastic/` | Qwen3 Base、max4、64-token块、8块预算；准确或新随机采样器；原/分层FFN | 只复用原生 QK-Norm/RoPE/cache 适配及覆盖规划；新模型入口使用 SparQ，不重跑原26项后缀 |
| Issue92，`experiments/pbit_gate_pilot_20261022/network.py` | Qwen2.5-0.5B局部教师；4→8→1、每层49参数、独立隐藏 Bernoulli | 不将该局部训练结论冒充 Qwen3 全模型验证；新基线不加载其权重 |
| `architecture_tlm` 旧 max4/预算修复成本 | 原块筛选与随机采样事务 | 新费用在 `architecture_tlm/sparq_baseline/`，不叠加旧selector单价 |

旧实验及其配置保留用于历史复现；本目录是后续 SparQ 配对实验入口。原 PR147 待审，当前任务 PR 堆叠在 `task/144-qwen3-stochastic@357db588`，不是声称已合入集成分支。

## 正确性约定

详见 [论文与官方代码审计](SOURCE_AUDIT_ZH.md)及 [冻结来源](SOURCES.json)。官方 `2024-05-sparq@554ea6db` 使用 logits 求和、历史 k 加当前 token；论文 v6 的 GQA 为 softmax 概率求和。本任务将两种变体明确区分，官方原源码只作为独立 oracle；主配置采用论文口径。

Qwen3 的32Q/8KV、head_dim128、hidden2560不能用 hidden/heads 推导投影维度。全部36层遵循 QK-Norm→RoPE→cache→SparQ→原输出投影。短缓存全部候选时走 dense；零通道覆盖按整个KV组退回 dense。r=d 不代表 k<N 时恢复完整注意力。

核心是 FP32 算术、BF16输入输出的数值参考。它仍会完整转换/物化KV及执行PyTorch选择算子，**没有实现稀疏HBM kernel**。正式评测显式关闭全KV有限值扫描；真实模型小样本先要求开/关扫描的 logits SHA 完全一致。关闭检查不改变选取或算术，仍检查所有结果NLL有限。原生 BF16 对照与 FP32 SparQ 的精度边界分别记录。

## 完整评测协议

- WT2 raw test，UTF-8原字节、无BOS、window2048/stride1024。额外运行未修改BF16向量化锚点；因BF16形状差异，主要因果对照为**同缓存、同batch、同分段的原生dense与SparQ**。
- 每个被计分预测器都以q_len=1经过全部层；dense prefill只包含其之前的token。逐window的目标位置严格覆盖1..N−1一次。PPL每32窗保存，batch32；最后不足32窗按实际计数处理，正式前核batch32峰显存低于28GiB。
- 官方 `lm_eval==0.4.8` 零样本 likelihood：PIQA validation1838、ARC-Easy test2376、HellaSwag validation10042；每模式14256题。保留官方提示、token边界、acc与acc_norm；不用chat template，不进行thinking生成。
- 各选项有独立cache，第一答案token也经过替换。共享第一预测器的复用次数显式记录；不填dummy、不静默截断。每256题保存连续分片；片内按完全相同提示长度分组，最多8题/32个真实选项，保持每题独立cache和原ID输出顺序；只有按原ID核验全部分片后才写完整结果。
- 任务数据助手复用 PR149/Issue145 的官方任务实现，来源 blob `406c1ce07ddc27cf8f0249e6f6f1b9c217728b8a`；本任务扩展为HellaSwag全10042题，不复用旧1000题准确率。

每片结果、源SHA、revision、任务/语料SHA、环境和job均记录。结果和内嵌摘要一次原子写入；未提交 `.tmp` 不参与恢复。更换执行源/配置/模型/输入后不能沿用旧结果目录。每个部分始终区分片段完成与全协议完成。

## 验证与运行

本地 CPU 无 CUDA：

```bash
python -B -m unittest qwen3.sparq.test_core qwen3.sparq.test_scoring qwen3.sparq.test_run architecture_tlm.sparq_baseline.test_ledger
```

服务器使用个人独立环境 `env-v2`，Torch2.7.1+cu128、Transformers4.51.3、lm_eval0.4.8。准备环境/模型只在CPU Slurm中进行，GPU最多1张。实际准备/测试/运行状态以 `work/amlink1219/157/HANDOFF.md`、原始日志及JSON为准。

原生CPU门禁作业2872已通过45项、无跳过、CUDA未初始化；其冻结源码为cdb1a73。后续新增诊断向量累计测试与GPU基准测试单独记录，最终执行快照将重新验证全部门禁。尚未写出完整PPL/任务结果时不得把实现测试当模型质量结论。

## 速度、能耗与面积

GPU基准分别记录prefill/decode、上下文、固定输入、重复轮次及分配GPU UUID。它测Python参考实现的实际耗时。NVML仅访问分配设备；长窗口可给板级遥测积分估计，短于传感器平均窗口的数据保持null。GPU板级功率不代表ASIC功率，更不能与条件周期混算能效。

硬件账本覆盖选择器、两级softmax、GQA共享K/V读取、双K布局额外容量/构建/追加写。读量下降不等于速度或面积下降。完整SparQ RTL顶层、库表征和STA/PPA尚缺，因此物理面积、功率、能量保持null。

文献后台收录状态：SparQ已有去重后的待导入任务和PDF，当前Zotero API未开启；本轮读论文/代码不等于已成功收录，保留可恢复待办，不打开用户窗口。

当前真实模型门禁：GPU2874通过；新批处理正式前另行运行51项CPU及真实BF16批形状门禁。同一形状native/dense要求逐bit相同；serial/batched预声明每目标平均logprob差不超过.02 nats，并报告所有预测/指标翻转。不能把串行基线数值与批处理候选混比。
