# Issue234 交接

日期：2026-11-03，北京时间。负责人amlink1219。正式目标`rayggxia-workspace/pbit-llm-qwen-baselines`。

## 版本与范围

- base：`main@639ffc28a8409e19f330413a0635f95939c20621`。
- 任务分支：`task/234-sparq-coarse-sampling`；独立稀疏目录`workspace_projects/cs234`。
- 交付：`qwen3/sparq/proposals/pbit_sampling_selector_20261103/PLAN_ZH.md`。
- 用户决定：首试粗阶段WH采样生成256候选，暂不做独立小网。本文不替换正式SparQ默认、不扩原13组训练。
- 正式方案提交：`2eee5845c8cf566a76fbf5b5f63861d0d6962880`；[PR235](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/235)已创建，5文件远端逐字节核验一致，待审未合并。后续元数据head以PR和发布回执为准；本轮没有远端实验。

## 已做与验证

方案已写明四头等权混合、P8 odds、32近期＋224唯一非近期、M与S区分、保持/重复计费、cap失败受控退出、支持集检查、mask条件化差别、N2048分批全局仲裁、数字IID收费和匹配PPL顺序。

两个独立审阅分别核对数学/实现合同和成本/证据边界，结论通过；补充意见已落实。实际静态检查、文件SHA与Git blob核验见`VALIDATION.json`及发布回执。

## 未做和待闭合

没有CPU/GPU仿真、训练、PPL、RTL、EDA或硬件计价结果；没有远端作业ID，没有运行中的任务。

后续执行仍需确认：个人服务器根目录与Slurm分配、原始粗分数数据的授权和位置、环境/源码快照、PPL容差、容量完成要求、实际预算。既有P8行诊断不代表本次粗QK已过门禁。

Zotero后台服务在本轮前次核验不可用，SparQ条目仍有可恢复待收录记录，未声称已入库。文档仅沿用已核读来源，没有新论文检索。

## 下一步

1. 查看Issue234及PR最新状态，确认是否已有执行者；不重复开工。
2. 优先实现A：四头WH混合地址流、recent预置、去重与cap；先小N oracle和粗P8支持检查。
3. 对照D0原SparQ256、D1数字IID、W0实际WH；先真实行/短测，再完整PPL。通过后才接同一后级S128。
4. A重复或支持不足时，按方案依次评估温度/mask/均匀探索；固定分布与mask版分开记录。
5. 执行结果按项目规则通过任务分支PR交付，不将本计划当作已完成实验。

Projects本轮未写入，待维护者同步。没有取消、恢复或修改其他成员作业。
