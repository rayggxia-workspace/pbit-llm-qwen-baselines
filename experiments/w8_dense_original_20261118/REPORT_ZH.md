# 原始W8 dense完整WikiText-2 PPL

2026-11-18 UTC，Issue259，负责人rayggxia。Slurm CPU5896预检通过；GPU5897为COMPLETED/0:0，单RTX5090，执行时长1分54秒。

| 配置 | 完整WT2 PPL | 相对同轮BF16 |
|---|---:|---:|
| 原始Qwen3-4B BF16，稠密Attention | 11.5371603731 | 参考 |
| 原始Qwen3-4B W8 FFN，稠密Attention | **11.4832106452** | **-0.467617%** |

W8权重量化在该完整WT2测试上保持了原始模型的PPL水平。本项没有训练，不使用任何训练后T64/Attention检查点。

## 配置与计分

- 模型：后训练版Qwen/Qwen3-4B，revision `1cfa9a7208912126459214e8b04321603b3df60c`，36层。
- 仅FFN的gate/up/down共108个矩阵量化；其余权重为原始BF16。每64×64权重块一个离线固定二次幂LSB，覆盖块最大幅值；最近偶数舍入，signed W8码[-127,127]。不是预训练后再学习尺度，不使用激活统计或测试集拟合。
- 激活、原始SiLU及逐元素乘法保留BF16；Attention为原生稠密BF16 SDPA，没有K筛选、PV采样或Ising采样。
- 量化权重被精确解码为BF16容器进行软件质量评测；本项是W8权重量化控制，不是P8激活或逐拍固定点MAC的RTL数值重放。
- WT2 raw test，window2048/stride1024，292窗，299077个不重复目标，不套聊天/thinking模板。
- 原始BF16先在同一GPU进程重跑，随后原位量化FFN权重，保持所有非FFN参数不变。

## 实际验证

CPU预检：量化器与已有PoT64初始化一致；符号、全零块、最近偶数舍入与独立标量二次幂算术一致；W8解码值可被BF16精确表示；所有299077目标连续且恰好计分一次。

GPU预检：相同合成BF16输入上，CPU与CUDA的整数码、尺度指数、解码权重逐位一致。两轮完整评测中36层均覆盖292窗/597062个前传token，后者包含滑窗重叠，不等同独立计分目标。

归档核验：两轮WINDOWS的292条记录连续覆盖、NLL求和与最终RESULT一致；PROTOCOL、两份RESULT/WINDOWS以及108矩阵的量化统计均与COMPLETE中SHA一致。各矩阵记录原始BF16权重、INT8码、INT8指数及BF16解码权重SHA。模型文件、原始文本、token序列和执行源码的SHA保存在协议/执行索引中。

BF16 PPL与此前同环境11.5371603731完全一致。历史8.742652来自训练后的T64检查点，不应填写为本项original W8 dense结果。

## 文件与位置

- `RESULTS.json`：机器可读结果、逐文件SHA和本地归档位置。
- `SUBMISSION.json`：CPU/GPU作业号、完整提交命令、不可变执行目录和源码SHA。
- `runner.py`、`PLAN.json`：本项量化和评测代码、配置。
- `wt2_reference.py`、`pot64_reference.py`：从已签SHA的既有冻结运行包复制的原始评测器和尺度参考，字节不改。
- 服务器原件：`/home/Hongjie_Zeng/projects/pbit-w8-dense-original-issue259-20261118/run_d20328393f5f/`。
- 本地唯一原件归档：`project_archives/w8_dense_original259_20261118/d20328393f5f-results.zip`，具体SHA见RESULTS.json。

没有修改论文正文、TLM默认、其他成员任务或旧执行快照。
