# 精确合并档位计数器：RTL与功耗校准入口

本目录实现N64固定W8（7bit幅度+独立符号，排除−128）、B4/T64和B7/T128的精确随机事件归约。随机数、比较器、权重SRAM、公共系数恢复/舍入都在模块外。

## 计算结构与数值合同

旧结构逐档计算 `counts[b] = sum_t,n(event[n,t] * signed_weight[n] * (bin[n]==b))`，最终将各档乘以 `2^(2*(BINS-1-b))` 后求和。

新结构先将每个输入的有符号权重按档位左移对齐，再用一棵树和一个时间累加器求和。`out_sum[m]` 等于旧结构各档对齐后的精确整数和，不是概率均值、不是BF16，也尚未乘coeff/做RNE。后续公共系数与一次最终舍入仍需连接恢复模块。

- 每个输入仅属于一个档；无效档号贡献零，与旧RTL一致。
- 负数先符号扩展，再左移；无中间截断、近似OR或饱和。
- B4/T64：叶子14bit、树15～20bit、累计26bit；B7/T128：20bit、21～26bit、累计33bit。
- BINS在每个固定top中是静态参数。本包没有在B7运行时直接复用B4 bin编码的动态切换；如后续支持，需要显式配置档位的最大移位。
- 所有权重/符号/档号必须从frame握手至out握手保持不变；模块内不额外复制权重寄存器。

| B7，2048输出 | 流水数据位 | 最终累计位 |
|---|---:|---:|
| 旧七档、六级寄存 | 8,945,664 | 301,056 |
| 新合并、PIPE_EVERY=1 | 2,826,240 | 67,584 |
| 新合并、PIPE_EVERY=2 | 970,752 | 67,584 |

这些是RTL结构位数，不包含控制/valid/ICG、组合逻辑或外部存储，不是面积和功耗测量。

## 接口、流水与门控

正式RTL在`rtl/sc_counter_merged.sv`。`rtl/counter_tops.sv`提供16个固定top：

`counter_b{4|7}_t{64|128}_m{1|8}_p{1|2}_g{0|2}`。

B4固定T64，B7固定T128。`p1`在六个加法层后都寄存；`p2`仅第2/4/6层后寄存。每个输出的时间累加器仍是一拍反馈加法器；若实际STA失败，必须调整结构或II，不能只补流水而声称反馈吞吐不变。

- `frame_valid && frame_ready`接收一个新帧并清空累计。
- RUN状态中`sample_valid && sample_ready`接受一个N位事件向量；sample II=1。
- 第T个接受事件后进入DRAIN；末样本边沿到`out_valid`分别6拍/3拍。
- 输出累计寄存器直接充当输出保持；回压期间保持不变。输出握手后回到IDLE，再接受下一帧。
- 无stall时，从frame接受到out_valid为`T+6`/`T+3`拍，最早输出握手再晚1拍。帧间还包含恢复IDLE后下一次frame接受的控制开销。II1指帧内样本，不是整帧每拍一个输出。
- 同步低有效复位；须在时钟低相位及后续上升沿前满足建立时间，至少跨过一个有效上升沿，确保关闭的数据时钟被复位请求打开。

`GATE_MODE=0`为不开门控；`GATE_MODE=1`仅供库无关功能仿真；`GATE_MODE=2`必须映射真实库ICG。门控模块来自`../common/pbit_icg.sv`，未映射不得综合真实门控版。

本版按一个M输出数据bank门控，控制器和valid/last始终运行；reset、frame清零、接受事件以及流水仍有valid时保持数据时钟开启。流水排空后关闭；test_en可强制开钟。叶子还用sample_fire隔离无效样本翻转。

**这是按实际数据有效状态开/关钟的校准实现，并未实现旧TLM的“空闲8拍再关、固定1拍唤醒”计时器。** 同步请求在低相位及时打开ICG时，frame不插入额外唤醒气泡。工艺STA必须检查ICG使能时序；TLM应按真实实现回填，不把本版当作旧80%门控假设已经得到验证。

## 功能验证

```
python counter/tests/verify_counter.py --output NEW_OUTPUT --icg common/pbit_icg.sv
```

