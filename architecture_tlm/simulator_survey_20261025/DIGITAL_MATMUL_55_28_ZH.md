# 55nm/28nm普通数字矩阵乘法：功耗、时间与可复用基线

日期：2026-10-27。负责人：rayggxia；Issue187 / PR189。只读文献与公开源码核查，无新RTL/EDA/TLM运行。本文补充原33条证据，不替代原记录。

**有可用数据，也有作者公开的传统MAC阵列RTL。建议复用已有实现，在本项目55nm库和统一激励下表征；现有手写BF16乘法+FP32累加核不能代替充分优化的INT8数字基线。** 目前未找到能直接填入本项目64维、单向量/小批次场景的完整实测时延表，不能把峰值TOPS折算的下界称为实际完成时间。

## 1. 已核到原文的数值

| 来源与对象 | 工艺/精度 | 面积 | 频率 | 功耗与吞吐 | 证据边界 |
|---|---|---:|---:|---|---|
| HPCA2025 TPE论文重实现的TPU式32×32 MAC阵列 | SMIC28nm-HKCP-RVT、0.72V；INT8乘、INT32累加 | 0.370631mm² | 1GHz | 0.25W；峰值2.05TOPS；8.05TOPS/W | 表VII空心菱形：逻辑综合；含PE输入/输出DFF、组合逻辑和时钟网络；不是Google TPU芯片实测或含完整存储的SoC |
| 同文传统Trapezoid乘法器+加法树阵列，32×32 PE | 同上 | 0.283704mm² | 1GHz | 0.22W；峰值2.05TOPS；9.31TOPS/W | 同为综合级，适合作为归约树形态参照 |
| 《面向边缘计算的可重构CNN协处理器研究与设计》，256PE | 55nm TT、1.2V、25℃；INT8 | 4.41mm² | 工作320MHz；最高328MHz | 峰值163.8GOPS；LeNet-5：138.4mW、29.16GOPS；MobileNet：279.6mW、95.23GOPS | 布局后网表、SDF、SAIF与PT-PX；含176KB片上存储、控制和后处理；非裸MAC，非硅片实测 |

