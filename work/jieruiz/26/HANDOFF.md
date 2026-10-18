# Issue26 原文阅读总结交接

更新时间：2026-10-18T20:34:24+08:00。实际GitHub登录jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。

- Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/26。
- 独立checkout：C:/Users/86134/Documents/a_P_BIT/tmp/pbit-reading-synthesis-issue26-20261018。
- 分支task/26-pbit-reading-synthesis；PR base pbit-tlm-attention-details-20261016；基线3553996bf014a29dee7fdb2250a3965e8fd881a4。当前仅本地完成，发布动作发生后追加回执，不宣称已合并。
- 正式单文件：architecture_tlm/PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md，SHA256 cfed61fc7eb8e3d12b802a50f8b601ae89c5f8a1f2a7781460a4c8ae09d03c05，32635 bytes；用户副本C:\Users\86134\Documents\a_P_BIT\pbit_llm_master_report_20261012\PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md与正文相同。
- 输入：用户原推荐清单，SHA256 8dcacd8d944d7b32b314c001305db0e5f2cdfb208ea5c173a3b0d8a93f8da25b，未改。逐篇版本/源URL/关键节页及26份字节验证见SOURCE_EVIDENCE.json。原文文件仅在本地tmp/pbit-reading-review及用户Downloads；不上传受限PDF、源码副本或图像。
- 已完成：17项阅读索引与正文，16全文/官方完整资料，1仅摘要；FFN/Attention/存储/调度/能效综合建议；SANTA v2新增decode、p-PIM100Hz/HIL、FIGNA28nm、Z1T含/不含读出边界均重新核对；独立复核通过，两处澄清已纳入。
- 验证命令（Python3，无第三方依赖）：python work/jieruiz/26/validate_delivery.py --verify-local-sources --user-copy C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/PBIT_LLM_READING_SYNTHESIS_ZH_20261018.md；提交后加--git-ref HEAD；git diff --check。无本次训练/PPL/PT/TLM实验，不需要Torch、GPU或服务器数据。跨机器可省去--verify-local-sources和--user-copy，只校验Git内报告/元数据。
- 未完成：Current Digitizers全文与补充未取得；APS要求授权、MIT仅摘要，不能填未验证的采样数/PPA。未启动任何新实验，未改变Issue19的Slurm任务或Issue22/23文件。
- 已核项目权限：本账号可push；Projects GraphQL缺read:project，未同步看板。相关任务Issue23/PR24、Issue22/PR25仍独立open，不能把本报告当它们合并回执。
- 下一步：核Git blob与文件范围、推workspace任务分支并创建关联Issue26的PR；按实际回执同步Issue/STATUS。等待审阅；不得把PR创建写成合并，不自动关闭Issue。

## 实际发布回执

- 已推送文档提交 `e84b25932e293801c8ab009a02a1a448007b386f`；PR #27：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/27，目标pbit-tlm-attention-details-20261016，open、merged=false，已附当前任务。
- Issue26验收清单与评论已同步：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/26#issuecomment-6250003655；保持open等待审阅，不宣称已合并。
- 报告SHA256 `cfed61fc7eb8e3d12b802a50f8b601ae89c5f8a1f2a7781460a4c8ae09d03c05`；Git blob、26份源资料及本地同字节副本均通过；初次Git未选择账号的推送失败已通过固定credential.username=jieruiz解决，最终推送成功，无凭据外泄。
- Projects缺read:project仍待同步；Current Digitizers全文仍未取得。其余16项的阅读和本次报告已交付。
- 下一步：审阅PR27。本回执随后同分支提交推送；无需重跑模型或硬件实验。

## 用户补充全文后的更新（2026-10-18T20:52:51+08:00）

- 用户提供C:/Users/86134/Downloads/s86j-5jcr.pdf，8页，SHA256 3281c29a64261886d3356028d3e93692f8d421dd6d16128d18644767c4c94cfc；已读全文、视觉核对第3–7页并独立复核。此前“缺主文”状态已失效，保留上方历史回执作版本记录。
- 最新报告SHA256 41d5118da9d0b259e1ee54453362251ed020e5f2e06baa6a7179bf07844c7970；正文、总览、源码/数据边界和证据已更新；用户副本同字节。17项均具备全文/完整官方材料，无主文待补。
- 新结论：sCDC替代模拟crossbar列ADC，非逐项随机乘法；均值为tanh(alpha I/2)需器件感知训练；1/2/4采样、160张MNIST、单器件时间复用；180nm后版图读出PPA，非整机实测。延迟降低30.2%与速度提高43.3%已区分。没有继承到我们数字FFN的节能倍率。
- 验证：27份源字节、17条总结、UTF-8/LF、同字节副本；独立复核PASS。Git提交后再验证--git-ref HEAD。无新PPL/RTL/PT/TLM或服务器任务。
- 当前新增改动本地已完成，继续同一task/26分支和PR27追加推送；发布后记录真实commit。Projects仍缺read:project。
