# Issue250 论文原图参考交接

负责人 rayggxia；2026-11-08。仓库 rayggxia-workspace/pbit-llm-qwen-baselines，基线 main@206bf81f18ea88c4c625ce8d32edd18a58edd1cd，分支 task/250-figure-references-20261108。独立最小工作目录 tmp/figure-references-issue250-20261108。

用户白板 Fig.1–10 已逐项辨认；用户明确 Fig.8 暂时留空，未新增其主题。正式主文件 architecture_tlm/paper_figure_references_20261108/README_ZH.md；SOURCES.json 固定 11 篇论文的 PDF 字节SHA、37处参考图号/物理页码及原文链接。每图给出画法、借鉴点和与项目的机制/结果边界，接续只读的Issue204 Fig.7计划，不修改该任务文件。

验证：37处图号/页码caption anchor与实际原页图像核对；加6项文档/引用/UTF8-LF/版本/空Fig.8检查，共43项通过。Poppler渲染，PDF.js提取，不依赖摘要猜图号。正式主文件与SOURCES的SHA见VALIDATION.json。PDF/截图/白板不公开上传；阅读缓存 tmp/pdfs/figure_references_20261108。模型、数据、种子、工艺/RTL/PPA字段不适用：本次没有新推理、训练、TLM、RTL或EDA实验。

发布：正式文件、本人STATUS、HANDOFF、VALIDATION及后续PUBLICATION通过本任务分支/PR交付；实际commit、PR与回读以PUBLICATION.json为准。PR待审不称已合并，Issue250保持open。Projects连接器无相应写接口，待维护者同步。

长期备忘录：唯一维护目录tmp/project-memory-issue28-20261018在本轮核对时存在其他未提交增量，不修改其工作树。MEMORY_APPEND_ZH.md为供Issue28维护者接入的任务摘要，不是另一本独立备忘录；发布后将结果入口同步至Issue28。

恢复：先核Issue250/PR最新状态和PUBLICATION，阅读README与SOURCES；按SHA复用现有原PDF。不需重复下载或运行硬件/模型。PR待审仅保留必要小工作目录，无运行作业。最终根architecture_tlm同目录为正式文档同字节阅读副本。

已发布：科学提交1c84d72f30740385cb60231eae94786678463787，PR251 ready/open未合并；6文件远端内容一致、tree与本地index一致。实际摘要入口PUBLICATION.json；无运行任务。