可用`--iverilog`、`--vvp`、`--ivl`指定工具。Windows的`--ivl`内部转为原生路径；Icarus可能无法处理正斜杠的库路径。

测试同时实例化：原193计数器+档间精确对齐、新版不开门控、新版行为门控；三者再与独立Python无限精度整数oracle比较。`tests/reference_ffn_counter.sv`为原件只读副本，原SHA在`REFERENCE_SOURCE.json`；它只供验证，不加入新设计综合。

完整验证已通过16配置、128完整帧（约989.56秒软件墙钟），见`results/functional_summary.json`；软件运行时间不是硬件延迟。覆盖M1/M8、B4/B7、两种流水；M1用seed17/31/193，M8用seed17；每配置8完整帧，零/最大正/最大负/抵消/各档/无效档/IID/32层分层事件，另外有中途复位、排空中复位、输入暂停、输出回压、实际停钟和test_en开启检查。只验证给定事件流，未模拟真实p-bit相关性或LLM质量。

## 用户运行功耗校准

`tests/tb_counter_power.sv`例化固定`DUT_TOP`，可直接用同名综合后网表替换RTL。只对`dut`层级dump，测试平台PRNG和oracle不进入DUT功耗。

编译宏：`DUT_TOP`、`DUT_M`、`DUT_BINS`、`DUT_T`、`DUT_AW`。运行参数：

- `+MODE=continuous|sparse|idle|wake|stall`
- `+PERIOD_NS=10.0`或`2.0`；这只是激励周期，不能证明100/500MHz时序通过。
- `+FRAMES=8 +SEED=17 +P8=128 +VCD=activity.vcd`。
- `+THRESHOLD_PROFILE=swept|uniform +THRESHOLD_SEED=193`；或`+THRESHOLD_FILE=per_lane.hex`回放64个十六进制阈值（0..256）。

连续/间歇/唤醒/输出stall分别计独立窗口；idle窗口没有有效操作，不能除以零或伪造pJ/op。stdout的`WINDOW start_ns=... end_ns=... frames=... accepted_samples=...`给出实际窗口、完成输出帧和接受事件向量数；一个样本是64输入的一拍，不是单个乘积。每帧结果数为M，输入事件数量为N*T；恢复/非线性不在本DUT。

激励使用固定帧内权重和档号，权重为合成均匀幅度。默认`swept`在P8中心±64范围生成64个逐输入阈值，夹到0..256，按独立threshold_seed随机排列；同一拍仍只用一个共享R8，各输入分别比较。边缘P8经夹紧后的均值不必等于P8，实际阈值列表为准。`uniform`保留同阈值、64位全同的强相关对照；`THRESHOLD_FILE`可回放真实逐输入阈值，文件不足64项或含未知值/越界将拒绝。

每次写出`thresholds_used.hex`，打印profile/原始threshold_seed/阈值列表；窗口输出也带profile/seed，汇总包含阈值SHA。各模式都先在测量窗口外完成一帧预热，idle测保留状态而非仅复位全零。上述仍是合成切换场景，不冒称真实Qwen权重或概率分布。建议三seed×五窗口，并可扫P8=32/128/224。旧PT若激励/边界不同，不是严格同输入A/B比较。

`verify_power_bench.py`验证20个默认swept窗口、uniform/文件回放/非法短文件3项和16top展开。旧统一阈值的首轮验证在`power_bench_uniform_legacy_summary.json`单独保留，不与新版混称。其中g2使用**显式FUNCTIONAL_ONLY mock**检查接口路径，不是实际ICG或PPA证据；用户工艺flow不得使用该测试替身。真实库门级仿真需按flow说明提供库模型、ICG映射与活动覆盖检查。部分Windows vvp在`$fatal`后仍返回0；检查必须同时要求PASS标记并拒绝FATAL，不能只看进程退出码。

期望回传面积、setup/hold及ICG timing检查、真实频率/PVT、电压、内部/切换/泄漏功率、窗口长度、有效计数、活动覆盖与所有告警。新旧比较须保持工艺、频率、电压、激励和模块边界一致，不将未通过时序的配置标为可用。
