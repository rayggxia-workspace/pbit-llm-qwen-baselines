# 完整 FFN 静态规模与局部墙时评估

本报告对应 `da24266` 的 host-order B4/T32/K32、64×64 tile、8 engines、8 weight slots、原 W8 二补码 bitplane 和 native LFSR 协议。后续 `93c26d9` 增加显式恢复 profile，默认行为不变。**没有运行完整 896→4864→896，不能承诺 event 模式在 20 分钟内结束，也没有完整层的数值、质量或性能结果。**

## 完整形状的解析计数

输入 D=896（14 个组）、中间 F=4864（76 个组）、输出 O=896（14 个行 tile），均无尾 tile。

| 项目 | 解析值 |
|---|---:|
| gate/up tiles | 2×14×76 = 2128 |
| down tiles | 76×14 = 1064 |
| 总 tiles | 3192 |
| x waves | 14×ceil(152/8) = 266 |
| z waves | 76×ceil(14/8) = 152 |
| 总 waves | 418 |
| 原生随机 frames（含 RESTORE 后重放） | 418×32 = 13376 |
| 不同 x/z group 门限轨迹 | 90×32 = 2880 words |
| partial reads | 2×76×13 + 14×75 = 3026 |
| 所有静态/动态 Operation | 210432 |
| SC tile sample frames | 3192×32 = 102144 |
| W8 输入 trials | 418381824 |
| 活跃 trial 全部展开 8 个平面的循环上界 | 3347054592 |
| restore counter reads / rail subtraction | 13074432 / 6537216 |
| restore plane-tree integer adds | 5720064 |
| 每类 bin scaling / ordered-bin add | 817152 |
| cross-tile FP32 adds | 204288 |

Operation 总数可复核为：`52*tiles + partial_reads + (3*T+2)*waves + 5*groups + 8`。52 包括本 tile 的权重/scale 搬运、32 次采样、显式恢复树与各档阶段、partial 写和释放；native 每步是 submit/delivery/frontend 3 项，每 wave 另有 SAVE 或 RESTORE 的 2 项；每 group 的 RELEASE 命令和 read/encode/release 共 5 项。该式与下列四个成功探针的实际 `len(kernel.operations)` 全部一致。其他配置、profile 动作名称或算法改动必须重新计数，不能机械沿用。

## 容量与地址

完整矩阵的 W8 payload 为 **13074432 B（12.46875 MiB）**；3192 个 FP32 scale 为 **12768 B**。这些是整个层的 backing payload，不是驻留阵列容量。

本地默认容量合计 **155936 B**：W8 32768、scale 32、counter 49152、raw/encoded 256、g/u/z/down/residual 65536、restore scratch 8192。完整形状的 `(3F+2O)*4=65536` 正好填满 partial 配额，无余量。RNG 内部状态、控制、接口寄存器和全局 backing 的容量不在该合计中，不能把它当作整个芯片 SRAM/PPA。

实际 backing SRAM 使用的张量、8 个复用 weight slot、scale 与输出地址对应至少 103712 个不同数据字节；backing DRAM 至少容纳 W8+scale 的 13087200 个不同数据字节。地址空间采用各张量/矩阵独立固定基址，本形状无重叠。当前实现并不执行全局 backing 容量分配，因此这些是数据量核算，不是容量验证。

主机 Python 还保留 fixture、量化副本、稀疏逐字节 memory dict、所有 Operation、memory read payload、trace、thresholds 和审计回执。主机内存显著大于硬件数据量。局部实测不能证明完整层的峰值；20 GiB allocation 是合理的实验上限候选，但不能称已经验证足够。当前首先暴露的是墙时和图扫描成本。

## 本机成功的局部探针

测量平台：Windows 11、CPython 3.13.3、Intel64 Family 6 Model 183 Stepping 1。每个 case 为新 Python 子进程、一次 event 运行、默认 native source；输入和 W8 由固定公式产生，**不是 Qwen 数据**。没有重复次数或置信区间。原始 JSON 保留在同目录。

| D→F→O | tiles | 实际 ops | event run 秒 | trace events | steps | 峰值 working set B |
|---|---:|---:|---:|---:|---:|---:|
| 64→64→64 | 3 | 370 | 0.576423 | 1390 | 837 | 33619968 |
| 896→64→64 | 29 | 3087 | 5.873015 | 11947 | 6625 | 59260928 |
| 64→512→64 | 24 | 2288 | 6.097535 | 9333 | 4538 | 54644736 |
| 64→1024→64 | 48 | 4564 | 17.843630 | 18617 | 9055 | 78389248 |

`run 秒` 不含 fixture 构造和初始 build，二者分别保留在 JSON 中。FFN 的后续 group 是 run 期间动态建图，因此其构图成本已包含在 run 时间。

另运行 `1→4864→1`，保留 gate/up 的完整 152 行 tile fanout，并大幅减少数值 trial。该探针在 **120 秒子进程上限**内未完成，已终止，未生成完整 result；预期若完成为 228 tiles / 21634 ops。见 `ffn_probe_1_4864_1_timeout.json`。这不是完整层超时，也不是完成结果，不能从它推算完整层准确时长。

## 20 分钟判断及后续条件

仅按已完成局部的每 tile 时间线性放大，完整层会得到约 **10.2–19.8 分钟**。这只是偏乐观的算术外推，不是预测区间：48 tile 的每 tile 时间已比 24 tile 明显增加；完整 fanout 的轻算术探针也未在 120 秒内结束。内核目前逐沿扫描 pending Operation，内存顺序判定还遍历历史 Operation，图增长会增加调度成本。

因此不能以“预计十几分钟”为依据直接启动一个必须 20 分钟完成的完整层实验。若另有更长 CPU allocation，应设置明确墙时上限、记录超时和中间进展，优先 event 单模式；cycle 模式和完整数值 oracle 另有额外成本。若优化 pending/hazard 索引，须先通过现有周期/事件、RAW/WAR/WAW、CDC、输出反压和独立审查，不能为赶时限改计数、剪掉真实数据维度或把解析估计写成完整实测。

复现示例：

```text
python -X utf8 work/amlink1219/116/ffn_scale_probe.py --d 64 --f 1024 --o 64 --out probe.json
```

该脚本无模型权重、无远程操作；只用于软件仿真器扩展性诊断，不能作为硬件吞吐或端到端模型速度。
