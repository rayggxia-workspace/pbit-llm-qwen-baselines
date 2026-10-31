# Issue139 SANTA 方法比较交接

负责人 amlink1219；2026-10-31。沿用同范围 Issue139，复用已合并 PR85/140 的资料，不重复接管旧任务。
分支 `task/139-santa-method-comparison-20261031`；base main@`7d42c7d30fa9c729c899ba7f815332dd6ed5671a`；独立 checkout `workspace_projects/sc139`。
完成范围和验收：两篇版本/全文核对；AV、QK、路由、校正、GQA、FFN、硬件边界分别比较；论文和项目来源带原始哈希及准确提交；文档上传与远端回读。
非目标：改模型/实现默认、恢复实验、跑训练或电路、证明全领域新颖性。依赖：两篇公开论文及清单中的项目报告；待审 PR 仅作为带版本的方案/结果来源。
成果：`architecture_tlm/research_readings/santa_comparison_20261031/SANTA_VS_SANTAPP_PROJECT_ZH.md`、两份 SOURCE_MANIFEST 和 VALIDATION；README/memo/个人进度只追加本任务入口。
验证命令：`python -X utf8 outputs/santa_comparison_20261031/publish_comparison.py stage`（仅首次、干净 checkout），随后 `commit`、`publish`、`verify`。内容核验不需模型/权重/数据集；本轮无运行任务 ID、无远端作业。发布回执为 `SANTA_COMPARISON_PUBLICATION.json`。
Zotero：已有 SANTA/SANTA++ 复用，v2 附件及本轮笔记未写入；可恢复待办保留本机，不上传私人库路径/笔记。
下一步：PR 审阅；如开展算法/硬件实验，另定同质量预算和真实成本边界。
