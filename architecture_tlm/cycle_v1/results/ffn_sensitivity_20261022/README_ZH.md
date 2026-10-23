# FFN 配置敏感性诊断

固定 synthetic_fixture 67→70→16、seed=0、B4/T32/K32、native source；三个轴共享默认配置，因此是 8 个去重配置。
全部 cycle/event 完整 trace、真实字节、动作与资源状态一致；每种模式均通过 count-compressed oracle、输出字节与有限 credit 检查。

| 配置 | 条件延迟 ns | 相对 baseline | 原生 frames | 输出相同 | 轨迹相同 |
|---|---:|---:|---:|---|---|
| baseline | 31375.00 | 1.000000 | 128 | True | True |
| engines_1 | 40512.50 | 1.291235 | 320 | True | True |
| engines_2 | 31625.00 | 1.007968 | 192 | True | True |
| engines_4 | 31375.00 | 1.000000 | 128 | True | True |
| lanes_8 | 43937.50 | 1.400398 | 128 | True | True |
| lanes_32 | 25225.00 | 0.803984 | 128 | True | True |
| memory_1 | 31212.50 | 0.994821 | 128 | True | True |
| memory_16 | 32112.50 | 1.023506 | 128 | True | True |

此表只诊断配置变化的模型响应，不用于 PPA 或架构优劣排名。weight/counter 容量保持不变；memory_latency 只改变 DRAM 基础延迟；vector_lanes 同时影响恢复、非线性与残差向量阶段。

此形状每个 x group 只有 4 个 gate/up 输出 tile，down 每组只有 1 个输出 tile，因此 engines=4 与 8 同延迟有明确的形状原因；不能外推为大 FFN 的 engine 扩展性。engines=1/2 分别产生更多重放 wave 和原生 frames，但本次保存/恢复后的组轨迹一致。native reseed 默认间隔 100000000 个 core cycles，本次各 case 未触及该阈值；更长运行或不同源参数不能仅凭相同 seed 假定轨迹配对。

恢复 lane 数变化会同时改变多个向量阶段。DRAM 延迟变化只在现有 bank/window/带宽、固定 SRAM 延迟与共享恢复资源条件下得到本表响应；不能将本表小变化称为访存成本不重要。
实际门限轨迹、各字段数值、原生源 epoch/seed 回执及配置保留在每个 JSON；跨配置输出/轨迹差异被记录，而非通过断言强行排除。
源文件 SHA、基线提交、fixture SHA、完整验证摘要见 summary.json；压缩 trace 的 SHA 在对应 case 中。单 seed、单输入不代表统计稳健性、完整模型 PPL 或物理源 IID。
