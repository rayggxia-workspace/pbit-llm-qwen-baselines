# Qwen3-4B：用LLMCompass核对当前TLM为何慢

2026-10-25，Issue186 / PR190；CPU Slurm3052，5/5完成。初轮3047保留在结果目录根，最终版在final/；差异是补齐贪心选词宏、RMSNorm计数4→5。无GPU计时、PPL、RTL或新功耗仿真。**以下时间是生成一个token的模型时延，不是运行模拟器花的时间。** 实际CPU模拟每种配置约18～38秒。

**结论：主流硬件配置确实可以快很多；此前约403ms主要不是Qwen3-4B必须这么慢，而是我们把大模型放在较小的计算和片上带宽配置上，并施加了保守的串行调度。** 换成HBM只解除了一个瓶颈。不能把我们的数字基线与现代GPU的差距归因于随机计算，因为这里首先比较的是未替换的数字模型。

## 1. 实际运行结果

同一模型：Qwen/Qwen3-4B后训练版，36层，D2560/F9728，32Q头/8KV头，head_dim128，词表151936。B1，2K总上下文包含当前token，单token decode；预填充和TTFT不计。包含三个FFN矩阵、Q/K归一化、RoPE、残差、KV更新、最终词表投影和贪心选词。

| 执行配置 | 算子服务时间 ms/token | 加上旧版软件启动代理 ms/token |
|---|---:|---:|
| LLMCompass：官方A100 | 4.162 | 20.989 |
| LLMCompass：小算力＋256GB/s HBM | 177.808 | 177.808 |
| LLMCompass：小算力＋186GB/s HBM | 178.006 | 178.006 |
| 上项：GEMV有效供数≤32GB/s敏感性 | 350.977 | 350.977 |
| LLMCompass：小算力＋双通道DDR4 | 371.383 | 371.383 |
| 我们当前TLM：数字BF16＋HBM | 402.629 | 不含GPU软件启动 |

A100的服务时间为4.162ms；其中原生LLMCompass矩阵和Softmax占4.154ms，新增Qwen向量宏占0.008ms。软件开销另列：原生类别旧版launch共7.257ms，Qwen新增算子的借用launch代理共9.570ms。**这两个时间口径不是置信区间；20.989ms不是A100实测或现代融合内核的准确预测。** 实际CUDA Graph、融合和运行时会改变启动开销。

“小算力”统一配置100MHz、512 MAC/拍、64向量FLOP/拍、8MiB共享SRAM和64GB/s共享接口。两者只能称名义资源匹配：LLMCompass仍采用自己的局部阵列/映射，普通Softmax在向量核上执行。外存用带宽模型，未调用DRAMSys。

## 2. 模拟器真正运行了什么

