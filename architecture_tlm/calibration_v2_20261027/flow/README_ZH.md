# 校准流程：先功能，再综合/STA，最后门级活动功耗

本目录提供可移植的DC、VCS、PrimeTime脚本；本次仅做主机端流程测试，没有运行许可EDA。旧Issue193的report_lib解析器按原字节复用，所有新脚本独立。不要将脚本可运行理解为已经500MHz通过。

## 先填什么

复制library.example.json到工艺私有目录，填target_db、reference_cell和verilog_models；填写实际corner、voltage_v、temperature_c。库本体、综合网表、私有路径和license信息不要上传GitHub。脚本读实际report_lib，核对电压、温度和1ns/1pF单位；不匹配立即失败。

门控分三种：

- GATE_MODE=0：无ICG基准。
- GATE_MODE=1：仅库无关功能模型，本流程禁止综合。
- GATE_MODE=2：必须给icg_cell和icg_wrapper；wrapper由包内common/make_icg_mapping.py生成，接口pbit_icg_tech(clk,en,test_en,gclk)。实际库须高有效EN/TE、低电平锁存使能、同相输出；不同极性不得盲目映射。flow定义PB_ICG_TECH_MAPPED，综合网表必须存在真实ICG实例，PT输出gating setup/hold报告。没有库名时先跑MODE0，MODE2保持待配置。

## 推荐首轮

先B4/T64、B7/T128，M1，六级/三级流水，不门控；每项100MHz、seed17，continuous与idle。确认功能和时序后再跑M8、MODE2、250/500MHz、三seed及wake/stall。不要一开始提交全部组合。

在calibration_v2_20261027目录下：

    python flow/make_counter_cases.py --output cases100
    python flow/run_case.py --case cases100/CASE.json --library /private/library.json --output /private/run_preflight
    python flow/run_case.py --case cases100/CASE.json --library /private/library.json --output /private/run_synth --stage synth
    python flow/run_case.py --case cases100/CASE.json --library /private/library.json --output /private/run_gate --stage gate_sim --reuse-synth /private/run_synth/synth
    python flow/run_case.py --case cases100/CASE.json --library /private/library.json --output /private/run_sta --stage sta --reuse-synth /private/run_synth/synth
    python flow/run_case.py --case cases100/CASE.json --library /private/library.json --output /private/run_power --stage power --reuse-synth /private/run_synth/synth --windows /private/run_gate/auto_windows.json

CASE替换生成的具体文件名，每次output必须新建，旧目录不覆盖。gate_sim只编译mapped.v+工艺Verilog模型+专用TB，不能再把原RTL并入同一仿真。数字算子每个top使用自己的bench和输入，不拿counter bench替代；case.example.json展示真实数字接口格式；用下方生成器把case与实际fixture一起生成，不能只复制example而遗漏向量。

实际bench应支持+PERIOD_NS、+VCD，并输出WINDOW start_ns=... end_ns=... frames=... accepted_samples=...。flow自动生成窗口文件，counter的frames是完成输出帧数；M8一帧包含8输出，在operation_unit记录，不能与M1每输出能量直接比较。数字bench须把frames定义为完成结果数量，并填写不同operation_name。若自己的bench格式不同，按windows.example.json从真实事件统计填写；不猜操作数量。

## 时序与门控

100/250/500MHz分别对应10/4/2ns。默认setup uncertainty为周期5%（0.5/0.2/0.1ns），可在case显式修改；hold uncertainty/transition默认0.05ns，I/O max delay默认周期10%，min为0.02ns，负载0.02pF。它们是首轮假设，必须与用户的IO/fanout/约束一致后比较。同步rst_n保持正常计时，无false-path、多周期或hold豁免。

从STA读取真实setup/hold slack，负值保留not_met。延迟L、启动间隔II来自RTL行为，不可用period直接推导。没有P&R/CTS/SPEF，零延迟门级活动不能覆盖时钟树与互连/glitch的全部开销。门控setup/hold报告必须检查；cell存在并不自动证明门控功能正确。

## 每个功耗窗口必须保留

continuous（连续工作）、sparse（间歇）、idle（时钟开着但无工作）、wake（关钟后唤醒）和stall（输出阻塞）分别测。对MODE0同样运行同事件日程，才能公平比较门控。

输出保留源文件/库/网表/VCD/窗口SHA，实际工艺、时钟、约束、面积、setup/hold、功耗单位、activity/check_power、分层及逐单元报告。功耗由internal+switching+leakage构成；别将clock_network与已含时钟引脚的cell表重复加总。

