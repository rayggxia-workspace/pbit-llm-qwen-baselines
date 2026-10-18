为 amlink1219 建立可恢复的硬件架构设计协作入口，避免本机旧上游 checkout、落后的默认 main 和最新 workspace 集成状态混用。在现有 AGENTS 后追加本机身份、工作入口和设计边界，完整保留原复现与协作规则；新增本人 STATUS、最新远端核查、来源 SHA 和可执行交接。

Refs #1。本次是既有治理任务的本机落地子项，负责人 amlink1219；原 Issue 负责人及 PR #2 保持原状态。本 PR 不关闭整体 Issue #1。

目标：rayggxia-workspace/pbit-llm-qwen-baselines。任务分支 task/1-amlink1219-hardware-onboarding；拟 base pbit-tlm-attention-details-20261016，创建前重新核对最新提交。

验证入口：work/amlink1219/1/VALIDATION.json、MANIFEST.json。检查两处原 AGENTS 字节保留、UTF-8/LF、JSON、链接、17份来源 Git blob/SHA、明确文件范围及提交 blob 字节。没有修改或运行模型、PPL、训练、RTL/DC/PT、TLM或服务器任务。

成员 Issue19/22/28/30 及关联评审状态已读取，不接管实现、不重复启动。大模型、数据、工艺库、凭据、DAC根规则副本及本机审查缓存不进入本 PR。

此文件是待创建 PR 的正文草案。当前 amlink1219 对目标 push=false，尚未推送此任务分支或创建 PR；Projects 缺 read:project，未同步看板。权限恢复后重新核目标、身份和范围，上传后回读提交及散列，再更新 STATUS/Issue 和有权限的看板。
