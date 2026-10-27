# 首轮怎么仿真

从本文件所在目录执行。全部代码是SystemVerilog，请开启SV模式。工艺库和网表留在你的私有目录，不放公开仓库。本包不会自动提交任务。

## 1. 先测不开门控的计数器和数字核

```
python flow/make_counter_cases.py --output cases100 --bins 4 7 --outputs 1 --pipeline 1 2 --gate-mode 0 --frequencies 100 --modes continuous idle
python flow/make_digital_cases.py --output fixtures100 --tops dig_fp32_add dig_bf16_mac --modes continuous idle --frequency-mhz 100
```

得到8个计数case和4个数字case，不会运行EDA。先挑B4/T64/M1/p1/g0连续与空闲两项，以及BF16 MAC连续与空闲两项。case里的源路径相对于本包，数字case同时绑定实际输入向量和golden。

将flow/library.example.json复制到私有目录，填写真实`.db`、库Verilog模型、参考单元、SS/TT、电压和温度。area的单位换算必须有库文档依据，不知道时保持null。建议先沿已有SS/1.08V/125C/100MHz口径。

```
python flow/run_case.py --case cases100/counter_b4_t64_m1_p1_g0_100MHz_continuous_s17.json --library /private/library.json --output /private/counter_preflight
python flow/run_case.py --case cases100/counter_b4_t64_m1_p1_g0_100MHz_continuous_s17.json --library /private/library.json --output /private/counter_synth --stage synth
python flow/run_case.py --case cases100/counter_b4_t64_m1_p1_g0_100MHz_continuous_s17.json --library /private/library.json --output /private/counter_sta --stage sta --reuse-synth /private/counter_synth/synth
python flow/run_case.py --case cases100/counter_b4_t64_m1_p1_g0_100MHz_continuous_s17.json --library /private/library.json --output /private/counter_gate --stage gate_sim --reuse-synth /private/counter_synth/synth
python flow/run_case.py --case cases100/counter_b4_t64_m1_p1_g0_100MHz_continuous_s17.json --library /private/library.json --output /private/counter_power --stage power --reuse-synth /private/counter_synth/synth --windows /private/counter_gate/auto_windows.json
```

数字同理，将case改为`fixtures100/dig_bf16_mac_continuous_f100_s17/case.json`，为每个阶段使用新的输出目录。idle可复用同top/源/约束/频率的综合结果，活动文件必须重新生成。综合只包含DUT，TB中的随机生成器不计入DUT功耗；真实随机前端以后单独计价。

## 2. 比较哪些设计

| 对照 | 相同条件 | 看什么 |
|---|---|---|
| 旧分桶树 vs 新合并树 | N64、M、档位、采样数、同事件流/权重/档位、PVT和约束 | 标准单元面积、每帧能量、关键路径 |
| 新p1六级 vs p2三级 | 功能和样本数不变 | 流水寄存减少是否值得组合路径变长 |
| g0无门控 vs g2真实ICG | 同事件日程，continuous/idle/wake/stall | 空闲节能、ICG/驱动开销、门控检查 |
| 单MAC vs 8lane vs 16context | 明确每次握手完成几个操作及外部供数边界 | pJ/MAC、吞吐和真实反馈等待 |

新计数器是精确计算，没有OR近似；权重为7位幅值+符号，范围−127…127，不覆盖−128。每个输入档位固定2幂步长为2，即对齐移位0/2/4/…；B4输出26位、B7输出33位。权重/符号/档位整个帧保持，外部存储不在模块面积里。

旧结构现成PPA可做历史参考，但严格节能比必须匹配刺激和约束；不能把旧均匀阈值与新非均匀阈值的功率差全归因于结构。新bench支持固定每路阈值、64路共享R8，默认swept；uniform保留为高相关压力情形，详细见counter/README_ZH.md。

100MHz通过后再生成250/500MHz用例，并重新综合。负slack如实保留，不能只修改TLM周期。三级流水更少寄存器，但不保证更快或更省电。

## 3. 门控暂不知道单元名怎么办

先跑g0。等拿到库中的ICG单元与CLK/EN/TE/Q脚位，填写common/icg_mapping.example.json，通过common/make_icg_mapping.py生成`pbit_icg_tech`；生成命令见common/README_ZH.md。library JSON同时填ICG名字、EN/TE和wrapper路径，再生成g2用例。

功能门控GATE_MODE=1禁止用于综合功耗。g2不填映射会报错；不会静默换成与门或按零成本处理。当前计数器按一个M输出数据组共用ICG；是否需分拆、时钟缓冲和负载必须由实库结果判断。数字核本轮仅数据保持，没有ICG，不能将其idle称为关钟后功率。

## 4. 请回传

每个case的RESULT.json、源/配置SHA、综合面积、setup/hold及关键路径、全部告警、功耗internal/switching/leakage、活动覆盖和窗口起止/实际完成操作数。精确字段见CALIBRATION_RESULT_FIELDS_ZH.md。

无需把大VCD、网表、工艺库放GitHub；保留原件路径、字节数、SHA。有时序失败也回传，后续根据关键路径调整流水，而不是猜下一版拍数。

本轮只有RTL功能与脚本验证，未运行DC/PT；没有新的面积/功率数字。BF16 MAC采用非融合乘加和DAZ/FTZ，不能未经数值协议对齐就等同GPU FMA。完整随机FFN、SRAM、PRNG、CIM外围和整片CTS不在本包测量边界。
