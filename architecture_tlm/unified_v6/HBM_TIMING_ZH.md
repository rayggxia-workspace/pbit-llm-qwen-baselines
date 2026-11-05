# HBM2 外存对照：Issue186 / PR190

本实验把同一完整 Qwen3-4B（后训练版形状）的外存更换为 DRAMSys HBM2，检查每 token 时间。属于合成事务的架构时序模拟，尚不是实际模型载荷、PPL、RTL 时序签核或芯片测量。结果以同目录 `results/hbm_20261025/` 的完成清单及 SHA 为准。

## 固定边界

36 层，batch=1，2K 已有上下文，decode 一个 token；包含所有 decoder 层、最终归一化和词表读出，不含 prefill。核心100MHz、512 MAC/拍、8MiB共享 SRAM/64bank/64GB/s、随机 FFN 8×64×64阵列和采样参数不变。SC 使用本任务已验证的 R8 局部部分和驻留候选；W8仅指数字 FFN 权重量化，其他矩阵仍按原 BF16 合同。没有增加全层权重驻留或改变概率计算的数制。

## 外存与请求入口

| 情景 | 外存容量/理论引脚带宽 | 主机请求入口 | 能量证据 |
|---|---|---|---|
| 原 DDR4 | 双通道、双rank、16GiB / 29.85GB/s | 64B事务，最多32条未完成 | 保留原 DRAMPower 诊断及已知限制 |
| HBM2，原入口 | 8通道×2伪通道、16GiB / 256GB/s | 64B事务，最多32条未完成 | 未校准，不计入有效能量 |
| HBM2，配套宽入口 | 同上 | span内自然对齐64/128/256B合并，最多128条未完成 | 未校准；控制器增量面积/能量也未知 |

宽入口的bridge配置响应容量上限由2KiB增至32KiB；Arbiter仍限定64个已接收父事务，实测峰值65包含1条等待，实际在途约16KiB。32KiB是预留上限，不能称为有效服务窗口。该容量增加，属于明确增加的外存控制器资源；没有悄悄扩大8MiB片上共享 SRAM。每条事务发起间隔1ns；上游仲裁器和 DRAM 时序仍可能降低实际吞吐。理论256GB/s不是实得带宽。没有假定一个100MHz核心周期只能访问一次独立时钟域的HBM控制器。

主机64B计费单位不等于HBM原生突发。HBM每伪通道突发32B，DRAMSys将256B主机事务拆为8条32B子事务。地址映射让单条主机事务不跨通道；通道取bit8..10，伪通道取bit5。不跨不连续span合并，不凭空降低读入字节数。当前PV调度以max_pending为V批大小，因此宽入口也让每批V位置上限从32增至128；样本地址和总字节数不变，但DMA描述符数和SRAM批启动次数会减少。它属于配套接口/分批改善，不能单独归因HBM器件。128个V的位置占用已分配的K_V_tile缓冲，不增加8MiB容量。`burst_count`保留64B主机计费单位，`host_transactions`记录实际父事务数；`physical_bytes/32`仅能作为预期原生突发数，不能冒充命令实测计数。

补充流水入口 `mature_hbm2_pipelined`：保持256B事务、同控制器缓冲和地址映射，将END_RESP额外接受延迟从1ps改为0。旧版1ps被上游取整到下一1ns，再加下一响应1ns，导致响应每2ns一次；流水版仍由上游保证每1ns最多一条响应。两组独立源码/输出保留，原17项不覆盖，补8项形成25项对照。微基准连续读取约112.10→185.79GB/s，仍不假定达到256GB/s。

## 配置依据与局限

使用 DRAMSys commit `9f15aaf1fe6f05ff16a2e521a20a96f3bfe29d52` 的 [HBM2配置](https://github.com/tukl-msd/DRAMSys/blob/9f15aaf1fe6f05ff16a2e521a20a96f3bfe29d52/configs/memspec/HBM2.json)，只扩展通道及对应地址映射，时序不变。它是公开参考时序情景，不能称为某一量产HBM产品的完整标定模型。容量16GiB足以容纳当前BF16完整地址空间。

原例电流IDD/IPP为零、接口参数也为占位，因此本配置显式关闭PowerAnalysis。HBM能量保留未知，缺失项记录在`uncalibrated_HBM_system_ns`；整机物理能量和面积继续为null，不能用已定价小计比较DDR和HBM的节能。

完整运行前检查连续读、连续写、混合、碎片请求；旧/新bridge的DDR四种情景要求每段时间和能量逐值相同。完整任务通过Slurm CPU作业执行，执行源码、配置和bridge SHA冻结；每个结果只有MANIFEST.completed且文件SHA吻合才算完成。

现有tile调度仍只允许下一DMA与计算重叠，后续SRAM填充受前一tile退休约束。HBM不会自动解决片上64GB/s吞吐、局部阵列容量、算子宏吞吐或流水线相依问题。本轮用于隔离外存收益，不声称全局最优。若替换后仍偏慢，后续优化应以实际阶段与资源忙碌统计定位，不能直接放大核心频率或相减各资源忙碌时间。

## 可复现入口

- 配置：`configs/dramsys/hbm2_8ch_16GiB_timing.json`
- CLI profile：`mature_hbm2_narrow` / `mature_hbm2_wide`，默认仍`mature_ddr4`。
- 源快照、17项矩阵、提交回执：`work/jieruiz/186/HBM_*`。
- `work/jieruiz/186/probe_hbm.py`：真实读写与DDR不变路径验证。
- `work/jieruiz/186/collect_hbm.py`：只采集封存且核验的结果。
- 全部算法和算术宏原有限制仍遵守`MATURE_SCHEDULING_ZH.md`、`FFN_LOCALITY_ZH.md`。

## 固定KV布局的通道限制（本轮不改变算法或数据布局）

Qwen配置为8个KV头、head_dim=128、BF16。当前token-major KV布局中，同一KV头相邻token相隔8×128×2=2048B；HBM通道位为8..10，因此一组查询访问的一串K/V向量映射到同一HBM通道。256B向量仍跨两个伪通道，但没有同时利用8个channel；现调度又逐KV组执行。因此全局连续读185.79GB/s不能拿来代替每个KV分组的实际带宽。原DDR通道位6，单个256B向量会跨两个DDR通道。部分注意力阶段可能略慢，必须保留这种结果。

后续可独立测试KV跨通道布局、XOR地址映射或并行多KV组；这些属于数据布局/调度优化，不能混入本轮“同布局更换外存”的结论。主体权重顺序读已使用8个通道。
