用户再次核实门控历史：双路gate/value及三投影K4 AND-bank均已做，不能把保留门控/多位编码当新主线。当前优先训练B4/T32/K32随机计算FFN；旧结构须明确新增条件和数字/原实现对照。报告§4.2与JSON已纠正，未启动训练。


用户纠正后的增量：旧两投影全路径降为高风险诊断，加入匹配20层连续入口与四层4bit原件、表示/采样/结构控制门禁；补充AGENTS防止按单层结果重复优先推荐失败扩层路线。没有新训练或质量结果。

# Issue61 硬件感知训练调研交接

负责人 amlink1219（GitHub75301230）；正式目标rayggxia-workspace/pbit-llm-qwen-baselines（repo1420564659）。2026-10-19核验push/admin=true。分支task/61-hardware-aware-training，独立本地目录workspace_projects/ht61；base集成88764ec8f6f00ed05f4ab337902bd23ad08cc4a8。不是旧个人上游。

## 已完成范围

一手文献和Extropic Z1T代码/版本核验；审计旧P-DNN/AND训练及variance负结果；给出现有模型三线微调与原生模型训练阶梯，精确区分SiLU恒等式、结构变化、T/N/S、真实前向与代理梯度。同参数Qwen FFN宽度4864→两矩阵7296已数学校核。正式报告及JSON位于architecture_tlm/，来源与校核在本目录。

仅CPU标准库公式、文档/链接/计划及四个既有FFN源SHA检查，不是新模型质量验证。没有新训练、checkpoint、数据下载、GPU/服务器作业或PPA。报告预算为建议，用户的H100资源描述不代表已获具体allocation。

## 验证与恢复命令

在目标checkout根运行：

```text
python -B work/amlink1219/61/validate_research.py
```

结果见VALIDATION.json。先按根AGENTS重读PROJECT_MEMORY§0/1/3.1/12及远端Issue61/PR、本人STATUS，再核对文件manifest。公开来源固定提交、路径和SHA见SOURCES.json；不要把本次报告称为本项目训练收益实证。

## 下一步

1. 审阅计划并为实际训练明确执行Issue/负责人；数据revision、许可、去重、train/validation/test、SHA及实际H100 scheduler/配额/本人存储尚需冻结。
2. 三线分别先实现短前向和梯度/缓存门禁，跑原BF16；冻结源码SHA后做同token数数字微调、未训练硬件、真实短流训练对照。FFN T16、激活N扫描、筛选8块/Ising S128先独立，不同时改变全部模块。
3. 在validation选参，后做完整WT2与另一个未见语料/下游任务，多训练seed与采样seed。禁止WT2 test调参。导出W8重载、真实有限前向与成本复核。
4. 只有质量和成本成立才扩32M/128M微调token或原生R1/R2/R3阶梯。更多算力用于受控比较和重复，不跳过物理概率/相关性/有限精度边界。
5. 最新Issue50/PR52及Issue59是同事既有质量工作，只读其公开结果；不能访问其私人服务器目录、取消或重交其作业。旧交接里的2430/2461不是本次实时队列查询。

## 发布与待同步

本文件创建时报告本地完成，发布后的真实分支/PR/提交回执另见PUBLICATION.json；没有该回执不能称已上传。Issue验收和看板按实际响应记录，不自动合并或关闭Issue。Zotero仅发布本批条目键/状态/附件SHA；全库去重快照和PDF留本机既有库，不进入Git。

实际研究交付已上传：结果提交`777b3e51aec48c5c689c78e2257e18243c18c4b8`，PR#63（https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/63）开放待审、未合并；远端ref/PR head及文件范围已核验，回执PUBLICATION.json。后续元数据提交不改变稳定manifest所核研究内容。
