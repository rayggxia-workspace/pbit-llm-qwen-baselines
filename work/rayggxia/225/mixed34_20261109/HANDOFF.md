## 2026-11-09 混合宏默认已发布

PR249源d5fe6e97333ba53fbaf925ea8ec990d2a53aa6ea，25文件远端完整回读一致，Issue225评论6738309665。两频默认832KiB/178混合宏，前端共享106、Attention72端口；小配对250/500慢0.133826%/0.016848%，SRAM宏面积减少0.192107mm²，能量估计约+2.4%。S2动态仅库差估价，不是新PT；完整token未重跑，55nm保持。原件zip/SHA与交接在本work，PR待审未合并，Projects待维护者同步。

---

# 混合宏默认与有限bank验证交接

## 2026-11-09 28nm混合宏默认：本地完成，待本次PR同步

Issue225/PR249，rayggxia；分支task/225-tlm-unified250-20261107，PR base task/225-norm-stream-20261106；工作目录tmp/tlm-unified250-issue225-20261107，恢复前确认PR最新head。用户决定30×8KiB＋4×4KiB CIM容量份额；两频832KiB总计30×8KiB＋148×4KiB/178真实宏，前端106共享端口、Attention72，不是独占34端口测量。55nm保持。

本机四case完成封存，250三核两层+384head 2.208844→2.211800ms(+.133826%)；500两核一层+384head .997122→.997290ms(+.016848%)。53248物理字无别名，真实端口、排空、核帧/转换/尺度/算术/采样/外存字节与地址SHA校验通过。首次混合未封存energy断言失败保留，确认binary64累计误差约3.1e-10；按N*epsilon界修复审计，调度不变。

SRAM宏2.471065→2.278958mm²(-7.77%)，条件250/500面积6.566340/6.592880mm²；S2用库面积时序漏电、动态S0_PT＋CLK库差估计，局部SRAM能量约+2.4%，不是新S2PT。新默认执行字段匹配冻结混合配置，四个说明字段纠正；208全4K/960参考保留。完整token、新PPL、nativeLPDDR、芯片PPA未重做，不用旧960时间改标签。无健康服务器任务变动。

正式process_28nm/SRAM_MIXED34_VALIDATION_20261109_ZH.md/json与DEFAULT_SRAM832；原件归档project_archives/mixed34_issue225_20261109/finite_pairs_and_failed_audit.zip/SHA见本work/ARCHIVE_INDEX.json。当前本地完成，发布结果以本work/PUBLICATION.json为准，PR待审未合并；Projects无已核实写接口，待维护者同步。下一步如需完整832 token，使用新WHOLE_CONFIG与独立输出；复现局部测试用归档冻结PLAN命令，不重写旧快照。

---

本次命令：

`python -X utf8 -B work/rayggxia/225/mixed34_20261109/run_pairs.py --run-dir work/rayggxia/225/mixed34_20261109/revision2 --reuse-base work/rayggxia/225/mixed34_20261109`

随后执行同目录collect.py、finalize.py。finalize是一次性验收/默认切换工具；证据已归档，不能覆写zip。run_pairs读取旧默认的冻结工具，在默认改为混合宏后不要直接重复；从zip恢复execution目录和冻结PLAN，改命令最后--out为新的绝对目录即可重放。

本次冻结六源码和两频绑定/旧默认的SHA见revision2/PLAN，源身份见机器报告sources；p250_base来自首次已封存快照，仅mixed_budget舍入审计发生变化。当前默认四个描述字段已更正S2为估价，执行参数不变。无需tokenizer/权重/语料：这是相同冻结事务地址的TLM验证，不是数值模型评测；Qwen形状、fixture/host manifest和seed已绑定。原ZIP不含工艺库。

首次失败日志和返回码保留；额外SRAM-only probe未完成并已停止，不作为结果或验收依据。全部本轮配对执行已结束，无新增Slurm作业。
