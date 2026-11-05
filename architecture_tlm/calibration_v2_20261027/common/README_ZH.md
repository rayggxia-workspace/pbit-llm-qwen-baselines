# 可配置时钟门控接口

用户确认暂不知道55nm库的ICG单元名，先保留映射接口。

GATE_MODE=0为不开门控对照；1为低电平透明锁存的无毛刺功能模型，禁止用其综合面积冒充真实ICG；2实例化用户提供的库单元。
调用方把reset/frame清零/有输入/有流水待排空的条件加入en，test_en保留。模块自身不设复位；功能仿真必须从clk=0启动，rst_n=0至少跨完整低相位及上升沿。

得到库信息后，填写icg_mapping.example.json的五个字段，运行：

`python common/make_icg_mapping.py YOUR_ICG.json --output YOUR_OUTPUT/pbit_icg_tech.sv`

编译加PB_ICG_TECH_MAPPED宏，同时提供生成的wrapper、实际库模型和实际库时序文件。此工具仅生成明确的引脚映射，不自动证明其门控极性、可测试性或时序正确。需要确认：EN/TE是否高有效、CLK低电平锁存、Q是否同相，实际库支持clock gating检查。若库不符合此接口，必须修改适配层并重新验证，不能只换名称。

没有真实映射时，GATE_MODE=2展开失败；GATE_MODE=1在SYNTHESIS下也展开失败。不开门控版仍可先测。ICG状态保持、控制常开和唤醒周期在对应counter/digital模块说明中列出，不能凭这一wrapper声称整机门控已完成。
