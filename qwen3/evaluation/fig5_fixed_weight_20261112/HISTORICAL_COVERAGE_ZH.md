# 旧数据为什么不能直接拼本轮曲线

已查本地完整WT2结果索引及PR252/253。这里仅说明来源和适用范围，不为旧结果重新命名。

| 旧数据族 | 已有预算 | 与本轮不同之处 |
|---|---|---|
| 20261106父模型完整预算扫描/扩展 | K128:S16/32/64/128；K256:S32/64/128；无筛选:S64/128/256；各3seed | 原始父模型权重、旧绝对signed12先量化/Philox路径，不能填K_WH64/GF新前端图 |
| 20261109 K_WH64 RNG扫描 | K128/K256、S64、GF64+Bivium各3seed | 旧signed12先量化，不是本轮FP32先减max |
| K_WH64 Philox预算补测 | K128 S32/S128 seed0 | RNG不同，seed不全，前端不同 |
| HF N_WH64/N_WH128/N_WH256 | 各自训练的无筛选权重结果 | 权重不同且训练端token协议不同，不是固定K_WH64跨S曲线 |
| Fig.4局部分布、无筛选分布拟合 | K128/K256/N2048多S | 是冻结QKV的TV/NMSE/频率结果，不是完整模型PPL |

公开历史入口：[PR252](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/252)、[PR253](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/253)。部分新结果只在本地或HF索引，不能假定所有原始轨迹已公开；本次运行不依赖那些私有结果。

本轮故意从相同固定权重、统一新前端重建12个点，不把“历史某K/S已经出现过”当作可直接复用。若远程已有同一weight SHA、raw/token SHA、前端、RNG、完整计分和seed的结果，先出具这些字段与源码/窗口NLL证据，再决定复用，避免重复算力。
