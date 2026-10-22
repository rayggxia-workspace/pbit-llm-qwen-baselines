# 交给55nm工艺库的仿真任务

最新范围请先读[LATEST_TLM_RTL_GAPS_ZH.md](LATEST_TLM_RTL_GAPS_ZH.md)：真实随机源接入后，新增的驻留/阵列/前端/完整采样FSM与带宽验证不能仅靠下方现成标量probe完成。以下仍是已有RTL包的实际送仿说明，不声称包含所有拟新增模块。

## 先测什么

先测KIND4/5（64值动态分档编码）、6（逐档恢复）、0（跨块FP32加法）、21（缩窄）、7（FP32 SwiGLU候选）、8（V累加）。这些对应当前时间代理的重要部分。KIND22作为融合恢复对照单列；不先用它替换原算法。

然后测9/10/11/12/13/20以补RMS、准确Softmax、平均、RoPE；14/15/16/17补比较交换、压缩/CDF和全宽结果的数字归约。随机源/p-bit本体和随机矩阵阵列不在本任务内。

已有格式转换probe继续沿原路径使用，不必重复重写；旧Q10 SwiGLU功耗也保留作不同数制的参考，不能当FP32实测。SRAM内部继续用已有库/校准结果，DRAM继续使用命令级模型/已有参数；本包不重造SRAM宏或DRAM PHY。

## 一套条件统一跑

建议先沿已有100MHz/10ns表征点：TT1.2V/25°C、SS1.08V/125°C分别报告，二者不混成一套芯片。默认输入slew0.1ns、输出负载0.02pF/bit、输入输出max1ns/min0.2ns、setup uncertainty2ns/hold0.1ns，与旧单元表征可核对。实际库若不适用，记录修改而不是无声换条件。

DUT不含测试用随机激励。`sim/tb_power.sv`的整数xorshift只在testbench生成合成数据；不计入芯片随机源。21种KIND都用连续、间歇、idle三种模式；外部数据在idle仍翻转，DUT输入寄存器隔离。用户实际激活轨迹到位后应再补真实分布，不能把合成均匀活动称作LLM实测。

## DC/VCS/PT操作

`flow/dc.tcl`、`flow/pt.tcl`是模板，尚未在用户许可工具/工艺库上运行。填写ROOT/STD_DB/OC_NAME，不上传库本体。例：

```sh
export ROOT=/absolute/repo_or_bundle_root
export STD_DB='/actual/standard_cell.db'
export OC_NAME=actual_operating_condition
export CASE_TYPE=arithmetic
export KIND=6
export OUT_DIR=/new/dc_kind6_ss
dc_shell -f "$ROOT/architecture_tlm/digital_ppa_v1/flow/dc.tcl"
```

时序不满足10ns时，先回传WNS/TNS/关键路径和可达频率。当前多个组合浮点路径很长，必须允许结果显示“不满足”；若需要流水线，改变RTL后重新做数值、有效信号和PPA验证，再更新TLM的latency/II。不要为了得到一个漂亮数字放宽时序后仍保留原吞吐。

算子门级活动，在每种模式的独立目录运行：

```sh
vcs -full64 -sverilog +define+GATE+KIND=6 \
  /new/dc_kind6_ss/mapped.v \
  "$ROOT/architecture_tlm/digital_ppa_v1/sim/tb_power.sv" \
  -v /actual/standard_cells.v -o simv
./simv +MODE=1 +CYCLES=4096 +SEED=20261022 +VCD=power.vcd
```

MODE0为idle，1连续，2每64拍前16拍有效。默认100MHz；修改TB半周期必须与DC/PT时钟一致。CYCLES须为128的正倍数，默认4096；三种子20261022/7/1234567。标量累加帧为16输入，CDF帧32区间；这是可重复表征活动，**不是Qwen实际14/76块帧**。要比较真实帧能量，按实际14/76或S128/512重新提供完整帧激励，不能用帧长度16的总能量直接替代。

