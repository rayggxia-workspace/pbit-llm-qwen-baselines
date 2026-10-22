# 数字在线 Attention 与 QK概率筛选＋Ising 对比

## 2026-10-22 最新实现与结果补充

[Ising Softmax 评估补充](ISING_UPDATE_20261022_ZH.md)核对已合并 PR79/80、待审 PR82/86/88：旧互斥网络的独立同步提交约束仍成立，新赢家保持/校正拒绝通过改变规则支持全候选并行提议；已有128目标后缀PPL、90配置真实QKV误差和v5内部时序结果，各自证据范围不同。新两条候选尚无模型PPL及已标定完整能量/面积；原100ns/索引黑盒表保留为历史条件结果，不能直接验收当前实现。来源SHA及46项离线检查见补充文档链接。

下方为2026-10-19原评估，保存的32场景原件和历史结论不改。原PR45已经由集成流程合入；文末旧权限/发布描述仅代表当时状态。

2026-10-19；负责人amlink1219；[Issue37](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/37)，依赖Issue36的数字定义。本轮评估已有模型并运行同边界条件事务对照；没有新模型推理、PPL、器件电路或硅片测量。

## 比较的边界

模型为Qwen2.5-0.5B、24层、batch1、单token decode，L指本次追加后参与扫描的总KV长度。模块从已归一化的输入开始，含QKV投影/偏置、RoPE与KV追加、Attention core、Wo。RMSNorm、残差、FFN、lm_head和prefill另属整模型范围；不把本轮ms称为完整decoder TPOT。

数字D0为分块在线Softmax、64-token tile、GQA七Q共享一KV组，全部key参与。P为max4摘要→独立Bernoulli筛选→固定预算修复→候选准确QK→Ising类别索引→V累加平均。默认固定8块×64=512候选，样本32/128/512；variable另按上下文容量预留宏。`screen_exact`诊断保留原独立Bernoulli、候选内数字在线Softmax/PV，不与固定预算P混称同候选集合。

输入/权重/KV/输出为BF16；QK分数、概率、在线分母、PV及累加为FP32数学契约，非有限字长RTL。D0和P都流式读84MiB投影权重/token，32KiB分块经DRAM读取、SRAM写入、再SRAM读出后计算；不继承旧16MiB权重cache的免费驻留或不同供数带宽。

共同假设：100MHz、512抽象MAC/cycle、64vector ops/cycle、16nonlinear ops/cycle；DRAM服务16GB/s、64B burst、每请求80ns，SRAM读写合计16GB/s。有限DMA队列以1/32请求批内共享链路、批末排空；pending1是串行化诊断，主对照双方均pending32。它不等于真实DRAMSys、FR-FCFS、跨descriptor重排或最优调度。

## 现有项目究竟报告了什么

源码与保存JSON的SHA核对通过，提取见[legacy_summary.json](../results/attention_comparison_20261019/legacy_summary.json)。以下是历史参数模型，默认简化Link、固定权重随机FFN，非全数字整机。

| L | 历史方案 | Attention core ms/token | Attention直接mJ/token | 整模型ms/token | 整模型mJ/token |
|---:|---|---:|---:|---:|---:|
| 2048 | dense v3 | 4.416840 | 1.924330 | 445.457377 | 170.656248 |
| 2048 | screen＋Ising固定 v4 | 35.271362 | 2.752337 | 476.445408 | 174.655911 |
| 8192 | dense v3 | 17.637192 | 7.695377 | 458.677729 | 177.780411 |
| 8192 | screen＋Ising固定 v4 | 59.437187 | 6.883673 | 500.611233 | 181.260643 |

dense是两token均值，v4是单个首token且摘要冷建立；core不含QKV/Wo，直接能量不含公共idle/root等。故不能从表中直接宣称同协议加速或节能，尤其不能拿core与Issue36的完整模块14.155776ms资源下界比较。旧16MiB cache＋1MiB scratch/64GB/s、32GB/s外存、256B burst与Issue36不同。

旧整模型均值功率由mJ/ms推导：2K dense约0.383W，P约0.367W，但P用时更长、token能量更高。较低平均功率不代表完成同一任务更省电。新表始终同时报告W、ms和mJ/token。

最新PR29的PROJECT_MEMORY_ZH.md还记录本地PV v6：systematic偏移、组V并集/广播、最多32个64B请求在途；它尚未集成筛选/Ising。其2K准确PV→采样PV约3.405→2.756ms，完整Attention约7.074→7.036ms，是历史另一调度的结果，不能移植为本轮同配置数据。可用源码位于`llama7b/runtime/pv_stream_v6.py`，本轮没有冒称已将其集成。

