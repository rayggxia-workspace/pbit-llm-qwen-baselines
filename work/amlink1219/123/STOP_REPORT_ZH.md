# Issue123 停止总结（2026-10-23）

按用户要求在当前进度停止。只完成停机、归档、核验和发布，不再启动优化或仿真。PR125待审未合并，Issue123保留开放供后续接手。

已在[停止交接评论](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/123#issuecomment-6349890389)再次@jieruiz，附本总结与STA/PPA任务文件；通知已回读核验。

收尾只读核对时，PR126任务分支已前进到 `3347bd8a0a46ad2533298d680d8a6800ad9fa8d4`。本任务实际执行仍固定 `160f46e`，停止阶段不纳入后续改动；恢复时应先看其新进展，不能把旧快照当远端最新状态。

## 已完成并有证据

| 项目 | 当前结果 | 证据入口 |
|---|---|---|
| 正式后端接合 | 已合并固定PR126@160f46e依赖，接入PR122@8007d98；可选完整FFN路径，legacy默认保留 | 接合提交d944081；architecture_tlm/ffn_cycle_integration/README_ZH.md |
| 软件验证 | 冻结包提取副本28项测试；120次独立随机执行、完整payload相等 | ffn_2783/TESTS.txt；reviews/ACTIVE_RANDOM_REVIEW.json |
| 完整形状输入 | 真实Qwen2.5-0.5B layer0/context64最后token，896→4864→896；41,405,784B fixture | capture_2777/MANIFEST.json；权重仅留本人服务器 |
| 编码恢复RTL | 45场景、11667输出、180reset flush；T16/32/64、BF16/FP32、depth1/3/5、3seed | architecture_tlm/encoding_restore_contract/results/rtl_2778 |
| STA/PPA交接 | 可执行DC→门级oracle→PT、固定顶层/位宽/PVT/窗口/模板已上传，已@jieruiz | architecture_tlm/encoding_restore_contract/ppa/HANDOFF_JIERUI_ZH.md |
| 后续主机调度候选 | 原型和生产化源码、小烟测及已有测试回执已归档；未接入发布runner | candidates/pending_20261023/SOURCE_MAP.json及evidence/STOP_RECEIPT.json |

## 已停止及尚未完成

- 全尺寸CPU作业2783于03:41:00（Asia/Shanghai）按用户要求停止，运行24分20秒；Slurm终态CANCELLED、ExitCode0:15。本任务没有剩余运行作业，其他任务未操作。
- 2783只有启动时的source/artifact清单；未完成kernel，不存在成功summary、完整trace、实际阈值或全尺寸数值验收。shell trap中的exit_code=0不能代表应用成功。2779/2780同为主动中断，均不计通过。
- 全尺寸896→4864→896的独立数值、存储信用和动作守恒尚未通过；90次组编码、204288次恢复/跨k加法仍是验收期望，不是本次实际测得结果。
- 候选调度的34项测试依据已完成控制台，未另存原始stdout；5→3→2 CLI原件可回读。候选尚需独立提取包验收和完整形状运行；55/300步收益仅是主机前缀，不是硬件加速。
- 实际licensed DC/PT/VCS、SS/TT STA、面积/功耗/每操作能量均未执行；物理值为null。完整24层、PPL、同质量系统PPA也未完成。

## 交给jieruiz

请先按PPA交接文件确认本人环境/库和单位，先SS/T32跑通，再扩到SS/TT五个固定顶层与三seed。保存源码/配置/库版本散列、STA余量、活动窗口、覆盖/XZ及完整动作计价；不上传工艺库或凭据。不把局部编码恢复PPA写成整FFN PPA。

完整FFN恢复工作与STA分开：先核最新Issue116/PR126和Issue123/PR125，保留Issue124短投影分工；若采用已归档的候选调度，按SOURCE_MAP还原到独立checkout、重新冻结并验收后再启动唯一作业。此次没有安排自动重启或后台继续。

## 文件处理和恢复

Git保留正式接合、测试证据、RTL结果、候选三文件和小烟测、停止日志及清单。服务器完整fixture与冻结执行目录保持原位；路径和SHA见各run记录。停止中间资料已逐文件压缩校验，见STOP_ARCHIVE_INDEX.json，归档在本地project_archives/issue123_stop_20261023。保留必要PR工作树和候选恢复树，未删除唯一源码/数据。归档不包含可重新提取的副本与pycache；原件保留。

Projects看板因token缺read:project待有权限者同步；仓库上传与Issue更新不受影响。不自动合并或关闭任务。
