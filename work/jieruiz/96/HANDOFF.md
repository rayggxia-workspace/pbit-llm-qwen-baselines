# Issue96: complete implementation and52 verified TLM scenarios

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
