# Qwen最新采样器联合PPL对照（Issue141）

独立推理评测，base 6966739；不改Issue138训练模块/主TLM/旧执行源，不恢复暂停任务。

## 冻结参数

- Qwen2.5-0.5B Base，原revision与train/test/tokenizer字节复用Issue30校验器；无训练。
- 全24层FFN固定W8、64×64历史对称量化；输入动态4档A/A4/A16/A64、T32/K32、64共享；gate/up共用x，FP32 SwiGLU后z独立编码，BF16接口。直接复用Issue50/46，不重写数值核。
- 每个被计分token全24层Attention替换。多token预填充Attention原SDPA，FFN仍替换。准确Q/K/V/O与RoPE；max4均值摘要、64位置/块、fixed8、强制首块与最近两块；原train校准moment.pt SHA fefbb90c4f38c5f7a6d51a672550bd684ffe3a1415d36dc115a8ca5e05c5db0b。
- BF16 1项；FFN-only、筛选后准确PV、CTMC128、校正拒绝128、赢家1024各3seed（0/1/2），共16项/协议。
- CTMC原burn16/spacing4不变；拒绝接受128个地址，初始偏移m0，0..24自适应，单行总cap128×128，无回退；赢家argmax初始化、偏移max(logits)、burn0、spacing1、1024次更新。新采样器地址直接取V均值，没有第二次PV采样。
- 采用Triton Philox模拟候选间/帧间独立FP32 sigmoid概率；无输入驱动/概率8位量化，无实际分层随机服务/物理轨迹回放。FFN沿用受控分层，不能把整套称为IID物理随机。

## 计分及守卫

同轮先原BF16向量化完整WT2复现11.652735047455899、299077目标；模型/语料及原冻结依赖全SHA核验。随后6项8目标pilot：仅接口/耗时，不称完整PPL。后缀32段×128=4096目标、batch8；完整window2048/stride1024/batch32、299077目标。各协议有自己新BF16与FFN-only对照，不混用历史后缀和完整数值。

保持旧cached scorer、筛选/缓存/全层hook/FFN保护器原字节，只通过局部受控上下文替换采样地址函数；输出明确actual_sampler并记录提议/接受/拒绝统计。严格snapshot原字节与输入/输出/config SHA；Slurm唯一输出目录，失败不产生completed结果，不覆盖冻结执行。

新Triton实现把候选并行、时间递推留在GPU程序内；没有直接multinomial替换拒绝或赢家，没有改变有限链成IID。验证包括三seed固定随机轨迹与独立标量oracle逐项一致、有限一步赢家分布/拒绝类别分布、padding、均匀仲裁和cap必须失败；不把GPU耗时当硬件周期。

执行：run.sbatch；先prepare，后worker --phase suffix/full --index 0..15，必须依赖准备门禁通过。完整确认是否已提交/实际任务ID以work/rayggxia/141/HANDOFF.md和SUBMISSION.json为准。当前说明不是结果，尚未产生新PPL。
