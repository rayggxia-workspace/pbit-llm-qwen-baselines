## 2026-10-25 Issue95 / PR188 已发布

理想读出分层质量已通过 PR188 发布并待审，未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/188 。科学提交413e786fd1a8d08c1825f1886a3000929aff5bc0；完整tree 38b2634008ef6db09b53a7e9872df0faf7ad60bd与本地一致，报告远端读回逐字符一致。225案例与验证结果不变；新增台账与根镜像已同步且保留并行记录。恢复见work/rayggxia/95/ideal_quality_20261025/PUBLICATION.json。Issue95保持开放，Projects待有权限维护者同步。

## 2026-10-25 Issue95：理想读出20k的定时分层质量

用户同意等待实际比较器数据时，先用三条理想阈值读出做基线。task/95-ideal-quality-20261025，tmp/rng-ideal-quality-issue95-20261025，base d6d33995754fcdcea99286e4ce43f91647aa231a；执行本地提交 bdbab3e38ff56e267783af9ac327dbba67a0e169，冻结5文件SHA。已有ideal_and_old_20000_v1三seed32003/32009/32027，各20000bit、1us，仍带旧比较器负载；无新Spectre。216主例+9重复种子对照全完成，每端点4096帧；四个固定5000bit冷启动段，不是12独立物理轨迹，也不触发默认1e8拍/1s周期换种。

理想原始rho1 −0.0037～0.0101，V128为1.208～1.596，不能凭lag1认定IID。VN理想保留约25%；旧比较器VN保留约12%，仍负rho1 −0.236～−0.187。分发逐bit保持，仅截断包末尾；LFSR每端32状态bit，Bivium192总线bit→177状态bit/15丢弃。理想直通双端首次请求63.03us/383.08us，VN为213.03～275.03us/1461.08～1617.08us。GF64前四路q128 XOR恒0，理想直通q4恰一路命中0.685～0.706，对比IID约0.371；Bivium q13约0.362～0.396，对比约0.377。较好种子不消除固定联合关系，PRNG不增加物理熵。

6单测、8956项可复现审计、独立只读复核及1280/390浏览器检查通过。归档project_archives/rng_ideal_quality_20261025（225NPZ、完整JSON、执行bundle、源码zip）；中央run rng-ideal-quality-95-20261025，仅DESIGN_PROOF/PPA未知。报告architecture_tlm/random_service/quality/results/ideal_20261025/REPORT.html，本机远端上传/rng_ideal_quality_20261025.html。HANDOFF/PUBLICATION位于work/rayggxia/95/ideal_quality_20261025；发布状态以回执为准，未自动合并/关闭Issue95。当前在仿真的物理任务Issue184/PR185及他人Issue152只读未改；Projects待有权限者同步。

恢复操作：

1. 先读最新Issue95/关联PR、PUBLICATION.json、STATUS和根记忆。PR134是已合并旧阶段，不能更新其旧分支；本轮独立task/95-ideal-quality-20261025，目标TLM集成分支。
2. 报告、源manifest及结果索引在quality/results/ideal_20261025；大RESULTS被gitignore，但稳定归档已有同字节文件，225NPZ也在稳定归档。input SHA由INPUT_MANIFEST绑定，物理原始包仍归原任务。
3. 原模型/backends/映射未改。本地执行bdbab3e通过execution.bundle保留（依赖base d6）；增强测试、审计、图文为后处理。运行命令及测试日志见VALIDATION.json/tests.log，源zip及SHA清单见SOURCE_PACKAGE_MANIFEST。
4. 不覆盖既有结果；新数据用新输出目录。不要循环有限记录、从MID筛选好bit、自动补充OS种子或把四窗口称作实际1s周期换种。
5. root中央台账比本分支含更多并行记录；本次只新增本run、保留原catalog所有ID并render，不能以本分支整目录覆盖root。根记忆只在Issue28 canonical追加本项后同步镜像，保留其他未提交内容。

疑点/后续：

- 物理源健康检测/调理、CDC尚无本次RTL实现；RandomNetwork的qualified接口是条件合同，不是熵检测结果。
- VN对相关输入不保证IID；实际比较器、并行空间相关、低频漂移仍等数据，不据当前结果定最终调理器。
- 一亿拍换种未实际触发；不使用旧1024拍加速协议替代（真实低速采种下可能导致同步端点饥饿）。
- GF64是否适合 具体消费者需看联合事件；本轮toy探针不能代替FFN/Attention/LLM质量。
- 本任务没有新RTL/EDA/Slurm/GPU作业。模拟器仅操作计数，面积/功耗未知。
- 本轮后处理增强测试曾因Counter字典显式0键与缺省0键格式不同失败，改为语义计数/内部状态对照后6项通过；执行源码未变。初次沙箱Edge启动受限，独立无头配置获工具批准后检查通过。

交付时保留最小PR待审目录，原始结果已稳定归档；只有本任务合并后再按恢复索引回收，不能删除其他物理任务。Projects连接器无已验证的写入能力，待有权限维护者同步。
