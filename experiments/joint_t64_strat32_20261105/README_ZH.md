# T64训练权重：分层T32 FFN＋当前概率Attention

Issue242，负责人rayggxia。Qwen/Qwen3-4B后训练版revision `1cfa9a7208912126459214e8b04321603b3df60c`。

FFN复用实际T64训练100M export、匹配non_ffn、W8码、冻结四档尺度和sigmoid表。GU入口32分层；后级g/sigmoid/u联合4×2×4分层，共32次AND；事件计数直接乘固定Wd，不先重编码z。与Issue204相同抽样分布的软件条件计数加速，不是逐拍GF64回放。

Attention使用同一T64导出的匹配non_ffn：上轮全模型训练已更新过这些参数，但当时Attention仍准确计算；本轮没有概率Attention适配训练。保留BF16 QKV/O、QK-Norm、RoPE、KV接口。默认SparQ r32/k128/recent32，四Q共享候选，无mean-V补偿；筛选沿既有FP32行为，尚未验为RTL量化筛选。候选QK分数按下列数制：

1. `q = clamp(RNE(score × 16), -2048, 2047)`：总宽12位，含符号、4位小数。
2. `gap = max(q) - q`：先用加宽整数作差，不回绕。
3. `address = min(gap, 255)`：U8地址，步长1/16。
4. `threshold = floor(256 / (1 + exp(address/16)))`：冻结256项P8 LUT；阈值范围0…128。
5. `R8 < threshold`产生各候选独立bit；赢家保持、空态保持、否则对所有激活候选作无偏公平选择。初始slot0、burn0、S64；重复地址重复累加V，最终除以64。

独立Philox经R8投影模拟候选随机字，公平rank使用独立uint32及无偏拒绝映射。不是单随机字共享全部候选，不宣称GF64或物理p-bit位真。CPU检查数制、LUT和分层边界，GPU检查原始byte帧的独立状态oracle。

计分使用teacher-forced cached单token路径，所有计分token均经过36层采样。前缀Attention准确；FFN在前缀及计分均分层T32。前缀逐样本生成KV，再拼batch，以免多条2048前缀同时撑大FFN临时张量。BF16/FFN-only/联合均采用相同目标位置和调用分组；cached分数不能直接当旧整窗FFN-only PPL，报告匹配对照。

默认先WT2固定8段×128后缀＝1024目标、三个部署seed101/102/103。完整WT2如后续执行，仍为window2048/stride1024、292窗、299077目标；不能将后缀标完整。原文无chat/thinking模板，不训练、不测PPA。

执行：`python run.py --phase cpu --runtime <verified-runtime> --out <new-dir>`；随后`--phase gate`。正式`--phase evaluate --mode bf16|ffn_only|joint --seed 101 --protocol suffix`；所有服务器运行均通过Slurm。私有输入路径及提交回执在work/rayggxia/242，Git只交付小型代码/数值摘要与SHA。
