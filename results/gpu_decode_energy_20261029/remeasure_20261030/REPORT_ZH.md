# RTX5090 同卡长窗口复测与公开基准核对（2026-10-30）

**结论以整卡累计能量为准；模块回放用于定位成本，不能直接相加当作整机能量。**

后训练 Qwen/Qwen3-4B，单 RTX5090、batch=1、原始 BF16 权重和准确 Attention；没有替换概率算子。prefill、加载和 token 传出不在 decode 能量窗口。
revision `1cfa9a7208912126459214e8b04321603b3df60c`；Slurm `3440`；代码 SHA-256 `58d36200ed5fd4f8c3351f3ab39e8e590d3e452b6fc59296e0db139691ec6d07`。完整权重、分词器、语料和输入 SHA 见原件 ENVIRONMENT/INPUT，全部窗口使用同一个 GPU UUID。

## 0. 本次能确认什么

1. 未发现mJ/J、token次数或平均功率换算错误；同窗计数器/积分及独立时间工具提供一致性证据。几J/token仍出现在重新测量中。
2. 冷却前后以及运行阶段会改变能耗；通用HF的eager路径还对主机发射状态敏感。保留两组，不把全部变化归因于温度，也不把小CV当作绝对精度。
3. 本实现仍慢于公开的成熟GPU引擎。关键差异包括Python发射、GQA头展开、缓存复制及未融合算子；它是通用HF参考，不是最佳GPU性能/能效。
4. 尚无条件完全匹配的公开5090 BF16 Qwen3-4B decode J/token可直接验证绝对能量；速度对照只能核查数量级，不能替代独立电表。

## 1. 连续长窗口测量（预热阶段）

|上下文|运行方式|ms/token 或固定 forward|J/次|整卡平均 W|重复能量 CV|
|---|---|---:|---:|---:|---:|
|2K|原始 HF 连续贪心生成|25.728|5.604|217.8|0.30%|
|2K|原始 HF 固定 forward|25.568|5.650|221.0|0.25%|
|2K|原始 HF 固定 forward＋Graph|10.343|4.218|407.8|0.31%|
|2K|静态 KV＋原始 SDPA＋Graph|9.958|3.762|377.8|1.53%|
|8K|原始 HF 连续贪心生成|25.891|8.326|321.6|0.95%|
|8K|原始 HF 固定 forward|25.854|8.647|334.4|0.51%|
|8K|原始 HF 固定 forward＋Graph|16.744|7.901|471.9|0.71%|
|8K|静态 KV＋原始 SDPA＋Graph|14.619|6.519|445.9|0.65%|

连续生成每次 256 步、三个重复，含逐步 argmax 与真实 KV 增长；2K 的 KV 从 2048 增长到 2303，8K 从 8192 增长到 8447。固定 forward 保持同一个输入和缓存长度，不含 argmax，也不是服务吞吐。Graph 去除逐算子 Python 发射开销；静态 KV 使用原始 SDPA，只替换整段缓存复制为当前位置写入，两种上下文 logits 均逐位一致。

## 1b. 固定冷却间隔对照（最终整模型参考）

同一张GPU，校准在冷却前完成；每个窗口前至少空闲10秒，最后五个约1s温度样本跨度≤1°C。四种方式轮换次序、各重复三次，保留实际起始温度；这不是40°C恒温或锁频实验。

|上下文|方式|ms/次|J/次|平均W|能量CV|实际起温范围°C|
|---|---|---:|---:|---:|---:|---:|
|2K|原始 HF 固定forward|22.566|5.074|224.9|2.46%|30–41|
|2K|原始HF固定forward＋Graph|10.320|3.948|382.6|1.30%|33–41|
|2K|静态KV＋原SDPA＋Graph|9.943|3.710|373.1|1.07%|36–41|
|2K|原始 HF 连续贪心生成|22.726|5.067|223.1|0.25%|38–42|
|8K|原始 HF 固定forward|22.660|8.057|355.6|0.69%|42–44|
|8K|原始HF固定forward＋Graph|16.681|7.617|456.6|0.57%|43–44|
|8K|静态KV＋原SDPA＋Graph|14.579|6.412|439.8|0.23%|44–45|
|8K|原始 HF 连续贪心生成|22.300|7.691|344.9|0.30%|45–45|

