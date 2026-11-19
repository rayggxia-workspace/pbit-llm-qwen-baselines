# 三组数字基线：统一cached完整WikiText-2 PPL

2026-11-19 UTC，Issue259 / PR260，负责人rayggxia。三份结果均为status=completed，封存与逐目标核验已通过。

| 配置 | 完整WT2 PPL | 相对同轮BF16 | 数组任务 | 计分耗时 |
|---|---:|---:|---|---:|
| 原始BF16＋稠密Attention | **11.5382889054** | 参考 | 5900_0 | 947.38s |
| FFN W8＋稠密Attention | **11.4823299065** | -0.4850% | 5900_1 | 948.64s |
| FFN W8＋SparQ K128＋准确Softmax/PV | **10.7699059654** | -6.6594% | 5900_2 | 884.82s |

第三组相对W8 dense的PPL降低约6.2045%。这是本次WT2质量评测结果，计分脚本在GPU上的耗时不是TLM硬件延迟或加速比。

## 对照边界

三组均来自原始后训练版Qwen/Qwen3-4B，revision `1cfa9a7208912126459214e8b04321603b3df60c`。无继续训练、无训练后FFN或Attention投影覆盖。模型、tokenizer与原始WT2文件在每个任务加载前按固定SHA核验。

W8仅量化36层FFN的gate/up/down共108个矩阵，沿用已完成5897的tile64固定PoT尺度、最近偶数舍入及signed码[-127,127]。激活、原始SiLU/逐元素乘法、QKVO权重、Norm、残差、embedding与LM head保留原BF16接口。两组W8的整数码、尺度指数及解码权重逐项匹配同一W8_MAPS，未改变其他权重。

筛选采用既有SparQ式r32、总K128包含最近32、同一KV组的四个Q头共享候选。候选内用FP32重算准确QK、Softmax和完整加权PV，返回BF16接口；没有mean-V补偿。无Ising、p-bit采样或稀疏PV采样，生产评测中的torch随机采样函数被明确禁止。该项是数字算法质量控制，不是逐拍RTL数值重放。

## 同一计分协议

完整WikiText-2 Raw test，2048-token窗、1024-token步长，292窗、299077个唯一计分目标，不使用聊天/thinking模板。未计分前缀用原生Attention，所有计分位置均通过36层的单token cached路径。筛选仅在存在超过128个历史位置时实际裁减候选，其余保留全部合法历史。

三个完整任务均采用同一个既有cached scorer，batch_windows=32。各层计分query数均为299077；每份292条记录连续覆盖位置1至299077，NLL求和及exp(NLL/299077)与最终PPL相符。token IDs的little-endian INT64 SHA为 `8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e`。

先前向量化锚点BF16=11.5371603731、W8=11.4832106452保留在上级目录。它们与本次cached结果有约0.001级差异；三组数字方案之间的正式比较采用本表同一cached路径，不将两种执行路径混成一轮结果。

## 验证及归档

CPU5898通过既有PoT64量化检查、独立SparQ参考、最近位置/全零回退及目标覆盖测试。GPU5899通过同dtype/同SDPA操作的原生与包装器logits逐位一致、真实W8＋筛选16query×36层覆盖及无随机调用检查；同环境完整BF16向量化参考仍精确复现11.5371603731。

三个完整任务的COMPLETE与RESULT SHA相符，全部连续目标、NLL、exp、36层覆盖、零采样和代码SHA核验通过。数组任务5900_0/1/2对应进程记录的SLURM_JOB_ID为5901/5902/5900，这是Slurm数组ID与内部JobID的映射。

- 冻结执行：`/home/Hongjie_Zeng/projects/pbit-w8-dense-original-issue259-20261118/screen_be7740802af7/`。
- 执行本地提交：`071e36e61823cd0aea8c2708dfc740bc8d841b38`；runner SHA：`f9d07d8974894bcb2322b0216b7fe7a6acf1c43247242c26b135de08bff9b821`。
- 原件归档：`project_archives/w8_dense_original259_20261118/be7740802af7-screen-results.zip`。
- 归档SHA-256：`765d6abd6f6e8d0d56de73779b5c85f20d12f0bb75dbb312d4b8bd100d1b0b93`。
- `RESULTS.json`包含三组PPL、准确结果SHA和归档位置；`SUBMISSION.json`包含资源、全部源码SHA及命令；`STATUS.json`保留最后的完成核验快照。

本轮没有新训练、TLM重跑或电路仿真；没有改论文正文、TLM默认或旧执行快照。PR未自动合并，Projects待同步。
