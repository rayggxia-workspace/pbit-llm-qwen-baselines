# 从已验证算子/小层到真实完整 decoder 的接口缺口

Issue116，2026-10-23。当前 `v6_adapter.py` 是可运行的算子配置桥；`layer.py` 是单头、小形状、同一个 Kernel 内的 decoder block 闭环。两者都不是 Qwen/Llama 全维多层 decode 的周期后端。下面是具体尚缺工作，不把已有 tile 结果乘以层数当作实现。

## 必须形成的共享状态接口

完整 decoder 应持有一个跨算子、层、token 持续存在的执行上下文，至少包含：`Kernel`、全局张量地址分配器、常驻权重索引、KV有效长度和地址映射、有限本地buffer的owner/lifetime、全局随机服务及种子总线、当前token/layer及其完成事件。每个 builder 接受明确 producer event、张量地址/形状/格式与唯一前缀，返回完成事件和实际输出位置。不能为每层重置kernel、随机端点、DMA窗口，或把各层完成时间相加就认为共享资源已联动。

| 待补接口 | 当前边界 | 可检查的下一项验收 |
|---|---|---|
| 统一有界地址分配/生存期 | cycle MemoryPort有真实字节、地址依赖和有限在途；全局address space未实施容量分配 | 所有DRAM/SRAM张量范围可追溯；输出/weight/KV不得覆盖未完成消费者；容量不足明确失败 |
| 全维权重与格式读取 | 已有真实/合成operator fixture；v6桥拒绝裁剪FFN冒充完整shape | 读取模型确定版本，固定W8及scale布局、BF16/FP32边界、bias与norm参数；验证全部矩阵维度和散列 |
| 多头/GQA执行与物理共享 | query为已投影Q、已有KV及候选；小层仅单头 | 在统一资源上运行完整head组；K/V候选并集只物理读一次，各query multiplicity保留，不能按逻辑保留率缩流量 |
| 候选筛选/摘要的在线产生 | query候选由fixture给定；v6桥screen_*只接post-screen部分 | max4摘要读取/当前token更新、归一化、随机判决、预算修复、候选图写入均产生真实完成事件，并驱动后续QK地址 |
| 真实QKV/RoPE/输出投影 | reduced layer有同kernel闭环，非完整Qwen/GQA | 用模型实际heads、KV heads、RoPE参数和bias执行；不能把fixture中预投影Q/K/V记作本次投影计算 |
| 持久KV追加与多token状态 | query使用冻结历史KV；小层追加一次 | token t 的真实K/V写完成后，t+1才能读取；验证长度、RoPE位置、物理layout、读写竞争和完整跨token依赖 |
| 完整decoder首尾 | v6旧整机有embedding/final norm/lm_head宏调度；新桥只算子 | embedding→全部真实层→final norm→lm_head→argmax在一个Kernel内产出下一个token，保持有限输出/权重资源 |
| 随机服务的全局共享 | 原生端点协议在线运行；builder通常建立自己的服务实例 | 按实际物理实例共享seed bus/endpoint pool；全层SAVE/RESTORE/RELEASE不会多分配后端；给出每实例独立/共享lane契约 |
| 在线真实DRAM后端 | cycle现有bank/descriptor服务；ONNXim只完成原生操作传输探针 | DRAMSys/Ramulator桥必须在线accept/reject、保留ID、异步乱序return、有限窗口/端口和写完成依赖；预计算离线trace不能代替 |
| 数值与质量 | FFN/query数值oracle、真实输入切片及small layer；未完成新组合完整PPL | 固定完整模型/分词器/数据/seed，在每层张量对齐后做完整decode/PPL或任务质量；不能继承旧算法的PPL作为新调度数值验收 |
| 全维执行成本 | event mode通过逐拍全trace对照；内核仍保留历史操作并有线性扫描 | 先profile实际全维图，再优化活动请求索引/ready队列；每项改动保留stall原因变化、仲裁、动态图和CDC的逐拍一致性 |

## 迁移顺序

1. 固定一个真实模型的一层、一个完整head组和完整FFN维度，形成显式地址、输入/输出事件与全局资源合同。先核完整数据依赖与容量，不以加速为验收条件。
2. 在该层完成一次多头/GQA执行及两token KV回读；确认随机服务与内存状态没有在builder边界被重置。筛选模式需要在线候选生成链独立验收。
3. 在同一个执行上下文增加全部层、embedding/final norm/lm_head。输出token必须来自实际计算结果，不能预读参考token来掩盖数值漂移。
4. 有限的小规模逐拍oracle继续验证event模式；全维运行保留资源/动作/存储守恒和必要状态散列。只有实际执行所得全模型时间才能称本实现的TPOT；尚未执行的维度留为空。

完整物理功耗、面积、SC数据通路STA及硅实测仍是另一层证据。现有9组RTL协议对照只证明有限流水/FIFO/单槽CDC握手的对应关系，不能替代上表的数据通路和整机验收。
