"""Document primary-source comparisons and derive current timing bounds; no new run."""
from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parents[3];D=R/'architecture_tlm/unified_v6';W=R/'work/jieruiz/186'
inputs=[];ds=[]
for i in (8,12):
 p=D/f'results/resources_20261025/results/case_{i}/COMPACT.json';b=p.read_bytes();inputs.append(dict(path=p.relative_to(R).as_posix(),sha256=hashlib.sha256(b).hexdigest()));ds.append(json.loads(b))
rows=[]
for d in ds:
 ph=d['phase_ns'];dense=sum(ph[k] for k in ['QKV_projection','O_projection','FFN_gate_up','FFN_down','lm_head_and_argmax'])/1e6;busy=d['resource_busy_ns'];dram=sum(v for k,v in d['DRAM']['traffic'].items() if k.endswith('_physical_bytes'))
 rows.append(dict(SRAM_GBs=d['SRAM']['fabric_combined_read_write_GBs'],TPOT_ms=d['metrics']['TPOT_ms'],dense_ms=dense,attention_ms=ph['attention_core']/1e6,other_ms=d['metrics']['TPOT_ms']-dense-ph['attention_core']/1e6,MAC_busy_ms=busy['mac']/1e6,SRAM_busy_ms=busy['sram_fabric']/1e6,DRAM_actor_busy_ms=busy['dram_dma']/1e6,descriptor_busy_ms=busy['dma_descriptor']/1e6,DRAM_bytes=dram))
