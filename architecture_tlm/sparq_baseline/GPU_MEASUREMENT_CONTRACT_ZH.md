# GPU 延迟和功率测量合同（待运行）

这是给Issue157 runner的协议，不是新实验结果，也不是ASIC PPA。

## 相同输入与两条基线

- 记录模型/分词器revision、数据SHA、代码/配置SHA、GPU/驱动/CUDA/Torch版本、batch、有效N、padding/causal mask、QKV dtype/布局、r/k/local、fallback原因及比例。
- 数值基线：与候选核同FP32计算、BF16输入/输出边界的准确Attention。部署性能基线：原生BF16 SDPA，记录实际Flash/其他backend，原生GQA且不复制KV。二者的数值和执行边界分列；不能用较慢的显式参考softmax作为唯一速度基线。
- 主方案是paper-v6概率sum，r32/k128/local32、meanV关闭；官方rawscore-sum/k+1是另一变体。若性能核改了精度、tau、local或补偿，先回到功能门禁。
- max4、小网、Ising等如参与比较，使用相同质量目标/有效token集合。替换后的原FFN、QK-Norm/RoPE/GQA/QKV/Wo保持，Attention-only与完整decoder性能分别报告。

## 计时窗口

1. 冻结真实post-QK-Norm/RoPE Q/K/V或完整模型工作负载；合成张量另标，不能称Qwen质量结果。
2. 分开预构建cache的单次attention core、包含新增token和双布局写入的decode、prefill/转置准备及完整生成。核心计时须包含通道选择、近似评分/softmax、概率sum/token topk、local、gather、准确QK/softmax/PV与最终转换。
3. `validate_finite`、diagnostics、全FP32 materialization、混合fallback的where都按实际执行记录。仅调取本账本logical_counts不代表实测读量；若关闭验证开关，应先验证同输入并单列该性能配置。
4. CUDA events在同stream包围完整调用，预先warmup，完成后同步并检查异步错误。计时内不得夹入CPU打印/结果复制/无关监控；另报host wallclock/完整生成。固定seed和输入不是任务泛化证据。
5. 预声明重复数，交替测dense/candidate，保留全部样本和每轮中位数、p50/p95、冷热策略、峰值分配/保留内存。记录功率/温度/时钟漂移及共享GPU活动。Graph capture、预分配与缓存冲刷两方案相同，未控制的因素写限制。

## 能量

- 优先用支持的GPU累计能量计数器差分；否则独立记录带单调时间戳的NVML功率采样并对**同一个明确窗口**积分。短单token事件不足以匹配低频功率传感器，须重复同工作形成足够长窗口，报告采样间隔、点数、有效时长、完成token/调用数。
- 累计计数器回绕、缺采样、不同设备、监控失败、窗口不覆盖完整工作均标无效，不填0。前后同步与能量读数之间的idle边界误差记录；计数器与积分估计不要混成同类精度。
- 报告窗口总焦耳、J/完成token或调用、平均瓦特。可额外报告单独匹配idle窗口扣除后的增量，不能用它替换总能量，也不能把较低平均功率直接等同省能。
- 芯片/板卡、GPU内存、主机边界依传感器实际范围写明。GPU能量既不是ASIC功耗也不是面积。ASIC `area_um2/power_W/energy_J`保持null，除非已有对应网表/工艺/活动证据。

## 最小结果字段

```json
{
  "status": "not_run",
  "source_commit": null,
  "source_manifest_sha256": null,
  "model_revision": "1cfa9a7208912126459214e8b04321603b3df60c",
  "algorithm": "paper-v6-gqa-probability-sum",
  "config": {"r": 32, "k_total": 128, "local_total": 32, "reallocation": false},
  "numeric_baseline": null,
  "deployment_baseline_backend": null,
  "timing_scope": null,
  "cuda_event_samples_ms": [],
  "host_wallclock_seconds": null,
  "accepted_calls_or_tokens": null,
  "fallback_counts_by_reason": null,
  "validation_and_diagnostics_flags": null,
  "cache_construction_and_append_included": null,
  "energy_method": null,
  "energy_window_seconds": null,
  "energy_samples_or_counter_receipt": null,
  "gpu_total_energy_J": null,
  "gpu_mean_power_W": null,
  "gpu_energy_per_completed_unit_J": null,
  "asic_area_um2": null,
  "asic_power_W": null,
  "warnings": []
}
```

这不是自动验收阈值。runner需保留原始样本/失败及来源，质量先通过匹配协议再作速度/能耗比较；实测结果写新目录、绑定实际执行SHA。
