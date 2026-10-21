按用户要求实现两种可使用的全候选并行采样器TLM：每轮赢家N路、校正拒绝N−1路同时读取。随机源后端未决定，支持后续PRNG＋比较器或DAC＋物理阵列；辅助公平随机位单独统计。v4默认不变，完整decode适配已接通。

- [x] 两种行为及空态校正/均匀仲裁、拒绝/保持/预热计数，超限明确失败且收费。
- [x] 明确源服务、树深、状态反馈、逐驱动/公共偏移两模式、单项输出回压及跨查询源间隔；没有64路分波或一拍完成一轮的假设。
- [x] 18新＋10旧检查通过，执行提交f6c6bd8215c2d702ab42e6a3078f64e0888cade8；30项三seed合成模块、两个单层完整decode连通情景完成。
- [x] 未知完整能量/面积null，输出活动与已知参数小计；原结果/代码/配置SHA和封存JSON已核验，34结果blob与Git提交字节一致。
- [x] 中文说明、结果、STATUS、HANDOFF、备忘录及任务PR交付；PR待审，不自动合并，Issue保持open。

设计说明：[PARALLEL_SAMPLERS_V5_ZH.md](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/task/87-parallel-sampler-tlm/architecture_tlm/PARALLEL_SAMPLERS_V5_ZH.md)。

本次没有新PPL/Slurm/训练/PT或真实DRAMSys运行，没有重跑90组真实QKV或接管Issue37/73/78。源服务及数字仲裁/反馈的功耗与面积待后续标定；默认连续响应参考传32位负载不等于选择32位DAC，8位负驱动是显式可选的数值格式。看板本轮未操作，沿既有read:project权限限制待同步。