a,b=rows;bounds=dict(HBM_256_ms=a['DRAM_bytes']/256e6,HBM_185786_reference_ms=a['DRAM_bytes']/185.786e6,A100_2039_reference_ms=a['DRAM_bytes']/2039e6,SRAM_doubling_saved_ms=a['TPOT_ms']-b['TPOT_ms'],SRAM_doubling_saved_percent=100*(1-b['TPOT_ms']/a['TPOT_ms']))
# All values are derived from archived full-model runs; no new execution or PPA.
record=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='primary-source literature review + arithmetic on existing sealed TLM results; no new simulation',inputs=inputs,rows=rows,bounds=bounds,upstream_execution='b01058f7e2143e81a602644d3d796768a8d008b5')
(W/'ASIC_COMPARISON_DERIVATION.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
table='\n'.join(f'| {label} | {a[k]:.3f} | {b[k]:.3f} |' for k,label in [('TPOT_ms','整机时间/token'),('dense_ms','全部稠密投影，含lm_head'),('attention_ms','Attention核心'),('other_ms','其他阶段'),('MAC_busy_ms','MAC忙碌'),('SRAM_busy_ms','SRAM fabric忙碌'),('DRAM_actor_busy_ms','DRAM actor忙碌'),('descriptor_busy_ms','DMA描述符生成忙碌')])
text=f'''# ASIC论文对照：高带宽可以采用，但剩余差距不只是L2

2026-10-25，Issue186 / PR190。本轮是一手资料核对及已有16项TLM结果的派生分析，没有新TLM运行、GPU、PPL、RTL、STA或PT。以下当前结果仍是Qwen3-4B后训练形状、B1、2K总上下文、单token decode的BF16数字参考；不是新概率路径质量或PPA结论。

**ASIC可以实现TB/s级片上存储带宽。当前约107–125ms/token不是ASIC的物理上限；同时，扩大后的剩余差距也不能继续主要解释为L2带宽不足。**

## 1. 其他工作到底采用了什么

| 工作 | 可核实的硬件/存储配置 | 与我们比较时的边界 |
|---|---|---|
| SambaNova SN40L | 5nm，1040个PMU，共520MiB分布式SRAM，聚合带宽数百TB/s；每socket64GiB HBM，约2TB/s | 商用芯片系统评估；主要CoE实验为8socket、Llama2-7B衍生模型、B1/B8；不是我们单设备Qwen4B。GPU对照含公开数据与估算。[原论文§IV/VI](https://arxiv.org/html/2405.07518v1) |
| Groq TSP | 作者演讲给出220MiB SRAM、两侧各44个MEM slice，slice内两个bank可并发；编译器显式分配位置/时序 | 是分布式scratchpad及流式通路的实例，不以2020图像模型性能推算今天LLM的TPOT。未采用当前不能完整打开的产品brief中的80TB/s作为定量依据。[作者演讲第8/12页](https://mlhardware.github.io/2020/groq.pdf) |
| AttAcc，ASPLOS2024 | GPU侧40个HBM3＋PIM侧另40个；GPU侧聚合26.8TB/s，PIM内部聚合242TB/s；GEMV逻辑666MHz | 修改Ramulator的系统仿真与RTL成本；大量堆栈与动态batch、10,000请求总执行时间。PIM内部带宽不是一条SRAM总线，也不是单设备B1。[原论文§5/7](https://scale.snu.ac.kr/papers/2024-04-Conference-ASPLOS-AttAcc.pdf) |
| NeuPIMs，ASPLOS2024 | 每芯片8个128×128阵列、32个HBM通道；未明确给可靠的片上SRAM带宽 | ONNXim＋DRAMsim3仿真；7B已用TP4，batch64–512。批量tokens/s的倒数不是B1 TPOT。表中1GHz在HBM栏，不能自动当NPU频率。[原文表2–4/§8](https://arxiv.org/html/2403.00579v3#S8) |
| OPAL，2024预印本 | 65nm综合、512KB global buffer，CACTI估计存储；报告Llama2-70B约1.98秒/token | 并非全部ASIC论文都追求几毫秒。该文外存/batch/context说明不足，不能按参数量缩放来证明我们更快。[§5.2](https://arxiv.org/html/2409.05902v3#S5.SS2) |
| DS-CIM，2026预印本 | 40nm后布局评估，128×32的32Kb计算宏，随机计算并行复制；LLaMA质量用FP8/INT8对齐及误差注入 | 高TOPS/W对应宏及指定归一化/采样条件，不是完整LLM的J/token或TPOT。其论文没有给完整LLaMA外存调度和token延迟，不能拿宏吞吐直接比较整机。[§III/V](https://arxiv.org/html/2601.06724v1) |

这些工作有真实商业芯片、系统仿真、宏后布局三种不同证据等级。不能汇成一个没有边界的“别人的ASIC速度”。对于数据中心目标，当前8–9.3token/s确实偏低；这需要继续改善，但不能用批量/多芯片吞吐直接计算落后倍数。

## 2. 我们为什么可以采用高片上带宽

L2是存储层级名称，不是GPU专用器件。ASIC可以采用多bank SRAM、分布式scratchpad、局部缓存和NoC。理想聚合带宽为各独立接口“字节/拍×频率”之和，再受bank冲突、路由和访问分布限制。

例如64个独立128B接口，100MHz下理想合计819.2GB/s；这是结构示例，不是现有16B宏突然变宽。需要相应并联宏、布线和控制。SN40L/Groq的意义在于把存储与计算分布到局部，并行读写；它们的局部带宽总和不代表任意单个算子都可独占全部带宽。

因此我们可以设512GB/s、1TB/s甚至更大档位，但应把“全局tile搬运带宽”“局部阵列供数带宽”“跨簇广播/归约”分开。用一条全局fabric承载全部局部读写，会保守地压低性能；反之，把所有局部带宽相加后免费赋给任意全局访问，也会过于乐观。更高带宽需要把宏、端口、网络的面积和能量一起计入。

## 3. 当前剩余时间并不主要等于L2差距

核心8192MAC/拍、100MHz、共享8MiB，其他条件一致；512→1024GB/s同时增加独立bank资源：

| 项目，ms | 512GB/s | 1024GB/s |
|---|---:|---:|
{table}

上半表各阶段可相加；下半忙碌时间互有重叠，不能直接相加或当独立时间占比。片上接口/bank资源翻倍，仅再减少 **{bounds['SRAM_doubling_saved_ms']:.3f}ms（{bounds['SRAM_doubling_saved_percent']:.2f}%）**。

同一份8.347GB/token外存流量：

| 外存供数条件 | 理想/参考时间 |
|---|---:|
| 当前HBM理论256GB/s | 至少{bounds['HBM_256_ms']:.3f}ms |
| 当前连续读微基准185.786GB/s | {bounds['HBM_185786_reference_ms']:.3f}ms，参考而非严格下界 |
| LLMCompass A100模型2039GB/s | {bounds['A100_2039_reference_ms']:.3f}ms，仅流量/带宽 |

**即使当前片上SRAM无限快，相同流量和256GB/s外存也突破不了32.6ms理想下界。** 这一下界不代表真实排程可以达到，也不能把107.6减32.6都算作可去除的浪费。

此前LLMCompass A100约4.162ms预测，其中约3.948ms（94.8%）来自M=1 GEMV快捷路径；该路径不计L2限制，主要取计算与外存时间的最大值。因此不能说它快主要因为7.22TB/s L2。该值是理想算子服务预测；旧launch代理20.989ms也不是当前GPU实测的上下界。见既有[独立模拟器报告](LLMCOMPASS_COMPARISON_ZH.md)及其固定上游代码。

## 4. 还需要查清的机制

1. **外存规模和入口匹配。** 当前256GB/s远低于数据中心级约2TB/s。升级HBM时要一起检查控制器队列、响应带宽及通道映射，不能仅改一个pin-bandwidth参数。
2. **DMA并发和本地缓冲。** 当前下一DMA在当前MAC开始才发起，只有一个在用本地操作数缓冲。大MAC配置计算很短，本次shared prefill开关没有有效覆盖窗口；并非所有调度优化都无效。先比较更早发DMA、有限多在途tile和本地双缓冲。
3. **描述符生成。** 每token约131万span，一拍一个，单独忙13.115ms。需要检查连续地址生成/描述符合并能否用成熟DMA模式完成。不能未经实现就把这13ms删掉；它也不一定全部落在关键路径上。
4. **KV布局和并行。** 当前2048B token步长、channel bits8..10使同KV组集中于同一HBM channel，逐组/逐块执行。SRAM扩倍后Attention仅少约0.72ms；应该检查通道交织与跨头/跨块流水。
5. **全局与局部数据通路。** 保持有限容量/端口/所有权，在合理的地方融合或直达局部缓冲；减少重复跨越全局fabric。数字和概率路径都给予相同可用优化。

目前只能量化已有16项扫描的差值，不能把这些尚未完成的优化各自能省多少加起来，也没有新的最快整机预测。

## 5. 论文应怎样比较

- 主结果采用同模型、质量协议、精度边界、batch、上下文、芯片数、时钟、共享/局部容量及外存配置下的优化数字参考与概率方案；报告TPOT、J/token、面积及带宽/容量代价。
- 另作同目标资源的平台对照：选择一个明确的ASIC/NPU配置，配置共同内存底座和合理并行度。宏级性能目标与55nm已标定电路分开标注，不能混称当前工艺下已实现。
- 模块表对比采样、计数、CIM宏；系统表计入存储、控制和非线性。TOPS/W与整机J/token分开。
- 目标应是同等质量和延迟约束下减少能量/面积，同时解释资源取舍。已有8MiB/100MHz小型配置可以保留为探索点，不能代表所有ASIC。

当前数字4B结果与几毫秒级商用配置不匹配，主要体现外存/算力/局部并行、排程及模型边界的共同差异。下一轮应优先排查上述入口与流水，配套更接近目标平台的HBM，而不是继续只把L2数值调大。

派生数据与输入SHA：work/jieruiz/186/ASIC_COMPARISON_DERIVATION.json；原始执行b01058f7/Slurm3058不变。本轮未更改配置默认、未重跑实验、未产生新物理PPA。
'''
(D/'ASIC_PAPER_COMPARISON_ZH.md').write_text(text,encoding='utf-8',newline='\n')
print(json.dumps(dict(rows=rows,bounds=bounds),indent=2))
