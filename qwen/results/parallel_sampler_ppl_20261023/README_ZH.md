# Qwen新采样器联合PPL：后缀16项完成，完整WT2运行中

2026-10-23更新：2804全部16项完成，原字节sidecar、输入/config SHA、24层每目标覆盖与NLL回算通过。此处是**4096目标后缀PPL**，不能与完整WT2直接比较。三seed为均值±总体标准差，原BF16一个seed。

| 配置 | 后缀PPL |
|---|---:|
| 原BF16 | 10.371557 |
| B4/T32/K32 FFN-only | 10.427377±0.012884 |
| 同FFN＋max4筛选后准确PV | 10.970368±0.017011 |
| 同FFN/筛选＋旧CTMC S128 | 11.197813±0.032905 |
| 同FFN/筛选＋校正拒绝128接受 | 11.164522±0.021928 |
| 同FFN/筛选＋赢家1024更新 | 11.043705±0.026136 |

旧BF16/FFN/CTMC同协议数值复现；新拒绝接近旧CTMC，赢家后缀更低但有8倍更新预算，不能称同成本胜出或完整质量通过。完整2805已按依赖开始，仍待三seed全量确认。局部原件稳定归档`C:/Users/86134/Documents/a_P_BIT/project_archives/qwen_sampler_ppl_issue141_20261023/suffix/`；服务器原件在下述输出根的`suffix/`；逐文件SHA与配置、NLL见SUFFIX_SUMMARY.json。无需重复健康任务。

Issue141 / PR143。执行源码`7a286ec140de6846006c96456275377fd22b4943`。

| 项目 | 实际状态 |
|---|---|
| 准备作业2802 | 缺外部历史校准资产，verify阶段失败，未进入模型评分；原快照/日志保留 |
| 修复后准备2803 | 已成功；两资产原SHA、模型/语料SHA、12组GPU轨迹/分布＋仲裁/cap检查、6个8-target pilot通过 |
| 同轮原BF16完整WT2 | **11.652735047455899，299077目标**，与原冻结参考完全一致 |
| 后缀数组2804_0..15 | 16项均完成并核验；4096目标/配置，原件与SHA留服务器和本地归档 |
| 完整数组2805_0..15 | 依赖已满足并开始运行；299077目标/配置，尚无三seed齐全的新采样器完整汇总 |

六种方案：原BF16（1seed）、FFN-only、筛选后准确PV、旧CTMC128、校正拒绝128接受样本、赢家保持1024更新（后五种各3seed），每协议16项。FFN W8/B4/T32/K32/shared64；筛选max4、64token块、固定8块、旧训练校准。Context2048，完整stride1024/batch32；后缀32段×128目标/batch8。预填充Attention准确、随机FFN启用；每个计分token全部24层按选定Attention执行。

赢家为argmax初始化、偏移max(logit)、burn0/spacing1；拒绝m0..24、总cap128×S、无回退。PLAN中的burn16/spacing4是旧Controller共用字段，仅CTMC使用；新采样器的实际参数以每份结果sampler_detail和源码为准。没有物理RNG、R8阈值量化或训练，不直接把此结果归给最新硬件随机服务。

`preparation/`保存准备门禁原件与SHA。pilot每种只有8个目标，PPL不可用来排序，也不是4096目标后缀或完整WT2。正式结果只接收status=completed并核对sidecar、输入/配置/源码及24层计分覆盖；不同协议的BF16基线分开。

服务器：`/home/Hongjie_Zeng/projects/pbit-qwen-sampler-ppl-20261023-issue141/outputs/7a286ec140de6846006c96456275377fd22b4943/`。
提交回执和恢复说明：`work/rayggxia/141/`。没有新增RTL/PT/PPA，不恢复116/123。