预热测量的6个同窗计数器/积分对照最大差异 0.66%；冷却对照18个固定forward窗口最大差异 6.94%，积分偏低。NVIDIA文档说明现代GPU的powerUsage是1秒平均，冷却后从约65–80W跃迁到工作功率会产生边界响应；这与观察方向相符，但没有外部电表证明全部差异只来自这一项，也未做任意时移修正。两接口同属NVML，不是独立精度认证。[NVML说明](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html)。连续生成另为256步×3，排除prefill，包含argmax和真实缓存增长。

初次3441/3442的40°C起点门控均失败，未列为有效配对结果：前者在回温后再次校准；后者证实停止短时加热后，计量准备期间温度快速下降（释放39°C、实际33°C）。失败窗口/快照保留。依据公开温度实验改用固定空闲冷却协议，不把失败数据改名为通过。

## 2. 模块时间与隔离回放能量

以下均为一次 decode 中全部 36 层的同类操作合计。时间来自独立采集的 CPU 标注所关联的 GPU kernel 总时长；不是含空隙的 CUDA 注释跨度。回放 J/次和 W 由长窗口直接测得，但其执行顺序、缓存复用和并发不同于完整模型，不能直接求和。

|部分|2K kernel ms|8K kernel ms|2K 回放 J/次|8K 回放 J/次|
|---|---:|---:|---:|---:|
|词嵌入|0.0024|0.0017|0.00052|0.00055|
|RoPE|0.6272|0.6460|0.05707|0.05924|
|Q/K/V 投影|1.1192|1.1230|0.43233|0.43414|
|Q/K RMSNorm|0.8213|0.8332|0.07334|0.07402|
|KV 当前位置写入|0.1530|0.1687|0.01342|0.01364|
|融合准确 Attention（含 K/V 头展开）|1.9712|6.6318|0.76063|3.49083|
|Attention 输出投影|0.5577|0.6550|0.26288|0.26675|
|层 RMSNorm|0.7622|0.8199|0.06707|0.06800|
|FFN Wg/Wu|2.4975|2.5358|1.25659|1.24747|
|FFN SiLU＋逐元素乘积|0.0841|0.0847|0.00871|0.00879|
|FFN Wd|1.2139|1.2248|0.58850|0.58752|
|残差相加|0.0728|0.0885|0.00703|0.00713|
|末尾 RMSNorm|0.0106|0.0108|0.00114|0.00114|
|输出词表层|0.4846|0.4852|0.26250|0.26140|

`MODULES.csv`另列诊断归因 `(模块回放功率−驻留空闲功率)×原位关联kernel时间`；时间已经包含所有层，不再乘36。底功耗与剩余残差单列在 DIAGNOSTICS.json，残差允许为负，不强迫饼图闭合。该归因是模型估计，不是每模块独立电源轨实测。

## 2b. Nsight Systems独立模块时间核对

另一个进程仅做CUDA/NVTX跟踪，未用其时长/能量代替无Profiler主结果。官方`nvtx_kern_sum`统计每类实际kernel总时长，除以四次forward；SQLite核对两种上下文全部36层/14类标签。它不是NVTX投影跨度。

|模块|2K Nsight ms|8K Nsight ms|
|---|---:|---:|
|QKV_projection|1.1231|1.1306|
|QK_RMSNorm|0.8275|0.8377|
|RoPE|0.6311|0.6520|
|KV_append|0.1524|0.1683|
|Attention_core|1.9693|6.5980|
|Wo_projection|0.5561|0.6531|
|Layer_RMSNorm|0.7667|0.8213|
|FFN_gate_up|2.4996|2.5337|
|FFN_SwiGLU|0.0848|0.0844|
|FFN_down|1.2250|1.2300|
|Residual_add|0.0734|0.0882|
|lm_head|0.4850|0.4850|
|Embedding|0.0019|0.0020|
|Final_RMSNorm|0.0106|0.0108|

