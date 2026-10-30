# Issue212 复测交付回执（2026-10-30）

负责人rayggxia；沿用task/212-gpu-decode-profile / PR214，base main。Slurm3440、3443已完成，82个小原件/派生验证文件及大轨迹索引SHA核验；2K/8K各14类模块，全部36层。3437隔离、3438原生GQA数值、3441/3442温度起点失败均保留且未纳有效结果。

正式报告：results/gpu_decode_energy_20261029/remeasure_20261030/REPORT_ZH.md；代码及EXECUTION：experiments/gpu_decode_energy_20261029/remeasure_20261030/。

同卡Qwen/Qwen3-4B后训练BF16/B1，冷却对照真实生成：2K22.7264ms、5.0673J/token，8K22.2995ms、7.6906J/token。预热阶段25.7276/25.8909ms、5.6044/8.3259J也保留，不归因全部变化给温度。静态KV固定Graph9.9433/14.5789ms、3.7098/6.4117J；不是实际连续生成。

GPU计量单位和计数验证通过；预热窗计数/积分差最大0.662%，冷却功率跃迁窗口最大6.941%，不称±1%绝对精度。Nsight/Profiler除约2us embedding外26项时间差<1%。模块能量是隔离回放，不直接求和。

公开速度对照详报告：官方H20 HF45.94tokens/s/SGLang133.13；5090 BF16项目自测TPOT6.53/6.71ms。硬件、输入和引擎不同，只核对数量级，无严格匹配公开J/token。不用通用HF宣布对最佳GPU的加速/节能倍数。

原3399/3417和已安装nsys不改写；无新训练/PPL/EDA，无运行中本任务作业。通过本PR交付，仍待审未合并。完整历史STATUS/HANDOFF因既往自动审批拒绝不重新上传；本地维护，远端以本回执/Issue评论/结果为准。Projects接口不可用，看板待同步。