来源：[TPE原文§V-A、表VII](https://arxiv.org/html/2503.06342v1)（PDF第10–11页）、[55nm论文出版页](https://jeit.ac.cn/cn/article/doi/10.11999/JEIT230509?viewType=HTML)与[出版方PDF](https://www.sciengine.com/parse/pdf/1009-5896/5C228C3A35B444898D93CBF950C7EFA5.pdf)（§8、印刷1508–1510页）。55nm表1的功耗仅保留三位小数，上表采用正文更精确值。4.41mm²在摘要称实现面积，正文§8称综合后总面积；不将它改写为最终GDS core尺寸。

每个MAC按乘、加共2ops做等效换算：28nm两阵列约0.248、0.215pJ/MAC（按原文能效）；55nm两任务约9.49、5.87pJ/等效MAC（按匹配任务功耗/吞吐）。后者含存储、后处理及任务利用率，不能当单MAC单元能量。原文舍入使功率、峰值与能效不完全相除一致，保留原数，不强行修表。不要用55nm峰值163.8GOPS除以MobileNet任务能效来反推其功率。

## 2. “算这个矩阵需要多久”目前能回答到哪里

统一写作 `Y[M,N] = X[M,K] × W[K,N]`；项目的单输出N64计数核对应K=64、M=N=1，只有64个有效MAC；完整64×64权重乘单向量则是M=1、K=N=64，共4096MAC。二者相差64倍，不能混用frame价格。

若只按峰值吞吐计算，不计填充/排空、装载、结果输出、bank冲突和利用率：

| 工作 | 有效MAC | 55nm 256PE×320MHz下界 | 28nm 1024PE×1GHz下界 |
|---|---:|---:|---:|
| 64×64权重乘单向量 | 4,096 | 50ns | 4ns |
| X[8,64]×W[64,64] | 32,768 | 400ns | 32ns |
| X[64,64]×W[64,64] | 262,144 | 3.2µs | 256ns |

**全表为数学峰值下界，不是文献报告的这三个形状的时延。** 尤其M=1时，传统二维OS阵列往往难以满用；单向量4ns不代表该32×32阵列能4ns完成GEMV。真实周期必须由实际映射、流水、供数和输出接口得到；已有作者测试台可用于后续测量。

55nm论文报告网络吞吐41851、1272images/s，其倒数约23.9µs、786.2µs，是每图平均服务时间，不是某次GEMM时延或首结果延迟。论文不能替我们证明某个64维矩阵的时间。比较SC时必须同时报告sample II、frame latency、连续frame II；T=64的64个输入采样拍不等于每拍完成一个完整矩阵。

## 3. 降低自己设计出错风险：已有作者RTL

优先候选：[High-Performance-Tensor-Processing-Engines](https://github.com/wqzustc/High-Performance-Tensor-Processing-Engines)，MIT许可，本轮锁定提交`ebe4db7d2d3c36d10c47683d7689f65f5c4ca3e4`。下列链接均固定版本：

- [传统MAC](https://github.com/wqzustc/High-Performance-Tensor-Processing-Engines/blob/ebe4db7d2d3c36d10c47683d7689f65f5c4ca3e4/OPT1/systolic_array_os/mac_pe/mac.v)：有符号8×8乘法和32位累加。
- [传统OS阵列PE](https://github.com/wqzustc/High-Performance-Tensor-Processing-Engines/blob/ebe4db7d2d3c36d10c47683d7689f65f5c4ca3e4/OPT1/systolic_array_os/array_mac_based/pe.v)、[阵列top](https://github.com/wqzustc/High-Performance-Tensor-Processing-Engines/blob/ebe4db7d2d3c36d10c47683d7689f65f5c4ca3e4/OPT1/systolic_array_os/array_mac_based/top.v)。仓库另有WS/Cube及论文优化版本，可作更强数字参照。
- [矩阵测试台](https://github.com/wqzustc/High-Performance-Tensor-Processing-Engines/blob/ebe4db7d2d3c36d10c47683d7689f65f5c4ca3e4/OPT1/systolic_array_os/array_mac_based/sim/test_mac_os_array.sv)：参数M/K/N，独立整数三重循环参考，100组随机矩阵比较。
- [DC脚本](https://github.com/wqzustc/High-Performance-Tensor-Processing-Engines/blob/ebe4db7d2d3c36d10c47683d7689f65f5c4ca3e4/OPT1/systolic_array_os/array_mac_based/syn/dc.tcl)：库、时钟和路径需替换。本轮只读，没有执行作者测试或工具。

需要保留的区别与适配：

1. **公开脚本实际是`saed32rvt_tt0p85v25c`教学库，论文是SMIC28、0.72V。** README里的154MHz等数组报告不是论文1GHz数据；也不能直接作为55nm结果。公开实现是可审查起点，不是已在本工艺验证的IP。
2. 作者为核对结果将全部输出寄存器直接暴露为端口，README明确建议实际系统改为移位或选择流水输出。需按真实带宽测完整完成时间，不能免费读出全部结果。
3. 单MAC文件虽然有WIDTH参数，但operand/result_p内部固定8/16位；本轮候选限定INT8。测试台`$urandom_range(127,-128)`涉及无符号参数语义，不能未经核实认定均匀覆盖有符号全范围。后续添加独立、有确定种子的显式向量，覆盖0、±1、±127、-128、抵消和累加边界。
4. 测试台先驱动M+N+K拍，再额外等待M+N+K拍后检查；这是验证等待策略，不能把总等待当最短硬件latency。应记录首输入接受、最后有效累加、输出稳定、最后结果传出等事件。
5. 当前SC不含-128，主对照数字输入范围也应一致，另保留完整INT8功能边界。相同量化/恢复规则、权重驻留与合理门控应同时给予两侧。

## 4. 对本项目比较的影响与下一步

文献表明传统数字也可以通过共享输入、局部存储和流水降低成本。28nm小于55nm，电压、corner和成本边界差异很大；不按55/28的线宽比例直接缩放功率，不用55nm整协处理器功耗与我们单计数树相比。现有BF16/FP32核代表较高精度服务，不能作为INT8普通数字的唯一主对照。

建议最小实施顺序（尚未执行，不自动提交昂贵任务）：

1. 固定作者RTL版本，先在原测试台和独立有符号向量中验证；建立单MAC和小阵列可追溯移植，避免先新写整套浮点单元。
2. 在55nm相同PVT/时钟、相同K=64与M=1/8任务上表征INT8×INT8→INT32，记录实际计算与输出周期；先100MHz与现有实测对齐，更高频单独STA。
3. 同时提供适合单向量的数字归约/驻留映射与二维阵列合理映射；只拿低利用率OS阵列代表所有数字实现会低估数字侧。确定性bit-serial作为另一低成本控制。
4. 给双方相同可实现的SRAM/权重驻留、输入广播和门控政策，分报计算核与包含存储/编码/恢复/输出的完整tile；匹配模型质量后再决定T32/64/128是否省能。

补充边界：[RDCIM](https://researchportal.hkust.edu.hk/en/publications/rdcim-risc-v-supported-full-digital-computing-in-memory-processor/)（TCAS-I2024，DOI10.1109/TCSI.2024.3350664）作者机构摘要确认55nm流片，报告8bit 16.6TOPS/W。它是**确定性全数字CIM**，适合作为存储本地化路线参照，不能混入普通外置MAC阵列。尚未核到全文计数口径、频率/功率/绝对时延，本文不据摘要推算本项目矩阵时间。

## 5. 复现与交付

`DIGITAL_MATMUL_SOURCES.json`记录论文原字节SHA、公开代码固定版本及7个文件SHA；PDF/作者代码仅保留本地ignored核查副本，不上传论文、代码或库。`work/rayggxia/187/check_digital_matmul.py`核查下载字节及公式，输出`DIGITAL_MATMUL_CHECK.json`。这是资料与算术验证，无新增数字run；模型、权重、训练/测试文本SHA不适用。本轮未测得任何新的55nm/28nm PPA、RTL正确性、GEMV时延或模型精度。
