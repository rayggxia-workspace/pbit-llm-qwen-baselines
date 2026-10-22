# 周期级执行后端 cycle_v1

Issue116，独立于既有 `unified_v6`。此实现把 FFN tile 和 Attention query 变成有真实字节、有限资源和在线反馈的操作图；同步逐拍模式与事件跳步模式必须在完整轨迹、接受/完成时间、状态、动作和读回字节上相等。配置时延是条件模型，不能当作 STA、物理 PPA 或全模型质量。

## 从这里运行

仓库根目录，Python 3.12 或更高，运行器仅用标准库；抓取真实 Qwen fixture 另需已有 PyTorch/Transformers 环境。每次选择新的输出目录，避免覆盖证据。

```bash
python -m architecture_tlm.cycle_v1.run --operator ffn --output /personal/new-ffn
python -m architecture_tlm.cycle_v1.run --operator attention --mode winner --output /personal/new-query
python -m architecture_tlm.cycle_v1.run_layer --output /personal/new-reduced-layer
python -m architecture_tlm.cycle_v1.run_gqa --heads 7 --mode exact --output /personal/new-gqa
python -m architecture_tlm.cycle_v1.matrix --suite smoke --workers 1 --output /personal/new-smoke
python -m unittest discover -s architecture_tlm/cycle_v1 -t . -v
python -m architecture_tlm.cycle_v1.audit.run_audit --output /personal/new-audit
```

`run --fixture PRIVATE.json --config OVERRIDES.json` 接收冻结输入和配置覆盖。默认执行 cycle/event 两种循环；`--event-only` 明确跳过等价检查，不能将其结果写成已验证逐拍等价。共享服务器必须在 Slurm 分配内执行，CPU 作业隐藏 GPU。

每例输出 `summary.json`、`contracts.json`、`trace.json.gz` 和可离线打开的 `timeline.html`。检查台可筛选操作、缩放时间、点击输入/输出额度、资源、依赖、地址和动作。trace 保存实际读字节的散列，不上传原模型权重。无可信系数时 `energy.status=unknown`。

## 模块与契约

| 入口 | 已实现内容 | 明确边界 |
|---|---|---|
| `contracts.py` / `kernel.py` | 整数 ps、多时钟/相位、latency/II 分开、有限在途/完成端口、资源实例、FIFO/额度、动态依赖、完整 stall 变化 | old-state 无同拍旁路；逻辑待执行操作图不是硬件指令 FIFO；通用 callback 不自动获得跨对象原子性 |
| `memory.py` | 实际 byte backing、地址/line/bank/端口、有限请求窗口、RAW/WAR/WAW、乱序返回、在线写后读 | banked 假设模型；未执行 Ramulator/DRAMSys；全局地址空间没有总容量 allocator |
| `ffn.py` | 固定 W8、64×64 tile、B/T/K、原输入符号 rails 与二补码 W8 位平面、有限计数/权重/尺度/partial、分级 restore、完整 gate/up→SwiGLU→down→残差 | 连续 SiLU、条件 FP32 边界；编码/恢复流水未做完整 STA；32KiB 阵列驻留供给是声明的接口假设 |
| `attention.py` | 实际候选 K/V、QK、分级数字 Softmax/PV、winner/rejection 反馈、空/多命中、无偏 rank 重试、计数/去重 V 地址 | query 从已投影/RoPE 的 Q/K 开始；候选输入不等于真实筛选器；q/256 自适应采样不声明 IID 或继承 PPL |
| `gqa.py` / `run_gqa.py` | 同 kernel 的多 query / 单 KV head，共享物理 K/V union 读；有限行缓存、操作数响应、metadata和运行时V合并扫描 | [GQA契约](GQA_GROUP_ZH.md)；K候选读计划是输入，V在所有query准备后合并；每head独立随机网络，不含投影/筛选/动态append/Wo/整层 |
| `rng_protocol.py` | 原 native LFSR32/Bivium、seed bus、warmup、epoch、hold、SAVE/RESTORE/RELEASE、有限交易信用 | 确定性协议模型，不是物理熵；整层当前为各算子独立网络，不是全局共享总线闭合 |
| `layer.py` / `layer_flow.py` | 单 kernel 的 RMSNorm→QKV→RoPE→KV append→Attention→Wo→残差→RMSNorm→FFN，所有动态跨界 payload 都走有 producer/CDC 的写请求 | 合成 16 维单头小层，不能称完整 Qwen/Llama 层；没有多头/GQA 或学习筛选 |

core 时钟 10,000ps，SRAM/内存端口 12,500ps。默认跨域 `cdc_cycles=3` 为两级同步寄存器之后，按旧状态在第三个目的沿被消费者接受。capacity=1、latency=1、II=1 且无旁路时实际不能连续每沿接受；该事实在测试和 RTL 中保持。

FFN 主参考 B4/T32/K32，三个对照 B2/T32/K32、B4/T16/K16、B4/T64/K64。T64 需要13bit位平面计数，48KiB 只能容纳7个完整 tile；不能保留8 tile 并悄悄溢出。`signed_bin` 是单独数学布局，不能继承原位平面 RTL 的 PPA。跨输入 tile 完成归约后才进入非线性。

## 独立证据

- [审查报告](audit/REVIEW_ZH.md)：手推时序、独立字节内存和标量 FFN oracle；cycle/event 两个循环共享核，因此等价本身不是独立证明。
- [RTL 对照](RTL_CONTRACT_ZH.md)：9组、252个数字握手，有限流水/FIFO/CDC mailbox；不等于完整算术 RTL、STA 或亚稳态验证。
- [ONNXim 试验](external/onnxim/README_ZH.md)：固定官方版本实际编译、两个官方小例、四个原生自定义 Operation 传输场景。其同沿窗口返还语义与本核不同，不能直接比较两者总周期。
- `results/reduced_layer_20261023/SUITE.json`：7个单层闭环成功场景、2个明确容量拒绝；有限窗口/慢内存改变时延而保持 exact 路径输出。

完整矩阵、源版本和发布状态见 [实施报告](IMPLEMENTATION_ZH.md)。历史 v6 与随机服务实现保持原样；本目录结果不替代旧52/40情景。

## 如何解释数字

资源 `at_least_one_inflight_fraction` 是接受至完成区间的并集，包含回压占位，不是晶体管切换利用率。`stall_operation_ps` 是可重叠的逐操作等待总和，不能相加得到端到端时间。`peak_reserved_units` 由同拍聚合 trace 重放计算；free-credit 的 token 高水位本身不是已用容量。

`memory.*` 物理字节动作与 `weight_read_bytes` 等语义动作有重叠。能量计费必须选择一个边界并绑定匹配的表征系数，不能全部相加。native source 动作另列，不重复把每个 tile 广播接收当新随机字。配置核宽、latency、II、bank 布局或内存后端一变，必须重做结果并保留旧版本。

本轮选择继续使用自有严格参考核作为 p-bit 数值/时序原型；ONNXim 保留为已验证的外部扩展候选。PyTorchSim 固定版本仅作可行性查阅，未构建或声称其测试通过。下一步由实际 DRAM/互连接口、全维模型规模和 RTL 接口证据决定迁移，不能直接继承框架默认硬件。
