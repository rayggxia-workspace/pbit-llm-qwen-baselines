完整TLM此前以宏级吞吐和存储契约估计decode，本改动给出52项封存情景的周期/阶段/访存审计，并提供可综合的非随机数字表征RTL。当前时序仍是有条件模型，功能RTL延迟不是STA达标证明。

RTL覆盖动态B4编码/恢复、FP32与BF16算术/累加、SwiGLU/RMS/RoPE/非线性候选、CDF/归约/压缩，以及小规模SRAM路由、DMA控制和算术数组。已有66组功能/12870输出、63活动预检通过，精确源23e8d65f；工艺DC/STA/PT尚待用户环境，近似非线性和融合恢复不继承模型PPL。

本轮对照真实随机服务整机PR103@b05fb36d与中央台账PR111@2b7935f4，补充[最新Verilog仿真缺口与优先级](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/107-tlm-cycle-digital-rtl/architecture_tlm/digital_ppa_v1/LATEST_TLM_RTL_GAPS_ZH.md)、11组机器任务表和PPA回传模板。按已完成PPA、现成RTL待工艺、需新增整合RTL区分，不把拟议顶层写成已提供代码。重点是SC四档短流tile/计数、32KiB权重驻留、编码/恢复、普通阵列吞吐、采样数字反馈/前端及真实SRAM/CDC/DMA带宽。

补充明确了：8tile按当前计数映射有48KiB逻辑状态；每档准确整数累计可作640B/tile状态对照，但尚未实现/验证PPA。100MHz单64B命令仅6.4GB/s，现成DMA小例不证明16GB/s；完整赢家需要真实popcount与均匀选秩，现成0/1/多树不能代替。驱动码−255..255和R8位宽不同；CDF的动态数制转换也不能免费。

本轮实际验证是32个Git源SHA、引用路径/单位/位宽及288组逐档整数和等价核对；完整记录work/jieruiz/107/latest_gap/SOURCE_INDEX.json、VALIDATION_FINAL.json。不是新RTL/DC/PT/TLM或模型运行，9626内部断言大多是循环边界，不作为电路测试数。

Refs #107。原RTL和52/40封存结果保持，未改Issue95随机核心。未知完整PPA仍空值；默认Link不是本次实际DRAMSys。Projects缺read:project待同步；沿用原分支/PR交付，等待评审，不自动合并或关闭Issue。
