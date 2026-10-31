# 已完成：K64幅值转换、三路比较与AND

2026-10-31，Issue204/PR219。最终结果见[报告](results/REPORT_ZH.md)、[精简数值](results/SUMMARY_SMALL.json)、[源码与执行索引](results/SOURCE_INDEX.json)。完整原始报告保留在统一台账`nonlinear-glue-204-20261031`的artifact地址，不把布局前功耗叫芯片实测。

8个原始配置＋6个限定宽度对照，RTL与门级各74,868逐拍oracle检查通过，126个PT窗口计算完成。SS1.08V125℃、100MHz、0.001pF输出负载；raw面积单次乘0.81。每帧64对g/u，1拍加载、T拍采样、1拍排空，T32/128分别340/1300ns。

选择T32三seed平均能量较低的等价版本：8位转换及core保留v3，9位转换及core用v4；AND的两个版本只测v3，不重复测未改变的模块。负面结果和前两次运行目录/编译失败均保留。

源码审阅入口是`execution_v3/rtl/glue.sv`（原始8位与AND）和`execution_v4/glue.sv`（限定宽度9位）；两个版本有同名模块，应分别编译，不同时加入同一设计。原比较器见`execution_v3/rtl/pbit_compare8.sv`。[源码ZIP](results/SOURCE_CODE_V3_V4.zip)含两套完整RTL、top、testbench、工具流程、准确执行manifest；不含工艺库、凭据、模型、数据、原始波形或网表。

ZIP各版本目录内运行`python -B rebuild_fixtures.py`可重新产生72份合成输入/oracle文件，并与执行manifest逐字SHA核对。完整原始7.4MB输入包仍在已授权的项目归档和EDA存储，准确位置与SHA见中央run记录。电路重放需VCS/DC/PT及外部提供的`MATRIX_PRIVATE_LIBRARY`绑定；提交job.sh时必须显式指定快照工作目录。

仅测试四档指数[3,4,5,6]；v4特化于这张连续测试表，未宣称适用于任意四档模型尺度表。g/u在采样期间保持，输入概率来自外部三路不同阈值；core包含192比较器和地址转换，外接已有Sigmoid q9，本轮不含LUT本体、PRNG、SRAM、尺度选择树、Wd或真实广播布线。

寄存版只有64个z＋1valid的CE寄存器，符号由外部保持至排空；并非任意跨帧切换的自包含流水。setup有余量，但I/O及寄存接口hold违例、功耗告警全部保留；需接上下游后闭合时序。本轮不改模型或默认方案，不新增PPL。
