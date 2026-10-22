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