功率解析只接受明确W/mW/uW/nW/pW单位；缺失为null。每操作毛能量=总功率×窗口时长÷真实操作数；idle没有每op。动态能量为internal+switching。增量能量要另取同口径idle相减，不能把毛能量、idle和增量重复相加。

当前覆盖率报告格式依PT版本不同，flow保留coverage.rpt、activity_boundary.tsv和check_power，不擅自填100%。所有power均CALCULATED_PROVISIONAL/activity_status=REQUIRES_REPORT_REVIEW；读回真实叶引脚覆盖/XZ、库表外推、gating报告后才能标注可用。警告不因工具exit0消失；时序失败的数据只能作为该活动下的条件功耗，不得作为该频率已实现性能。

## 回传与台账

回传RESULT.json、configuration.tcl脱敏副本、pvt.txt、units/area/setup/hold/constraints/check_timing/gate_setup/gate_hold、power/hierarchy/cells/coverage/checks/activity_boundary、输入和操作数manifest。工艺库、mapped.v/ddc、完整大VCD留私有存储，回传大小和SHA索引即可。

根任务将结果登记digital_circuit_simulation_registry。没有真正运行DC/PT时只登记功能/流程已验证，不登记新PPA。run_case默认preflight不会消耗EDA许可；只有显式指定--stage才运行工具。

主机测试：python flow/test_flow.py。每个测试中的假文件仅用于路径/状态/解析拒绝机制，不是工艺数据。

复用综合时必须同时保留原运行RESULT.json及synth/mapped.v。脚本核对top、频率、全部约束和RTL/库/网表SHA；频率改变需要重新综合，不把旧频率网表悄悄当新配置。功耗窗口同样绑定top、周期、网表和VCD SHA；手工窗口必须补齐这些字段，否则拒绝。

面积保持area_library_units原值。只有在library JSON填写area_scale_um2及area_unit_source（.lib/LEF/编译器文档依据）后才生成area_um2，否则为null。不要将库area无条件写成平方微米。
MODE2需icg_enable_pin及icg_test_enable_pin（实际EN/TE）。PT报告到这些真实ICG端点的max/min路径并保存slack；还须报告明确识别clock gating检查。无路径、缺slack或不能确认gating路径时返回review_required，不能标为可用频率；负门控slack返回not_met。

数字bench的plusargs支持{CASE_DIR}和{RUN_DIR}，例如+VECTORS={CASE_DIR}/vectors.txt、+OUTPUT={RUN_DIR}/trace.txt；前者指case JSON所在目录，后者指本次新gate_sim目录，避免覆盖原验证trace。
首次使用本流程尚需用户工具环境的真实DC/VCS/PT smoke；本机29项测试只验证配置、解析与Tcl文本完整性，不证明某个许可证版本支持全部命令。遇到工具语法错误应保留FAILURE和日志后适配，不能跳过检查冒称成功。

## 数字算子：生成绑定到实际向量的用例

    python flow/make_digital_cases.py --output digital100
    python flow/run_case.py --case digital100/dig_fp32_add_continuous_f100_s17/case.json --library /private/library.json --output /private/add100 --stage all

默认生成FP32 add和BF16乘后加FP32两种top，各continuous/idle窗口；增加`--tops dig_fp32_mul dig_bf16_mul dig_fp32_to_bf16 dig_bf16_mac8 dig_bf16_accum dig_bf16_context16 --modes continuous idle stall`可展开。`--frequency-mhz 250`或500会重新生成对应真实时钟窗口。全部先生成数据，没有自动调用EDA。

每个case同目录生成vectors.txt、独立整数oracle的expected.json、FIXTURE.json。flow在preflight核验两份数据SHA、top及周期；VCS输出后运行prepare_power.py的逐周期ready/valid/输出值/status检查，再核验WINDOW的起止时间、完成事务数和接受输入数。任何不匹配都失败，不以sim退出0代替结果校验。数据与验证脚本SHA写入RESULT.json。

一个MAC8事务包含8个乘法和8个加法；每事务能量不能直接冒称每个MAC能量。case同时保留primitive_operations_per_transaction和macs_per_transaction，后续按明确单位换算。单context累积II=15；16context轮转可II=1，但同一context仍II=15。这些元数据来自RTL功能验证，时序是否支持目标频率仍由STA决定。数字活动为合成普通浮点数分布，不是Qwen真实激活；本轮数字top未声称有ICG门控，MODE0只是其原始校准。
