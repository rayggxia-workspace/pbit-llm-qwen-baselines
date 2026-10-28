
发布确认：面积0.81默认规则已上传 [PR203](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/203)，ready/open、未合并；Issue28已同步。本地规则即时按用户要求执行，正式合并状态以后续回执为准。
## Issue28面积口径更新：本地已完成，待发布

2026-10-28T11:12:48+08:00；负责人jieruiz；分支task/28-area-081；base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166，目录tmp/area-scale-issue28-20261028。登记用户指定65流程→线性0.9→面积0.81为后续默认55nm口径，原始报告/功耗/时延不改；未新建仿真、未批量改历史数值。AGENTS和长期备忘录已同步本地入口。旧Issue28工作目录有未提交内容，未触碰。下一步通过同Issue的新PR交付（PR29已历史合并），不混入其他实验。Projects沿既有权限限制待同步。

## 2026-10-25 第十一轮实际合并回执

已发布 [PR194](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/194)，待审、未合并。PUBLICATION.json是PR创建时的精确回执；后续文档同步提交不改变封存源码55c607dc和ZIP。

# jieruiz当前进度

2026-10-25；负责人jieruiz；Issue193；分支task/193-ffn-calibration-stage1；base main d83eeb1f；目录tmp/ffn-calibration-issue193-20261025。第一轮55nm计数/整数恢复校准包本地完成，源码55c607dc已推送；结果PR交付状态以work/jieruiz/193/PUBLICATION.json为准。

实际验证：9配置RTL功能、9固定top展开、29流程测试通过；没有VCS/DC/PT/新Slurm/PPL。100MHz为目标，不是工艺时序通过。正式成果architecture_tlm/ffn_calibration_stage1；ZIP位于本地根ffn_calibration_stage1_20261025.zip；哈希见work/jieruiz/193/DELIVERY.json。

新增台账record并在根联合阅读索引check/render，67条旧记录不变。main尚未包含完整registry，正式台账集成待后续同步；Projects缺read:project。用户下一步按RUN_FIRST_ZH.md先运行SS两项smoke，把小报告包回传后调整流水线。交接work/jieruiz/193/HANDOFF.md。

此前Issue186/PR192独立待审；本任务未接管、覆盖或合并。
