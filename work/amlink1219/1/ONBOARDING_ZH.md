# p-bit for LLM 硬件设计接入核查

核查时间：2026-10-18T22:39:51+08:00。本地落地负责人：`amlink1219`。关联既有 [Issue #1](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1)，其原负责人 `jieruiz` 和待审 PR #2 保持原状态。本次不新建重复治理 Issue，不接管其他成员的实现任务。

## 身份、目录及远端

- 通过本机 GCM 凭据调用 `/user`，实际身份 `amlink1219`、ID `75301230`；连接器列出的其他账号不用于本任务认证。
- 正式目标 `https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines`，repository ID `1420564659`；pull=true、push=false、triage=false、admin=false。Projects GraphQL 实际返回 `INSUFFICIENT_SCOPES`，缺 `read:project`。
- 当前 DAC 根不是 Git 仓库。旧本地 `pbit-llm-qwen-baselines/` 指向 `jieruiz/...`，分支 `codex/and-variance-20261005`，核查时干净，未改动。
- 独立项目根：`E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/pbit-llm-qwen-baselines`。本地任务分支 `task/1-amlink1219-hardware-onboarding`，基线 `3553996bf014a29dee7fdb2250a3965e8fd881a4`，拟 PR base 为 `pbit-tlm-attention-details-20261016`。origin 的 fetch/push 均为 workspace 目标，无额外 pushurl/URL 重写。
- `main` 为 `8068bfbb71d892ef8b0850dea391aa612739aa4f`，停留于 2026-10-03；近期工作在集成分支和任务 PR，不能只看默认首页。

## 已读取的项目上下文

main/集成分支 README、集成/治理/待审备忘录 AGENTS、Issue/PR 列表与相关正文、Issue7/19/22评论、成员 STATUS、Issue1/19/22/28交接、TLM总索引、BASELINES、requirements和sources。原字节来源与 blob/SHA 在 SOURCE_MANIFEST.json；完整API快照在本机 outputs/pbit_hardware_onboarding_20261018。项目备忘录来自待审 PR #29，不表示已合并。

## 最新进展与协作边界

| 范围 | 最新远端状态 | 接续注意事项 |
|---|---|---|
| 治理 #1 / PR2 | open / 待审 | 本次仅在本机采用并补齐入口，原负责人仍为 jieruiz |
| 可用性 #3 / PR4、DRAM #5 / PR6 | open / 待审 | 使用其缺口与成本边界，不把审计当硬件实现完成 |
| FFN调度 #7 / PR8、11 | open / 待审 | 数字后处理RTL和工艺流程已有交付；PR11交接仍待工艺运行，备忘录另列本地PT摘要，远端未核原件，不能混称工艺结果已入库 |
| K访存 #9 / PR10 | open / 待审 | 区分GQA候选并集、逻辑保留率及物理burst读取 |
| Llama1 #12/PR13、Llama2 #14/PR15、目录 #16/PR17/18 | closed / 已合并到集成分支 | Llama1有82项TLM，Llama2有116项；TLM不是新随机方案联合PPL或硅实测 |
| Llama2精度 #19 / PR20、21 | Issue open / 阶段PR已合并 | 16/26项为已发布阶段；剩余运行状态是成员交接快照，本次未连服务器核实时队列，不重复提交 |
| Qwen短流 #22 / PR25 | open / 待审 | A8共享64、固定W8、IID/分层/枚举RTL已做功能验证；新Qwen短流PPL、新RTL DC/PT仍待测，能量表是条件估计 |
| 文献 #23/PR24、#26/PR27 | open / 待审 | 本次只核任务/交接，不宣称重新阅读或复现17篇原文 |
| 备忘录 #28 / PR29 | open / 待审，head ed1f9c9 | 读取PROJECT_MEMORY_ZH.md用于导航，与原证据/最新Issue交叉核对 |
| 双侧自然随机 #30 | open，负责人 jieruiz | 已新建精确条件Binomial短片段多seed/高斯对照任务；本次不重复开工 |

质量锚点均为仓库报告而非本机复现：Llama2 BF16完整WT2 2K PPL 4.979503；W8+A8准确SiLU5.038305；128拍分层三seed5.308904±0.001642；IID256三seed6.256753±0.005911。Attention保持原BF16，不能冒称Qwen/双随机/整条有限位硬件结果。Qwen双侧全量旧结果含Gaussian权重近似，Issue30正在补精确分布证据。

## 本对话后续硬件设计工作

1. 新任务先定位或建立Issue，明确本人范围和接口；先读Issue19/22/30更新及Issue3/5/7/9待审报告，避免重复实现或接管运行作业。
2. 固定工作负载（模型、batch、上下文、prefill/decode）、质量容差、数制与随机协议，再决定阵列并行度、共享和采样预算。固定W与双随机分别评估；128拍分层不冒称自然IID。
3. 明确权重SRAM/bank/端口/带宽、gate/up/down复用、部分和与计数位宽、非线性/格式转换、随机源/广播、KV/DRAM及控制的端到端数据流。
4. 将数值参考、bit-true功能、RTL、工艺PPA和TLM逐级连接到同一配置与SHA，并保留确定性低位/位串行比较；不先承诺采样缩短比例就是整机能效比例。

## 本次交付和阻塞

仅更新两处AGENTS和本人的STATUS/核查/交接/溯源记录；无实验代码、数值、训练、GPU、RTL/PT或TLM运行。原项目规则按原字节前缀保留。由于push权限缺失，没有推送任务分支或创建PR，没有修改原Issue正文、验收、标签、assignee或其他成员分支。看板未更新。待同步事项见HANDOFF和STATUS；权限恢复后先重新核对最新远端，再提交明确文件，通过任务PR交付。

远端进度同步：已用amlink1219在[Issue1发表评论](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/1#issuecomment-6251225780)，说明本地完成、未上传和权限阻塞；POST后已回读全文/作者一致。该评论不代表文档分支或PR已经上传。
