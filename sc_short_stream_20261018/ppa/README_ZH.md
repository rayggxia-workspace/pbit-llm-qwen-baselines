# 交给工艺环境的最小DC/PT任务

本目录只提供脚本模板，不含工艺库、许可证配置或芯片PPA结果。目标是为新A8共享64短流核提取数据，替换旧12位独立随机字+DFF核的功率代理。

先运行包内功能测试。随后用同一55nm库、原SS 1.08V/125°C、100MHz、相同IO驱动/负载/不确定度，表征定型的IID4096、IID128、分层128、分层64、枚举256；需要同T排序控制时加IID64。默认保持ACC_W27，再单独综合分层128的22位、分层64的21位优化版。

每个定型top单独建输出目录。内置源完整top、external-source compute top、sampler-only top分别综合，源/前端能在多个输出列之间共享，不能按输出列数重复乘完整top的源功耗。实际top列表、源文件与VCD命令见包的RTL说明。

## 先综合，再生成门级活动，再PT

1. 设置模板要求的环境变量，运行`synth_template.tcl`；确认库、corner、面积和时序报告。脚本的10ns即100MHz，默认不造手工ICG。所有模式使用相同约束，不将测试中的固定W/q通过case_analysis综合成常量硬件。
2. 用得到的`mapped.v`和用户可用的标准单元Verilog仿真模型，连接包内相同接口的power TB，生成门级VCD。保持同一配置、种子、帧边界和输入负载。先按golden逐拍验证输出，再进入功耗；若用SDF，标注为带时延结果。
3. 只截取1启动拍+T个有效拍对应的活动窗口，记录实际start/end/clock/valid；排除reset、seed和配置阶段，另单独记录配置能量。RTL层生成的VCD可做活动检查，不能不核映射就直接当作综合网表全部节点的活动。
4. 用`power_template.tcl`读取匹配的网表、SDC和门级active VCD。核实际注释覆盖、未建模单元、slew/load超表、timing和时钟报告；别将成功退出等同所有报告合格。

`synth_template.tcl`必需变量：

| 变量 | 填写内容 |
|---|---|
| TOP_NAME | 包内一个定型模块名 |
| STD_LIB_DBS | 同一corner的`.db`文件Tcl列表；库文件不放入公开交付 |
| SC_RTL_SOURCES | RTL源文件绝对路径Tcl列表 |
| OPERATING_LIBRARY / OPERATING_CONDITION | 从实际库读取的名称，不根据文件名猜测 |
| INPUT_DRIVER_CELL | 延用旧实验的真实驱动单元 |
| OUTPUT_LOAD_LIB_UNITS | 延用旧负载，单位按库，不默认认为fF |
| INPUT_DELAY_NS / OUTPUT_DELAY_NS / CLOCK_UNCERTAINTY_NS | 与旧同频比较的实际约束 |

PT另外需要`MAPPED_NETLIST`、`SDC_FILE`、`ACTIVE_GATE_VCD`、`VCD_STRIP_PATH`。strip路径用实际TB/DUT实例层次；不能照抄其他包的层次。保留完整输入/输出逻辑，不加不适用的false path。

## 最好返回一张总表

每行一个top×case×seed，建议3个种子。case至少包括全0、q=1/2的小概率、q约26、q约128；最好再加真实Qwen x/z和W tile片段（另存hash，不上传受限模型内容）。

| 字段 | 含义 |
|---|---|
| 模式/T/ACC_W/seed/case | 必须能复现 |
| 有效样本数/完整窗口ns | 核1启动+T接受，停顿另列 |
| 总功率/内部/开关/泄漏 | 单位明确，给frame能量nJ |
| 源、前端、空间计数、时间累加分项 | 从实际保留层次报告，不虚构不可分解单元 |
| 总面积/时序/寄存器数量 | 原标准单元单位与面积单位写清；不是die area |
| 载入/seed/config能量 | 与计算窗口分开，后续按重用次数摊销 |
| 模型与活动检查 | 缺失注释、超表、X/Z、输出golden一致性 |
| 版本/环境/SHA | RTL、TB、约束、库版本标识、网表、波形、工具版本与报告hash |

权重/概率/符号是外部帧内稳定总线，因此独立compute top不包含SRAM或外部保持电路。请将SRAM读取、保持和数据分发另列回填；外部总线不代表SRAM能无代价并行给出所有位。对比旧全寄存器核时必须先对齐这个边界。

内置源含32位工作状态与seed_load逻辑；`seed_in`的上游种子/检查点保持不在该top内。需要重播时，在帧边界载入相同初始seed并重新计帧；上游可能需要的一份32位检查点保持与配置能量也应计一次，不逐输出列复制。本接口不提供任意半帧恢复。

最终回填方法：用新单元的frame能量/时间替换TLM的旧SC body代理；source按实际共享数量计一次；输入前端、SRAM、配置和数据分发各计一次。保留准确数字SiLU(g)u和残差的既有路径，本包不替代这些算子。
