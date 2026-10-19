# Issue51 新器件LLM质量指标交接

日期2026-10-19；实际GitHub登录jieruiz。目标rayggxia-workspace/pbit-llm-qwen-baselines。

- Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/51。
- 独立目录：C:/Users/86134/Documents/a_P_BIT/tmp/emerging-quality-issue51-20261019；分支task/51-emerging-quality。
- base：pbit-tlm-attention-details-20261016 @c1555ae6594c863011a70845d88c950a68de732b。
- 已完成报告：architecture_tlm/EMERGING_LLM_QUALITY_METRICS_ZH_20261019.md；用户master_report目录有同字节副本。EVIDENCE JSON含14项原文表值及算术复算，非新模型实验。
- 主要结论：5%仅可作为自定PPL工程预算；Kelle有大于5%的PPL操作点，DS-CIM用准确率、UniCAIM用F1、CQ-CiM用检索、SCARLET用token accuracy。指标/基线和应用范围不同，不作跨指标换算。
- VQT-CiM、HEIRS、DBC本次全文质量表未取得，报告明确列出DOI和需核查事项；未引用二手精度数字。
- 无新模型、训练、PPL、TLM、DRAM、RTL/PT/PPA或服务器任务；未动Issue46/48/50的实现或作业。所有数值均为论文转录/复算。
- 实际验证：UTF-8/LF、14项算术复算、2个既有本地链接、正文/用户副本一致；来源PDF五份的SHA仅记录、不上传全文。发布前再核Git blob。
- 准备/核验脚本位于tmp/emerging-quality-preflight-20261019/prepare_delivery.py；来源与正式成果SHA见MANIFEST。
- Projects实际GraphQL返回INSUFFICIENT_SCOPES、缺read:project，未同步看板。
- 下一步：核文档范围后推任务分支PR至TLM base；长期备忘录在独立更新分支向task/28-project-memory提交小补丁，保持唯一主维护文件和根阅读副本不被并行覆盖。实际远端动作发生后补回执。
