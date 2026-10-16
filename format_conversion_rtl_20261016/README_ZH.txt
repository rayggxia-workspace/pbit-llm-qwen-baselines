数制转换与宽定点/浮点累加比较：RTL及仿真任务
2026-10-16

一、本包做什么，先仿真哪些
=========================
提供可综合SystemVerilog小模块、逐位数值参考、功能测试、统一寄存接口和DC/PT模板。
不是完整FFN/Attention电路，不包含SiLU、Softmax、PRNG、矩阵核或SRAM宏。
输入测试数据在testbench/Python产生，不将测试用随机源计入待测电路。
当前只做功能验证；用户工艺库的DC/PT尚未运行，本包不提供虚构的面积/能量结果。
最终功能验证已通过Slurm CPU作业1587；具体数量与源文件校验见FUNCTIONAL_STATUS_ZH.txt。

建议第一轮：
  独立转换KIND=0、1、3、5、6、8、9、16、17；KIND=11可单独看FP32加法成本。
  累加组合：FIXED=0（FP32每块转换再累加），FIXED=1/ACC_W=40和64（宽定点路径）。
  ACC_W=32是溢出/面积敏感性对照；没有质量验证不能因它最省就采用。
  其他KIND是备选或接口检查，不要求全部先跑PT。

二、哪些地方涉及转换
===================
路径 | 输入→输出 | 对应KIND | 当前是否发生/说明

FFN权重准备
  BF16权重→INT8码、符号/幅度、tile scale：离线，不计每token转换器。
  实际任意scale权重量化在CPU/GPU预处理，本包KIND=2只适用于2幂尺度，不冒充完整离线算法。

FFN入口x
  BF16→A8阈值+符号：0。24层每token共21,504值，gate/up共享同一编码。
FFN中间矩阵g/u
  有符号采样累加count×每块scale→FP32：9；若选BF16内部则用12。
  每token最终逻辑g/u值233,472个；但64输入分块恢复次数更多，见后文。
SwiGLU结果z
  当前软件参考为FP32→A8阈值+符号：1。每token116,736值。
  原来g/u分别编码再AND的旧路径也可复用0/1，本次主路径不增加那两次编码。
FFN down输出
  宽累加/scale恢复→FP32再BF16：9/5后接6；也可直接12/13。
  最终输出21,504值/token。直接转BF16与先转FP32再转BF16可能有双重舍入差异，需分别验证。
64输入块之间
  不同scale对齐到共同定点LSB：8或10；累加后统一转换：5或13。
  每token部分结果4,902,912个，最终三投影逻辑输出合计254,976个。
  不允许把未经scale恢复的原始count直接相加；当前权重scale未必是2的幂。

Attention筛选概率
  已算好的FP32保留概率p→32bit随机字比较门限：17。
  用33bit门限表示0..2^32，确保p=1可全部通过；不是把最大门限截成2^32-1。
  当前2K/64token块/14头/24层，至多10,752个块概率判决；强制块可绕过概率门限。
Attention紧凑QK→Ising配置
  预处理后的FP32分数→有符号16bit定点：3，LSB可配置。
  max/减最大值/温度缩放不在这个编码器内，仍要另外计费。
  当前固定512候选槽时最多172,032有效分数/token；尾块/短上下文实际数可更少。
Attention采样V累加
  若V保持BF16、采用FP32累加：BF16→FP32为7，累加加法为11。
  若样本数N=512，求平均是乘2^-9：15；平均并直接输出BF16可用16。
  N非2幂的除法/乘倒数不在15/16中，不能按免费位移处理。
RMSNorm/RoPE/残差接口
  BF16/FP32扩缩转换可复用6/7；算术本体不属于数制转换。
  实际位置和次数取决于所选算子内部位宽/融合，不能只按软件.float()调用强行复制硬件。

A8不是signed INT8：它是8bit无符号幅度门限+1bit符号。
采样比较器仍在随机计算前端，不包括在本包的数制转换器成本中。
BF16→FP32扩展的组合逻辑近似接线，但寄存、时钟、缓冲和分发仍有成本。
以上表是覆盖清单，不能将互相替代的所有KIND同时加到同一TLM账单。

