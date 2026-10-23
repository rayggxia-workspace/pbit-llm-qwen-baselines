# PR142 的 main 集成交接与审核（2026-10-23）

负责人：jieruiz。沿用 Issue138，用户明确要求把两种可训练采样器合入 main。

来源 PR142，精确 head bac0e0479dd974eb634ae8203f51cdc906226ab7；原 base 是 TLM 集成分支6966739。main 基线35db820，独立分支review/138-main-port-20261023，工作目录tmp/pr142-main-review-20261023。

main仅接入 experiments/trainable_pbit_attention 完整模块、原实验记录及 Issue138 发布证据。测试依赖的历史 NumPy samplers.py 从同一源提交按原字节带入；无需把此前625个TLM分支独有提交一并引入。SOURCE_MAP.json逐文件记录来源SHA256。源模块与原记录均未重写，旧PUBLICATION/HANDOFF中待审描述属于原发布时点，当前实际状态以本次PR合并回执为准。

审核覆盖真实Bernoulli前向、均匀仲裁、赢家保持、全零2^-m校正、拒绝自适应、全部轨迹score-function、直接V梯度、掩码和cap失败行为。有限赢家链不等于独立Softmax抽样；量化模式明确限制精确梯度；代码没有预训练或微调好的权重。

本地复核：Python3.8.1/Torch2.4.1 CPU，22/22单测通过、0跳过；原6源码及2结果SHA一致。独立重跑两个方法各3seed、100步合成训练，结果见main_review/TRAINING_SMOKE.json。没有GPU、真实LLM训练/PPL、RTL、物理随机源或PPA。

复现：python -B -m unittest experiments.trainable_pbit_attention.test_samplers -v；python -B -m experiments.trainable_pbit_attention.demo_train --output <新的结果路径>。保留原results，不覆盖历史验证回执。

运行中任务：无。后续真实模型集成、CUDA、梯度方差与轨迹内存压力另做验收；不由本次合并宣称完成。Projects沿既有read:project权限限制待同步。完整本地回执归档project_archives/pr142_main_20261023；合并后回收本人稀疏目录，不清理来源作者目录。
