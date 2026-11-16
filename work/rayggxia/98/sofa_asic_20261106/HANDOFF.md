## 2026-11-16 Issue98：Fig.11 片上能量及解码覆盖

- 继续 Issue #98 / PR #246，工作分支 `task/98-sofa-asic-comparison-20261106`，PR base `main`，表格更新以 c2bc743d7c47a2170a9b74a300bae71fe8d99cbe 为基础。
- 18 行保持每篇一行。11 行有数值片上能量，其中 BitMoD/Tender/EVA/M-ANT 为已计价小计，OASIS/Harmonia/Kelle 为局部算子，OPAL/EdgeCIM/SoulMate 保留明示原生边界。本项目完整 TLM 15.27 mJ/token 片上，173.16 DRAM，188.43 计价总量。新增原论文的 `Original decode coverage`，并标注 embedding、LM head、token selection 的公开范围。
- [复算方法](../../../../architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/ONCHIP_PRICE_METHOD_ZH.md) 与输入输出在同目录。DeepScaleTool Fig. 3 读图约 65→28 为 0.37×、45→28 为 0.58×，只用于明确分出的 OPAL/Kelle 逻辑代理。
- 已本地验证：`python price_onchip.py` 与 JSON 数值一致，XLSX 18 行文献链接、能量列和来源覆盖列有效，唯一匹配总能量为项目自身。XLSX SHA-256 `4a28a15796dc2d65635bbddb4c85c2d28126ba135a5bd28462b35804a9dec9fe`。工作目录 `tmp/qwen-aligned-ext-issue98-20261116`。无新推理、训练、RTL、PPA 或外存仿真，无新数据集/模型字节，沿用已有冻结输入。待 PR 审阅和论文版表格排版。

## 2026-11-16 Issue98：Fig.11 一篇一行 benchmark

18 行覆盖本工作与 17 篇论文。片上、外存传输、含外存总能量分别列示；同一论文的其它精度和调度放在同一行。P-bit 15.27/173.16/188.43 mJ/token；外部部分能量小计保留在备注。Excel 与 Markdown 内容已比对，工作表可筛选。Issue #98 / PR #246，负责人 rayggxia，目标 main，工作目录 C:/Users/86134/Documents/a_P_BIT/tmp/qwen-aligned-ext-issue98-20261116，Projects 待同步。

渲染检查数据区和表头，确认 18 条唯一工作、18 个源链接、表筛选及冻结表头，检查能量边界、封存数值和原字节。无新增模型或电路仿真。SHA-256

- 5221b846d52264398ab6c69b1e0a7dd7c6396521c038dc6c0b7a46572d40a4b0 FIG11_LLM_BENCHMARK_ZH.md
- 3225d0185a17d549c6bfb2543ec2b7cb05bbba71b3e537c762d35bdbb6c8e9cc FIG11_LLM_BENCHMARK.xlsx

---

## 2026-11-16 Issue98：EVA / M-ANT 快速外部估算

Qwen3-4B B1/2K、250 MHz、共同 LPDDR 与 BF16 全词表 head。EVA 的 252 个线性算子 × 三种位宽与作者原始 FC 叶函数逐项核对，W2/W3/W4 为约 51–62/67–82/83–103 ms/token，外存约 64/78/93 mJ/token。M-ANT 每 4/8 拍发一个 tile 的情景为约 37–56/67–86 ms/token，外存约 91 mJ/token。文档含 EdgeCIM/CELLA 原报范围。无新整机签核或模型质量；见 architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/EVA_MANT_ESTIMATE_ZH.md。负责人 rayggxia，Issue #98 / PR #246，分支 `task/98-sofa-asic-comparison-20261106` → main。工作目录 `C:/Users/86134/Documents/a_P_BIT/tmp/qwen-aligned-ext-issue98-20261116`。Projects 待同步。

两次运行 JSON 原字节一致；共 7 情景，以相同 argv、Windows CPU/Python 3.8.1 从冻结模型和封存摘要复算。原作者 EVA FC 取 blob 指定的 `_run_decode` 与 IS helper 逐项验证 756 项，核对周期、外存读写位数、相同带宽时的重叠公式。原始权重/数据集未加载。可复算命令见报告。SHA-256：

