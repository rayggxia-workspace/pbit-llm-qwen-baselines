# Apple 7B 配对 Attention 基线（Issue #65）

本实验下载并验证论文官方 7B Sigmoid Attention 与 7B Softmax Attention 最终检查点，按 DS-CIM 表 II 的六项任务和完整 WikiText-2 PPL 比较。详见 PROTOCOL_ZH.md；当前结果状态见 results/apple_sigmoid_7b_eval_20261019。

原始模型位于本人服务器 /home/Weican_Chen/models/apple-sigmoid-attention-7b/，约 50.17 GB，Git 只保留 source generation/MD5/SHA-256 索引。官方 AXLearn 原始数组由 TensorStore 读取并分别转换 BF16 / 原始 FP32 safetensors；原文件不改动。通用 NumCodecs/Zarr 读取曾失败，不等于经过 MD5 校验的来源权重损坏。

原 SentencePiece 含 32000 pieces、pad/eos/unk=0/1/2；模型嵌入及输出容量为32768，保留完整输出头。换行按原 notebook 替换 <n>。两模型均使用 QK RMSNorm、ALiBi、Attention/FFN HybridNorm 和 SwiGLU；Sigmoid 偏置固定 -log(4096)。本次是原始确定性模型质量评测，不是概率采样实现或硬件 PPA 结果。

model.py 是待原生对齐验收的 PyTorch 推断移植；native_reference.py 使用固定版本官方 AXLearn 层构造相同配置，比较同一 BF16 参数在 FP32/BF16 下的短前向。preflight.py 的 logits/NLL、因果及 padding 检查必须通过后，才能给出正式质量结果。历史失败快照、环境修复和调度状态按 handoff 保留。

数据使用固定 HF commit 的公开 parquet，经本机可达网络获取后逐文件 SHA 校验传入服务器，offline_data.py 按原 harness 数据接口加载；PIQA 使用明确记录的官方转换分支提交，区别于其 main 脚本提交。harness 0.4.8 原任务模板及处理函数不更换。prepare_data.py 重建 WT2 空行并核验项目原始文本 SHA。服务器保持 HF 离线，避免把 GPU 用于下载重试。

所有安装、转换、数据处理及推断通过 Slurm，在本人独立项目目录执行，同一时刻最多一个本用户 GPU 作业。cpu_prepare.sbatch 记录当前原生/移植检查命令；native_setup.py 只操作本任务隔离环境。恢复先看 work/amlink1219/65/HANDOFF.md，并核实最新 Issue/PR 和作业状态，不重复提交运行中的任务。

当前精度入口：原始FP32权重和计算先建立质量参考，converted-original-fp32、source/run-v6、reports/float32/<model>/；BF16移植未通过GPU门禁。FP32路径采用Q/K/V投影视图避免在32GB GPU额外复制6.4GB权重。完整PPL和准确率状态以STATUS/实际结果为准。
