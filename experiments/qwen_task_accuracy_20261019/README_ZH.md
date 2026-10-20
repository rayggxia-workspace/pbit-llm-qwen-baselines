# Qwen任务准确率：联合概率FFN/Attention

Issue59，依赖PR52的冻结数值实现e3c5e957。模型Qwen2.5-0.5B Base，全24层固定INT8权重、A8共享64路、四档二次幂尺度、T32/K32分层FFN；Attention沿用max4筛选、固定8个64-token块、hard-onehot有限CTMC Ising、V索引平均。Ising保留观测数S64/128/512，burn16、spacing4，三个种子。FFN预填充和解码均替换，Attention多token预填充保持SDPA。

选择PIQA(validation1838题)、ARC-E(test2376题)全量，HellaSwag(validation10042题)预定1000题子集，Python Random(20261019)无放回抽样，先于任何模型得分。全部0-shot、原Base不套聊天模板。模型原版BF16、仅FFN替换三seed、联合三档×三seed，共13配置×3任务。

官方lm-evaluation-harness0.4.8构造prompt/候选、处理HellaSwag文本并计算acc/acc_norm。后者按候选字符串字符长度归一，并非token数或扣除猜测概率。只覆盖数据加载为已缓存完整parquet，没有修改任务逻辑。输入边界使用官方HFLM._encode_pair。

普通向量化候选评分会绕开decode-only替换，本任务采用无padding缓存解码：预填充prompt[:-1]，最后一个prompt token以q_len=1前向，实际执行全部24层替换并预测第一答案token。所有候选共享这一步的logits；随后恢复独立分支的KV、随机生成器状态和摘要，逐token teacher forcing。按相同prompt长度及候选数分批，候选尾部无效行不计分。保存执行审计和逐题结果。

这三项输入均短于512 token，固定8块策略预计保留全部K。因此可验证短任务的FFN＋Ising/V采样，不能据此证明2K/8K上下文的QK筛选损失。报告实际候选比例、题数、三seed均值/标准差、相对新BF16的百分点和逐题对错翻转。seed标准差不等于题集置信区间；1000题HellaSwag不能称为完整榜单分数。

首先在Slurm CPU预检运行测试并冻结任务输入，再运行GPU准备：模型/分词器/WT2 SHA校验、新BF16完整WT2环境参考和最长题pilot。准备成功后才提交正式数组。权重、数据和全部逐题原件保留本人服务器项目目录，Git仅存配置、manifest与汇总。无新训练、RTL/PT/PPA或硬件实测。