- 2c359c61b753b98091daa622ebcf4aeea02fb2a934140682eb148cf02e24e203 estimate_eva_mant.py
- 7a1eb5e278328c1e8940cc2e64508efd9b2b6481bb0eefe6dc6dbe406e0f7ff5 EVA_MANT_ESTIMATE.json
- 94da9811e20a68f9673b5e4fd73f34909a3eafeec4b6929fee2ae8742efc378e EVA_MANT_ESTIMATE_ZH.md

---

## 2026-11-16 Issue98：Qwen3-4B 快速外部 benchmark

按用户要求优先轻量估算，沿冻结 B1/2K、250 MHz、136.46 GB/s LPDDR 计价，以同一个完整 BF16 head 对齐。BitMoD 重跑作者阵列周期，原阵列 W6/W3 为 187–214 / 130–144 ms/token，映射敏感性 256×4 为 54–80 / 39–53 ms/token。Tender 原 64×64 OS、B1 推导为 248–268 ms/token。上述为解析重叠/串行情景，作者原生运行及完整同库 PPA 独立。P-bit 封存项目 TLM 51.13 ms/token。五个情景的两次运行各约 3 秒且 JSON 原字节相同。见 architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/QUICK_BENCHMARK_ZH.md。Issue #98，PR #246，负责人 rayggxia，分支 `task/98-sofa-asic-comparison-20261106` → `main`。本机复算目录 `C:/Users/86134/Documents/a_P_BIT/tmp/qwen-aligned-ext-issue98-20261116`。Projects 暂无本会话可写入口。

验证：`python architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/quick_benchmark.py --artifact BitMoD --summary architecture_tlm/process_28nm/results_20261111/SUMMARY.json --out architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/QUICK_BENCHMARK.json` 重复两次，覆盖 324 个 decoder 矩阵及一个共享全词表 head、五个情景，核对能源单位和重叠顺序；无新实际权重/PPL、STA、外部原生 DRAM 或数字网表。项目参考源 01a2fb1d13018d381e012630ea1be442e85bdd26；任务父 1afec23a36f56e7af372f2afb8c2a16c752e41d7。产物 SHA-256：

- 181130ca321794f652d270a92a132541a836f25767278fce0a113d560fb67fc1 quick_benchmark.py
- 8b09ed8e7bdd8c2b4d1866bf9a0cb8eeb6cb614f23a98cf4c79f926b80c1778d QUICK_BENCHMARK.json
- 870bb7ec83067d087a55267b20010eac56590064c7777d9444a2c56fb7df072f QUICK_BENCHMARK_ZH.md

---

## 2026-11-16 Issue98：Qwen3-4B 外部架构对齐协议与 benchmark

用户要求外部架构运行相同 Qwen3-4B，统一 28HPC+ TT 0.9 V／25°C、250 MHz、原生 Ramulator LPDDR5-derived8533。新版固定模型、原生桥和配置散列，生成项目四组及外部资格状态。已实际运行 BitMoD 作者 e445a5f3 的阵列周期模块，覆盖 325 个矩阵项、36层及全词表。未执行外部整机原生 LPDDR、真实权重推理或 28 nm PPA。远程预检 DNS 11001，未提交作业。此轮所有外部整机值为空。PR246 待审。

交付目录 architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/。验证了原生桥与 YAML 的原始 SHA-256，复算并检查项目摘要，复跑上游 BitMoD 矩阵模型，确认局部输出会被整机导入器拒绝。6个交付文件的 SHA-256：

- 5c5c434637d21b25c9fccab186cb68d60d5fe49d2146cd732ed6a55f1d1a6e9e architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/BENCHMARK_ZH.md
- 928305e927cb0e56d6214cc61c80e7920e0d5a9d660519007ab363522c587676 architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/BITMOD_MATRIX_PILOT.json
- cbe3f7ca44a47a2336fe6d4ada9cd7215f5fe6c01617da0b05917813375f540e architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/build_benchmark.py
- ae6656497f35788cca468b938e63a8940a73c44c3cff8acb21837f71d3d4066c architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/README_ZH.md
- 68f7131823390c08ff4d55458be873b7a6d73a0e615e9887bb9b62dba2a2dd15 architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/run_bitmod_pilot.py
- 6aaac122d52941a067b070ef6dc4959ecbf27ddbb1228680094090083e9660fc architecture_tlm/benchmark_inventory_20261029/aligned_qwen4b_20261116/TARGET.json

下次继续需要候选实现和资源证据。BitMoD 首先接入其地址排程与共同原生桥，并补未覆盖算子；EdgeCIM 等需正式架构实现或可校验的移植。看板待同步。

---

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