## 为什么不能按25%候选率计算75%访存节约

每个KV组含7个Q头；K读取必须取它们候选的并集。V读取取实际样本、缓存命中、LRU重读及物理突发，不是逐头保留率简单相乘。旧2K/S512事务中，候选QK只保留25%，K物理读却是dense的93.36%，V物理读92.95%；加暖摘要读后约为dense KV的99.40%，冷建立则进一步增流量。新64B burst会改变这些比例，必须重跑地址账本。

摘要常驻外存，2K为64KiB/层、24层读取1.5MiB/token；冷建立另全读12MiB K并写1.5MiB摘要。暖态将历史建立成本归入prefill，同时必须维护刚追加的新K，不能漏掉首个decode的更新。本轮显式修正该接口。

现有v4 tile128的2K固定预算core活跃量267776B，超过D0的64KiB。改tile64后仍约235008B，再加共同接口保留。新对照逐方案根据峰值向64KiB一组的16个E宏上取整计费；增加容量不免费增加总带宽。D0保留自身实际需要的较小容量，不为了“同容量”人为抬高D0面积。wrapper、bank仲裁和STA仍未验证。

## Ising宏的明确假设

当前macro为`ideal_iid_oracle`：软件按候选浮点Softmax生成理想索引来形成访存，硬件账本只收宏服务一次，没有第二套准确Softmax/CDF。它没有模拟真实Ising网络、bias量化、相关样本、混合、有效样本数或全模型PPL。16bit bias只决定配置流量，不证明16bit精度已通过。

单宏在336个层/头请求间串行复用，容量按512或variable最坏值收费，masked slots也付配置、功率和面积。内部随机源/状态/反馈/编码按宏合同封装一次；外部root/32bit leaf只服务筛选，不重复收费内部随机数。当前筛选仍是数字sigmoid＋PRNG，尚非原生p-bit概率判决。

原始512槽示例值：配置16GB/s＋100ns、settle500ns、burn2000ns、readout20ns、样本100ns；工作功率0.612mW、面积0.01512mm²、配置0.1pJ/bit。全部未表征。S512仅宏服务约18.1ms/token；S128约5.2ms。宏周期1/10/100ns敏感性用于找器件预算，不能写成器件能够达到。

算术也受资源比例约束：2K dense PV的纯服务量为0.86016ms；若采用现有重复加法映射，S512要1.72032ms，S128为0.43008ms。因加法通道64、MAC通道512，仅该阶段想更快需S/L<1/8。这不说明加法能量比乘法高，而是说明降低运算复杂度不能替代吞吐核算。

## PPA证据和质量门槛

E/SS SRAM来自已发布exact_macro_table.csv：1.08V/125°C，每4KiB宏0.03322622205mm²，读10.0527pJ/128bit、写13.9599pJ/128bit。其面积、内部读写能量是已知局部项；没有使用CACTI插值冒称直接查库。

2pJ/MAC、独立FP32 PV 2pJ代理、1pJ/vector、10pJ/nonlinear、1mm²逻辑、DRAM64pJ/B/背景50mW以及Ising PPA仍是占位系数。因此输出把`proxy`场景值与`physical_PPA`分开，后者完整能量/面积/功率均为null。寄存器/operand分发、EXP/倒数的有限字长实现、RoPE系数生成、wrapper/时钟、真实DRAM/PHY仍缺表征。

主目标是相同完整PPL预算内的PPA。此批合成地址与理想宏没有新PPL，不能将同C/S说成同PPL。旧BF16完整WT2 11.652735只是Issue35软件锚点。数字PWL/systematic采样也是后续强对照；当前P对D0的任何优势尚不能单独归因为原生p-bit。

## 新条件事务结果

Slurm2164已在CPU1分配完成，COMPLETED/0:0；23源文件SHA通过、9/9快照测试、32/32完整24层场景成功。回收归档及40个文件逐一独立验SHA。执行版本`7f1cc0d5c3e967f4983727c726b7e1d6e36e7873`。没有GPU、模型推理、PPL、RTL或DC/PT。完整结果见[同协议汇总](../results/attention_comparison_20261019/MATCHED_RESULTS_ZH.md)、[机器可读表](../results/attention_comparison_20261019/matched_summary.json)。

2K、warm摘要、pending32、512候选、100ns输出周期；概率方案为三个seed均值：

