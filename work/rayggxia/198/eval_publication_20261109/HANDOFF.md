# Attention/FFN评测公开交接

2026-11-09，负责人rayggxia，Refs #198；独立分支task/198-eval-publication-20261109，base main@206bf81f18ea88c4c625ce8d32edd18a58edd1cd。仅本侧对话评测汇总；不修改PR199及其所有者的工作树/STATUS。

成果位于qwen3/results/attention_eval_20261109。76项接受结果，58项完整WT2、18项短测；原件SHA与公开规范化载荷SHA分开。七批窗口、目标范围、NLL到PPL、公开SHA与已提供层覆盖字段经verify_results.py离线复验通过。没有本次GPU重跑，没有训练、TLM或硬件默认变更。公开包不包含权重、语料、凭据、SSH配置和服务器操作脚本；完整GPU复现依赖归档运行时与原始模型/语料。

远端发布状态以本任务PUBLICATION.json及PR为准。项目看板无写接口，待维护者同步。自动公开审核拒绝详细训练审计和包含历史跨任务内容的整个STATUS上传；本轮剔除二者，只发布本轮训练范围摘要及此独立交接，不覆盖远端已有STATUS。本地STATUS有本轮追加记录。原始失败/恢复与负结果保留，不能用短测代替完整WT2或把单seed当质量验收。下一步先做FFN条件均值与抽样配对诊断，用户尚未决定启动联合训练或最终任务集。
