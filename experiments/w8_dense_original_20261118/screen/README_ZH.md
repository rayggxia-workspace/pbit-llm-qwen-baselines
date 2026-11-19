# BF16 / W8 / W8＋K筛选：统一cached完整WT2

已完成并核验：BF16 dense **11.5382889054**，W8 dense **11.4823299065**，W8＋SparQ K128准确PV **10.7699059654**。三组同一cached计分器；配置、边界及归档见[REPORT_ZH.md](REPORT_ZH.md)与RESULTS.json。

接续Issue259/PR260。已完成的原生向量化完整WT2为BF16=11.5371603731、W8-only FFN dense=11.4832106452；保留原结果，不改原执行。

本批补齐同原始模型W8＋SparQ K128准确Softmax/PV，并让三组使用同一个既有cached计分器，排除向量化与逐token执行的差别。分三个确定性任务：BF16 dense、W8 dense、W8＋K筛选。没有FFN采样、Ising或PV采样，没有训练后投影覆盖。

W8沿5897的原始模型tile64/PoT/RNE权重量化；激活及SwiGLU保持原始BF16。筛选采用既有r32/k128/recent32、每KV组四个Q头共享候选，不带mean-V补偿；候选内FP32重算QK、准确Softmax和完整加权PV，再返回BF16接口。是算法质量控制，不是完整RTL数值重放。

完整WT2为2048窗/1024步长，292窗、299077唯一目标。未计分前缀使用原生Attention，所有计分目标均通过36层单token路径；审计每层实际299077个计分query。cached与向量化结果单列，不假定逐位相同。

CPU先运行原W8算术、独立SparQ参考与计分覆盖测试。GPU门禁重跑未改BF16完整向量化参考，验证相同SDPA操作的原生/包装器logits逐位一致，并验证真实W8＋筛选路径的所有层覆盖、有效候选及零随机调用。通过后释放三个完整任务，无人为array并行上限。

本地入口：`python experiments/w8_dense_original_20261118/screen/ops.py stage`；提交后只用`status`。源与输入冻结到本人服务器新screen目录，依赖源码按既有execution manifest逐SHA核验后复制，不修改其原件。作业号、命令、配置与源码SHA见SUBMISSION.json。不得把未完成窗口估成最终PPL。
