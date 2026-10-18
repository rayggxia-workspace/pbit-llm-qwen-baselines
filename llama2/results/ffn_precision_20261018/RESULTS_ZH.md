# Llama2 FFN完整WT2精度分解

更新 2026-10-18T15:18:31+08:00。Issue19；Attention全部保持原BF16准确SDPA，没有PV采样。

| 方案 | 完整2K WT2 PPL | 相对BF16 | 实际状态 |
|---|---:|---:|---|
| BF16参考 | 4.979502845 | — | Slurm2081完成，与旧记录一致 |
| w8_only | 4.980946374 | +0.029% | 完成，335686目标；Slurm2085 |
| a8_exact | 5.038304561 | +1.181% | 完成，335686目标；Slurm2086 |
| a8_q10 | 5.048801081 | +1.392% | 完成，335686目标；Slurm2087 |
| enum256_q10 | 5.048801081 | +1.392% | 完成，335686目标；Slurm2088 |
| iid_T256_s0 | — | — | 尚未收回完整结果；数组2084 |
| iid_T256_s1 | — | — | 尚未收回完整结果；数组2084 |
| iid_T256_s2 | — | — | 尚未收回完整结果；数组2084 |
| iid_T4096_s0 | — | — | 尚未收回完整结果；数组2084 |
| iid_T4096_s1 | — | — | 尚未收回完整结果；数组2084 |
| iid_T4096_s2 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T16_s0 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T16_s1 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T16_s2 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T32_s0 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T32_s1 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T32_s2 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T64_s0 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T64_s1 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T64_s2 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T128_s0 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T128_s1 | — | — | 尚未收回完整结果；数组2084 |
| stratified_T128_s2 | — | — | 尚未收回完整结果；数组2084 |
| midpoint_T16 | — | — | 尚未收回完整结果；数组2084 |
| midpoint_T32 | — | — | 尚未收回完整结果；数组2084 |
| midpoint_T64 | — | — | 尚未收回完整结果；数组2084 |
| midpoint_T128 | — | — | 尚未收回完整结果；数组2084 |

已收回4/26项替换PPL；未完成项不能用于结论。另有BF16 4K PPL4.895831220529201，仅参考，不与2K替换交叉比较。

所有正式替换使用2K window/512 stride、noBOS、335686个真实next-token目标，各一次；FP32 CE、FP64总NLL。Sx/Sz仅train前8192token校准。W8为每64×64tile；A8为8位幅度q/256加独立符号，非普通signed INT8。

w8_only保留连续激活与准确SiLU。a8_exact编码x和z，准确SiLU；a8_q10在同编码上改为Issue7 Q10 RTL算术；enum256_q10用完整门限遍历。随机/分层/midpoint项均使用准确SiLU，隔离采样误差，不能冒充Q10+随机组合已经测过。

## 三种子汇总

| 方法 | T | 完整种子数 | PPL均值±样本标准差 |
|---|---:|---:|---:|
| iid | 256 | 0/3 | 待三种子完成 |
| iid | 4096 | 0/3 | 待三种子完成 |
| stratified | 16 | 0/3 | 待三种子完成 |
| stratified | 32 | 0/3 | 待三种子完成 |
| stratified | 64 | 0/3 | 待三种子完成 |
| stratified | 128 | 0/3 | 待三种子完成 |

## Q10截断诊断

累计471022280704个g/u位置暴露（包括滑窗重叠，不等于独立token数）。
- g_input_clipped：1055081，占0.000223998%。
- u_input_clipped：746340，占0.000158451%。
- output_saturated：0，占0.000000000%。

## 校验与限制

- 模型官方revision01c7f73d771dfac7d292323805ebc428287df4f9；11文件重新核SHA。身份manifest SHA8ba3ccc3acf4b1a38a8c41a71ecafa8f4a0c1f53900a6298a32088dd57847d74。
- 原test raw SHA173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08；完整token IDs SHAd47afcd2762c6a3e70f50c5b7de0e4ccad565d812aee21772b7cd276b7b8626c。
- 执行源码a8ea21f75ae6d736b2bc0136f8ee55977b082060，配置在experiments/llama2_ffn_precision/configs；BF16源码base dd9f12b。对应source/config/protocol/environment/command均随各结果保存。
- CUDA核心2082的17/17验证通过，无跳过；独立只增测试快照3ea0541的2090补测18/18通过，覆盖正式确定性开关下的CUDA IID。两份原日志随附；评测快照a8ea21f未修改。校准只使用train前8192token；calibration/calibration.json列出固定尺度和原始语料/选中token SHA。
- 原始完整成果留服务器个人项目/home/Hongjie_Zeng/projects/pbit-llama2-ffn-precision-20261018-issue19/outputs。REMOTE_INDEX.json指出每项原目录、原manifest SHA及已复制文件。每个ARTIFACT_MANIFEST保留所有原始文件（含未复制的逐窗NLL）散列。
- 本目录仅收回完成且SHA全匹配的小型JSON与测试日志；逐窗NLL.jsonl留服务器。Git保存原始字节；PUBLICATION_MANIFEST.json列出本目录实际发布文件的SHA。
- 数值模型用共享64联合事件计数压缩+恢复后的FP32 GEMM；不是整条有限位tile重缩放电路或实际PRNG逐拍验证，不测能耗。只有Q10后处理本身匹配整数RTL oracle。
- 单次GPU评测时间受实现/启动/算子开销影响，不用于ASIC的采样周期与能耗比较。

[详细编码、256拍证明及比较方法](../../../experiments/llama2_ffn_precision/README_ZH.md)。
