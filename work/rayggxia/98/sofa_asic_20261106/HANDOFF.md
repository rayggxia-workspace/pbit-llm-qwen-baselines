## 2026-11-16 Issue98：纠正 Harmonia benchmark 证据

Harmonia 未运行其实现、未接入项目 TLM，也没有 Qwen3-4B 推理或正式同条件整机结果。此前用论文公开参数和 Qwen 形状得到的数值为单独的探索性解析估算，现已撤出正式表。当前 Excel 与正文只标本项目四组为项目 TLM，Harmonia 只列作者发表的综合 PPA 和 Llama-3.1-8B-Instruct 分项。历史脚本和输入结果用于追溯，当前说明加归档标签。此次为证据纠正，未新增仿真。PR246 待审。

工作簿两个工作表已渲染，并检查了 Harmonia 行的来源、能力范围、NR、以及可筛选结构。此次改动文件 SHA-256：

- d65d1208983f13e3dbad02a9ec969d2edcb0c1d62bff9d2cd9eadcb91cb3c2ea architecture_tlm/benchmark_inventory_20261029/LLM_HARDWARE_BENCHMARK_20261116.xlsx
- 7d4ca46c8eabae887d17cbdf2ceb42611ad94819e6e63542cb7d4b316f029ee5 architecture_tlm/benchmark_inventory_20261029/LLM_HARDWARE_BENCHMARK_20261116.md
- 5e428618a5603b93b5f7812e9f2214ae97df864df8faf8e1e0fc29b8cdc2069e architecture_tlm/benchmark_inventory_20261029/harmonia_full_decode_20261116/REPORT_ZH.md
- 033c10eb4da7885add0de7c0f176275df09bbda71f201d1e6d2e001abd9f314c architecture_tlm/benchmark_inventory_20261029/harmonia_full_decode_20261116/BENCHMARKS_ZH.md

---

## 2026-11-16 Issue98：Fig.10/11 benchmark 表

新增可筛选 Excel 和 Markdown，正文候选 13 行，来源 36 行。每个指标保留各自模型、数制、阶段、工艺、内存和计价边界。优先 Harmonia、EdgeCIM、Zhou 等人、NVLLM、Sirius、RS-LPU；BitMoD 工件作为可执行下一轮候选。Harmonia 采用此前已核验的近似情景。本轮做原文审计、表格与取舍，未执行模型推理、TLM 或 EDA。PR246 待审。

文件路径 architecture_tlm/benchmark_inventory_20261029/LLM_HARDWARE_BENCHMARK_20261116.{md,xlsx}。核验主表与来源页的独立筛选表、Times New Roman、OOXML 文件和两页预览。文件 SHA-256：

- ba2439e3c506706651d7774ece359649e6968d6f06714fc14ebbd9d1dad94cf4 LLM_HARDWARE_BENCHMARK_20261116.md
- d170e6aaad8f965ab70785684a23b7cf45e6e73b750c49cd5f8a484b0b28cdb9 LLM_HARDWARE_BENCHMARK_20261116.xlsx

原始字节和小数边界见文档及各行来源。当前主表的 EdgeCIM Qwen3-4B 数值仍用原作者 Fig.12 定位，后续按同模型场景复跑。看板待同步。

---

## 2026-11-16 Harmonia 精度展示与权重流量复核

沿 Issue98、PR246，基于 da0cbb8d16eab453c3d0bf9e0d18fcf0531df11c。外部 Harmonia 以情景量级展示，双缓冲约 40–50 ms/token，单缓冲约 60 ms/token，整机能量约 80 mJ/token、面积约 4 mm²。三种子冻结账本证实项目权重流量约 5.36 GB/token，Harmonia 两个情景约 2.14 GB/token，4 pJ/bit 下权重字节差约 100 mJ/token。外部主表保留原生量化，采用共同任务和质量门槛。现有 W8 + Key Selection / P-bit 配对用于机制消融。

本次两个科研文件：
- architecture_tlm/benchmark_inventory_20261029/harmonia_full_decode_20261116/REPORT_ZH.md SHA-256 da8b57f9b1e9fdb5c6861e8f5b809315069aa530830b1d203405d877c71e25e5
- architecture_tlm/benchmark_inventory_20261029/harmonia_full_decode_20261116/BENCHMARKS_ZH.md SHA-256 e56d8e50fb787b17457f5108f47e39b3502eff7d2dc1feb6704a6563e5a5012a

验证采用已有 RESULT.json 三种子 memory.by_kind、封存项目摘要以及外部 RESULTS.json 的八个线性投影和内存事务。读写能量按 32 pJ/B 复算，结果代码/输入/JSON 的原 SHA-256 匹配。权重数值精度和应用质量须在未来的正式对照测定。无新推理、布局或芯片数据。

---

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
