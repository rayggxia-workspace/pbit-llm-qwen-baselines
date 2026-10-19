# 本轮补传状态（2026-10-19）

权限已恢复，当前为发布准备阶段；尚未推送/创建PR。实时状态以PUBLICATION.json及本人STATUS为准。以下交接保留原执行时点；其中无push权限/未发布描述仅指原时点。原manifest应按原交付提交验证。

# Issue36 交接

负责人amlink1219；2026-10-19。正式目标仅为 `rayggxia-workspace/pbit-llm-qwen-baselines`；[Issue36](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/36)。

本地工作目录 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/pbit-digital-attention-issue36`，分支 `task/36-digital-attention-reference`，PR base `pbit-tlm-attention-details-20261016` @3553996bf014a29dee7fdb2250a3965e8fd881a4。执行账本源提交a4f19659922b26db89c662f5c6d90cf1136bcf8c；文档/交付提交由本分支git log读取，非执行源。独立实现工作树da36保留，原提交d07780dfea32e1c9d363fe279f3c41420e6b029d，已cherry-pick。

## 已完成

- 按用户意图把主验收改为完整模型PPL预算下的完整Attention PPA，补充AGENTS，保留原规则和Issue35执行快照/CPU预检约束。
- 阅读目标项目最新README、AGENTS、状态/协作、Issue和PR；发布前复核base未变，没有接管Issue32/34的FFN改动。
- 阅读FlashAttention/online normalizer/ITA/FSA一手文献及作者实现入口，给出具体BF16/FP32、64tile、GQA复用、64KiB scratch与明确数据流的D0参考；未直接移植跨工艺PPA。
- 10/10本地解析测试通过，512/2048/8192三点账本生成成功。无本任务服务器作业。不是模型推理、TLM时序验证、RTL或DC/PT。
- 2K共132120576MAC、KV24MiB/weights84MiB，主SRAM流式两pass的16GB/s资源下界14.155776ms；仅宏面积0.5316195528mm²及已知流式内部能量0.169958493mJ有表来源。完整PPA与实际延迟为null。
- Zotero去重新增FSA v4一篇，复用三篇；四篇托管PDF回读与SHA核验，实际阅读范围见REFERENCES.json。论文PDF/工艺库/权重/原始模型数据不进入本提交。

正式代码/报告 `architecture_tlm/digital_attention_reference/`，运行产物 `architecture_tlm/results/digital_attention_reference_20261019/`，验证与模型/数据来源见本目录JSON。模型未参与本轮解析运行，既有BF16质量锚点及原始版本/输入SHA已索引在QUALITY_ANCHOR.json；旧Issue35分支仍未上传。manifest不对自己做循环哈希，提交后核对Git blob字节。

## 远端和阻塞

已核实登录amlink1219/id75301230、仓库id1420564659，fetch/push解析到唯一正式workspace目标。push=false、triage=false，因此没有推送任务分支，也未创建PR；没有自动合并。本人Issue36可同步结果摘要，结果同步后保留open。Projects查询实际返回INSUFFICIENT_SCOPES，缺read:project，故看板待同步。REMOTE_STATE.json记录实际核验时间和权限。

## 接续步骤

1. 重读最新Issue36、PR与本人状态，核验base及目标remote/pushurl；保留本地提交。获得同账号push权限后，仅推 `task/36-digital-attention-reference`，使用PR_BODY.md创建指向上述base的PR，并把真正PR链接、commit和验收结果写回Issue/STATUS。不要回退旧仓库或陌生账号。
2. 如仅要复核账本，从仓库根运行VALIDATION.json的两条命令，输出到新的目录，不覆写归档；只需普通CPU毫秒级计算。任何新模型/综合长跑按服务器规则走调度。
3. 完成有限字长EXP/倒数/PV数字实现与同工艺单元表征，接入行为级模型跑完整PPL，再构建有bank/互连依赖的调度。报告中的下一步有明确缺口，不能以占位系数宣布数字基线PPA已闭合。
4. p-bit方案与数字PWL/采样都使用同一PPL预算与完整模块边界；用户尚未固定允许的PPL增量。当前没有新D0有限字长PPL，也没有新PPL8192。
