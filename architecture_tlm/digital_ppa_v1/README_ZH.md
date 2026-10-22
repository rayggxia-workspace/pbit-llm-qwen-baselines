# 完整TLM周期、访存审计与非随机数字RTL

Issue107，jieruiz，2026-10-22。**当前TLM给出条件时序，不是已通过RTL/STA确认的芯片周期。** 未标定的延迟、吞吐、局部状态和数据供给会同时影响时间、功耗和面积。

- [周期与访存完整报告](CYCLES_MEMORY_AND_RTL_ZH.md)：整机/阶段周期、已建模存储和未闭合假设。
- [52配置周期CSV](results/cycles_52.csv)、[阶段CSV](results/phase_cycles.csv)、[版本与原件SHA](results/CYCLE_AUDIT.json)。全部只读冻结结果，不是新跑模型。
- [仿真任务说明](PPA_TASK_ZH.md)：优先模块、输入和统计口径、DC/VCS/PT操作。
- `rtl/`：确定性算术、B4编码/恢复、非线性候选、累加、数字归约/控制和存储外围；没有PRNG、p-bit、随机矩阵阵列或DFF权重存储。

## Verilog范围与用法

SystemVerilog，可综合DUT仅使用整数、位运算、静态循环和项目已有浮点电路。没有`real/shortreal`、DPI、宿主数学函数或未实现算术黑盒。ROM常数由`sim/generate_roms.py`离线生成，综合使用完整case表；ROM映射到标准单元的成本需要实际综合，不能按零成本存储。

复用`format_conversion_rtl_20261016/rtl/`，精确版本和SHA随验证记录及便携包manifest绑定；不修改历史转换代码。旧Q10 SwiGLU已做过55nm TT/SS PT，但它与当前FP32路径的数制和范围不同，不能直接套价。本包的FP32非线性采用分段线性候选，不继承旧FP32/Ising组合PPL。

主表征顶层`nr_digital_probe`，KIND综合时固定：

| KIND | 电路 | PPA计费单位 |
|---|---|---|
| 0、1 | FP32加、乘 | 每标量操作 |
| 2、3 | BF16乘积/FP32累加；BF16残差相加 | 每MAC输入、每完整累加帧；每残差值 |
| 4、5 | 64路BF16/FP32→B4、A8、符号/满幅标记 | 每64值组，含absmax、PoT档位、编码和边界寄存 |
| 6 | B4×双输入符号×8权重位的逐档FP32恢复 | 每输出的一个64输入块部分结果；包含权重scale |
| 7 | 连续FP32 SwiGLU候选 | 每g/u对，包含sigmoid近似和两次乘法 |
| 8 | BF16 V→FP32累计、最后除2幂并转BF16 | 每输入V及完整累加帧；不含随机选地址 |
| 9、10 | RMS平方和/均值/rsqrt候选；归一化及gamma应用 | 每平方和输入及完整帧；每输出值 |
| 11、12、13 | exp负域、倒数、rsqrt候选 | 每非线性输入 |
| 14、15 | 比较交换、64路候选prefix写地址 | 每比较对、每64位mask |
| 16 | S128系统采样的Q0.32 CDF计数，offset外部输入 | 每概率区间，不含随机数生成 |
| 17 | 512路0/1/多命中归约、首地址 | 每全宽结果帧，不含p-bit及源 |
| 20、21 | RoPE二元旋转、FP32→BF16 | 每通道对、每转换值 |
| 22 | 先整数对齐B4、最后一次FP32转换/权重scale | 优化对照；改变中间浮点舍入，不能冒称已验证等价替换 |

独立顶层`nr_sram_router`仅银行路由/仲裁/返回保持，存储数据从宏接口输入；`nr_dma_window`仅有限窗口命令/完成控制，不包含DRAM控制器/PHY。功能例使用4请求端/16bank/DW32/ROW4和4项DMA窗口；模块默认16端/DW128/ROW12、窗口32可另综合，但不得用小例功耗无条件放大冒充实际系统。

独立数组`nr_fp32_array`和`nr_bf16_mac_array`用于检查单lane到16/64/512lane的实际布线/共享控制开销。lane复制不证明供数带宽、面积或时钟树免费；本轮验证4lane数值/有效信号，尚无数组工艺结果。

## 数值和时序边界

FP32加法/乘法/缩放使用RNE、subnormal及明确特殊值策略。编码范围逐64值组确定，B4尺度为`2^e、2^(e−2)、2^(e−4)、2^(e−6)`，比较门限A8附加符号和true-one，未重新排列通道。

非线性ROM：sigmoid/exp在16幅度内、步长1/32并线性插值；sigmoid在±16外钳为0/1，负域exp在−16外为0，正域输入按exp(0)钳位，因此exp只用于已减最大值的非正分数。倒数/rsqrt对规格化尾数按1/256分段插值、指数独立恢复；不是标准库逐bit正确舍入的超越函数。使用这些候选必须重新核对数值/PPL、控制与参数，不能仅因端口是FP32就当相同算法。

KIND6逐档恢复保留每档scale乘法和有序FP32相加。KIND22将POT bin归约提前到整数域、减少浮点恢复和scale乘法；数学实数等价不保证每一步FP32舍入一致，两者分别测试和计费。

所有普通probe输入只在valid时装载；输出在valid时更新，持续时钟仍消耗功率。模块功能仿真测得的边沿延迟不证明100MHz可达；必须先看STA。查表与多级浮点组合路径可能需要流水化；不能把失败的WNS静默忽略，也不能只降低频率而保留原TLM时间。

RMS分为两部分，原x和gamma由外部提供；没有隐藏整向量RAM。实际RMS需要保留x或再读一遍，SRAM/寄存选择仍须在系统中落实。V累加器同样是标量probe，不隐含完整head缓存。最后一次平均/转换/rsqrt在last之前输入隔离，避免名义最后转换、实际每块都翻转。持续输入、同周期first/last、暂停和输出排空均有功能检查。

## 复现

在仓库/便携包根，Python3.10+、Icarus支持SystemVerilog：

```sh
python architecture_tlm/digital_ppa_v1/cycle_audit.py
python architecture_tlm/digital_ppa_v1/sim/generate_roms.py
python architecture_tlm/digital_ppa_v1/sim/validate.py --iverilog /path/iverilog --vvp /path/vvp --ivl-lib /path/ivl --out /new/personal/project/output
```

`cycle_audit.py`需要保留Git原件及PR105指定观察blob；便携RTL包不携带52个大结果，不能在缺少Git原件时伪称完成该审计。RTL验证则可脱离Git运行，以源文件SHA和便携包manifest为据。`--out`必须是全新目录；失败前缀不覆盖。本次没有新的模型推理、PPL、GPU、Slurm、用户工艺DC/PT或实际DRAMSys执行。