三、模块文件与接口约定
=====================
rtl/fc_scale_mag.sv：整数幅度×2^shift，RNE与饱和，共用基础电路。
rtl/fc_fp_to_quant.sv：BF16/FP32到概率幅度或有符号量化幅度，参数化。
rtl/fc_fixed_to_fp.sv：宽整数×2^LSB指数到BF16/FP32，支持subnormal。
rtl/fc_float_resize.sv：BF16↔FP32、FP32乘2幂、融合缩窄。
rtl/fc_scale_count.sv：count×24bit系数、共同定点域对齐、浮点恢复。
rtl/fc_fp_add.sv：FP32组合加法器，支持subnormal/特殊值，非FMA。
rtl/fc_accum_compare.sv：两条完整标量跨块累加路径。
rtl/fc_probes.sv：统一表征顶层fc_conversion_probe / fc_accum_probe。
CASES.csv：KIND=0..17各探针的映射；未选generate分支不进入综合。

通用转换顶层：
  clk/rst_n同步低有效复位；in_valid输入握手（无背压）。
  data[63:0]：低16/32bit浮点位模式，或signed int32/int64二补码。
  aux[31:0]：KIND=11的第二FP32输入；其他情况可置0。
  coefficient[23:0]：正scale的整数尾数M；无scale乘法时可置0。
  exp_a/exp_b为signed16bit指数/位移，具体见下。
  result[63:0]低位为有效结果；FP16/FP32和signed8/16码均是低位打包，不做64bit符号扩展。
  概率A8：result[7:0]门限，result[8]符号；其他高位0。
  flags[0]=inexact，[1]=overflow或saturation，[2]=invalid，[3]=tiny。
  tiny表示非零数转为subnormal/零，不是完整IEEE异常标志；flags不改变计算有效性。

KIND=0/1：q=clip(round_even(abs(x)/2^exp_a),0,255)。
  若范围S=2^s，设exp_a=s-8；软件编码的LSB就是S/256。
KIND=2/3：signed symmetric量化，最大幅度127/32767；不是含-128/-32768的非对称饱和。
KIND=4/5/13/14：real=signed_integer×2^exp_a，变浮点。
KIND=8：real=count×M×2^exp_a，定点整数结果代表real/2^exp_b。
KIND=9/12：real=count×M×2^exp_a，直接输出浮点。
KIND=10：signed_integer×2^exp_a，饱和到signed64。
KIND=15/16：real=FP32×2^exp_a，输出FP32/BF16。
KIND=17：clip(round_even(p/2^exp_a),0,2^32)，使用时exp_a=-32。
  负概率钳为0，正无穷钳为2^32，NaN输出0并invalid；随机字须扩成33bit再比较。

从正FP32常数C离线准备系数M/exp：
  normal：M={1,frac23}，exp=raw_exponent-127-23；subnormal：M=frac23，exp=-149。
  Sx和1/T若是2的幂可以合并进exp；若不是，离线形成实际采用的系数再编码。
  系数准备不收费到每token，但每个新count×M的32×24整数乘法必须计费。
  当前系数只支持非负scale；负号已在count中。不可将负scale/NaN/Inf当合法系数。

所有转换采用round-to-nearest-ties-to-even，支持有限subnormal输入/输出。
量化NaN输出0并invalid，量化Inf饱和；整数转浮点溢出输出Inf。
浮点加法NaN采用canonical quiet NaN；FP32→BF16缩窄保留高payload并置quiet位。
这些是明确的参考契约；正式部署如果采用FTZ/其他异常策略，应更改并重新验证。

四、两种累加路径的公平比较
=========================
fc_accum_probe FIXED=0：
  每块count×M → 按exp恢复FP32 → FP32加法累加 → 最终FP32。
FIXED=1，ACC_W=32/40/64：
  每块count×M → RNE对齐到共同LSB → 宽定点加法累加 → 最后一次FP32转换。
最后转换器输入在last之前隔离为0，避免名义“最后转换”、实际每块都翻转。

