# GPU decode复测工具（Issue212，2026-10-30）

当前模型为后训练 `Qwen/Qwen3-4B`，BF16原始权重；不是Base、量化模型或概率替换版本。继续PR214，不新建平行任务。冻结依赖来自原任务执行快照 `7911a0aff763f0dc`（源提交20d46ec7）；脚本逐项SHA检查，不能随意用新版本替代。

## 测什么

- `controlled_remeasure.py`：同一GPU的2K/8K，原HF eager固定forward、原Graph、静态KV Graph、真实连续贪心生成256步；14类模块隔离回放，每类包含所有36层的同类调用。整体10秒×3、模块5秒×3；移除原来对小算子不合适的100000次上限。每个阶段温度筛查、窗口温度和时钟记录，未通过筛查照实保留。
- `paired_thermal.py`：每个整模型窗口前恢复40±1°C起始温度（预热/校准后的实际起始状态还须满足范围），三个方式以拉丁方次序交错，各10秒×3；用来识别连续窗口温升造成的偏差。它不锁GPU时钟，不宣称外部电表精度。
- 同一脚本`--trace-only`：独立进程在Nsight Systems下运行2K/8K、各四次静态KV前向，14类NVTX；原始模型logits逐位一致。能量测量进程不在Profiler下运行，跟踪时间不替代主TPOT。
- `build_controlled_report.py`：校验下载封存原件的SHA、计量单位和调用数，区分实际生成和固定forward，输出整体表/模块表。CPU标注关联的kernel总时间包含所有层，不能再乘36。

## 重要命名与负结果

`StaticGQA`是探索期类名，**正式配置`native_gqa=False`**：静态KV更新用当前位置写入，SDPA helper仍是原安装版本，因此仍会展开K/V头。`PROFILE_STATIC_GQA.json`和`INVENTORY_STATIC_GQA.json`也是历史开发文件名，不表示开启原生GQA。正式输出`WHOLE_STATIC_KV_GRAPH.json`。2K/8K静态KV路径都要求与原模型logits逐位一致。

先前Slurm3438的原生Flash GQA探索在2K relative-L2为0.7090%、8K为1.42698%，均top1相同；8K超过预设1%门限，因此不纳正式基线，不放宽门限。此差异可能来自BF16后端归约次序；尚未用PPL/多输入验收。保留冻结失败，不据此宣称GQA数学上不可用。

## 运行

必须通过Slurm，单卡计算，不与其他进程共用GPU。本站点存在未被Slurm追踪的卡0进程：本任务申请两个GRES，只在合法`CUDA_VISIBLE_DEVICES`集合中选空闲的一张，另一张不计算；不操作他人进程。所有2K/8K窗口在同一进程、同一物理GPU上完成。

```text
python controlled_remeasure.py --prepared PREPARED.json --executed-code ORIGINAL_SNAPSHOT --output NEW_OUTPUT --smoke
python controlled_remeasure.py --prepared PREPARED.json --executed-code ORIGINAL_SNAPSHOT --output NEW_FORMAL_OUTPUT
python paired_thermal.py --prepared PREPARED.json --executed-code ORIGINAL_SNAPSHOT --controlled-code CONTROLLED_SNAPSHOT --output NEW_PAIRED_OUTPUT

nsys profile --trace=cuda,nvtx,osrt --sample=none --cpuctxsw=none --capture-range=cudaProfilerApi --capture-range-end=stop --cuda-graph-trace=node --output NEW_TRACE python paired_thermal.py --prepared PREPARED.json --executed-code ORIGINAL_SNAPSHOT --controlled-code CONTROLLED_SNAPSHOT --output NEW_TRACE_META --trace-only
nsys stats --report nvtx_kern_sum --format csv --output NEW_STATS NEW_TRACE.nsys-rep
```

所有输出路径必须不存在，后续修复使用新快照和新目录。不要把未封存窗口写成完成。NVML总量是整卡边界，模块隔离回放不直接相加；按回放功率与原位kernel时间做的归因只是一种估计，底功耗和残差需单列。

## 验证

`python -m unittest test_controlled_remeasure -v`：温度筛查、能量mJ/J与单位时间/调用换算、坏计数器边界。真实模型门禁包含权重/语料/token SHA、36层调用覆盖、插桩与Graph逐位一致。无新PPL、训练或电路PPA。

结果位置：`results/gpu_decode_energy_20261029/remeasure_20261030/`；公开速度来源和不可直接比较的口径写在报告，不把TDP推算当作公开实测J/token。
