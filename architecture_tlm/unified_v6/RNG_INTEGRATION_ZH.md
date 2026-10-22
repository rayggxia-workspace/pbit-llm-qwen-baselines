# 随机服务真正接入整机TLM（Issue96，2026-10-22）

本版将默认`FullDecode`从足量本地源接口切换为Issue95的实际有限端点协议。`random.backend=integrated_service`为新默认；旧`local_prng_interface`仍可显式选择，旧52项结果与原始执行源不改。此前PR103“小接口连通、未接入整机”的结论是旧36d5e108时点，不能套到本版。

用户要求统一时钟：**计算核、SC采样消费、随机服务、种子总线和采样器均为100MHz/10ns**。构造时不一致直接报错；命令行以计算核时钟统一源配置并将最终配置保存。SRAM继续80MHz，这是已知SS宏最小周期约束，不把它强改为100MHz；已有20ns跨域代理保留。

## 实际连接

`FullDecode → IntegratedRandomService → EventNetwork → Issue95 Endpoint/SeedIngress/SeedWords`。

| 消费者 | 真正执行的源 | 消费方式 |
|---|---|---|
| FFN | 一个本地LFSR32端点，每请求生成一个8bit字 | K32时取3bit层内抖动，与5bit分层计数拼为R8，同64个输入共享；固定W8不另造权重随机源 |
| QK块筛选 | 本地Bivium端点池 | 沿用max4/自由块归一化，经过q/256响应；强制块q=256，响应实际决定候选，固定预算修复仍显式收费 |
| 准确Softmax后PV | 独立公平Bivium端点 | 一个160bit原生帧取32bit systematic偏移，剩余128bit仍生成并统计，不存S个随机字 |
| 赢家保持/校正拒绝 | 同一个Attention端点池＋独立公平端点 | 全候选一次提议；每端点20个8bit字，只启用所需端点，最后不足20路的余量照算；公平位不与候选字复用 |

GF64后端仍保留在原随机架构中，但本版不默认用它代替Attention独立候选响应。其两两秩性质不证明全候选联合分布。Bivium本身也不是经认证IID或物理熵。

2K Qwen的筛选同KV组7个Q头×32块=224路，`screen_exact/screen_pv`端点池为12个Bivium；若再使用赢家/拒绝采样器，其最多512候选，端点池扩大为26个Bivium。8K筛选需要896路，配置45个Bivium。实际查询用多少就启用对应前缀端点；多余已实例化端点保留时钟/idle成本。公平源和FFN源另外各一份。Llama的MHA每KV组1个Q头，独立按模型/模式确定容量，不复用Qwen的GQA数。

所有端点在整次decode中持续存在，跨头、层、token不重新构造。一个共享32bit种子总线按原模型包级轮询；默认每100源时钟提供一个合格字、启动10拍，每端点每1亿拍到期换种。LFSR每次1字，Bivium6字含177bit有效状态，丢弃15padding bit如实统计。默认可复现fixture是仿真输入，不是物理熵证明；不暗中使用固定种子回退或免费派生种子。

## FFN没有把32拍算成64拍

每个64输入组：SAVE并锁定epoch → 当前输出波次的32次真实请求/消费 → RESTORE → 下一波次 → 最后RELEASE。gate/up仍在一个合并投影中共享输入流；z另行编码、另起输入组。换种到期时原端点延后并累计`reseed_deferred_cycles`，RELEASE后才换种。

源生成与SC计算流式重叠。首字形成后每拍可提供一个字，最后一字的消费排空计入原drain。隔离验证T32、II1的消费段连同原startup/drain为34拍，没有先生成32拍再另算32拍。SAVE/RESTORE/RELEASE和真实等待另计，不把它们当免费。无随机流SRAM、随机序列FIFO或第二套概率副本；PRNG状态、checkpoint和单响应寄存器是端点真实状态，不能宣称没有寄存器。

FFN数值张量仍是宏级TLM，不在这里运行权重乘法。实际源字被生成、分层、消费和散列，帧数/重放与矩阵调度绑定；并不因此获得新的模型PPL。

## Attention时序和数值