接口：in_valid、first、last、count、coefficient、coef_exp、common_lsb_exp。
first/last均可与valid同拍，单元素帧可同时first+last；无背压，输入边界寄存一级。
共同LSB在一帧中必须不变；每块coef_exp和M可以不同。
固定累加发生溢出时饱和并sticky标志。正式可用情景应报告无溢出或明确精度影响。
转换探针是一层输入寄存＋一层输出寄存，支持逐拍输入；是否可达100MHz以STA为准。
累加探针每块经输入寄存后在下一沿更新，最后沿捕获结果；关键路径含组合尺度运算。
没有证明该未优化组合结构在55nm下达到100MHz；若不满足须流水/降低频率再比较。

硬件倾向：宽定点减少重复前导零检测、指数对齐/规格化和浮点舍入，通常值得优先尝试。
但它需要更宽的加法器/寄存器、scale乘法、共同LSB对齐，以及最终转换器，所以面积
不保证更小。两条路径用相同count/scale流、帧长度和吞吐目标比较，不能删掉scale成本。

精度：无溢出且scale能精确落到共同整数域时，定点加法没有逐次浮点舍入。
若每块都需右移舍入，对K块、LSB=Delta，额外绝对量化误差上界约K×Delta/2
（仅此步骤，另有最终浮点舍入；不含系数准备误差）。共同LSB过粗会损失小量。
保守位宽起点：32bit count＋24bit系数＋ceil(log2(K))＋块尺度指数跨度。
K=76时约63＋指数跨度bit；真实count范围较小时可缩小，但64bit不保证任意scale精确。
因此先比较40/64bit及溢出/误差，再决定实际位宽。不能宣布与FP32路径逐bit完全一致。
测试中包含1e8+1-1e8：FP32逐次累加可能得到0，足够宽定点可以得到1。
这说明算术顺序可影响精度，不构成LLM PPL验证。
如果最终矩阵输出才进行规格化，调用次数可由4,902,912降到254,976/token，
减少约94.8%的这类浮点恢复调用；scale乘法和每块定点对齐仍在，不能把94.8%
当成总转换能耗或整个FFN的节能比例。是否值得采用由实测与PPL共同决定。

五、我需要你仿真回传哪些信息
===========================
优先采用一套统一55nm PVT；主组建议TT/1.20V/25°C，已有SS/1.08V/125°C可另组跑。
不能用TT转换器与SS其他模块混在一个无标注的总能耗里。
默认100MHz/10ns，输入slew0.1ns、输出负载0.02pF、每lane一值每拍目标。
不随便放宽约束、添加false path，或用修改min delay掩盖真实hold问题。

每个单lane转换器至少三个模式：
  MODE=0：in_valid=0，时钟保持运行，输入配置与数据稳定，得到真实idle功率。
  MODE=1：连续有效输入，得到最大吞吐下active功率、每值动态能量。
  MODE=2：每16拍一个有效输入，看到稀疏调用的寄存时钟/空闲开销。
额外真实trace：如果有x/z/QK/部分结果片段，保持格式与scale契约后替换向量，
  作为最终工作负载功耗；当前提供的是确定种子的有限值合成激励，不是实际Qwen轨迹。

每个累加组合至少比较：
  14块一帧（gu输入896/64）；76块一帧（down输入4864/64）。
  两条路径使用相同count、M、coef_exp。common_exp=-24只是初始测试值，不是PPL最优值。
  同时记录fixed溢出数、inexact数、与高精度参考的误差；溢出的低功耗结果不可当等精度胜出。
  连续/sparse需完成整帧：例如MODE1有效拍数为14或76的整数倍；MODE2总拍数约乘16。

每项需要回传的表格字段：
  case_kind或FIXED/ACC_W；源码hash；PVT/频率/负载/输入scale分布；
  单lane总标准单元面积，以及组合逻辑/边界寄存器/状态寄存器分项；
  active与idle的internal/switching/leakage/total功率（均注明W或uW）；
  有效输入数、完整输出数、帧长度、测量起止、启动/排空是否包含；
  pJ/输入值（转换器）或pJ/帧（累加器），另给pJ/部分结果；
  实际latency cycles和issue interval；setup/hold最差slack及约束违例；
  活动覆盖率、未反标nets/cells、X来源审查；
  组合/寄存器是否被常量折叠或优化、是否插入ICG、是否使用SPEF/CTS。

