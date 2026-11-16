## 2026-11-16 Qwen3-4B 同条件整机重放

沿 Issue98 / PR246，父提交 588b7f76a1d002c7a04bda01b692bfda80b305f4，分支 task/98-sofa-asic-comparison-20261106 → main，负责人 rayggxia。主比较使用冻结的 PR249 Qwen 原生 LPDDR 数据。算法数值本次不跑，模型形状与工作量取已封存版本。外部证据锚为 Harmonia v3 Table I、§IV、§V-D。

复算目录 architecture_tlm/benchmark_inventory_20261029/harmonia_full_decode_20261116/。工作区根执行 python architecture_tlm/benchmark_inventory_20261029/harmonia_full_decode_20261116/replay.py --workspace .。仅外部重放可在其所在目录执行 python replay.py。JSON 记录主配置、阶段和敏感性。Python 3.8 两次完全重放通过，消费的四份项目来源通过 SHA-256；结果逐字一致。表覆盖 15 篇，论文范围逐行注明。补充项目解析链路运行核对到第 5 层后主动结束，完整归档行不受影响。

发布科研文件 SHA-256：

- 8a953c5112f27d283078b1b7a8cfb8f774b2524f4401f0d5ff5034bd9678cb90 benchmarks_zh.md
- ef9e054bb06071c8b8a365336a21caafff6c95fc1e5a7e384c507ddfd40cd2e3 inputs.json
- b5a0819d47ba4d1739c23effd5820876ed414d3832591201204c69a53f067ffe replay.py
- 33f4fc997d7dcdace88dd9345f6899c45e115c891ae4f44728052ff216c8468f report_zh.md
- dc326cbe2272315595e5f2e132ae3d2e5835f805b7c760e5a8140d8440f8205e results.json

无新 GPU/PPL/RTL/EDA；未验证 Qwen W4/BFP 质量、同库 STA、真实 SRAM 宏与同一详细 DRAM 后端。Projects 更新接口未提供。PR 待审，保持分支和 Issue 开放。

---

# Issue98：SOFA与ASIC比较专题交接

负责人：rayggxia；日期2026-11-06；仓库rayggxia-workspace/pbit-llm-qwen-baselines。
分支task/98-sofa-asic-comparison-20261106；base main@8cd4fba009598184bce4f1c806f038299b011ea0。
最小工作目录：tmp/sofa-asic-issue98-20261106（相对授权工作区）；没有模型、环境、原PDF复制。

成果：architecture_tlm/benchmark_inventory_20261029/SOFA_ASIC_COMPARISON_ZH.md。复用PR213目录，不修改amlink1219文件或继承其未合并实现。已有Issue98记录本次分工，无重复Issue。
来源：用户SOFA v1 PDF SHA已写正文；在线原文/作者材料与阅读位置在正文§10。FACT/DTATrans全文未核，DOTA生成协议未核，未改成确定的decode结果。

验证：正文UTF-8/LF、无本机/服务器私有路径、20组合/9配置表、归一化/DRAM公式与Git diff空白检查；详见VALIDATION.json。GitHub发布后逐字回读正文与辅助文件，PUBLICATION.json记录commit/tree/PR。模型/数据revision、推理命令、seed、数制实验均不适用，本任务无新实验。

发布边界：仅正文、本人STATUS前缀（其后保留main已公开原字节）和本任务小型交接/校验/回执；不上传PDF、权重、数据、工艺库、认证信息或其他任务未提交资料。通过独立分支/PR，未授权自动合并；Issue保持open。Projects连接器无接口，待维护者同步。

恢复：先读Issue98最新评论和本分支PR，再核PUBLICATION.json与正文SHA；仅补正文证据或发布元数据，不重复实验。最新主线若移动，保持已发布科学源可追溯，不覆盖其他任务STATUS。长期备忘录在唯一维护目录追加本专题入口并同步阅读镜像，整份记忆不随本PR公开上传。

已发布科学提交68ccc135fea89ab6b8ba5bcc427877fce762972b；4文件逐内容/blob回读一致，21检查通过。PR246 ready/open、未合并，base main；PUBLICATION.json为实际回执。后续交付元数据不改变正文SHA。

PR待审保留此最小目录；合并后核对refs/未跟踪资料和恢复索引再回收。没有大型临时结果或运行中作业。