| 完整Attention | ms/token | 条件mJ/token | 条件平均W | 延迟相对D0 | 能量相对D0 |
|---|---:|---:|---:|---:|---:|
| D0数字在线 | 29.480 | 10.057 | 0.341 | 基准 | 基准 |
| QK筛选＋Ising，S32 | 27.963 | 8.961 | 0.320 | −5.15% | −10.90% |
| QK筛选＋Ising，S128 | 33.038 | 9.495 | 0.287 | +12.07% | −5.59% |
| QK筛选＋Ising，S512 | 49.921 | 11.080 | 0.222 | +69.34% | +10.17% |

这里的能量/功率继承未校准逻辑、DRAM及Ising系数，不能称芯片预测值。低功率但更长时间可能更费能，S512就是该情景下的例子。9/9测试或23源SHA通过只验证程序/来源，不会把占位系数变成器件证据。

8K下D0为55.340ms/17.638mJ，S128为38.652ms/10.582mJ，条件延迟约低30.16%、能量低40.00%；但是512候选仅占6.25%，质量没有验收。它说明长上下文存在潜在空间，不是等PPL硬件优势结论。固定预算cold的8K/S512为72.675ms，进一步说明prefill摘要建立与decode稳态必须分开。

本轮2K物理K约为dense K的75.43%，并未随25%逻辑候选率降到25%。V物理读取随S32/128/512约为8.64%/22.91%/46.92%。这些为当前合成分布和64B事务映射的实际计数，旧256B结果没有静默覆盖。

### 对硬件架构的具体约束

1. **先把S128宏的目标写成预算。** 固定地址/其他阶段时，2K/S128的延迟盈亏周期约17.27ns；1ns/10ns单seed实际条件值28.796/29.183ms，接近或略快于D0。此周期是输出索引间隔，真实器件必须同时满足相关性、预热、偏置量化和PPL，不能直接当独立样本周期。
2. **S512不能只靠把宏加快。** 三seed均值即使去掉全部约18.107ms宏服务，剩余约31.814ms仍高于D0的29.480ms。原映射中的逐head V gather、histogram/映射、重复加法和summary/sort也要改；64个通用vector通道承接512样本的重复加法并不快。可研究组V并集＋广播、descriptor合并、专用累加通道，但需连同带宽/寄存器/面积重新计费。
3. **面积优先改缓冲数据流。** D0用64KiB、宏面积0.531620mm²；P在2K用256KiB/2.126478mm²，在8K用448KiB/3.721337mm²，分别为4倍/7倍。不是小Ising宏0.01512mm²就能代表整体省面积。应将全摘要/all-head maps改为逐组/逐head流式或分阶段复用，再验证64KiB预算和新增外存重读；当前未实现这种重排。
4. **完整收益受共同投影限制。** 所有方案共同阶段约20.854ms/token，包括84MiB权重流式投影、bias/RoPE和KV追加。在当前固定调度下，即使core消失，2K数字模块加速上限也仅约1.414倍；整模型还有FFN等共同项。该上限只针对本轮映射，非所有数字架构的物理极限。
5. **收益归因要增加同候选数字采样对照。** 当前`screen_exact`保留原variable Bernoulli，主P为fixed-budget8块，尤其8K保留率不同；其差额不能单独称p-bit贡献。下一步应固定同一candidate_ids并比较数字PWL/systematic与真实有限时间Ising。原生p-bit概率筛选也需要独立成本和相同PPL验收，本轮仍为数字sigmoid＋PRNG。

因此当前优先级为：行为级验证S32/128及固定512候选的PPL；并行重排SRAM/V-gather数据流，明确S128约17ns的宏输出预算；用真实器件或有限时间采样轨迹替换IID地址，再做同工艺单元表征。不能直接沿用S512默认配置宣称低面积、低能量且更快。

### 复现与交付

`evaluate.py --batch-config comparison_config.json --source-commit <执行版本> --output <新目录>`执行有限条件批次；完整CPU作业命令、源/配置SHA和Slurm terminal见[交接](../../work/amlink1219/37/HANDOFF.md)。从已有原始结果重新汇总：

```sh
python architecture_tlm/attention_comparison/summarize_results.py --input architecture_tlm/results/attention_comparison_20261019/raw --output <新汇总目录> --no-copy-raw
```

正式后处理入口已重新核算并与三份现有汇总逐字节一致。旧core沿用保守bulk向量计数，不同于Issue36逐项解析账本；本轮是新增完整阻塞事务情景，不把它叫最优数字电路、周期准确RTL或实测时延。代码/结果在独立分支本地提交，本人Issue可同步，任务分支和PR仍待仓库push权限。
