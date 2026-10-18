# Llama 2 7B：当前标准的完整模型 TLM

任务 [Issue #14](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/14)，负责人 @jieruiz。本目录保存 Llama 2 7B Base 的独立配置、运行入口及结果，不覆盖 `llama7b/` 中的 LLaMA-1 结果。共享引擎固定来自已合入的 PR #13 / `07d03385a3b16b1f81a987c031f667c13876edf1`；执行快照还逐文件核验运行时、Attention、SRAM/DRAM 配置，后续公共引擎变化不能悄悄混入旧结果。

Llama 2 7B 与 LLaMA-1 7B 的矩阵形状一致，但**不能把 LLaMA-1 的真实 logits 轨迹换名当作 Llama 2 结果**。模型不同会改变筛选、PV 去重和物理访存地址，模型身份与原 BF16 参考须重新核验。

| 项目 | Llama 2 7B 本次配置 | 与 LLaMA-1 的关系 |
|---|---|---|
| 模型 | `meta-llama/Llama-2-7b-hf`，Base | 不使用 Chat 版本 |
| 结构 | 32 层、hidden 4096、FFN 11008、32Q/32KV、head 128、词表 32000 | 仍为 MHA，7B 版本没有 GQA |
| 参数 | 6,738,415,616；embedding 与 lm_head 不共享；无 QKV 偏置 | 矩阵形状和参数量相同 |
| 原生最大上下文 | 4096 | LLaMA-1 为 2048；这里不做 RoPE 外推 |
| RMSNorm ε | 1e-5 | LLaMA-1 为 1e-6 |
| 模型发布 dtype / 本次捕获 | 原配置 float16；显式 BF16 加载与计算 | 发布存储 dtype 不等于本次推理协议 |
| Attention | 准确 Q/K/V/O 投影，MHA QK，再按方案执行完整、PV、筛选或 Ising | 沿用已验证的有限资源数据流，重新捕获模型轨迹 |

上游具体 revision、模型与分词器逐文件 SHA-256 由 `model_identity.json` 固定。受访问控制的权重不提交 Git。镜像下载仅是合法可访问的传输来源，必须核对官方同版本文件的 SHA；不能用“同名模型”代替身份核验。

## 同一硬件情景下比较的方案

| 名称 | FFN | Attention 核心 |
|---|---|---|
| `bf16_dense` | BF16 数字矩阵、SiLU、逐元素乘法 | 完整准确 QK、Softmax、PV |
| `int8_dense` | 固定 W8 数字 FFN、连续 SiLU 与接口 | 同上，区分量化收益与随机计算收益 |
| `sc_dense` | W8、A8 随机输入、精确并行计数 | 完整准确 Attention |
| `sc_pv` | 同上 | 准确 QK/Softmax，systematic PV 采样 |
| `sc_screen_exact` | 同上 | max4 筛选后候选内准确 QK/Softmax/PV |
| `sc_screen_pv` | 同上 | max4 筛选、准确 Softmax、PV 采样 |
| `sc_ising` | 同上 | 准确 QK、Ising 宏直接给出 V 索引并累加 |
| `sc_screen_ising` | 同上 | max4 筛选、候选 QK、Ising 宏及 V 选择累加 |

所有方案包含32层、完整投影、归一化、残差、独立输入嵌入和最终词表层。TLM 从已有 prefill/KV 开始，单步 decode；测量时缓存长度为 L，prefill 为 L−1。输出为 greedy argmax，不添加词表 Softmax。这里的 BF16 数字基线仍是相同 ASIC 资源假设下的 **TLM 基线，不是 GPU 的实测性能/能耗**。

## 从当前 Qwen/LLaMA 引擎完整继承的优化

- FFN：100 MHz、8 个 64×64 随机阵列、W8/A8、T=4096 精确计数；合并 gate/up，数字 SiLU(g)×u，再随机 down；宽累加统一转换后与 BF16 残差相加。
- 随机源：FFN 本地32位 PRNG 状态与检查点，一个8位阈值随机字共享64路，按输出波次恢复；分层根熵、扩种及种子传输均按原模型计费。**不把4096拍随机比特流存 SRAM**。权重侧保持原方案。
- PV：按原上下文 S=L/16，而非固定样本数；512/1024/2048/4096 分别为 **32/64/128/256 次/头**。前缀和、块预算、非零索引和描述符收费；只读取实际需要的 V，重复索引只读一次，重复样本的累加仍计费。
- 筛选：prefill 已有 max4 摘要，首次及后续 decode 均更新新 K。每头独立候选直接控制 MHA 的 K 读取；摘要、mask、筛选随机源及读取都收费。没有继承 Qwen 的校准参数。
- Ising：足额容量为 L 的宏，串行服务各头，内部随机源、反馈、状态和读出均包含在宏参数内；不再额外加一次 PV 采样。IID oracle 只提供地址情景，不证明器件有限时间混合精度。
- SRAM：统一8 MiB、16条128-bit lane、SS角80 MHz、16 GB/s fabric，4096×128 宏校准；有限端口、分块与双权重槽、CDC、工作区峰值及真实读写均保留。4K 时已有 KV 为 **2 GiB**，放在 DRAM；地址空间另保守预留一个新 token 槽。
- DRAM：同一已审计 DRAMSys/DRAMPower，2通道×2rank×8颗4Gbit x8＝16 GiB；64B 请求、32在途请求、真实稀疏地址和闭环调度。Staggered 主表与 NoPowerDown 对照；Micron 电流情景不当作本工艺典型板级实测，接口/PHY 代理单列。

共享引擎通过绝对路径加载 `llama7b/runtime/` 与单独命名的 `llama7b/attention_adapter.py`；不 `import run`，避免命中 LLaMA-1 或其他实验入口。新代码、配置、输出目录和执行 manifest 均属于本目录。主任务包括 Link 72 项、DRAMSys 36 项；额外 NoPowerDown 配对由任务清单单列，不混入原72/36项的完成计数。

## 正式真实轨迹入口与明确的合成入口

```sh
python architecture_tlm/llama2_7b/test_model_contract.py
python architecture_tlm/llama2_7b/run.py --case sc_screen_pv --context 4096 \
  --seed 0 --trace /path/to/c4096.trace.json \
  --identity-manifest /path/to/model_identity.json --output NEW_RESULT.json
python architecture_tlm/llama2_7b/run.py --case sc_screen_pv --context 4096 \
  --seed 0 --trace /path/to/c4096.trace.json \
  --identity-manifest /path/to/model_identity.json --output NEW_DRAM_RESULT.json \
  --bridge /path/to/pbit_dram_bridge_sg_v6_audit \
  --dram-config architecture_tlm/llama7b/dram/configs/ddr4_2ch_2rank_Staggered_core_limits.json
```

正式 `--trace` 必须携带身份 manifest；入口检查 `REAL_LLAMA2_7B_POST_ROPE_QK_LOGITS`、模型和 tokenizer SHA 身份、manifest 字节 SHA、结构、上下文、每 token 原 BF16 参考输出逐位一致、完整无重复32×32个头及有限 logits。LLaMA-1 同形状轨迹、缺身份、缺 BF16 对照或错误上下文均拒绝。

`--synthetic` 是另外的显式选项，只用于结构测试或无权重环境；它与真实 trace/identity 互斥，并把输出标记为 `SYNTHETIC_LLAMA2_SHAPE`。默认没有轨迹时直接报错，不静默生成“Llama 2 结果”。例如：

```sh
python architecture_tlm/llama2_7b/run.py --case bf16_dense --context 512 \
  --synthetic --output NEW_SYNTHETIC_ONLY.json
```

输出文件存在时拒绝覆盖；原生长度超限、SRAM不足及能量账不闭合都会失败。Slurm 脚本在运行前必须核验执行快照；提交后不改源文件。记录代码提交、原共享源码 SHA、配置、模型/数据 SHA、种子、命令及输出 SHA，真实捕获与后处理版本分别记录。

## 怎样理解结果及当前限制

真实 QK 轨迹来自重新运行的原 BF16 模型。它是相同地址工作负载的对照证据，**不是随机 FFN 后的联合推理结果，也不是随机方案 PPL**。`quality_reference_ppl` 明确为 null，不拿旧 Qwen 或 LLaMA-1 数值成绩充数。若另行进行完整 WT2 滑窗 PPL，则独立记录其窗口/stride、语料、模型、种子和精度，不混入宏级 TLM 验证。

SRAM 有工艺校准、DRAM 有成熟模拟器和核查电流情景；随机核、A8 PRNG/分发、resident SRAM接口、数字算子、Ising宏和互连面积/能量仍部分依赖参数或旧 RTL 代理。模型不宣称周期精确 RTL、布线后芯片或 GPU 能效倍率；主要用来判断 FFN 采样长度、存储驻留、稀疏读取和资源调度的瓶颈。可运行的8 MiB配置不等于已经完成全局最优硬件搜索。
