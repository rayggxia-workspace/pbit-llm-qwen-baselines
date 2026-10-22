# 完整 FFN 编码恢复接合 / Issue123

本任务将 PR122 的指数域编码、FUSED0 完整恢复接到 Issue116 的 FFN 数据流。
STA/PPA 按用户安排交给 `jieruiz`，可执行任务文件在
[编码恢复 PPA 交接](../encoding_restore_contract/ppa/HANDOFF_JIERUI_ZH.md)。
本目录不含工艺库、权重或实测物理指标。

## 接合内容

默认 `legacy` 路径保持不变。新模式必须显式指定 `pr122_b4_fused0`、
`restore_rounding=rtl_fused0_order` 和全部 Profile 字段，不将默认数字当 STA 结果。
当前 x/z 均按 FP32 存储和编码；原 fixture 的 BF16 数值不等于 BF16 接口。

一个 x 编码组由全部 gate/up 输出 tile、所有 wave 共享。每个输出独立做 B4
恢复和跨 k FP32 加法，结果槽包含在途、待消费以及下游加法状态；tile scratch
保持到实际 partial write 完成，组状态保持到所有消费者结束。旧代理子步骤不再
与完整操作重复计费。SiLU 仍为连续软件函数，SC/存储/CDC 仍是已声明条件模型。

完整链为 gate/up → SiLU/product → z 重新编码 → down → BF16/残差。
独立 oracle 使用整数尾数编码与 signed-W8 已接受样本数收缩，不调用生产编码/
计数/恢复实现。五阶段按 FP32 原始字节核对，另检查内存最终字节、动作单位和信用。

## 依赖与应用

PR126 已公开 Issue116 正式后端，本任务固定其 `160f46e0b63bdf94499e2434dc35e09f44fc2fcc`
及 PR122 的 `8007d98f15676ad316180ee18b5d1b29aa00af95`，在任务分支合并依赖并直接
接合 `architecture_tlm/cycle_v1/ffn.py`。PR125、122、126 均待审，未自动合入主线。
早期未公开基线 `902c49b` 与正式发布的运行核心逐 Git blob 一致；变化仅为不参与
本 runner 的打包工具。最终执行包在独立树重放本任务提交后冻结，源 SHA 为准。

[backend_overlay/README.md](backend_overlay/README.md) 保留精确补丁和只读预检，
用于从固定依赖重建或核验。当前 PR 分支已经接合，无需重复应用；不能对正在开发
的 `cycle23` 直接应用。应用器保留原文件、意图和回执，不做模糊补丁或重置。

执行入口（组装并验收依赖之后）：

```text
python -B -m architecture_tlm.cycle_v1.run_contract_ffn --fixture FULL.json --profile PROFILE.json --output NEW_RESULT --expect-shape 896 4864 896
```

默认全尺寸使用事件模式；小形状 `--compare-modes` 核对完整周期/事件轨迹。
主机仿真加速 helper 必须与原核保持完整 trace 相等，主机墙钟改进不计作硬件加速。

## 证据与边界

- 真实完整输入：CPU-only2777捕获 layer0、context64 最后token的896→4864→896
  全部W8矩阵、FP32 scale、真实x/残差。41,405,784字节 fixture 保留在个人服务器，
  SHA为 `c4e8100441db57858fff8682af5acfb5ca06cb61fbd3b16e29a631bd230b640c`。
- 功能 RTL：CPU-only2778通过45场景、11667输出、180reset flush；T16/32/64，
  BF16/FP32编码，DEPTH1/3/5，3seed。见相邻包 results/rtl_2778。
- 冻结包在独立提取目录通过28项测试：新6项合同、14项原FFN、8项原核/helper测试。
  覆盖多k、多wave、尾块、depth1慢消费者、−128端点、子正规数和legacy默认。
- 小型外部runner与失败保留原件在 results/smoke_20261023；版本和限制见
  work/amlink1219/123/reviews/REVIEW.json，旧注入目录不冒充最终版本执行。
- 全尺寸T32期望90次完整组编码、204288次逐输出恢复及同数跨k加法、3192个权重tile。
  这是验收期望，实际通过状态以服务器结果summary/manifest和任务交接为准。
- 正式后端完整运行 CPU-only Slurm2783 已按用户要求取消（CANCELLED/0:15）；执行包及配置索引在
  `work/amlink1219/123/ffn_2783/`。2779/2780也为主动中断，三次均不能算完整验证成功。
- 主机调度 helper 的55步、17350事件前缀与旧版本全状态相等，3.868→1.226秒。
  此外独立随机测试120次完整payload一致；不由前缀推算全程或硬件加速。

长链结果先保存实际阈值、逐阶段FP32原始字、native报告、完整压缩轨迹，再做
oracle/账目验收。Git只放必要小摘要、索引和SHA；原件留个人服务器。
单token单层差异不是模型PPL；条件周期不是STA；未知PPA保持null。

上传/作业状态入口：[任务交接](../../work/amlink1219/123/HANDOFF.md)。

当前已停止，无自动继续。详见[停止总结](../../work/amlink1219/123/STOP_REPORT_ZH.md)。更快调度候选及小型证据仅归档于[candidates/pending_20261023](candidates/pending_20261023/README_ZH.md)，未取代发布runner。
