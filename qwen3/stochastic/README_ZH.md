# Qwen3 最新概率架构迁移（Issue144）

依赖 Issue136/PR137 的原始 Base 基线，不使用 Chat/Thinking 权重。负责人 jieruiz；分支 task/144-qwen3-stochastic，PR base task/136-qwen3-bf16。2026-10-23全部26项4096目标后缀已完成并独立验证，见[最终结果与完整WT2预算](../results/stochastic_20261023/REPORT_ZH.md)；完整候选WT2未运行。执行快照8c35145保持原字节，当前新增验证/汇总代码只用于收尾审计。

## 固定架构

| 部分 | 本轮参数 / 边界 |
|---|---|
| 模型 | 1.7B：28层、H2048、FFN6144、16Q/8KV；4B：36层、H2560、FFN9728、32Q/8KV；head_dim均128 |
| FFN | 固定对称W8/64×64块；B4幅度档 A,A/4,A/16,A/64；A8 q/256、符号独立、满幅旁路；T32/K32，每个8值区间一次随机门限，64通道及跨档共享 |
| FFN非线性 | gate/up共享同一x流，FP32 SiLU(g)×u，z独立重编码；x与z各T32；不是整个FFN只需32时钟 |
| QK筛选 | 64-token块，四个16-token均值取max4；free-block均值/标准差（floor=.01）；首块和末两块强制；Bernoulli后按原始优先规则修复为8块，尾块有效mask保留 |
| 校准 | 各模型原生BF16、WT2 TRAIN，16个拟合窗口+16个不重叠TRAIN holdout窗口，2048上下文；逐层/逐Q头标量bias二分拟合，temperature固定1；总原始期望保留率.30，最终固定8块是不同指标 |
| 校正拒绝 | 128个接受样本；m初值0，上限24，proposal cap=128×128；无静默fallback；直接索引V并平均 |
| 赢家保持 | 1024个更新/保留值；argmax初始化，burn0、spacing1、shift0；保持/均匀仲裁；相关链不是IID；直接读V，不再二次PV抽样 |
| 保留 | QKV、QK-Norm→RoPE、GQA/cache、Wo、RMSNorm、残差、embedding/lm_head；BF16接口，FP32概率/FFN归约/CE，FP64 NLL累加 |
| 作用域 | FFN：prefill+decode全部层；Attention：全部计分query单token decode，prefill仍原生SDPA；不新增GQA组共享筛选策略 |

两个采样器的128/1024不是等成本，报告PPL不能据此声称赢家采样在相同成本下更优。本轮是理想FP32响应+软件Philox数值实现，不是硬件量化概率、物理随机源或RTL/PPA验证。

## 对照与口径

- 每模型13配置：cached BF16 seed0；FFN-only、FFN+screen-exact（定位筛选误差）、FFN+拒绝128、FFN+赢家1024，各seed0/1/2。
- 固定相同token集合、batch2：32×128=4096目标、初始context2048；后缀上下文随后增长，不称为固定2048全量滑窗。所有计分目标必须执行全部层单token路径，另有逐层FFN/Attention调用与target审计。
- BF16完整锚点复跑不改Issue136源码/config；要求NLL完全复现，若失败停下调查，不放宽阈值。
- tiny非等Q投影宽度以及真实两个模型均要求原生SDPA包装后逐logits hash完全相同。CPU门槛成功再申请GPU；Triton独立oracle/分布/仲裁/失败测试先于PPL。
- 后缀结果必须与cached BF16后缀相减，不减已有完整基线8.3673395/7.0386116。完整候选WT2尚未提交，先按实测耗时估算；不得声称本轮后缀已覆盖299077目标。
- 每结果记录源commit/config/模型manifest/原文及token SHA、校准SHA、环境、实际命令、seed、逐段NLL和覆盖；独立小型归档验证后才正式报告。

## 源码复用与部署

vendor来自已发布执行提交7a286ec140de6846006c96456275377fd22b4943（路径及blob见UPSTREAM.json）。仅改本地相对imports、FFN code缓存int16→int8无损存储；量化码[-127,127]、decoded FP32值完全一致且门槛测试逐值验证。scorer从同版本joint_evaluate迁移动态层数/Qwen3类/显式新sampler；adapter.py负责原生Qwen3接口、QK-Norm、4B 4096投影宽度及2项返回值。不修改Issue141/Issue136已有执行快照或他人工作目录。

使用Issue136的既有venv与已校验本地权重，无联网/重下载。新个人目录限定 `/home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-20261023-issue144`。从提交Git原件package，源目录只读、CPU Slurm验证、GPU两模型各一个作业，最多并发2GPU；首次冻结每模型24小时上限。不重复提交健康任务，错误/失败原件保留，新修复另行冻结。

运行：`python -m qwen3.stochastic.run --root PERSONAL_ROOT --stage cpu`，通过后每模型 `--stage pilot --index 0/1`。必须由run.sbatch在Slurm中启动。输出已存在则报错，恢复须显式审查，不自动覆盖结果。
