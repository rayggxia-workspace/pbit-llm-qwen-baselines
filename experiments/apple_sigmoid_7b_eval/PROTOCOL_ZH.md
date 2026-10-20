# Apple 7B Sigmoid / Softmax 配对基线（Issue #65）

用户指定下载两个论文官方配对模型，在 DS-CIM 的六项任务和完整 WikiText-2 上比较原始确定性模型质量。

模型来源为 apple-aiml-research/ml-sigmoid-attention@76a8d3ad9ac8c074de92cbe3791768924e7ebd86 的 AXLearn notebook。两模型均 step_00250000、1T 训练 token；32 层、4096 hidden、32 头、128 head dim、11008 SwiGLU、32768 嵌入/输出容量（原 SentencePiece 为 32000 pieces），ALiBi、QK RMSNorm、Attention/FFN HybridNorm、共享输入输出嵌入。不是 Meta Llama2 权重，也不是在 Softmax 权重上运行时直接替换 sigmoid。

分词器采用官方 bpe_32k_c4.model，按 notebook 将换行替换为 <n> 后编码；不得套用 Qwen/Llama tokenizer。Sigmoid 偏置固定为 -log(4096)，不随当前序列、padding 或当前可见 key 数变动。所有归一化和 mask 由原生配置及短前向对齐门禁核验。

质量协议（当前正式首轮）：原始 FP32 检查点、FP32 参数与计算，先与原生 AXLearn FP32 对齐；BF16 移植作为独立后续项；完整 WT2 raw test，window=2048、stride=1024，逐个真实目标 token 的总 NLL / 总计分 token，首 token 无前缀不计分。文本需重建项目原始空行格式并核验 SHA；新 tokenizer 产生的新 token 数单独记录，不沿用 Qwen 的计数。尾窗不重复计分，不把前缀冒充完整 WT2。

六任务为 BoolQ、PIQA、HellaSwag、WinoGrande、ARC-Easy、ARC-Challenge，0-shot，完整验证/测试 split 依 frozen lm-evaluation-harness 定义。保存数据 revision/哈希、模板、版本、逐题分数、acc 与支持的 acc_norm；主表以 raw acc 的六项算术均值呈现，另列 normalized 口径，不混用。DS-CIM 原文表 II（arXiv 2601.06724v1 / DOI 10.23919/DATE69613.2026.11539592）只固定任务集合，未完整固定 harness 版本/模板；本次不声称严格复现其 LLaMA 7B 数字。

先通过原生 AXLearn 与移植短前向 logits/NLL、因果性、batch padding 与分词拼接检查，再跑完整指标。GPU 仿真时间不视为 p-bit 硬件功耗/面积/延迟。原始权重、数据、环境只放本人服务器；Git 保存代码、协议、小型结果和完整性索引。全部重型任务通过 Slurm，同一时刻最多一个本用户 GPU 作业。

精度状态更新：Slurm2538/2539的GPU BF16移植未通过门禁，未执行正式PPL或准确率；关闭BF16归约或将RMSNorm改用FP32均未解决两个模型的全部差异。2536通过的是同一BF16量化参数上的FP32计算，不能视作BF16部署通过。当前另保留未量化原始FP32数组，以2541进行转换和原生FP32对齐，按单独FP32输出目录执行质量评测。FP32GPU执行时间不继承为BF16或硬件PPA结果。