能量口径：
  实际窗口总能量=窗口Ptotal×时间；先完整报告。
  工作负载增量=(Pactive-Pidle)×相同时间/接受输入数，作为一种额外可比指标。
  idle值包含时钟/泄漏等，增量不能称为全部动态能量；不替代internal+switching分项。
  1uW×1ns=0.001pJ；总功率单位W时E[pJ]=P[W]×t[ns]×1000。
  N=0时不要计算pJ/值；不要把库面积当版图die面积。

六、运行方法
===========
先做开源功能检查（Linux，已装iverilog/vvp）：
  bash sim/run.sh
快速检查：bash sim/run.sh --quick
本包已携带Ubuntu官方iverilog二进制归档，sim/verify.sbatch只在用户目录解压使用。
不要在其他Linux发行版上直接假定其二进制兼容；有VCS时可用同样testbench。
Slurm脚本只申请CPU，未申请GPU。

生成有限值功耗激励：python3 sim/power_vectors.py
功能向量用独立Python整数/二进制有理数参考生成，不依赖宿主float实现舍入。
sim/tb_conversion.sv验证组合与寄存接口；sim/tb_accum.sv验证四条累加路径；
sim/tb_power.sv带结果检查、VCD和window.txt，功耗刺激本身也先做功能检查。

DC环境模板（在本包根目录运行，路径填写本机实际值）：
  export STD_DB=/实际路径/标准单元.db
  export STD_LIB_NAME=实际库名
  export OC_NAME=实际operating_conditions名称
  export CASE_TYPE=conversion
  export KIND=0
  export OUT_DIR="$PWD/results/ppa_case0"
  dc_shell -f flow/dc.tcl

累加器：CASE_TYPE=accum，FIXED=0/1，ACC_W=32/40/64，再选新的OUT_DIR。
flow/dc.tcl只读取普通标准单元，不需要SRAM宏或DesignWare浮点IP。
如果库/工具环境需额外link库，由实际运行者加入并记录，不能用未建模blackbox代替算子。

综合后门级功耗激励示例（在独立SIM_DIR执行，ROOT为本包绝对路径）：
  vcs -full64 -sverilog +define+GATE+KIND=0 \
      "$NET_DIR/mapped.v" "$ROOT/sim/tb_power.sv" -v "$STD_VERILOG" -o simv
  ./simv +MODE=1 +CYCLES=10000 +VECTORS="$ROOT/vectors/power_case0.hex"
每个MODE单独目录，避免覆盖power.vcd/window.txt。
累加器用+define+GATE+ACCUM+FIXED=1+ACC_W=64，向量选择power_accum14.hex/76.hex。
DC参数、testbench宏定义和向量KIND必须一致；GATE模式不重新参数化映射网表。
VCS的库仿真模型路径由STD_VERILOG提供；未执行过这份用户工具模板，需要按工具版本
处理环境兼容，但不允许无记录地改变算术位宽/舍入/流水结构。

PT：提供STD_DB、STD_LIB_NAME、OC_NAME、CASE_TYPE、NET_DIR、SIM_DIR环境变量，
  pt_shell -f flow/pt.tcl
该脚本读取window.txt对应窗口和tb_power/dut波形，报告层次功耗、时序和活动缺项。
没有SPEF时标为pre-layout；不要声称最终物理功耗/时序签核。
功能仿真通过与DC/PT完成是不同状态，本次未替用户运行工艺库DC/PT。

七、文件和交付
=============
结果保存results/functional...日志与source_hashes.json；确切功能检查状态见FUNCTIONAL_STATUS_ZH.txt。
面积功耗结果请分设计/模式目录保存，回传原始报告而非只给一个总功耗数字。
不必一次做18种PT；先完成第一节优先集合和两条累加器，再按瓶颈补测其他探针。
新TLM接入时用这些实测动作费用替换旧6op编码/2op部分和预算的对应部分，防止重复收费。
