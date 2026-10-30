## 2026-10-30 同卡长窗口复测

最新[完整报告](../../../results/gpu_decode_energy_20261029/remeasure_20261030/REPORT_ZH.md)、[复测代码与协议](remeasure_20261030/README_ZH.md)。包含固定冷却对照、14类模块和独立Nsight，保留所有失败及原测量。

# Qwen3-4B decode：GPU 实测与 TLM 对照（Issue212）

对象为后训练版 `Qwen/Qwen3-4B`，revision `1cfa9a7208912126459214e8b04321603b3df60c`。B1，BF16 权重/输入，保留原生归一化与融合内核的内部精度；Transformers SDPA。测量不修改 FFN/Attention 的数学计算，不做训练或 PPL 评测。

## 测量边界

| 输出 | 具体含义 | 用途 |
|---|---|---|
| `NATIVE_CONTINUOUS_DECODE` | 原生逐 token 贪心生成128步，包含 argmax，KV长度增长；prefill与主机输出传输不计入 | 当前 Transformers 实现的实际 decode |
| `FIXED_CONTEXT_DECODE` | 固定总KV长度2K/8K的完整forward，复用不可变前缀；包括Python调度，不包括argmax | 匹配TLM形状的参照 |
| `CUDA_GRAPH_FIXED_CONTEXT_DECODE` | 相同forward/内核经CUDA Graph回放，排除大部分Python发射开销 | 更有竞争力的GPU参照；不是完整持续生成，也不代表vLLM等系统的最佳性能 |
| `TIME_PROFILE` | 独立Profiler运行，记录36层各类算子的GPU内核时间 | 定位计算和访存热点；不能用内核时间总和替代端到端时间 |
| `REPLAY_*` | 捕获真实decode的输入，按同一类操作回放全部36层，以NVML累计能量差测整卡能量 | 模块隔离回放的功率/能量；不是原生运行时各模块独立供电轨测量，不可直接求和 |

累计能量差为主要能量依据，平均功率为能量差除以窗口时间。主要窗口目标5秒、三次重复；以JSON记录的**实际窗口长度**为准，极小模块可能达到迭代上限而窗口较短，需降低其能量估计置信度。预检中此卡的能量计数器约100ms更新，不能逐微秒读取来宣称测出单个算子能量。空闲扣除值仅为诊断，报告主值使用未扣空闲的总能量。

NVML边界为设备及其相关显存电路；不包含服务器CPU/主存。重型Profiler不放在能量窗口内。采集时核对Slurm分配设备UUID及其他计算进程，记录温度/时钟，不锁频或修改服务器功率上限。

## 分组与局限

覆盖Embedding、QKV投影、Q/K RMSNorm、RoPE、KV追加、Attention核心、输出投影、层RMSNorm、FFN gate/up、SiLU及逐元素乘法、FFN down、残差、末尾Norm、词表投影。QK、Softmax、PV保留GPU的融合实现，作为一个Attention核心报告；强行拆开会改变原始基线。数制转换等内部操作遵循原始模型，不能把GPU实现当作概率硬件的电路实现。

隔离回放会改变缓存驻留、操作顺序和并发。投影回放包含全36层不同权重，避免仅反复访问一层而人为放大L2复用；小算子仍有缓存/主机发射影响。原生连续decode与固定形状回放应分别看待。模型载入、prefill、图捕获和预热均在能量窗口外。

## 运行与复现

复用已准备好的环境，不安装新的CUDA/驱动。依赖PyTorch、Transformers及系统NVML，无需额外Python版NVML包。仅通过Slurm申请一张GPU，建议4 CPU、48GB主存；精确命令参数在结果 `PROVENANCE.json` 中。

```bash
python -m unittest test_meter
python run_decode.py --prepared /authorized/prepared/Qwen3-4B.json \
  --output /authorized/results/new_immutable_run \
  --contexts 2048 8192 --window-seconds 5 --repeats 3 \
  --native-steps 128 --profile-steps 3
```

`prepared`格式沿用本项目既有准备清单：`model.id`、`revision`、`local_path`、`files[{name,bytes,sha256}]`、`data[...]{path,sha256}`、`test_corpus_tokens`、`test_token_ids_sha256_le_int64`、`tokenizer_class`。先校验全部权重/配置/分词器、原始语料和token序列SHA，再测量。使用冻结WT2测试文本前缀，不套聊天模板、无BOS、固定步数无EOS提前结束；这不是聊天能力或thinking评测。

`--smoke --contexts 128 --window-seconds .5 --repeats 1 --native-steps 8 --profile-steps 1`只用于门禁。插桩及CUDA Graph输出必须与原始forward逐位一致，QKV/FFN/Attention/KV/残差计数必须覆盖全部36层。烟测的短窗口功率不是正式2K/8K结论。

仅从 `COMPLETED.json`、`ARTIFACT_MANIFEST.json` 及各文件SHA确认完成。大Chrome trace及安装代码快照保留任务存储，Git提交小型结果和校验索引。正式任务Slurm3399，冻结执行快照 `7911a0aff763f0dc`；GPU预检3389，真实模型门禁3398。

与ASIC比较时同时列出ms/token、mJ/token与W。GPU设备能量不能只与ASIC算子核心能量比较；TLM片外存储、未标定模块及算法质量差异必须另列。条件TLM估算不改称芯片实测。

方法依据：[NVML累计能量接口](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html)、[PyTorch Profiler](https://docs.pytorch.org/docs/main/profiler)、[Zeus能量窗口测量](https://ml.energy/zeus/measure/)、[Transformers KV cache说明](https://huggingface.co/docs/transformers/kv_cache)。

真实执行源码保存在Git提交 `20d46ec7f04021e90bba42312681ad4f7bbe81ee`。测量后修正了Profiler的CPU范围选择，未重跑能量窗口或改写封存结果。`build_report.py`兼容原始双行，并有回归测试；原始SHA与新版汇总源码SHA分开记录于结果PUBLICATION。