筛选、PV和两采样器均使用实际后端响应决定地址，不再只统计“需要多少随机数”后调用理想随机oracle。端点有限宽度、种子等待、5拍Bivium预热、计时、拒绝和输出sink回压进入同一时间线。请求没有到来时，端点不额外生成帧；原生寄存器时钟、age和后台换种继续运行。

采样器前端配置由真实随机服务负责，`external_source_programming=True`禁止另收一遍虚构drive写入；原接口默认False，历史结果的行为不变。已有数字树、偏移运算、仲裁和输出等待仍保留。真实源的计数取整次网络账本，不逐query叠加累积快照；已有源内部比较/寄存器成本不在sampler里再收一次。

数字响应使用`SigmoidTable`：驱动网格0.125，输出q/256，q可到256，随机字仍8bit。**这会改变理想sigmoid目标分布**，尤其拒绝偏移后的极小概率；新结果不继承旧理想源PPL。报告保存零概率lane计数、真实输出SHA及后端标记。新旧源采样地址不同，整机时间差还包含候选/K/V流量变化，不能全解释为协议开销。旧串行Ising的事件压缩oracle未接入本后端，显式拒绝该组合，不偷偷回退理想源。

## 功耗面积回填边界

`configs/rng_ppa100.json`绑定用户任务38322118的100MHz、55nm SS1.08V125°C实际报告及源manifest SHA。按各物理端点的真实active/idle周期估计原生端点能量；原生LFSR/Bivium端点含自身比较、状态、seed ingress/控制和输出。**这只是有工艺依据的两状态插值**，不是新PT或每次动作精确标定。

FFN目前采用LFSR原生端点PPA，64比较/分层/广播另列未知；不能把边界不同的639.6µW FFN共享顶层和162.47µW LFSR顶层相加。全局种子仲裁/合格材料、LUT、阈值编程/保持、FFN比较及长线不完整，完整随机模块与整机能量/面积仍为null。原工艺告警、无CTS/SPEF/SDF等限制保留，idle不是停钟。

## CPU模拟加速与证据

原Issue95源码和RTL未改。`FastEndpoint`复用原`Endpoint.tick`的同一代码对象，私有绑定一个逐位等价的Bivium块求值器；原160个硬件递推步骤仍是一拍展开，CPU的三次块循环不代表硬件三拍。1000随机177bit状态与原逐位参考完全一致。

`EventNetwork`只跳过无响应、无预热、无可交付种子、无到期事件的稳定空闲区间；保留age、每端点时钟沿、延后换种与种子可用时刻。与原逐拍网络逐状态/输出/账本/种子记录对照通过，模拟器没有通过跳事件减少硬件周期。

执行冻结31aa4fa31fbfb7d74629b54811936ac30a41c250。原52项不变，新版定向完整模型40项在独立目录`results/integrated_rng_20261022_v3/`。其中12项为赢家/拒绝各三seed×两后端的S8连通诊断，赢家倍率1，不与默认S128/8倍质量预算混比。其余覆盖2K/8K、三seed筛选PV、Llama1/2完整层数及两后端；现已40/40完成、0失败，93项机制/回归和1421项归档/模型核对通过。具体时间、周期、能量边界和SHA见[正式结果报告](RNG_INTEGRATION_RESULTS_ZH.md)及目录SUMMARY/ARTIFACT_MANIFEST。

最初104项宽扫描v2主动取消：0完成、0失败；原因是全预算赢家路径的Python参考仿真成本高，超出接口接合验证所需范围。PLAN/EXECUTION/CANCELLED原件保留，不将计划或未完成项算成结果。首个完整24层pilot v1单独封存，不合并进40项计数。

```sh
python -m unittest architecture_tlm.unified_v6.test_rng_integrated -v
python -m architecture_tlm.unified_v6.run --model qwen --context 2048 --ffn sc --attention screen_pv --output NEW_DIR
python -m architecture_tlm.unified_v6.run --model qwen --context 2048 --ffn sc --attention screen_pv --rng-backend local_prng_interface --output OTHER_NEW_DIR
```

执行源、模型配置、SRAM校准与整个随机后端依赖逐文件SHA由EXECUTION.json封存；历史`SOURCE_INDEX.json`仍指原语义/质量来源，不用它冒充新执行版本。无新训练、GPU、模型权重加载、PPL、RTL/DC/PT或实际DRAMSys运行。
