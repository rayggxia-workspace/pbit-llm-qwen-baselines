# Issue261: real FFN address-coverage handoff

2026-11-22; owner rayggxia; repository rayggxia-workspace/pbit-llm-qwen-baselines.
Branch `task/261-ffn-address-coverage`, PR base `main` at
`206bf81f18ea88c4c625ce8d32edd18a58edd1cd`.
Local directory `C:/Users/86134/Documents/a_P_BIT/tmp/ffn-address-coverage-issue261-20261122`.

## Completed

- Read-only full-width real Qwen3-4B capture, all36 layers × 16 positions in
  the first WT2 2048-token window. This reuses trained100M T64/strat64, not a
  new GU16/Wd32 forward. Capture commit `e6a1cb0a6bee9cff3a89de126f0ecab94aa4d3df`.
- Slurm capture6094 wrote a completed sealed RESULT.json in282.0194seconds.
  Entire-window no-op logits bitwise equal; nine legacy x/g/u comparisons equal.
- CPU6096 failed before analysis because sbatch copies `$0` into its spool.
  CPU6099 uses a separate fixed launcher with an explicit immutable source path.
  No captured model tensor or frozen helper was changed or rerun for this fix.
- CPU6099 completed all440 aggregate rows,15840 per-layer rows,264 MC rows.
  Five finite-enumeration/boundary tests passed remotely and locally. Three-seed
  MC validation uses48 matching vectors per signal/law; headline expectations
  use576. Maximum mean coverage error0.227629percentage points.
- All server CSV SHA and capture-result/source hashes checked locally.
- No model default, Attention, training, PPL, TLM, RTL or PPA changes.

## Results and scope

Formal entry `experiments/ffn_address_coverage_20261122/REPORT_ZH.md`.
Under IID whole-vector categorical sampling with replacement and real
`abs(input)*decoded_weight_norm` probabilities, K128 unique-row coverage is
4.7063% for GU and1.2642% for Wd. If any hit forces an entire adjacent64-row
group to be fetched, the corresponding fractions are94.8845% and53.1893%.
Use full CSV precision rather than these rounded handoff values.

The new address probability law is ideal categorical and has NOT been mapped
to P8 thresholds or winner-hold/Markov hardware. P8 labels refer to the original
FFN signal encoding. Coverage is not PPL or a measured DRAM/energy reduction.
K is one selected address per draw over the entire vector; it is NOT the old
parallel Bernoulli stream T. All output tiles must share the same address list
for these unique-row byte savings to apply. Existing64×64 tile storage is not
assumed to force64 adjacent input rows on every access; grouped results are
explicit conditional scenarios. Wd mean signals and finiteT64 realizations are
separate, retaining the latter's extra zeros as a diagnostic only.

## Private source / recovery

Remote root `/home/Hongjie_Zeng/projects/ffn-address-coverage-issue261-20261122`.
Capture raw `result/capture.npz`,33035912bytes,
SHA256 `8213fdd53b66b9dded08e9e70a2fd4d2c2cd53e32f47c93d0d2c7b7ac7031c37`.
Keep raw tensors private; no large weights or corpus were copied into Git.
Capture `source/` and analysis `analysis_source_f44acb9637d0/` stay immutable.
Executed command/environment/source hashes are in SUBMISSION.json. Logs for
all three jobs are retained locally in this work directory. Slurm accounting
is disabled, so terminal scheduler status is not asserted from sacct. Completion
is based on the sealed JSON, passed assertions, logs and empty own job queue.

Reproduce without GPU using committed aggregates:
`python experiments/ffn_address_coverage_20261122/test_coverage.py`
`python experiments/ffn_address_coverage_20261122/render_report.py`
NumPy is needed; report rendering also needs Matplotlib. On this local host,
Python38 has both. The bundled primary-runtime Python has NumPy but not Matplotlib.

## Publication / next action

See PUBLICATION.json for the actual PR/head and remote verification; do not
call the task merged or close Issue261 until review/merge. No remaining jobs.
Projects board is not synchronized by these repository tools; maintainer action
is pending. Root PROJECT_MEMORY and the main-branch memo already have differing
preexisting SHA; do not replace either with an older copy. The compact task
memory note is MEMORY_NOTE_ZH.md for the Issue28 maintainer to integrate.

Next scientific step, if requested: evaluate output error and model PPL against
a matching unchanged reference at K64/128/256/512/...; first GU-only and Wd-only,
then joint. Separately test a row-vector layout, deduplication and cross-output
reuse. Do not inherit quality from the old T64 bitstream, or rerun this capture
merely because the result is a one-window scope.

实际发布：PR262开放待审未合并，科学提交a03fff8f66aa16ff7efe41fa8090331647422215；29文件完整tree逐项核对。Issue261和Issue28交接评论均成功发布。执行捕获提交的3592B增量Git bundle已验证，便于恢复e6a1cb0原提交。后续元数据提交以PUBLICATION/PR为准。

## 2026-11-22 用户后续：具体地址/次数/DRAM方案

