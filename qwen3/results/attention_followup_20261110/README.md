# Matched Attention evaluation follow-up (2026-11-10)

Refs #198; depends on the accepted evaluation evidence in PR252. This package records an authorized, submitted evaluation plan and its numerical sampler patch. Full results are pending; this is not a quality acceptance report.

All variants retain exact original BF16 FFN and use the same K_WH64 QKVO overlay. Full WikiText-2 scoring covers299077 targets in every one of36 layers, with native exact unscored prefill. Window/stride are2048/1024 (292windows) or8192/1024 (286windows). No training, final benchmark inference or hardware/TLM default changes.

| Group | New configurations | Deployment seeds |
|---|---|---|
| Priority2K | Four-head coarse-logit sum, K128/S64 winner hold |1,2; completed seed0 reused |
| Digital2K | FP32 Softmax/CDF, fixed64 IID categorical draws, K128 |0,1,2 |
| Digital2K | FP32 Softmax/CDF, fixed64 systematic draws, K128 |0,1,2 |
| Long context8K | K128/K256, each exact weighted PV and winner hold S64 |0 each |
| References | Unchanged BF162K and8K |0 each |

Fourteen complete evaluations are expected including two references. CPU5237 passed17 tests. GPU gates5238/5242 passed native-wrapper bitwise comparison, winner replay, CPU/GPU CDF address checks, model probes and production memory checks. References5239/5243 were running at the recorded observation. Priority array5240 releases digital array5241 only after success;8K array5244 follows its own reference. Arrays have no artificial concurrency cap; Slurm enforces one GPU per task and24/48GiB host memory for2K/8K.

Digital IID consumes64 uniform draws per query/head; systematic uses one random offset and64 evenly spaced CDF points. Both return exactly64 addresses, allow repeated V, and use the same FP32 gather/sum/divide64 readout as the winner-hold path. Zero-width CDF bins and float32 rounding of the final point to1 are covered. This is an algorithmic FP32 categorical reference, not a P8/R8 digital circuit replay. Comparisons with S12/P8 Ising include numerical quantization and finite-chain effects.

Ising retains signed12/F4 score quantization, integer max-gap, saturated U8/F4 LUT address and frozen floor-P8 threshold; initial winner0, burn0, spacing1 and all-zero hold. SparQ r32/recent32 uses four-head shared candidates and no mean-V compensation. Direct logit sum changes aggregation only, retaining the four coarse dot products.

Model: Qwen/Qwen3-4B post-trained revision1cfa9a7208912126459214e8b04321603b3df60c; overlay HF revision d5e64227171c59ead00c00e610b53f424fbcbba2 and SHA25689619fc18a1ea2a885f8495ea1ebddb4d187b3d8ae1096292dc8d046173cdfa9. Raw test text SHA256173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08; token IDs SHA2568d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e. Raw teacher-forced scoring uses no chat template.

`PLAN.json` records cases, jobs, source identity and gate observation. `SOURCE_INDEX.json` binds every frozen dependency and the two public numerical patch files. Files under `source/` are evidence copies of the original package experiments/attention_followup_20261110; imports require the indexed parent execution snapshot. This small package does not itself reproduce full GPU inference. Archived runtime/model/corpus and the frozen runner remain in authorized private storage; no credentials, operations scripts or large artifacts are published.

Run `python qwen3/results/attention_followup_20261110/verify_plan.py` for independent standard-library checks of the plan and public patch hashes. Complete results will require RESULT/complete, all part/provenance SHA, exact target coordinates and36-layer coverage, with NLL-to-PPL reconstruction. Empty queues or partial PPL do not establish completion.