`window.txt`由TB实际记录开始/结束、接受输入和完成输出，窗口包含32拍排空。PT读取同一份window，不把整个仿真/reset/warmup平均功率混进去：

```sh
export NET_DIR=/new/dc_kind6_ss
export SIM_DIR=/actual/mode1_seed20261022
export OUT_DIR=/new/pt_kind6_ss_mode1
pt_shell -f "$ROOT/architecture_tlm/digital_ppa_v1/flow/pt.tcl"
```

无SPEF/SDF/CTS时标为布局前；不要把寄存器时钟引脚功耗称为真实时钟树。门级有实际延迟时优先用同网表/SDF及寄生活动，报告映射覆盖、X/Z、未标注nets/cells。模板不提供虚构的库数值、power单价或时序成功结论。

存储外围另设`CASE_TYPE=router|dma`，模板综合的是与功能TB匹配的小配置（4端/16bank/DW32/ROW4，DMA窗口4）。使用`sim/tb_memory.sv`，门级编译加`+define+GATE_ROUTER`或`GATE_DMA`，同时编译另一种未映射控制模块的RTL和标准单元模型；`+VCD=power.vcd`生成轨迹。PT分别采用`tb_memory/router`、`tb_memory/dma`及各自window，宏/测试用存储不在待测模块里。该轨迹只有4次SRAM请求和35次DMA突发，用于接口/计费校验，**不是足够代表真实系统的功耗分布**。最终需按16×128b/ROW12、窗口32和实际请求序列补门级活动；默认模块可参数化，但不能只乘缩放系数就宣称满足16GB/s。真实库宏读出延迟/使能/保持必须按厂商端口接入，这不由RTL数组替代。

数组顶层`nr_fp32_array`、`nr_bf16_mac_array`支持lane数参数。先单lane，再测16/64lane；512MAC/周期只有在512lane算术、供数和布线都落实后才成立。数组功能样例是4lane，本轮没有16/64/512lane版图或PPA；共享控制、时钟和跨lane互连不能按零成本添加。

## 请回传的结果

| 字段 | 要求 |
|---|---|
| 版本 | 源/ROM/约束/网表/激励SHA，KIND和所有参数，工具/库版本/PVT |
| 面积 | 总标准单元、组合、时序、寄存器数量；是否包含边界寄存、ICG和CTS |
| 时间 | latency边沿定义、实际II、Fmax、setup/hold WNS/TNS、关键路径、违例 |
| 功率 | 每mode/seed的internal、switching、leakage、total，注明W或μW |
| 活动 | window开始/结束、输入/输出数、帧长、backpressure、覆盖率、X/Z/SDF/SPEF |
| 能量 | 完整窗口能量、每输入值/每输出/每帧；idle只报功率，不除以零 |
| 归属 | 宏内/外围/逻辑/时钟分别，避免完整核价格与子模块重复计费 |

`E[pJ]=P[W]×t[ns]×1000`，或`P[μW]×t[ns]×0.001`。可额外报告`(Pactive−Pidle)×t/N`作为增量，不能替代完整total或称作所有动态功耗。

KIND6每次输出是一个64输入块的部分和，相当于旧TLM的72个SC_restore代理op。**不能把一次整个恢复器的能量再乘72次。** 编码器每次处理64值，不能把组能量当每值能量；流式累加器区分每输入与整帧。KIND22改变运算融合/舍入，需另跑质量检查后才可进入系统。

## 怎样回填TLM

先确定真实实例数量和服务契约（latency/II/能否重叠），再替换对应stage时序；能量按真实动作单位替换，删除被覆盖的旧代理项。数组和边界状态只计一次；随机源账本保持接口。随后重跑同配置TLM，核对字节/容量/周期守恒。当前冻结52结果保持原件，新结果必须写新目录和执行SHA。
