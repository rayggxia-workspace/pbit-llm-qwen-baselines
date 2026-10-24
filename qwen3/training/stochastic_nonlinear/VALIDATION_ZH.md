# 实际验证记录（2026-10-24，Issue177）

本次实现可以训练随机非线性FFN；尚未开始完整Qwen3-4B适配，也没有新的PPL结果。昨日训练仍待结果/交接，不受本任务影响。

| 检查 | 实际结果 | 范围 |
|---|---|---|
| CPU新模块测试 | 13项：12通过、1 CUDA项跳过 | PyTorch2.4.1+cpu；包含前向oracle、三权重梯度、checkpoint重算和断点恢复 |
| 远程原oracle＋新训练测试 | **34/34通过** | Slurm2906，RTX5090，PyTorch2.7.1+cu128；包括CUDA检查 |
| 两层随机初始化HF Qwen3训练 | 5步CE 4.1924→4.0532 | Transformers4.51.3；所有6个FFN权重更新，其余参数逐值不变；非重入激活checkpoint |
| 三seed、64×64合成优化 | 每seed100步，训练与独立输入MSE均下降 | CPU和CUDA均完成；不是预训练模型精度指标 |

CUDA合成独立输入的MSE（16个固定评估噪声键平均）：seed0 0.015120→0.010735；seed1 0.016446→0.010751；seed2 0.012022→0.007487。它验证有偏代理梯度可用于这组小问题，不代表Qwen3-4B一定恢复精度。

硬前向对照：W8下3种固定g/u档位策略×3种采样数均逐值匹配冻结 `ShortStreamFFN`；采样过程在train/eval中相同。另测W4/W6的码字范围和有限梯度，不将其混称已有大模型PPL。通过禁止运行时 `torch.sigmoid/F.silu` 的测试确认硬非线性没有浮点函数回退；LUT在初始化时离线产生。反向仍明确使用FP32代理梯度。

执行快照 `a3f5a4ac092f1543aef2c5137a61446092e94f7a`，归档SHA-256 `46199b02b5e70311553d7c36f76b0ede83eaa92b5e7544bd4a15846c07442560`。远端个人目录 `/home/Hongjie_Zeng/projects/pbit-trainable-and-20261024-issue177/`，源码 `snapshot-a3f5a4ac`，结果 `results-2906`。本地同字节封存 `validation/results-2906/`，COMPLETED.json记录5个documents和源码SHA，已逐项核验；原件不做换行美化。

之后只增加诊断函数、DDP诊断和文档；核心前向/反向未变。DDP验证单独记录，不与34项单卡通过混称。没有RTL/PT/PPA、4B训练、H200吞吐或完整WT2验证。
