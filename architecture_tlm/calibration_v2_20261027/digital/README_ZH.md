# 数字算子校准候选：分段流水、实际反馈与可重复功耗激励

本目录是新写的可综合 SystemVerilog，不含 `real` 算术、DPI、浮点IP黑盒或仅在完整组合算子之后追加延迟寄存器的做法。仿真器使用的 `real period_ns` 只出现在测试台时钟中。

这里提供电路和功能依据，**尚未通过55nm综合、STA或PT，也未证明500MHz可达**。不要把本模块的已知RTL拍数当作该频率的时序验证。需要先测真实面积、活动功耗、开钟idle和关键路径，再替换旧2pJ/MAC等代理。

## 固定顶层与算什么

| 顶层 | 功能 | 无阻塞输入接受到输出握手 | 独立事务II | 额外说明 |
|---|---|---:|---:|---|
| `dig_fp32_add` | FP32加法 | 7拍 | 1拍 | 解码、对阶、加减、前导零、规范化、舍入、打包分开 |
| `dig_fp32_mul` | FP32乘法 | 7拍 | 1拍 | 24位有效数拆四个12×12乘法，再两级加权归约、规范化、舍入/打包 |
| `dig_bf16_mul` | BF16×BF16→FP32 | 7拍 | 1拍 | 采用相同分段结构；常量低位允许综合裁剪成有效8×8乘法 |
| `dig_fp32_to_bf16` | FP32→BF16 | 2拍 | 1拍 | RNE、特殊值处理；单独测转换成本 |
| `dig_bf16_mac` | 先BF16乘积转FP32，再加FP32外部c | 14拍 | 1拍 | **非融合**MAC；c和异常状态随各级stall同步 |
| `dig_bf16_mac8` | 8路独立上述MAC | 14拍 | 1拍 | 每次握手8个MAC；不是8输入点积归约 |
| `dig_bf16_accum` | 一个真实32位反馈累计状态 | 14拍 | **15拍** | 必须等上次结果被消费后才能接受下一输入 |
| `dig_bf16_context16` | 16个真实累计context，共用一个MAC流水 | 14拍 | 轮转独立context可1拍；同context15拍 | 不隐藏累计寄存器及tag队列；热点context显式背压 |

“7拍”指输入在边沿c被接受，无阻塞时最早在c+7边沿输出握手；输出valid会在c+6边沿之后可见。全局弹性阻塞下周期数可变。所有模块均支持下游回压，阻塞时合法输出、状态、context标签保持。

FP32乘法器中的四个乘法有输入数据寄存、部分积寄存、两级归约寄存；加法器的对阶、加减、前导零检测和移位也分开。因此不是把旧组合核包成一个虚假的多拍核。不过12×12乘法、48位加法、前导零/移位和舍入仍可能成为500MHz关键路径，真实结果出来后需要迭代。

## 数制和异常合同

- 输入subnormal先变为同符号零（DAZ），并标记`input_flushed`。
- 有限正常数据采用round-to-nearest ties-to-even。下溢边界先按FP32的渐进下溢格点判断舍入，**能舍入到最小normal的结果保留**；其余subnormal输出变为同符号零（FTZ）。因此不是完整IEEE渐进下溢实现。
- 示例`0x00800000 × 0x3f7fffff`在舍入后保留`0x00800000`，不会因为“先按24位正常精度舍入再FTZ”的不同规则被清零。独立整数oracle专门覆盖这个边界。
- NaN统一输出`0x7fc00000`；BF16输出NaN为`0x7fc0`。Inf按操作处理；Inf−Inf、Inf×0以及NaN输入标为`invalid_or_nan`。这个标志不是严格IEEE区分qNaN/sNaN的exception flag。
- `status[4:0] = {invalid_or_nan,input_flushed,output_flushed,overflow,inexact}`。FTZ改变非零数值时置`output_flushed`和`inexact`；DAZ单独用`input_flushed`记录。
- 溢出为对应符号Inf，置overflow和inexact；精确抵消为+0。两个零相加只有两者都为−0才为−0；乘法零符号为两输入符号异或。
- BF16乘法顶层a/b仍为32位端口，但**只用低16位**；转换顶层y低16位有效，高16位为零。转换的b端口保持统一接口，未参与运算，综合可裁剪。
- 不把非融合MAC等同GPU FMA或不同归约顺序。要比较严格模型数值，必须采用同一舍入、FTZ和累加顺序，必要时另加融合/渐进下溢版本。

