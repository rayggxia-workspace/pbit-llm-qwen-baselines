# Issue96 / PR99 交付回执

2026-10-22；GitHub登录核实为jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。

实现、配置、52项结果、中文说明和验证证据均已推送至`task/96-unified-tlm@9621e1db35491e530d35b86e0ef884572b1df0a6`。PR99已从草稿转为开放待审，未合并；Issue96实现验收清单与结果链接已更新，保留open等待评审。

冻结数值执行为`fba22b192ab914046e50cc405f6dd473bf30d154`，没有为发布改写或重跑。`REMOTE_VERIFY.json`读回核对五个关键GitHub blob原字节，`PUBLICATION.json`记录上传状态。这些回执指向已发布的科学交付提交，不自引用后续回执提交SHA。

已完成21项新机制、18项原v5、10项原v4检查；同一49项在新上游默认接口下覆盖通过，不重复计为49个额外新测试。52项条件decode模型、62个原件校验、22个执行源blob和764个契约均通过。完整物理能量、面积与新组合PPL仍未知，不能由缺项能量小计得到整机能效。

没有运行中任务，没有新GPU/Slurm/PPL/PT/真实DRAMSys执行。Projects本轮实际查询缺`read:project`，已单独记录待同步；不影响仓库分支、PR和Issue交付。下一步为PR评审及恢复/编码、权重驻留、采样器输出/反馈、本地源接口的成本标定。
