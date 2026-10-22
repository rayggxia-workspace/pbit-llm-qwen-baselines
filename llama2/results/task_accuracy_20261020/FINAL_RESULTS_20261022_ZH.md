# Llama2-7B任务评测：26项最终核验（2026-10-22）

PIQA validation1838与ARC-E test2376，各13配置，zero-shot、原始lm_eval0.4.8、无额外BOS/聊天模板。保留旧8项与无损W8存储修复18项，未重复推理。

## 独立官方逐题验收

26/26封存完成，共54782个配置内文档、109564个acc/acc_norm指标逐题等于固定版本ConfigurableTask.process_results。使用原始YAML解析的doc_to_choice/doc_to_target与parquet标签，未用已存metrics当oracle；同时核验源码/输入/文档SHA、完整唯一ID、候选token、全部32层prefill/decode和active/dummy覆盖。未重哈希14GB权重，模型身份继承已核验manifest。

|任务|配置|acc均值(%)|acc_norm均值(%)|相对BF16 acc百分点|acc_norm百分点|
|---|---|---:|---:|---:|---:|
|piqa|BF16|77.85637|78.99891|0|0|
|piqa|ffn_only，3seed|77.80196|78.99891|-0.05441|+0.00000|
|piqa|attention_S128，3seed|77.18535|77.43925|-0.67102|-1.55967|
|piqa|joint_S128，3seed|77.29416|77.87450|-0.56221|-1.12441|
|piqa|joint_S512，3seed|77.87450|78.67247|+0.01814|-0.32644|
|arc_easy|BF16|76.30471|74.66330|0|0|
|arc_easy|ffn_only，3seed|76.27666|74.32660|-0.02806|-0.33670|
|arc_easy|attention_S128，3seed|75.40685|73.83558|-0.89787|-0.82772|
|arc_easy|joint_S128，3seed|75.46296|73.58305|-0.84175|-1.08025|
|arc_easy|joint_S512，3seed|76.27666|74.06004|-0.02806|-0.60325|

逐seed指标、seed总体SD及相对BF16逐题改善/退化/不变计数见[官方核验JSON](FINAL_METRIC_ORACLE_20261022.json)。seed SD不是题集置信区间；小幅提高不代表统计显著胜出。

FFN为B4/T32/K32，Attention为原未筛选有限CTMC：FFN在prefill/decode替换，Attention在计分decode的32层替换，原始QKV/RoPE/cache/Wo及前缀Attention保留。短任务all-K，不证明长上下文筛选收益。Apple FP32独立模型仅历史参照。

本结果没有采用新赢家保持/校正拒绝、8位驱动或新物理随机源，不能继承到这些组合，也不是新PPL/PT/PPA。用户要求的llama2-7b定时已删除，本轮没有重建或修改自动化；无新推理、Slurm或冻结快照改写。

旧检查点和旧pending叙述保留其历史时间；本次最终核验覆盖它们的进度状态。Refs #73 / #55。
