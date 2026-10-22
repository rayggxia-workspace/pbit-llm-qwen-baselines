# unified_v6 与周期执行入口的可运行桥接

`architecture_tlm.cycle_v1.v6_adapter` 读取已有 v6 配置与明确形状，把支持的算法、并行度和原生随机源参数映射到 cycle_v1。它分别运行旧 v6 原有算子方法与新周期算子，输出两份结果及逐字段边界。没有修改 `unified_v6` 源码或历史结果，也没有把一个 tile 的周期乘成全层/全模型。

## 运行

先运行独立小形状验证。`--smoke` 明确选择 64→64→64 的完整 FFN，以及 hidden=64、单头单KV、9 token 的查询；它不是 Qwen/Llama 层。FFN 沿用 B4/T32/K32、8 engines，采样查询用4个输出。

```bash
python -m architecture_tlm.cycle_v1.v6_adapter --operator ffn --smoke --output /new/ffn
python -m architecture_tlm.cycle_v1.v6_adapter --operator attention --smoke --smoke-mode exact --output /new/exact
python -m architecture_tlm.cycle_v1.v6_adapter --operator attention --smoke --smoke-mode pv --output /new/pv
python -m architecture_tlm.cycle_v1.v6_adapter --operator attention --smoke --smoke-mode winner --output /new/winner
python -m architecture_tlm.cycle_v1.v6_adapter --operator attention --smoke --smoke-mode rejection --output /new/rejection
```

使用已有配置时，`--v6-config` 接受完整配置 JSON，或 v6 结果中含 `config`、`model` 的对象；`--shape` 可显式提供独立形状。`--fixture` 使用周期 FFN/query 的实际张量 JSON，不上传其中权重。

```bash
python -m architecture_tlm.cycle_v1.v6_adapter --operator ffn \
  --v6-config /existing/v6-result.json --fixture /private/full-shaped-ffn.json --output /new/bridge
```

输出目录必须不存在。默认新模拟器同时运行 cycle 与 event，并逐项比较接受/完成时间、完整 stall trace、内存读取、动作、状态和数值轨迹。`--event-only` 会明确取消该次交叉检查；不会暗示已经完成。失败后保存 `FAILED.json`，已有旧算子结果保留用于诊断。

服务器执行快照使用 `python -m architecture_tlm.cycle_v1.package_snapshot --archive /new/snapshot.tar.gz --manifest /new/manifest.json --check-directory /new/extracted`。打包器包含 v6 桥的 13 个历史模块及默认 SRAM 校准 JSON，并逐文件核对解包后的 SHA-256；随后以 Python `-I`、清除 `PYTHONPATH` 执行小 FFN 和完整 64→64→64 的 v6 桥 smoke，确认加载的项目模块全部来自解包目录。快照不包含模型权重、输入 fixture 或历史结果集；自定义校准路径与实际 fixture 仍需在执行配置中另行明确提供。

## 映射与拒绝条件

- FFN：映射 B/T/K、engine 数、vector lanes、seed 和原生 seed-bus 参数。fixture 必须完整匹配 `hidden_size`、`intermediate_size`、完整 down 输出和 residual；拒绝把裁剪行称作完整 FFN。旧 SC 仅支持本桥的 startup/II/drain=1/1/1 基线，不将 II 擅自赋给 latency。
- Query：映射 exact/PV，或 screen_exact/screen_pv/screen_winner/screen_rejection 的**候选列表已经给定之后**部分。旧的 `qk`、`sampled_attention` 和 sampler 方法实际运行；不执行 `route`，因此筛选、摘要更新、QKV/RoPE、KV append、GQA 并集不在范围。screen 模式不能因为名称保留就宣称筛选模块已迁移。
- winner 的输出数按旧 `samples × winner_update_multiplier` 映射；burn、shift、retry/proposal cap 明确映射。原生 q/256 源使用旧 sigmoid step。不同端点池及请求时刻可改变相同 seed 下的轨迹，不声称两个模拟器样本相同。
- 当前要求 core/source 100 MHz、SRAM 80 MHz、原生 integrated_service、Link 后端；拒绝 DRAMSys、串行 Ising、非本桥 SC 格式、GQA query 和非显式完整 query 形状。非 screen 的 exact/PV 必须覆盖全部 context 候选。

## 两列结果如何解读

`v6_summary.json` 来自旧 `FullDecode` 的真实算子路径。FFN执行 gate/up→SwiGLU→down→转换→residual；query执行给定候选的 QK→采样/准确PV→输出。没有执行 embedding、其余层或 lm_head。旧 FFN是工作量与时序模拟，不读取权重值进行数值推理，故 `numeric_output=null`。

`cycle/summary.json` 来自新有限资源图，带真实地址与数据、原生随机源、有限缓冲和新数值检查；`cycle/contracts.json` 给出其全部独立硬件假设。`mapping.json` 保存原配置、形状、映射字段、双方独有契约和不能等同的字段；`START.json` 保存 fixture 散列、新源码及旧 v6/校准依赖散列。

旧 v6 的 blocking SRAM/fabric、批量排空 burst 窗口、additive CDC、宏恢复调度与条件价格，**不会**静默转换成新 MemoryPort 的 descriptor window、bank 端口或三个目的时钟沿握手。旧 exact query 是 BF16 KV 的 fused online 路径，新 query 明确保存 FP32 与分数；旧 FFN假定入口已在SRAM，新链有显式入口读取。这里并列展示独立耗时，不据此比较加速/能效，`speedup=null`。

桥给旧 sampler 构造的 logits 使用每乘/每加 FP32 舍入；cycle query 使用 double 乘积/`fsum` 后转 FP32。因此即使输入Q/K和seed相同，也不承诺两个分数或抽样轨迹相同。旧侧保存该score fixture散列与算术说明；它不是旧v6原生数值数据通路，也不作为新周期算子的数值oracle。

## 实际 smoke

五例都完成新 cycle/event 全 payload 一致性与数值检查，六项映射/拒绝测试通过：

最终回执位于 `results/v6_adapter_20261023_v2/`，固定执行提交 `d0ccc5e`，已包含 `414e1aa` 的恢复舍入profile与 `e2695e2` 的有序V消费者prefetch信用死锁修复。先前 `results/v6_adapter_20261023/` 仅保留为历史输入/执行记录；最终报告引用v2。

| 算子 | 旧 v6 operator ns | 新 cycle ns |
|---|---:|---:|
| FFN B4/T32/K32，64→64→64 | 6890.5 | 11962.5 |
| exact query | 840.5 | 1137.5 |
| systematic PV query | 5665.5 | 6125 |
| winner query | 6415.5 | 6012.5 |
| corrected rejection query | 13115.5 | 13437.5 |

这是接口连通和可检查的独立执行结果；两个时间列不构成同资源对照，不形成 TPOT、PPL、全芯片周期精确、STA 或物理能量结论。
