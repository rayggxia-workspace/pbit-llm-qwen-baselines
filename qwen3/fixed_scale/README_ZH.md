# Qwen3-4B 固定四档小规模PPL（Issue168）

模型Qwen/Qwen3-4B后训练版，固定revision见config.json。依赖PR160@98954637模型与准确SDPA，静态编码移植PR153；原源码不修改，static_core只改导入。固定W8/64x64、A8/共享64、T=K分层采样，36层FFN全输入替换，不训练。

TRAIN均匀16段×512token，W8连续及动态T32/seed917两条传播路径取各层x/z各64通道组最大值，向上取二次幂，固定S/S4/S16/S64。测试不再在线估计尺度，超顶档截断。此小校准没有独立候选选优或跨语料保证。

本轮18项：fresh BF16；W8-only；固定mean；动态32/64、全固定32/64、仅x固定32各3seed。保持原Attention，不包含SparQ/Ising/PV替换；不是训练方案57项。

评分：沿历史suffix_plan均匀32段，每段2048前缀上下文、128后缀目标，共4096目标；一次向量化前向处理2175输入，所有前缀和计分输入均经过所选FFN。逐段batch1、不使用cache。只比较本轮同形状BF16；不得混作完整WT2或直接和cached/batch2结果算增量。小模型独立逐前缀NLL与覆盖测试、随机重放及静态边界等价测试先通过。逻辑q/256+full-one；随机分层不是自然IID物理源。

每项记录NLL/PPL、36层覆盖、尺度/权重不变检查、x/z截断/编码误差/档位占比，原件与sidecar SHA封存。复用已有个人服务器只读模型、数据、venv；所有执行Slurm。运行步骤/ID/发布见work/jieruiz/168/HANDOFF.md。不声明已测硬件能耗。
