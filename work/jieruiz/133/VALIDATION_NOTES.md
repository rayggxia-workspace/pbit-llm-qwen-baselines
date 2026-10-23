# Issue133 验证记录

- 生产RTL已冻结在首个源提交；最终功能证据只取 `validation_final/VALIDATION.json` 和它的逐源码SHA，不把其他目录累计为新增成功测试。
- `validation_v1` 是本机受限进程启动失败；v2、v3、full_v1、full_v2含早期结构的部分通过/编译过慢后主动结束。保留日志，不标完整通过。
- `validation_full_final` 的N64/M64/T32/PIPE1/A在Icarus展开超过600秒。Python先终止iverilog驱动，其cmd/ivl子进程仍占用，核对父子PID和专属临时配置后终止27400/30968。没有完整64输出功能结果，B完整64尚未启动。该情况不能解释为硬件STA失败。
- `sc_sum_tree_scalar_candidate.sv` 是未采用的局部展开实验；candidate.log的通过不替代生产版本验证。
- 本次没有DC/VCS/PT许可证环境，没有综合/时序/功耗或后布局结果，没有新模型PPL/服务器任务。用户后续执行包内VCS全64输出golden检查，再运行PT。
- Python/Tcl完整性、位宽端点、活动合成、VCD逐bit映射与X/Z拒绝、综合对照条件共6项通过；三份Bash启动脚本 `bash -n` 通过；中央台账8项测试通过。它们不能替代实际商业EDA运行。
- 仅归档日志、输入向量、manifest和源文件；vvp是可重建的工具中间产物，不作为权威实验原件，交付时回收，不上传大副本。
