# Issue225：1216KiB候选交接

负责人rayggxia，task/225-norm-stream-20261106，PR248，独立工作目录tmp/norm-stream-issue225-20261106。用户最新授权是在总TLM落实Attention缩容并探索约1.2MiB；原模块198/204只读，旧冻结任务不改。

正式入口architecture_tlm/sram1216_20261106/README_ZH.md、model.py和RESULTS.json。候选真实304个4KiB/1RW宏：前端176，八Attention组各16；640/8-K/提前补货、12个C20/T64、96KiB GU状态、CIM32槽、K128/赢家S64、norm32KiB和真实24KiB入口保持。权重普通双缓冲2×80KiB，激活128KiB，Attention8×64KiB。没有把删掉的端口免费留下，也未改FFN/Attention概率规则。

8个本地检查和三配置一层完整形状合成时序回放通过，关键计算actions/外存字节守恒。相对1952KiB控制：仅缩Attention一层+0.250%，完整1216一层+1.922%；这是解析外存与合成采样时序，不是原生LPDDR或完整token结果。逐物理word、tile最大字节、活跃别名负对照均已实际执行。SRAM读少135个16B词，写与外存字节不变，保留调度变化，不称所有读写完全相同。

当前仅按已有宏价面积预算57.573748→52.621712mm²；新增地址译码/互连未独立PPA，无新模型PPL或RTL/PT，不把容量变化乘到动态能量上。

## 原生提交阻塞与恢复

本轮没有成功作业号。第一次远端Python生成脚本语法错误，未执行；修复后一次读超时，随后只读RECOVERY_PROBE核实目标父目录下无快照/回执、队列无本候选。此后打开SSH channel连续超时，均在远端代码执行前失败。不能记为submitted。不要改动原204完整作业38616054或225旧norm/compact作业。

用户随后确认服务器暂时有问题，明确允许本地初步估计。本轮停止EDA重试，不等待远端任务；交付本地8项机制及三配置一层回放和条件功耗面积。后续原生计划保持未提交，不能说仍在排队或运行，也不创建回查/自动化。

`work/rayggxia/225/sram1216/ops.py`已经改为先小脚本创建独占目录、SFTP上传、同连接验证和提交；含身份/目录/manifest/SUBMISSION守卫。准备identity为509fba14a32424b3b8a2d72c80c7f6acaf9ea651d55786af565f3314460ca7c7。下次先只读检查PREPARED中的目录和回执；若实际已生成提交则恢复回执，仅status/collect，不重交。无快照/作业才执行submit。计划8项EDA门禁→三配置两层seed17→1952/1216完整36层+lm_head各一项，1CPU/0GPU，分别最多3和2并行。

源依赖快照14文件只读保存于本地project_archives/sram1216_225_20261106/dependencies，manifest SHA4ce8d1065aa7d4b5f2067e9e409d5bc56bad987cb6b3edf945719ac85777e483；固定旧runtime SHA7c5cb9b603ca2bd139ac6fa7b75d789e00c316acde994ff3db9bdcbb33c4bb40。它们不是本次新硬件结果，未把他人未发布原件复制进Git；外部复现需按DEPENDENCIES.json取得相同版本或原共享目录权限。

原始本地合成结果project_archives/sram1216_225_20261106/LOCAL_SYNTHETIC_SMOKE.json；逐字节SHA见RESULTS.json，源码和验证见VALIDATION.json。根正式目录为同字节阅读镜像。个人STATUS及长期备忘录同步；远端交付以PUBLICATION.json/PR实际回读为准，PR待审未合并，Projects无写接口待维护者同步。


## 2026-11-06 Issue225：用户保留1216KiB，更新各模块面积主表

用户明确先保留约1.2MB，即1216KiB/1.1875MiB；不继续压992KiB等候选。当前本地面积参考compact1216，2K/K128/赢家S64、640路普通池、12个C20/T64、96KiB GU保持；旧CLI/冻结源不静默改写。未重试故障EDA，无新作业/PPL/RTL/PT。

正式architecture_tlm/sram1216_20261106/AREA_BREAKDOWN_ZH.md及JSON/CSV，15面积项归6组一次求和：FFN15.949424、共享数字池与归约10.981999、Attention14.782192、SRAM8.181625、DMA入口1.188795、格式向量/数字保持1.537678，合计52.621712mm²。55等效已单次x.81，不再次缩放；FFN随机源/比较器已含C20核价，零额外proxy不表示硬件免费。

SRAM内部按用途512/160/256/128/96/32/32KiB拆分，等价304宏；前端176bank交织共享，按容量摊分面积不意味着另外独占宏；内部表不能再加到总面积第二次。沿上一轮既有逻辑价格，仅更新主表与归属；新增紧凑译码/互连、完整NoC/CTS/PHY/IO/pad等仍缺项，不称最终die面积。

长上下文不使所有SRAM线性增长：FFN/权重tile/norm通常可保持，KV主体片外；若K128→256并整份保留候选V，单组V缓存32→64KiB，当前64KiB/组不能容纳全部原工作区，需要加容量或新流式/缓存调度。未运行长上下文适配，不将条件推断当结果。

生成与核算入口work/rayggxia/225/sram1216/build_area.py、AREA_VALIDATION.json；来源SHA、15项归属无重复、SRAM1216KiB/304宏及子面积守恒已核。沿Issue225/PR248，同工作目录，发布回执AREA_PUBLICATION.json为准；PR待审不合并，Projects待维护者同步。

---

