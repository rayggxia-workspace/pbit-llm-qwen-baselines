# 实际验证记录（2026-10-17）

- 已执行独立公式与归档真实循环的零等待桩回放，gate/up 和 down 的周期、tile 数、权重载荷、显式部分和读写一致；与归档历史的 24 层/2 token 计数一致。
- 隔离计算服务为 411.01104 ms/token；历史 FFN 时间提取为 431.095812 ms/token；只读历史时间，不认证其能量。
- 1/8/9 输出 tile 的尾波检查和非对齐输入拒绝通过。
- CLI 输出与保存审计 JSON 数值一致；重复输出路径被明确拒绝，未覆盖历史结果。
- 6 个新文档相对链接有效；新文件 UTF-8/LF 检查通过。git diff --check 通过。
- 实际命令：`python architecture_tlm/audit_ffn_schedule.py --evidence work/jieruiz/7/evidence.json --excerpt work/jieruiz/7/stochastic_matrix_excerpt.py.txt --output <temporary-new-path>`；临时路径位于已核验的本地个人工作区 tmp 内。
- 本记录未声称新 PPL、RTL 功能、DC/PT、版图、DRAMSys 或完整 FFN 硬件验证；没有自动映射搜索。
- 发布时另检查准确文件范围、提交 blob 与 manifest 的 SHA-256、仓库/身份/远端基线及 PR。

发布检查：目标仓库/身份/base重新核实；明确范围文件暂存；manifest各文件与暂存blob SHA-256一致；PR已创建，未合并。

## 经典结构与 RTL 补充验证

- 新增 12 个总阵列数/采样数组合的算术服务场景；独立 GU/U 资源划分与阶段式总服务等价，跨阶段分区的逐块依赖/互斥检查通过。8阵列T4096阶段式418波、有限枚举流水532波。不是完整调度/存储/面积验证；resource_validation.json 记录126项断言，不冒充126项独立硬件测试。
- 新增单通道定点近似 SwiGLU RTL，独立子工作树验证后，在主工作树再次执行 run_validation.py。Icarus功能三种子各12295周期，同时比对24/16位输出，含正负舍入tie、饱和、CE暂停、气泡、在途复位与操作数隔离。
- active/burst/idle各4096拍，接受/产生有效项为4096/1024/0，排空后计数一致。已有小型归档摘要与主工作树验证摘要保留各自原字节；VCD仅本地留存，散列可能因运行日期头不同而不同。
- LUT逐字节重生成检查通过；遍历65536种g给出误差界。黄金模型验证的对象是本候选整数算法，不是BF16、PPL或芯片PPA。
- 代码/README经过另一个只读审查，未发现阻止交付的符号、位宽、RNE、流水或默认功耗窗口错误。没有运行DC、布局、PT或新DRAMSys。

补充发布前：13个新/更新文档相对链接检查通过；主工作树再次Icarus验证与归档RTL字节散列一致。提供本地18,757字节交付zip及SHA索引，未将工具/工艺库/原始VCD加入Git。
