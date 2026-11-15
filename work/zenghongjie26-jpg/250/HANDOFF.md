# 最新图稿发布交接

用户2026-11-15要求将目前全部图的最新版上传GitHub。复用图稿Issue #250，保留原负责人维护的PR #251与其他成员分支，不改其文件。执行人zenghongjie26-jpg，组织仓库只有pull权限，走个人fork task/250-latest-figures-20261115 → upstream main。

## 成果

见 figures/latest_20261115/README_ZH.md、MANIFEST.json、VALIDATION.json。完整主PPT按原字节保留；最新版页码见索引，主要为第1页，Fig.4为第9页。Fig.7备选和Attention训练补充不冒充新增主图编号。Fig.9/10未定位到成稿，Fig.11只有数据说明，本轮未上传原文参考图与白板照。

## 验证与边界

11份PPT ZIP/XML、源SHA复核及PowerPoint打开/导出通过。所有图中原数值不修改；不是重新进行科学结果验收。模型revision/语料/seed不适用于纯文件发布，沿用各图来源与备注；没有运行新实验。原始工作文件未改动。

## 发布状态

本提交是供PR审阅的图稿快照；不自动合并。实际远端链接以本任务PUBLICATION.json及PR为准。Projects无写接口，待维护者同步。

## 发布阻塞（2026-11-15）

图稿提交 b8c8a6f3 已本地完成，尚未推送。自动审批拒绝向公开个人 fork zenghongjie26-jpg/pbit-llm-qwen-baselines 推送，理由为用户虽要求上传GitHub，但未明确授权该公开个人仓库作为工作图稿发布位置。当前等待用户明确确认目标，不能改用API或其它方式绕过。组织主仓库当前账号只有pull权限。个人fork已建立，尚无本批图稿；PR未创建、Issue/Projects未更新。