除约2微秒的Embedding外，其他26项与Torch Profiler的kernel总时间差异均小于1%（最大0.92%）。`NSYS_MODULES.csv`保留逐项差异。两个独立采集的启动/缓存/时钟状态不同，微秒级算子尤其敏感；不据此指定绝对计时精度。

## 3. 与公开速度基准比较

|来源|条件|公开结果|如何比较|
|---|---|---|---|
|[Qwen 官方](https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html)|H20、Qwen3-4B BF16、B1、输入1/输出2048、Transformers4.51.3＋FA2|45.94 tokens/s，约21.77 ms/输出 token|GPU和内核不同，只能检查 HF 数量级；输入1时官方含输入的计数差异很小|
|[Qwen 官方](https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html)|同上，SGLang0.4.6.post1|133.13 tokens/s，约7.51 ms/token|说明成熟引擎可快于通用 HF，不是我们的严格同卡对照|
|[pegainfer 作者基准](https://github.com/pegainfer-project/pegainfer/blob/main/docs/models/qwen3/serving-performance.md)|单5090、Qwen3-4B BF16、TP1、输入1024/输出128、QPS1；驱动590/CUDA13.1|pegainfer TPOT6.53 ms；vLLM0.24 TPOT6.71 ms|同卡型/精度，输入、软件、服务路径不同；不能用高并发总吞吐替代单请求 TPOT|
|[Grout 论文 §5.3](https://arxiv.org/html/2606.15991v1#S5.SS3)|5090、Qwen3-4B、f16、B1；prompt18、生成长度扫描|长生成8192时154.7 tokens/s，约6.46 ms/token|FP16和短prompt增长上下文，作为融合/Graph实现的旁证，不混称 BF16 同配置|

Qwen 官方 speed 的定义是“输入＋输出 token 数／总时间”。6144、14336等长输入的数百 tokens/s含 prefill，不能把倒数当作 decode TPOT。公开能耗方面，尚未找到与本轮同模型、单5090、BF16、B1、2K/8K且仅decode边界完全匹配的独立 J/token 原始结果；不拿 TDP×时间冒充它人的实测能量。

## 4. 异常检查与适用范围

- 每个正式窗口核验 `平均W×秒=J`、`J÷实际执行次数=J/次`，不用 GPU TDP 替代读数。整模型首个长窗还对照同窗功率积分；两个接口同属 NVML，只验证内部一致性，不是外部电表校准。
- 所有阶段先按最后五个约1s温度样本跨度≤1°C筛查，最多等待25s（整模型60s）；没有锁频/改功率上限。每个窗口保留前后温度和 SM/显存频率；未通过筛查照实列出，不静默剔除。它不是完整的冷却配对实验，温升/动态频率仍会影响绝对能量。
- 原生 Flash GQA 在最初8K门禁 relative-L2 为1.42698%、top1相同，超过预设1%，保留失败而不放宽门限。本轮正式静态KV路径保留原始头展开；历史文件名 STATIC_GQA 是开发命名，不表示正式开启原生 GQA。
- HF固定/Graph路径仍没有成熟引擎的线性层合并、QK Norm/RoPE融合及原生GQA等全部优化。若它慢于公开成熟引擎，不能推导 GPU 硬件本身只能达到该速度，也不能据它宣布概率ASIC对最佳GPU的倍数收益。
- 只测GPU及其关联板载显存电路，未计主机CPU/系统DRAM。ASIC/TLM若对比整卡 J/token，也要标清外存、未定价模块、质量和速度差异。无新PPL、训练或ASIC电路验证。

## 5. 复现与证据

`raw/COMPLETED.json`封存状态与ARTIFACT_MANIFEST相互校验；本地所有小JSON按原字节SHA下载。大TRACE留既有个人服务器存储，REMOTE_INDEX.json记录原位置、大小及SHA。冻结依赖7911a0aff763f0dc、源代码和启动/失败记录见EXECUTION.json。

方法依据：[Zeus温度与长窗实验](https://ml.energy/blog/energy/measurement/thermally-stable-profiling-for-accurate-gpu-energy-measurement/)、[NVML设备接口](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html)、[PyTorch2.7 SDPA/GQA说明](https://docs.pytorch.org/docs/2.7/generated/torch.nn.functional.scaled_dot_product_attention.html)。
