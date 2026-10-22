# Issue96最新交接：真实源整机接入完成（2026-10-22）

负责人jieruiz，task/96-unified-tlm，PR103仍开放不自动合并；原PR99已经合并。继续使用本独立checkout，不另建全量副本。最新代码31aa4fa已推送；本轮40结果、报告及校验本地完成，最终发布/远端HEAD以integrated/PUBLICATION.json和Issue96最新回执为准。

- 执行冻结31aa4fa31fbfb7d74629b54811936ac30a41c250；40/40完成0失败，93机制/回归、1421归档与模型契约核对通过。run_targeted.py是40项精确计划；源/配置/数据(合成)/校准版本和SHA在results/integrated_rng_20261022_v3/EXECUTION、PLAN、逐case及ARTIFACT_MANIFEST；AUDIT在work/jieruiz/96/integrated。
- integrated_service为默认，core/RNG/sampler/seed100MHz；SRAM80MHz单独约束。FFN本地LFSR32流式共享64/T32K32，源与SC重叠不算双份；SAVE锁epoch/RESTORE/RELEASE及换种延后。Attention真实Bivium池+独立fair源，q/256、有限端点/种子包/预热/输出等待累计一次。原random_service源码/RTL未改。完整设计与结果RNG_INTEGRATION_ZH.md、RNG_INTEGRATION_RESULTS_ZH.md。
- 40项含12项S8赢家/拒绝各3seed×两后端诊断，倍率1，非默认质量预算；其余完整Qwen24层2K/8K、筛选PV三seed及Llama1/2的32层形状对照。Llama数据为合成路由，并未加载权重。新数字q/256不继承旧PPL。
- 首个完整pilot v1独立封存；v2 104项扫描0完成/0失败，CPU参考开销过大，主动Ctrl-C停止本人session90160，CANCELLED说明替代40定向验证；不计入成果或失败。新session93988已正常40/40退出0，无本任务运行作业。
- 初始deferred-age跳事件偏差修正和无效长换种测试改为压力200拍，FAILED_PREFLIGHT保留；默认1亿拍不改。旧v4第一次默认临时目录权限失败，指定本人test_tmp后10通过，未改旧源。补充3检查源码check_extra.py及独立重放EXTRA_REPRO，不把重放再计数。
- 原生LFSR/Bivium100MHz PPA只按active/idle条件插值，任务38322118/中央记录PR111；无CTS/SPEF/SDF与库告警保留。FFN共享比较/分层、Attention LUT/阈值保持、全局seed材料/仲裁/长线等未知；全随机和整机PPA null。普通算子512/64/16吞吐和编码/恢复仍假设，外存本次Link非DRAMSys。
- 执行冻结源不修改。重跑unittest/check_extra可直接；新整机执行先提交依赖并用新输出目录。run_targeted.py和audit.py包含本次封存路径，重放须在新目录/副本明确改OUT后冻结源码，不覆盖原件。
- 发布工具integrated/publish_exact.py保持双亲merge原SHA，限定本人路径，force=False，上传前重新核实jieruiz/workspace和原branchhead。原publish.py为旧线性helper，不支持本轮merge。外部发布原件放root/project_archives/rng_integration_issue96_20261022/。不要上传凭据/工艺本体，不改他人STATUS。
- 无新GPU/Slurm/模型PPL/RTL/DC/PT/STA/实际DRAMSys，未改变任何其他远端任务或定时。Projects沿read:project不足，最终Issue/STATUS仍需如实同步。旧架构检查台冻结52项，不假装跟本版自动刷新。

下一步：将本地成果提交同PR103，远端逐blob读取核对；更新Issue96/本人STATUS/长期备忘录并保留最小待审工作目录。review前不自动关闭Issue或合并PR。以下为历史交接，旧未接入结论只适用于旧源。

# Issue96: complete implementation and52 verified TLM scenarios

## 2026-10-22 随机源接口可用性补充

用户问新版随机架构TLM接口能否接合。继续本Issue/分支，不改Issue95后端或其负责人文件。原PR99在核实时以a7a4829合并0575a633（2026-10-22T09:38:49Z），不含本次后续36d5e108/ac971e1；因此新开补充PR103，待审未合并，不将它写成随99合并。实核最新集成5dbd9e39，random_service树及parallel_sampler_v5与本地对象相同。新前端和11项检查在architecture_tlm/unified_v6/rng_frontend.py、test_rng_interface.py，完整中文结论RNG_COMPATIBILITY_ZH.md。执行36d5e1085e82a982c9e689a467b3b2042ca36f4d：11新＋21整机＋19本目录随机源检查通过，共51，三seed两采样器连通，26个Bivium一帧供512路。来源RNG_INTERFACE_SOURCE.json，结果RNG_INTERFACE_VALIDATION.json及三个RNG_*.log。

