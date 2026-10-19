# Issue39交接

2026-10-19，负责人jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines，PR base pbit-tlm-attention-details-20261016@c1555ae。独立分支task/39-ffn-clipping，目录tmp/qwen-ffn-clipping-issue39-20261019。

新任务：裁剪PPL、静态train分组尺度与二次幂实现成本，依赖已合并范围修正Issue32，避免修改Attention成员任务。已读最新README/AGENTS/STATUS/TLM索引，核实账号jieruiz有push/admin；开始时本人Slurm队列为空。

当前本地编码中：experiments/qwen_ffn_clipping_20261019/，未提交/未上传/未运行。并行kernel工作树tmp/qwen-ffn-clipping-kernel-agent39，仅负责clip_core和单测；主工作树负责runner、部署、汇总。

验收步骤：核对control严格重现、端点p1、分组scale恢复、PoT舍入；先提交源代码再打tar部署不可变快照；Slurm prepare跑原BF16完整基线/hash/train校准，成功后53case数组（含无采样control、3固定seed、512及预选2048诊断）。记载实际job/hash；收回所有完成输出，逐SHA核验，通过PR交付，更新memo。无新PT/TLM数据；Projects曾缺read:project，需要再核实但不阻止代码和Issue同步。


## 实际提交回执（2026-10-19）

执行源6b57b92305cab5dbee2a53c0c65cb297ac976261。原本地caf4193导出受core.autocrlf影响导致sbatch拒绝DOS换行，未创建作业；新增目录eol=lf并以core.autocrlf=false导出后提交成功，旧未运行快照保留。Slurm2167准备、2168数组0-52%4，最多4GPU，详见SUBMISSION.json。

本地10项kernel通过；服务器10项新kernel、8项旧range及共享计数/方差测试通过。完整原BF16重现11.652735047455899，299077目标；512/2048前缀分别12.089225/9.328747。train-only8192token百分位已校准，数组运行中，替换PPL尚未全部收回。早期mean结果不是最终随机PPL，不预判裁剪收益。

没有新的PT/PPA/TLM，源码已推送task/39-ffn-clipping；提交快照不可覆盖。下一步按check39/collect39收回，逐SHA验证，汇总并更新PR/Issue/Memo。端点变化与裁剪是共同方案，缺少dynamic100(one)独立消融，报告不得将二者完全分离归因。Projects缺权限待同步。


补充：最早0.75无采样PPL17.07已差于control12.03，另注册0.95/0.90和dynamic100恒1端点。源e0cf563daceb4e8528d9b1ca38da58e434907811；Slurm2185准备、2186补充数组12项，重新BF16/校准通过。主数组2168由4限到3，补充限1，总并发4。没有覆盖原6b57b92快照。此补充使用相同测试前缀，属探索，不是独立验证集。


## 结果完成与交付（2026-10-19T11:09:36+08:00）

两批65项替换及6项BF16共71输出已齐，逐SHA和执行源复核通过。正式结果qwen/results/ffn_clipping_20261019/RESULTS_ZH.md，完整索引/SUMMARY同目录；新算法分数均为前缀，不是全WT2。服务器2167/2168与2185/2186全部实际结束情况见收集/状态回执。
源码执行6b57b92与e0cf563不可变；post执行analysis另有后续提交，未覆盖旧快照。当前任务分支和PR40待审、未合并，Issue39保持open直到验收/合并。下一步审阅结果/方法及限制，若继续应另选独立文本/完整PPL，避免把同一512前缀探索当最终泛化分数。Projects待同步，无新PPA。


交付回执：结果提交6642594实际发布，PR40 ready for review、未合并，Issue39保持open；Issue评论6258863708。Git HTTPS失败后API逐commit/tree SHA完全一致地正常快进；22文件Git blob通过。备忘录560f88e已推送PR29、根副本一致。全部计算输出齐且队列为空；sacct禁用、旧controller过期的状态不可查已单列，不能当失败。下一步仅审阅/后续独立实验；不重复这65配置。Projects缺read:project待同步。
