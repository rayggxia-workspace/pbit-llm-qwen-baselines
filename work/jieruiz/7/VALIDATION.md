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