这只是薄前端/接口连通，不是FullDecode已启用有限速率源。正式拼合要做：跨查询保留源时钟/epoch，FFN供给消费重叠及SAVE/RESTORE/RELEASE，PV实际打包周期，筛选宽度/端点实例分配，替代旧源成本别双计；q/256 sigmoid不能继承理想源PPL。默认和52冻结结果保持。无新GPU/Slurm/PPL/PT/DRAMSys。最终上传看Issue96及RNG_INTERFACE_PUBLICATION本地归档回执；PR103待审未合并，99已合并。RNG_PR_BODY为新PR说明，旧PR_BODY保留99历史版本。

可重现命令：python -m unittest architecture_tlm.unified_v6.test_rng_interface -v。完整核验运行器work/jieruiz/96/check_rng_interface.py要求执行源已提交且结果文件不存在；重放时选择新OUT目录或仅跑unittest，不覆盖原验证JSON。其时间是16候选小模块配置周期，不是全模型/物理周期认证。

以下保留原52情景的完整交接：

Owner jieruiz; branch task/96-unified-tlm; base83e15289434af50fc09c35e699d8b39965389d98; immutable execution fba22b192ab914046e50cc405f6dd473bf30d154. Checkout C:/Users/86134/Documents/a_P_BIT/tmp/unified-tlm-issue96-20261022. Target only rayggxia-workspace/pbit-llm-qwen-baselines. All implementation,52 results and report published at9621e1db35491e530d35b86e0ef884572b1df0a6; PR99 ready/open, not merged. Five critical remote blobs byte-verified. PUBLICATION/REMOTE_VERIFY record that snapshot; later receipt-only commits do not change execution or results. Issue96 implementation checklist updated; review/acceptance and Projects permissions remain pending.

## Completed

- architecture_tlm/unified_v6/{core,model,config,run}.py plus per-model config/optional entry, Chinese design and RESULTS_ZH.md. Existing defaults untouched.
- Current fixedW8/B4/T32/K32, gu shared input/replay, separate FP32 z, exact bitplanes/scale restoration, BF16 residual; full decoder and lm_head. Same-resource digital/W8 controls; online/GQA, systematic PV, max4 screen, explicit winner/rejection FSM.
- Local random-service contract only, no random-stream SRAM/FIFO or extra probability copies. Backend Issue95 remains separate;97 merged27bf9c48 during execution; 49 default-path overlay checks pass without backend switch.
- Qwen2K/8K each8methods×3seed=48 archived cases in results/qwen_20261022_v2. Llama1/2 each BF16/exact andSC/PV full32 layers single seed=4, model folders separate. All52 finished.21+18+10 mechanism/regression,62 artifact SHA,22 execution Git blobs,764 model contracts verified. No GPU/PPL/Slurm/PT/new actualDRAMSys.
- Old4e0d26b failed W8 metadata preflight retained; fixedfba22b1 regression. Old partial BF16 files excluded. Compatibility V1 temp and V2 helper import errors retained; V3 all49 passed.

## Reproduce and inspect

Use Python3.10+ (executions3.12.14). Repository root:
python -m unittest architecture_tlm.unified_v6.test_model -v
python architecture_tlm/checks/test_parallel_sampler_v5.py
python architecture_tlm/checks/test_screen_ising_v4.py
python work/jieruiz/96/collect.py --verify
python work/jieruiz/96/run_compatibility.py

Full commands and exact source/config bytes in each EXECUTION.json/ARTIFACT_MANIFEST. Check out executionfba22b1 to reproduce the archived numerical scenarios; run.py refuses a dirty execution dependency and existing output directories. Current docs/receipts need not share that old source commit. Main command:

```sh
python -m architecture_tlm.unified_v6.run --suite --models qwen --contexts 2048 8192 --seeds 0 1 2 --include-winner --output NEW_ABSOLUTE_DIRECTORY
```

52 raw files are small, no weights/data/PDK.

## Evidence limits and next steps

Timing is bounded macro/tile scheduling, default DRAMLink; no prefill/TTFT. Full physical energy/area/PPL null; priced subtotal coverage differs and must not be compared as total. SC restoration/weight feed and source/sampler costs need characterization. Current FFN barriers and sampler/serial histogram are feasible conservative mappings, not optimum. W8 mixed-MAC rate is configured, not calibrated GPU performance. source/register/clock and SRAM wrapper/CDC still open. Prefer correcting a mechanism that can change ranking, not blanket cycle simulation.

Formal report gives summarized time, K/V physical reads, SRAM footprint and bottlenecks. Next review PR99, then fill module latency/II/energy with evidence; use SOURCE_INDEX and original manifests, do not repeat completed PPL/expensive experiments. New timed source requires explicit adapter/precision validation. No current remote jobs; no automation changed. Projects GraphQL INSUFFICIENT_SCOPES(read:project) recorded in PROJECTS_CHECK.json; update later with permission. Do not close Issue96 until PR acceptance; do not merge without appropriate authorization. Keep only this minimal pending-PR checkout; no full duplicate worktrees were created.
