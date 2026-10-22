# 同 Kernel 的共享 KV head group

`gqa.py` 将多个已经投影/RoPE 的 query head 接入一个实际 Kernel，读取同一份 K/V 地址。当前边界是一个 KV head 的分组，支持已有 exact、systematic PV、winner、corrected rejection query 路径。没有接入 QKV 投影、筛选、Wo、动态 KV append 或完整模型，时间仍是未表征硬件参数下的条件模型。

## 数据与运行接口

```json
{"queries":[{"q":[0.0,1.0],"candidate_ids":[1,2,10]},
            {"q":[1.0,0.0],"candidate_ids":[10,3,2]}],
 "k":[[0.1,0.2]],"v":[[1.0,2.0]],"provenance":{}}
```

上例仅展示字段结构；K/V 实际必须含所有被引用的物理 token。每个 query 可带原 `random_replay`；使用时需显式选择 `random_backend="replay"`。Q/K 维度 D 必须相同，V 的 Dv 可不同，存储均为 FP32。一个配置对象会为 head h 使用 `seed+h`；传配置列表则原样保留各 head seed，不暗示独立随机性。

```text
python -m architecture_tlm.cycle_v1.run_gqa --heads 7 --mode exact --k-slots 1 --v-slots 1 --memory-window 1 --output /new/synthetic-group
python -m architecture_tlm.cycle_v1.run_gqa --fixture /private/gqa.json --mode winner --samples 32 --seed 0 --output /new/real-group
```

私有激活留在服务器时加 `--public-report`，只取回 `public_report.json`。该文件采用字段白名单，仅保留配置、计数、误差、容量峰值、时序和散列；原始 fixture、logits、输出数组、概率、样本索引/直方图、native report、完整 summary/trace/HTML 都保留在执行目录。`--operand-slots`、`--metadata-capacity`、`--union-scan-lanes` 分别控制有限操作数响应、group metadata 字节与运行时扫描吞吐。

`make_gqa(fixture, attention_configs=None, group_config=None, *, prefix="gqa", memory_latency=4, memory_window=4, memory_banks=4, memory_latency_by_address=None)` 返回 `(kernel,state)`；`state["queries"]` 保留独立 head 结果。`build_gqa` 可将分组加到调用者持有的 Kernel，调用者须先配置 `default_resources`/`default_buffers`。初始数据只允许在执行前装载；该 API 不假装已解决动态 append。`address_layout` 返回实际对齐地址及区间，支持显式配置 bank/返回延迟反例。碰到已有初始化内存或内存操作的重叠地址，构建会拒绝。

运行目录必须全新。入口保存 START、配置、fixture/source SHA、每 head 输出/直方图/采样轨迹、物理 union/读地址/字节数、有限信用峰值与资源统计、完整 gzip trace、交互 HTML 和成果 manifest。不写出原 fixture 张量。两次执行比较逐拍/跳事件的完整 payload 和全部 head 状态；数学比较按各 head 实际保留样本重建 weighted-V，采用注明的 FP32 累加容差，不将其当作 PPL。

## 共享的真实生命周期

- K 按候选物理 ID union 读取，每个 token 仅一个 DRAM 请求。行 slot 在请求接受时预留，直到所有需要该 token 的 QK 操作完成后，显式 release 才归还。
- 每个 query 的 Q、histogram 和 output 地址按实际尺寸分别分配，互不重叠。score/sampler/直方图状态和计数独立，不能把多个 head 的重复采样数合并成一个分母。
- 所有 head 的权重准备、采样与 histogram 写回完成之后，执行一个显式 V union barrier，再按 `sum(head候选数)` 扫描和 `K union大小` 压缩，分别以 `union_scan_lanes` 计有限周期。实际 V union 在扫描/压缩完成回调中发布。K union 是已给定候选的预编译读计划；不把入口的静态计划冒称在线筛选/合并。
- V 按各 head 需要的物理 token union，每个 token 只读一次；每个使用者仍执行自己的 weighted MAC。slot 必须等该 token 的所有使用者完成才释放。K/V 都采用共同物理升序、最多相应 slot 数的前视资格，避免稀疏 ID 和后项响应占满缓存造成死锁。
- K/V 行保存在有限 response-cache 中。`k_slots`/`v_slots` 是行数，分别换算成 `slots × D × 4` 与 `slots × Dv × 4` 字节。独立的共享 cache 读口按 `cache_bytes_per_cycle` 限制每次读取的 latency/II，并在每个 query 消费前产生显式完成依赖。每次 cache read 接受还预留一个 `max(D,Dv)×4` 字节 operand slot，直到对应 MAC 完成才释放；V cache read 也必须等本 head 的前一 MAC，防止后项占满操作数信用。这是配置的本地行缓冲读口，不是已经表征的 SRAM 宏。
- 所有数值消费来自实际共享 DRAM read 的返回 bytes；没有绕过请求用 fixture 数值替代返回。`memory_reads` 中为审计保留的历史 bytes 是模拟证据，不能用于声明额外硬件驻留容量。slot 结束后没有未完成的合法消费者。

各 head 的 V 都按自己使用的**物理 token 升序**逐项 FP32 乘、FP32 加，保持当前 standalone query 的顺序。数学 oracle 用 double `fsum`，故有明确 FP32 reduction 容差；不强行宣称与另一求和顺序 bitwise 相同。

## 有限预算与随机源边界

所有 head 共享 QK、vector、exp、sampler、V MAC、memory 与 cache 资源。因此其 `mac_lanes`、`vector_lanes`、`exp_lanes`、exp/reciprocal/drive/LUT 延迟、source latency/II、CDC 设置必须一致；不支持在同一资源上静默更改物理 lane 数。算法样本数、mode、seed、输出背压等可以逐 head 配置。

每 head 的完整 `score_capacity_bytes` 都计入 group 总预算（默认1MiB），不是只计当前已用字节；总额超过预算直接拒绝。每个 head 的 native RandomNetwork、endpoint 状态及 seed bus 是**各自的实例**，只共享 Kernel 中 `rng_submit`/`rng_delivery` 资源。实例数、lane、seed 和 bus 配置会明确报告；这不是一份全局共享随机源，也不构成 IID/物理熵证明。

group metadata 独立预留：两份最多 K-union 行数的目录，每项为 token ID 4B、refcount 4B、head mask `ceil(H/8)`B、压缩临时空间4B，加每 head 16B ready/cursor 状态。query 候选表/分数/直方图已计入 query 自身预算。metadata 从 group initialize 接受到所有 head 输出真实写回、全部行释放后的 group release 才归还；超过 `metadata_capacity_bytes` 拒绝。Python字典和证据轨迹不额外提供硬件容量，也没有无界操作数返回队列。

只读现有 `attention.py` 的默认行为通过可选 hook 保留；group 才启用地址/共享K/共享V接合。原核心、v6 和已有矩阵结果均未改动。
