# SparQ候选数与P8采样预算预评测（Issue222）

用户授权的小规模推理测试，不训练。原后训练Qwen3-4B BF16 FFN/QKV/Wo/norm保留，数据/模型身份复用已封存准备清单，原样BF16同环境重新运行。

主对照：r32/local32不变，K64/128/256使用准确候选Softmax/PV；K128赢家保持采用PR221的signed12/F4→U8/F4差值→冻结P8 LUT，S8/16/32/64/128，burn32、spacing1，三部署seed。另有P8稳态均值和P8稳态IID32诊断，它们不是Ising硬件实现。

8个WT2窗口、每窗64目标、全36层decode替换，共512目标；准确前缀，实际上下文约2048至2111，不称完整WT2或独立最终验收。调参观察过的test子集不作为未观察测试集。模型质量优先，Python GPU时间不用于ASIC速度/能耗。

通过同一概率生成接口给原Triton赢家核供给精确二进制P8概率。u<q/256与floor(256u)<q逐元素等价，预检核对256项LUT、R8比较及实际Triton轨迹对整数规则oracle；不使用理想sigmoid概率、不模拟GF共享相关性。

同一原生BF16轨迹还捕获8×36×32头行，比较K64/128/256保留的真实注意力质量与V输出误差；有/无诊断logits逐字节一致。原始BF16、纯SparQ和P8均值/采样的误差分开报告。唯一V按4Q/KV组的逻辑去重，不称实际DRAM事务。

依赖固定服务器源a7108f8cba2c72ad319114af34557f4cec2b793d（公开算法来源PR199/PR163），提交前验证其execution.json全部源码SHA。旧快照只读、不复制大模型。GPU计算仅Slurm，使用已有个人环境；自己的源快照和结果目录由部署回执指定，提交后不可修改。

本目录是探针，不是训练器，未知PPA保持null。执行方式：python -m experiments.sparq_budget_probe_20261031.run --root PERSONAL_PROJECT --phase preflight；通过后Slurm数组seed0/1/2运行--phase short。runtime.json由个人准备配置派生，不把凭据/SSH/工艺库或大权重提交Git。
