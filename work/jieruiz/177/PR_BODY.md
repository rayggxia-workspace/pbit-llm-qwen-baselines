为 Qwen3-4B 后训练版增加可训练的随机非线性 FFN：前向将 P8 的 g、sigmoid(g)、u 三流 AND 直接送入固定权重 Wd，训练仅更新 gate/up/down 权重。默认 x 为共享64路的64次分层采样，非线性为32联合分层共128次；保留64次配置及W4/W6选项。

关联 #177；依赖 #173 / PR #174，接续训练方案 #159。PR base 为 `task/173-and-direct-wd`，差异仅本任务代码、验证和交接，不自动合并依赖。

包含明确分离的硬前向/有偏STE反向、TRAIN固定尺度校准、严格FFN checkpoint接续/断点恢复、可运行CE入口与远程agent说明。昨天训练结果仍待完成，本PR不重复启动它；既有checkpoint可在核对SHA和参数范围后作为warm start。

验证：默认W8与冻结推理oracle逐值一致；本机13项（12过、1CUDA跳过）；Slurm2906的34项全部通过；两层随机初始化Qwen3 CUDA训练5步、三seed合成优化完成；两卡DDP＋非重入checkpoint三步通过，权重跨rank一致、非FFN参数不变。默认NCCL通信曾挂起；本机socket隔离后通过，保留失败日志，不据此声称H200吞吐。

边界：Wg/Wu尺度恢复仍FP32参考；部署非线性路径用signed8驱动、P8 LUT和有限采样，反向FP32仅为代理梯度。不是整链bittrue、不是新4B训练/PPL结果，也没有RTL/PPA。完整模型训练、同轮基线与三seed评估由后续agent按交接执行；Projects权限不足待维护者同步。