## 反馈与存储不能漏掉

`dig_bf16_mac8`的c由外部输入，**没有包括c的SRAM/寄存器存储和供数成本**。不能凭它的II1宣称一个累计状态每拍反馈更新。

`dig_bf16_context16`显式含16×32＝512位累加寄存器、16位busy、16×4＝64位tag FIFO，以及指针/占用计数。输入context忙时返回`in_ready=0`。在输出被接受时才更新对应累计值并释放busy。16context轮转可覆盖14拍MAC反馈延迟；重复一个context仍需15拍。最终跨context求和不在这个模块内，必须另计能量、时延和可能的数值顺序变化。

该版本的寄存器`if(valid)`是数据保持，不是实际ICG门控。数字算子的时钟始终输入，连续/idle PT能测出这项成本。整块idle门控或每段ICG需要额外实现与验证，不能把当前CE冒充时钟已关闭。

## 功能验证入口

```
python tests/verify_digital.py --output /new/output/digital
python tests/verify_context.py --output /new/output/context
```

可以用`--iverilog`、`--vvp`、`--ivl`给路径；Windows的Icarus `-B`库路径需使用原生反斜杠。输出目录必须是新目录，不覆写原件。`--vcd`可生成波形，默认不生成大量VCD。

6类独立算子/8lane×3seed和两类反馈累计×3seed：共24项。检验包括独立任意精度整数oracle、全部特殊值类别、对阶/抵消/舍入/下溢边界、随机正常数、强回压、连续输入、间歇输入、idle唤醒和途中复位。context测试另核对busy、FIFO标签、实际累计值、存储占用、热点阻塞和真实II。

源码末尾没有仿真替代算术；可按相同顶层综合后，用同一固定顶层TB替换为mapped.v及用户库模型复放。

## 功耗校准入口

功能向量刻意包含NaN/Inf/极端值，**不直接作为代表性LLM功耗活动**。先生成另一个有明确统计范围的normal合成激励：

```
python tests/prepare_power.py --top dig_fp32_add --mode continuous --seed 17 --period-ns 10 --output /new/fixture
```

top可选表中的8项；mode可选continuous、idle、stall。输出`vectors.txt`、`expected.json`、`FIXTURE.json`。普通输入采用正负随机normal，FP32 a/c指数在123～131、b在122～130，尾数均匀；context累计激励采用a/b指数121～132。无特意增加零或稀疏率降低功耗，**仍是合成活动，不是Qwen运行trace**。

FIXTURE给出TB名、编译defines、plusargs、窗口起止ns/周期、输入接受数、输出握手数和每事务操作数。典型：

```
iverilog -g2012 -s tb_digital -DDIG_TOP=dig_fp32_add -o sim.vvp rtl/*.sv tests/tb_digital.sv
vvp sim.vvp +VECTORS=/new/fixture/vectors.txt +OUTPUT=/new/run/trace.txt +VCD=/new/run/wave.vcd +PERIOD_NS=10 +WSTART_CYCLE=64 +WEND_CYCLE=640
python tests/prepare_power.py --check-fixture /new/fixture --trace /new/run/trace.txt
```

MAC用`tb_mac`和`MAC_TOP`/`MAC_LANES`；反馈核用`tb_context`，单context需`SINGLE_CONTEXT`，16context不加。固定top列表和defines以FIXTURE为准。TB输出统一`WINDOW start_ns=... end_ns=... frames=... accepted_samples=...`，记录实际硬件握手；在门级复放后重新核对窗口，不只复用RTL计数。映射网表时避免同时编译同名RTL顶层。

功耗单位请分别记录：总窗能量/完成事务；MAC8再除8得到每MAC成本；已包含乘法和加法，不重复加价。idle没有有效事务，报告功率和泄漏，不能除以零计算“每MAC能量”。总能量与减去匹配idle的活动增量分开，不能同时叠加。另记录clock pin/clock network包含关系，避免重复计费。

必须回传：工艺/PVT/电压/时钟约束、source SHA、激励SHA/seed/窗口、功能结果、setup/hold关键路径、面积、internal/switching/leakage、活动反标覆盖及check_power警告。100/250/500MHz是测量目标，不是本包的保证；先跑100MHz与500MHz各代表性核，失败保留负slack再调整流水。