同一Issue261/PR262新增ADDRESS_SAMPLER_AND_DRAM_PLAN_ZH.md、address_plan.py与test_address_plan.py。新10项CPU整数/地址/次数检查及原5项通过，ARTIFACTS.json原19文件逐SHA未改。新增PLAN_VALIDATION.json记录源码/方案、两份用户PDF的原字节SHA及文献入口。无新模型或硬件任务。远端增量提交和逐blob/tree核验看PLAN_PUBLICATION.json；PR尚待审，未合并。

推荐C256/512输出分条，GU同输入的g/u权重连续；先整数质量树按幅度抽地址，再去重/计数并发DMA。count重放只证明精确归约，不继承OR4价格。原64输入/输出权重尺度分组不能打散。Wd分布不能从z_p8mean无代价取得；先GU-only质量实验，再Wd-only、联合。QKV/O可参考TEAL继续扩展，LM head需独立量化/采样质量验证。下一步不必重复旧捕获。

增量发布核验：科学提交93f492abd3f6e07e581d891a52724fc7efa4876b，7个blob与完整tree d4de6ed83d781a79fd2f1b8a663917c3775b727b匹配本地；远端方案blob938de588亦匹配。PR262开放待审未合并。后续只有交付回执/STATUS/PR说明同步，不把新方案误记成PPL或TLM结果。

## 2026-11-22 新授权的GU-only PPL执行

用户已明确授权远程Slurm小规模PPL/地址比例，合格候选再完整WT2。正式实现experiments/ffn_address_quality_20261122/。GPU执行快照a9d9af6a494d7dec338e0df9fc030dc021244476，控制/加强恢复核验896fe5515afebab43ebf1f6187aa826459658733。服务器本人项目/home/Hongjie_Zeng/projects/ffn-address-quality-issue261-20261122/；原checkpoint/inputs/helpers/runtime全部只读。

算法已确认：P8输入/原四档PoT→采样→CSR地址/次数（每输入唯一）→GPU-global bank仅加载选中输入的Wg/Wu W8权重→signed64计数累加、原64×64权重指数对齐→PoT或整数总质量补偿/平均/RNE24。后级P8、sigmoid LUT、AND和Wd原函数保持，Attention原SDPA。不是把零输入送全量GU矩阵乘法，不是DRAM时序或芯片PPA。

作业：6105 launcher spool路径失败（无模型），6106同源码绝对路径bash--wrap通过8GPU检查/36层整数与2048logits no-op；6107独立9配置恢复检查通过；6108实际提交screen 6109/6110/6111（三seed）；6112等待全部screen后选择，合格时自动提交候选及匹配原P-FFN全量对照。所有正式GPU脚本必须用绝对bash路径--wrap，避免$0指向spool；不修改source-a9d9af6a494d。

恢复检查：source-a9d9af6a494d/EXECUTION_MANIFEST.json SHA3f8d1880c7e9f45238ab30dcdc2f4ec51c18bb7516666a9ce68234ba15fd558d；gate-a9d9af6a494d-v2/RESULT.json SHA37d930b57386202d9cb97b01759b118c2a2f1fef10a3967c2dfe8e9156b34b2a；restore-896fe5515afe/RESULT.json SHA2f262c2eb5226622ae4465a71230ea9660a774b803eccdce73dd10390341efc6。每RESULT有.sha256，PROGRESS不能作完成证据。

下一步：读取screen-gate-a9d9af6a494d-v2/seed{101,202,303}/{case}/RESULT.json，要求9case×3seed相同8窗口/9215目标及token ledger；读取FOLLOWUP_gate-a9d9af6a494d-v2.json、SCREEN_SUMMARY_gate-a9d9af6a494d-v2.json和FULL_SUBMISSION_gate-a9d9af6a494d-v2.json。三seed齐且PPL比<=1.05优先/<=1.10上限、地址减少>=5%才完整；无合格则不扩大。screen最近运行，full未提交。保留pilot负结果，不把原P-FFN近99.79%覆盖与新cat64的2.44%混淆；后者pilot PPL已严重下降。

本地证据见quality_gate_v1/GATE_SUMMARY.json、quality_control_v1/RESTORE_RESULT.json及FOLLOWUP回执、quality_run_v1/SUBMISSION_INDEX.json。仅原gate JSON本地镜像212KB未发布，原件与SHA在服务器；小型源码包用于恢复精确执行字节。当前等待PR同步/审核，勿称已合并或全WT2完成。

实际发布：科学提交aef86f11adea55e476a4b56b787852bc0da73e8e，29个blob和完整tree30a428bde07ffaec9161af33dc87dc93ccb86c02与本地一致，运行manifest远端读回匹配。PR262已更新为稀疏W8执行与T64质量筛选，保持开放待审未合并。原执行a9d9/控制896f的准确字节可从已发布小型tar恢复，清单SHA不变；当前源码HEAD新增的是文档/控制/回执，不改服务器冻结snapshot。

后续SSH banner超时（8s与25s有界重试），最后一次成功队列读回为screen三任务运行4m35s、6112等待。没有取消/重提作业，不能把读回阻塞写成作业失败。另有SUBMISSION_GATE_v1/v2及gate-6105.log原件仍在服务器，本地只登记路径/既读SHA，首次多文件scp已取消；其它小型proof与screen命令回执已成功取回。恢复先检查原job/output，不重新执行gate或健康screen。
