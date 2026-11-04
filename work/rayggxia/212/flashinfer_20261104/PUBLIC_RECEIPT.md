# FlashInfer补测提交回执

负责人rayggxia，继续Issue212/PR214及task/212-gpu-decode-profile；2026-11-04用户授权编写并提交脚本。本次不改旧测量与结果、不自动合并。

新增公开范围仅experiments/gpu_decode_energy_20261029/flashinfer_20261104中的脚本/固定配置/测试/说明及本回执。私有原始交接、完整历史STATUS、工具凭据、模型权重和大trace不公开。

CPU安装/预检4388已完成0:0/11秒，6项CPU检查通过。当前有效GPU4392申请单张RTX5090，正在排队，尚无GPU测量结果。先前4389在PENDING时被v2撤回：新增连续生成HND步幅与两步更新数值检查，旧冻结字节保留，CPU安装复用。

四后端：SDPA显式头展开、SDPA原生GQA、FlashInfer CUDA-core、FlashInfer Tensor-core。保持原BF16 Qwen3-4B/B1/2K/8K，测完整固定Graph、连续生成、36层Attention独立回放及模块时间；数值失败单列。

v2执行包SHA256：5e5f0f324f84bdeb7cc73e50bd04083aa3b0d03bedeccffff06c4c0d92322f11。
源码manifest SHA256：d2afc2b2239ecfb66f31837fe456365040ba117cb303c7a7050d53536d2ee5d8。
配置SHA256：bb68cc009fb4bbc262a2a188c7bd50bc698ff1589adca42084026f0013848741。

当前阶段为已提交、未完成；没有新的PPL、训练、TLM/芯片PPA或节能倍数。Projects接口不可用，未同步看板。GPU完成后须核验完整manifest、输入/模型/配置身份和通过门禁的各case，更新同一Issue/PR。