固定[LLMCompass官方源码](https://github.com/PrincetonUniversity/LLMCompass/tree/2e015fd2ee750e6cad8d7152df52551e5b41ef20)，适配源码执行3b06f29595e2d58fc92a701666236d8f83955c6e。**上游源码未改动。** 直接调用Matmul.compile_and_simulate与Softmax.compile_and_simulate；不是把我们自写的roofline改名为LLMCompass。

- **单token投影**：上游M=1原生快捷分支，返回max(计算时间,外存时间)，不进入tile搜索，且忽略L2带宽限制。我们用5项测试复核这一行为。
- **动态QK/PV**：每个KV组做M=4的原生tile映射，八组顺序执行；四个query头共享同一个K/V，不复制成32份KV。两者确实执行了原生mapping/SCALE-Sim缓存路径；部分阵列成本仍由上游利用率公式给出，不是全程逐拍。
- **Softmax**：上游tile搜索与在线归约模型，原生执行。
- **RMSNorm、RoPE、SwiGLU、残差及选词等**：官方旧Transformer没有这些完整Qwen边界，我们补透明的操作数/带宽宏，并单列服务时间。不是已标定RTL。
- **数据类型**：官方FP16作BF16的两字节性能代理，无实际数值推理。上游局部部分和通常按2B，而我们的PV/若干输出为FP32；此差异保留说明，不冒称完全同构。

完整图中矩阵MAC=4,626,251,776/token，与当前TLM逐项总数一致；不是套用官方GPT两矩阵GELU模板。模型配置及revision/SHA、执行源码、输出和缓存SHA在results/llmcompass_20261025/final/。权重和语料版本不适用：本次是形状/事务时延，无新质量结论。

## 3. 最大差异是资源与片上通路

| 资源 | 当前小型ASIC模型 | LLMCompass内置A100 |
|---|---:|---:|
| 核心频率 | 100MHz | 1.41GHz |
| 本轮GEMV计算吞吐 | 51.2GMAC/s | 38,983.68GMAC/s（原生向量模型） |
| 外存带宽 | HBM理论256GB/s；连续读微基准约186GB/s | 2039GB/s |
| 片上共享接口 | 64GB/s，读写共用 | L2接口7219.2GB/s |
| 共享容量 | 8MiB | 40MiB |

容量、吞吐和接口同时不同，不能只归因于工艺或时钟。A100列是官方性能模型参数，不是我们新测出的GPU指标。

当前每token需8.347GB外存流量、16.705GB共享SRAM读写。仅MAC理想下界90.356ms；仅SRAM裸传输下界261.020ms。忙碌时间可能重叠，不能把这两个下界直接相加。

最重的是稠密权重8.044544GB经过“写入共享SRAM→读到本地操作数单元”两次，64GB/s接口仅这两步就需251.392ms。LLMCompass的M1快捷分支没有这条路径，因此原生小配置约178ms显得过于乐观。我们另加“权重有效吞吐≤64/2=32GB/s”的敏感性情景，结果约351ms；代码只把GEMV的有效io.bandwidth限制为32GB/s，这是供数敏感性情景；**没有模拟相同共享总线竞争、bank、端口或双缓冲，也不是403ms可以直接降到351ms的证明**。

## 4. 逐算子对比，避免把所有差额叫调度收益

| 部分（全部36层汇总） | 官方A100 ms | 小配置原生 ms | 补SRAM限制 ms | 我们TLM ms |
|---|---:|---:|---:|---:|
| Q/K/V投影 | 0.556 | 11.059 | 35.421 | 48.971 |
| O投影 | 0.371 | 7.373 | 23.608 | 32.502 |
| FFN两个入口矩阵 | 1.760 | 35.021 | 112.122 | 155.033 |
| FFN输出矩阵 | 0.880 | 17.510 | 56.061 | 77.682 |
| 词表投影及选词 | 0.382 | 7.621 | 24.343 | 34.046 |
| QK＋Softmax＋PV | 0.206 | 98.152 | 98.152 | 53.533 |

当前TLM在每个矩阵tile依次做共享SRAM填充、读取、MAC、输出；下一DMA可覆盖当前计算，但下一共享SRAM填充要等前tile退休。仅密集权重搬运251.392ms＋密集MAC78.560ms约329.952ms，还没算启动、格式转换和Attention。因此有明确的重叠优化空间，不能称已经充分流水。

与此同时，LLMCompass小配置的QK/PV约55ms、Softmax约43ms；它的小型脉动阵列利用率及向量exp模型与我们专用512MAC/拍、16路非线性宏不同。这里Softmax每元素使用上游3×35+7=112 FLOP：6.4GFLOP/s下光算术就41.288ms，加tile/IO后42.795ms。35是A100向量exp代理外推，不能称小ASIC必须的代价。当前TLM的专用宏给出Attention核心约53.5ms，也没有因此得到RTL时序验证。**351与403ms的净差不是纯调度差，也不能作为可兑现的节省。** 应优先对照密集投影的相同搬运路径，再隔离注意力算子实现。

## 5. 下一步应如何修正比较

1. 先建立明确的数字参考硬件档位，分别给“小资源55nm探索”和“较高性能目标”；概率方案与数字方案共享同档资源及存储路径。
2. 对密集投影实现真正的分块重叠：下一块共享SRAM填充、当前块本地供数与计算、上一块输出由独立资源/端口排程；检查缓冲容量、回压和带宽守恒。不能只把阶段相加改成max而不写依赖。
3. 对比两种成熟通路：DRAM→共享SRAM→本地，与可行的DRAM→双缓冲本地直达；后者必须计本地存储/接口，不能把数据搬运免费删除。
4. Attention另对照向量Softmax、专用非线性宏、分组/融合内核，避免拿不同算子内部实现的差异解释成调度。

如果保留当前BF16流量，要达到20ms/token，理想下界要求至少231.3GMAC/s、417.4GB/s有效外存，以及835.3GB/s当前路径的共享SRAM读写能力。实际还要留利用率、依赖和延迟余量；这不是已验证硬件设计。随机W8方案流量和算力不同，必须另列，不沿用此数字作为其需求。

## 6. 复现与限制

运行入口probes/llmcompass/qwen_decode.py；冻结与提交work/jieruiz/186/submit_compass.py，CPU Slurm脚本compass_run.sh；结果收集collect_compass.py，生成本文report_compass.py。先按compass_bootstrap.sh准备固定上游与scalesim2.0.2，复用已有Python/PyTorch环境，不需要GPU。上游lookup缓存仅写在每配置独立scratch中，136个原始文件SHA仍一致。

最终5配置各5项合同测试全部通过；真实QK/PV/Softmax mapping均非空，结果清单completed且源码/模型配置/结果SHA核验。上游Pandas缓存出现PerformanceWarning，原stderr保留；没有异常退出。初轮和最终源快照、结果均未覆盖。数字电路台账不新增run：这里没有新电路仿真。

参考：[LLMCompass论文](https://arxiv.org/html/2312.03134)、[官方自建算子图说明](https://github.com/PrincetonUniversity/LLMCompass/blob/2e015fd2ee750e6cad8d7152df52551e5b41ef20/docs/run.md)、[GEMV与tile实现](https://github.com/PrincetonUniversity/LLMCompass/blob/2e015fd2ee750e6cad8d7152df52551e5b41ef20/software_model/matmul.py)、[官方A100参数](https://github.com/PrincetonUniversity/LLMCompass/blob/2e015fd2ee750e6cad8d7152df52551e5b41ef20/hardware_model/compute_module.py)。论文的既有验证误差不自动适用于本次Qwen适配或55nm模型。
