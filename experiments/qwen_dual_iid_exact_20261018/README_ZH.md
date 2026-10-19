# Qwen2.5-0.5B双随机IID：精确分布短片段核查

任务：Issue #30。只验证数值，不训练，不跑RTL/PT，不把软件运行速度当ASIC速度。物理随机源没有回放到本实验；模拟的是没有挑选种子或特定序列的理想IID分布。

## 实验范围

先核验模型、tokenizer、完整WT2 train/test、token、原校准和冻结源码的SHA-256，重跑**未改变的BF16完整WT2滑窗PPL**。协议为context2048、stride1024、299077计分token；预期PPL11.652735，超过绝对0.02差异即停止后续比较。该容差为环境差异检查阈值，不是数值等价证明。

随后对同一WT2 test前128token（127计分token）依次运行：

| 方案 | T | seed | 说明 |
|---|---|---|---|
| 原BF16短参考 | — | 0 | 与全部短测同一段 |
| 双随机＋精确条件Binomial | 64/128/256/1024/4096 | 0/1/2 | 精确有限T分布，压缩时间顺序 |
| 双随机＋条件Gaussian | 同上 | 同上 | 对应旧完整PPL的近似，不写成精确结果 |
| 固定W＋精确输入计数 | 同上 | 同上 | 只改变权重是否随机的匹配对照 |

共47个输出：1个BF16完整参考、1个BF16短参考、45个短片段随机配置。随机结果**不是完整WT2 PPL**，用于低T性能风险及精确采样运行时间检查，不直接外推全量质量。seed0/1/2事先写定，仅用于重复实验，不按结果筛选。

全部24层FFN替换；Attention、RMSNorm、残差、embedding、lm_head保持原BF16路径。FFN：`x幅度采样 → gate/up → 准确FP32 SiLU(g)*u → 固定Sz重编码采样 → down`。没有普通OR、互斥重映射、特殊序列或训练。

## 编码和“精确”的含义

- W为每64×64块对称INT8；双随机权重概率`abs(code)/127`，恢复幅度`127*tile_LSB`。仍沿用旧版本，并未改成0…255直接比较权重阈值。
- A8是8位幅度概率`q/256`加独立符号；使用冻结的每64通道Sx、Sz。Sz来自8192个训练token校准，不用测试集更新；该Sz最初按A12路径校准，A8实验复用原字节以便对照。
- 同64输入通道每拍共享随机字；不同token/组/层/阶段独立；同一输入沿输出方向广播，gate/up共用输入计数。权重每连接独立，且与输入独立。
- 输入联合计数严格保留共享阈值嵌套与协方差。给定输入流C次为1，一条连接的AND事件数为`Binomial(C,abs(code)/127)`，逐连接精确抽样后恢复符号与尺度、准确求和。阶段内线性，无须展开每拍顺序。
- Gaussian后端仅保留条件均值/方差；尤其低T不能默认与精确分布相同。两个后端使用相同seed编号，并不表示每个随机事件相同或逐样本耦合。
- “精确”指所声明理想IID统计模型；没有模拟物理源偏置/自相关、计数溢出、截断电路或物理数据回放。

## 文件

- `vendor/frozen/`：8个历史源码，保持原始归档字节；两份校准原始数据保留在既有服务器个人存储，公开仓库仅有索引与SHA；`.gitattributes`禁止Git换行转换。
- `frozen_manifest.json`：运行时冻结源码/校准的10文件大小及SHA-256；其中2份校准不随公开Git分发。
- `expected_identity.json`：2026-10-18在服务器实际重新hash的模型、tokenizer、train/test身份，共9文件。不是从本地不完整WT2副本生成。
- `verify.py`：输入身份和8192训练前缀、完整test token校验；记录全部执行源码hash。
- `run.py`：完整BF16门禁、47配置短测、逐配置独立进程、汇总。不得覆盖已有输出。
- `run.sbatch`：1张5090、4CPU、16GiB、2小时上限；不设置CUDA_VISIBLE_DEVICES。

`test_shared.py`验证共享阈值的联合分布、解析协方差和独立组；`test_sz.py`验证符号/尺度恢复、无采样极限和小事件精确二项均值/方差。两者在完整基线前执行。脚本未创建临时checkpoint；若未来需要TemporaryDirectory，必须显式使用个人项目内目录。

## 远程执行

由根任务发布代码commit后，将Git归档放入个人项目的不可变snapshot。模型/data只读符号链接复用`/home/Hongjie_Zeng/pbit_llm`，不复制模型。执行输出放在snapshot之外，且必须在已验证个人项目内。

```bash
export PBIT_PROJECT_ROOT=/home/Hongjie_Zeng/projects/pbit-qwen-dual-iid-exact-20261018-issue30
export PBIT_CODE_COMMIT=<40位执行源码commit>
export PBIT_SNAPSHOT="$PBIT_PROJECT_ROOT/snapshots/$PBIT_CODE_COMMIT/experiments/qwen_dual_iid_exact_20261018"
sbatch --export=ALL --output="$PBIT_PROJECT_ROOT/logs/slurm-%j.log" "$PBIT_SNAPSHOT/run.sbatch"
```

`models/Qwen2.5-0.5B`与`data/wikitext-2`须预先建好只读复用链接；`logs/`需预先存在。每配置子进程重载小模型，防止历史模块全局factory污染；最多一张GPU连续执行。历史同片段精确T4096约20.6秒，整批时间应以本次日志为准；未启动几十个完整随机WT2配置。

结果在`outputs/<commit>/`：`identity.json`、`suite.json`、`runs/*.json`、`summary.json`、`RESULTS_ZH.md`。逐结果包含实际环境/作业号、命令、代码commit、模型及输入identity hash、配置和源码hash、计分协议、计分token、精度、采样、诊断和峰值显存；汇总包含每个结果SHA-256。NLL按目标token总和计分，不平均窗口PPL。

当前是否已运行、作业ID、实际结果和发布状态以Issue #30、个人STATUS及HANDOFF为准，不以本说明的计划当完成证据。

## 公开交付与私有执行快照

自动审批拒绝包含大份冻结校准原始数据的公开推送，因此本分支从集成基线重新建立，不包含原执行分支的提交历史或两份原始校准JSON。公开的算法源码与实际执行代码逐SHA对应；数据索引见CALIBRATION_ARTIFACTS.json。两份文件均为模型算法校准数据，不是工艺库；本次仍保留在已有授权服务器，不假定可公开。

复现时须取得这两份校验匹配的授权原件，放入vendor/frozen/results/对应位置，再冻结个人执行快照；没有这些文件时verify明确失败，不会偷偷下载或重校准。请勿将原件加入公开Git。运行快照ad14096615054a7ef0a72e43f670863e4a205b11只在本地及服务器保存，公开交付分支的Git SHA与其不同；结果保存原执行SHA、源码/校准hash和位置，不能将公开提交冒称原运行提交。
