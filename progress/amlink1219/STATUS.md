# amlink1219 项目进度

- 更新时间：2026-10-18T23:30:29+08:00；本机GCM身份amlink1219/75301230；正式目标rayggxia-workspace/pbit-llm-qwen-baselines。
- 当前任务：[Issue #33](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/33)，负责人amlink1219（正文已明确；无triage，assignee待维护者同步）。范围为Attention p-bit价值文献调研、随机源审计及仿真安排，不是实验实施。
- 独立工作目录：`E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/pbit-attention-issue33`；分支`task/33-attention-value-plan`；base `pbit-tlm-attention-details-20261016` @ `3553996bf014a29dee7fdb2250a3965e8fd881a4`。未设置跟踪集成分支，发布时必须显式推本任务分支。
- 本地已完成：主要原文/官方实现调研、当前RNG与Attention源审计、数字/原生p-bit公平对照、E0-E5阶段与有限case矩阵。Zotero实际回执另附，不能以下载代替入库。
- 正式文件：`architecture_tlm/ATTENTION_PBIT_VALUE_AND_EXPERIMENT_PLAN_ZH_20261018.md`及`architecture_tlm/configs/attention_value_plan_20261018.json`；辅助资料、来源SHA、验收和交接在`work/amlink1219/33/`。
- 实际验证：本轮仅文档/配置结构、链接、计数、来源SHA与Git字节检查，没有新模型推理、PPL、训练、RTL/PT/TLM或服务器计算。
- 协作范围：Issue3/5/7/9报告复用，Issue19/22/30/32及其他成员工作不接管、不覆盖、不重交。
- 阻塞：push=false，任务分支/PR未上传；Projects缺read:project待同步；原生器件传输曲线/相关时间/反馈与同工艺PPA未提供，正式GPU/PDK环境需要执行前核实。直接相关LED论文仅元数据/摘要可读，全文待获取。
- 下一步：审阅本计划的质量门槛和优先级；按E0另行实施明确模块和preflight，先pilot再决定长评测。权限恢复后核目标/差异/清单，显式推任务分支、PR交付并回读；不自动合并、不回退旧库。
- 前序本机协作接入Issue1仍保留在独立`task/1-amlink1219-hardware-onboarding`，本次不覆盖其提交/交接或其他成员STATUS。

- 文献归档已回读：11项，新增4、复用7；9项有托管PDF，本次新增3个PDF。SPAD2024已读在线相关章节但托管附件待补，LED2026仅元数据/摘要；两项附件待办已保存默认pending目录。
- 独立审查已处理：输出契约拆分、短样本TV偏差、长链诊断、Ising全量运行预算、8K仅成本stress及强制块下限；623行均为计划，其中24行显式不可行，未执行。
