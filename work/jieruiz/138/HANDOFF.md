# Issue138 交接

- 负责人：jieruiz（已通过GitHub /user核验）。Issue138，独立分支task/138-trainable-samplers；目标仓库rayggxia-workspace/pbit-llm-qwen-baselines，PR base为pbit-tlm-attention-details-20261016@6966739a5223680888bf0315f7bb4f73423a1ae6。
- 本地目录：C:/Users/86134/Documents/a_P_BIT/tmp/sampler-training-issue138-20261023。稀疏工作树，没有复制模型/环境或长轨迹。
- 源码提交：b6e3d034455270f697c2c40dcb42b5d52b446cda。正式目录experiments/trainable_pbit_attention/，没有改旧NumPy、TLM、RTL或默认模型；遵守Issue37/78/95边界。
- 已完成：赢家保持/校正拒绝真实前向、完整轨迹score-function训练、有偏代理显式分离、mask/batch/cap/seed/量化接口、随机活动统计、22测试和6次三seed合成训练；结果及源SHA在results/VALIDATION.json。无新模型PPL/大模型训练/GPU/Slurm/RTL/PPA。
- 本地解释器：C:/Users/86134/AppData/Local/Programs/Python/Python38/python.exe，Python3.8.1、Torch2.4.1 CPU，复用现有环境无安装。
- 命令：`python -m experiments.trainable_pbit_attention.validate`；`python -m experiments.trainable_pbit_attention.demo_train --output experiments/trainable_pbit_attention/results/TRAINING_SMOKE.json`。重新运行会刷新本机结果，已封存Git原件勿覆盖后再冒称旧执行。
- 发布：科学交付准备完成，实际远端commit/PR以同目录PUBLICATION.json为准；不得把PR待审写为合并。本轮不合并/不关闭Issue。
- 待补：CUDA与真实LLM训练集成、梯度方差/内存压力、量化误差、物理随机源联合分布都未验证。cap失败应显式处理；不得直接扔掉失败批次声称无偏。Projects权限沿既有read:project限制，发布时再次检查并记回执。
- 下一步：审阅采样规则/梯度接口后，用户若要求模型实验，再用匹配BF16和语料SHA、目标层覆盖及Slurm冻结快照；不要因本小例子重复提交历史大评测。
