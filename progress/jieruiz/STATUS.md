# jieruiz 项目进度

更新 2026-10-18T16:36:42+08:00；实际GitHub登录@jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。

## 当前 Issue19：Llama2 FFN精度与低于256拍

- 分支：task/19-llama2-ffn-precision；PR base=pbit-tlm-attention-details-20261016 @dd9f12b8cc25f474cafb54b1a58f2be20506cd9e。
- 工作目录：C:/Users/86134/Documents/a_P_BIT/tmp/llama2-ffn-precision-issue19-20261018。数值子任务独立目录tmp/llama2-ffn-numeric-issue19-20261018，提交a03fde7已cherry-pick为e10896e。
- 范围：只读核对Qwen既有PPL；Llama2全32FFN的W8/A8/Q10/采样消融。Attention保持准确BF16 SDPA。Llama1不测，不训练。
- 实际状态：BF16 2081已复现2K4.9795028452/4K4.8958312205；Q10与enum256完整PPL/NLL相同，5.0488010814；CUDA追加2090已18/18通过。当前收回14/26完整替换PPL，64分层三种子6.758371±0.008464，128分层当前3/3种子。PR20草稿已存在、未合并，Issue19开放；新增文献/功耗分析待本次推送，没有新PT功耗测量。
- 方案：完整WT2 noBOS，2K/stride512；新BF16同时重跑2K/4K。固定尺度取train前8192tokens，测试数据不参与校准；A8为8位幅度+符号，不是通常signed INT8。
- 已知缺口：Qwen旧A12结果不等价当前A8；新Q10从未接LLM PPL。统计计数参考使用FP32矩阵恢复，不是完整有限位硬件模型。
- 成果：experiments/llama2_ffn_precision/；辅助与交接work/jieruiz/19/。
- 阻塞/待同步：无模型或语料阻塞。Projects缺read:project待同步。Issue7的脏工艺checkout只读，不覆盖或发布。
- 下一步：收集数组2084确定性精度分解与低T分层/中点/历史IID三种子完整PPL；通过各输出ARTIFACT_MANIFEST验证实际产物；任务分支/PR交付并持续记录完成项。执行源码快照a8ea21f75ae6d736b2bc0136f8ee55977b082060不变；只增测试的独立快照3ea0541。

## 已交付

Issue14/PR15 Llama2 BF16+116 TLM已合并7a506365；Issue16/PR17三模型入口和PR18状态回执已合并，当前base为dd9f12b。
Issue12/PR13 Llama1已合并07d0338。此前治理/硬件/筛选等独立分支维持原审查状态。

## 分层效果与功耗文献追加分析

- 当前收回14/26项完整替换PPL，全部核模型/语料/token/配置/校准/源码一致。64拍三种子均值6.758371±0.008464；128拍当前3/3种子，数值见正式报告。IID256已2/3，不能把2种子均值当三种子正式结论。
- 结论：64拍尚不保精度；小概率z及粗事件是重要线索，未做逐矩阵因果消融。相同T的分层方差不增不等于T缩小4倍仍保PPL。
- 功耗：平均W可能同量级，E=P×t；有序门限使单路帧内至多1翻转，但PRNG/时钟/累加等不同比。当前没有分层VCD/SAIF/PT，不能宣称实测节能倍数。旧PPA含12bit独立源/寄存器且不含RNG/SRAM，不直接迁移。
- 资料：experiments/llama2_ffn_precision/STRATIFIED_EFFECT_ENERGY_LITERATURE_ZH.md、analysis/EFFECT_AUDIT_20261018_v3.json；4篇primary文献及RTL证据SHA位于work/jieruiz/19/。
- 调度：128三种子和midpoint64/128均已完成；其他原对照仍运行/排队，仍最多2GPU。midpoint64=5.995513，优于分层64；midpoint128=5.412020，略差于分层128。midpoint128是向零截去幅度低位，不是最优RNE；不宣称随机已优于所有确定性方法。
- 发布：继续同Issue19/草稿PR20；本次追加分析尚待push。Projects无read:project待同步；没有新硬件功耗实测。
