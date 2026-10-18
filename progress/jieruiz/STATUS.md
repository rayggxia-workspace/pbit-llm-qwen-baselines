# jieruiz 项目进度

更新时间 2026-10-18T20:34:24+08:00；实际GitHub登录@jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。

## 当前Issue19：FFN精度与短流基线

- 独立工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/llama2-ffn-precision-issue19-20261018；分支task/19-llama2-ffn-precision；PR20到pbit-tlm-attention-details-20261016 @dd9f12b8cc25f474cafb54b1a58f2be20506cd9e。
- 阶段基线PR20已实际合并到pbit-tlm-attention-details-20261016，merge `40ea9f121c27ed7ea6e8a2e653e92246f3adcbfa`，源码head `1cbf4168b8d2e37dbd398d88e5823c3db009eecd`。Issue19同步评论：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/19#issuecomment-6248484271。16/26项已交付；剩余评测未完成，Issue19仍开放。
- 已收回16/26完整FFN替换PPL：IID256三种子6.256753±0.005911，分层64为6.758371±0.008464，分层128为5.308904±0.001642；IID4096首种子5.091985，另两种子仍运行。无采样W8+A8准确SiLU为5.038305，原BF16为4.979503；Q10与enum256的完整NLL相等。
- 已实际验证：模型/语料/token/配置SHA、原BF16重新运行；服务器2082为17/17、追加2090为18/18；新收回产物全部按原manifest逐SHA核对；v4分析16项同口径通过。仅本地无Torch环境测试会跳过相关项，不代替服务器验证。
- 当前运行：原数组2084，8/9对应IID4096种子1/2运行；10-15、22/23排队，最多2GPU。执行快照a8ea21f75ae6d736b2bc0136f8ee55977b082060不变，未取消/重交/覆盖。
- 范围：只测Llama2全部32FFN；Attention仍原BF16，无PV/Ising；不测Llama1，不训练，不改RTL或工艺数据。数值恢复为FP32统计参考，非完整bit-true硬件。
- DS-CIM对照：128拍归随机舍入/混合unary；DS-CIM的二维优化PRNG、偏移编码、SRR与旧普通双流/OR不同；论文LLM为256拍误差注入且有3.4/7.2个百分点平均准确率损失。Issue5/PR6只读，不接管。
- 已知缺口：RNE低位对照、逐投影与尺度/共享粒度消融、原权重+FP32内核控制、真实PRNG及完整定点硬件。没有新PT功耗或同精度能效证据。
- 正式成果：experiments/llama2_ffn_precision/、llama2/results/ffn_precision_20261018/；辅助work/jieruiz/19/。权重和逐窗长NLL留既有服务器个人项目。
- 阻塞/待同步：无评测数据阻塞；Projects缺read:project待同步。Issue19保留开放，合并本阶段基线不等于剩余评测已完成。
- 下一步：收集剩余2084结果，先核原manifest，再从最新TLM base创建独立结果分支/PR追加；保持执行快照与原件SHA。不得重开已完成基线或把旧PR20当未合并。

## 既有交付

Llama2基线+116TLM为Issue14/PR15，已合并7a506365；三模型入口Issue16/PR17及回执PR18已合并，base dd9f12b。Llama1 Issue12/PR13已合并07d0338。治理/DS-CIM/硬件/筛选其他独立分支维持原审查状态。

合并回执记录：2026-10-18T17:57:41+08:00，独立checkout `C:/Users/86134/Documents/a_P_BIT/tmp/issue19-merge-receipt-20261018`，分支`task/19-merge-receipt-20261018`。仅同步既成合并事实，不改运行快照或数值产物。

## 当前Issue26：17项推荐文献原文阅读总结

- 更新时间：2026-10-18T20:34:24+08:00；负责人@jieruiz；Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/26。
- 独立工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/pbit-reading-synthesis-issue26-20261018；分支task/26-pbit-reading-synthesis；base pbit-tlm-attention-details-20261016 @3553996bf014a29dee7fdb2250a3965e8fd881a4。
- 阶段：本地已完成；任务分支/PR发布后追加回执，尚未合并。与清单Issue23/PR24、短流Issue22/PR25及运行中Issue19保持独立，未接管实验或修改其快照。
- 成果：architecture_tlm/PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md；原清单未改，用户pbit_llm_master_report_20261012目录保存同字节副本；SHA256 cfed61fc7eb8e3d12b802a50f8b601ae89c5f8a1f2a7781460a4c8ae09d03c05。
- 阅读：17项全覆盖，16项有全文/完整官方资料；Current Digitizers DOI10.1103/s86j-5jcr仅摘要。p-PIM主文和补充已读，SANTA明确区分v1/v2，Z1T源码和配置固定revision。
- 实际验证：17行总表及17个逐篇条目、26份源资料字节SHA、UTF-8/LF、原清单SHA不变和同字节副本；独立技术复核通过，两处边界澄清已纳入。无新模型/PPL、RTL/PT、TLM、服务器任务。
- 证据/交接：work/jieruiz/26/SOURCE_EVIDENCE.json、MANIFEST.json、VALIDATION.json、HANDOFF.md；公开Git不含论文原文或受限工艺资料。
- 阻塞/待同步：Current Digitizers需合法全文后补评；Projects实际查询缺read:project，未同步看板。不影响本次文献报告交付。
- 下一步：审阅本任务PR；若补到Current Digitizers全文，再补正文/补充的阵列、采样和PPA边界。实验建议不等于已授权启动新实验。
