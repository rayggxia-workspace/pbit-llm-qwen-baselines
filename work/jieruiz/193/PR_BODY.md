针对FFN计数和恢复算子尚未经过55nm时序校准的问题，提供第一轮可执行RTL与综合脚本。64路二值输入经过固定W8精确计数、4/7档整数恢复、64位本地累加；六级计数归约、恢复流水线及回压均显式实现。先运行2项SS smoke，再按真实路径决定扩展和流水调整。

关联 #193。独立目录 `architecture_tlm/ffn_calibration_stage1/`，不改现有TLM默认或PR192。新增一个中央台账record；main缺少完整registry，根联合索引已增量验证，不搬入其他未合并记录。

验证：9配置Icarus功能通过、9固定top的SYNTHESIS展开通过、29流程测试通过。包括整数极值/负数/偶数舍入/溢出/复位/回压/元数据锁存；完整链无阻塞80/146拍。原240s宽并行软件仿真超时保留，正式900s上限运行已通过。

未运行：许可VCS/DC/PT、55nm综合/STA/功耗、PPL。100MHz是目标，周期合同不是工艺时序闭合；实际模型尺度到coeff/rshift编译仍待数值验证。本轮无PRNG、SRAM、比较器、非线性和BF16转换成本。使用说明和两项首次提交命令见RUN_FIRST_ZH.md；执行源码与结果SHA见SOURCE_MANIFEST及HANDOFF。PR不自动合并。
