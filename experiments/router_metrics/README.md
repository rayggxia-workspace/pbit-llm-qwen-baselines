# Simple p-bit attention scores and budget control (2026-10-07)

This experiment compares simpler block scores and separates score quality,
random selection, and query-to-query budget drift. Original Qwen2.5-0.5B FFNs
and all backbone weights are frozen. Only unpadded single-query decode attention
in all 24 layers is patched; prefill is original SDPA. Blocks contain 64 tokens.

## Scores

| ID | CLI mode | Score | Dot-product MACs / block / query head |
|---|---|---|---:|
| A | mean_softmax | Mean-Key dot score, block softmax, inclusion probability | 64 |
| B | mean_sigmoid | Mean-Key dot score | 64 |
| C | max2 | Maximum of two 32-token mean-Key dot scores | 128 |
| D | max4 | Maximum of four 16-token mean-Key dot scores | 256 |
| E | bound | Per-coordinate min/max Key bound, selected by Query sign | 64 |
| F | mix | Nonnegative mixture of normalized mean and bound scores | 128 |

For E, select max Key when q>=0 and min Key otherwise, THEN multiply by q.
Thus only 64 products are required; comparisons and extra summary reads are not
counted as MACs. The score bounds the maximum token logit, not block probability.
For F, alpha is chosen from {0,.25,.5,.75,1} separately per layer/head using
validation coverage; runtime conservatively executes both dots, even at endpoints.

Key summaries are cached after RoPE and updated only for the newly appended Key.
Each method maintains only its necessary sums/extrema. Prefix initialization is
linear in prefix length. Summaries use FP32, K/V use BF16, score computations FP32.

## Four selection rules

- `stochastic`: query-max-referenced sigmoid with fixed head temperature and bias.
  A instead uses block softmax followed by `1-(1-p)^M`, with M calibrated as a
  positive real-valued budget parameter. First and last two blocks are mandatory.
- `deterministic`: top ceil(budget*blocks), including mandatory blocks. A is omitted
  because its ranking of the nonmandatory full blocks equals B. Top-k cost is real.
- `adaptive`: diagnostic p-bit control. Sixteen bisection iterations per query/head
  adjust bias to match EXPECTED selected-token fraction, including partial and
  mandatory blocks. Actual sampled count remains random. Tested for B,C,D,F.
  No test labels are used, but the extra root-solving cost must be counted.
- `moment`: cheap dynamic threshold for C,D. Compute mean and standard deviation
  of current nonmandatory-block scores, normalize `(s-mean)/std`, then apply a
  fixed calibrated bias/temperature and one Bernoulli draw. No root solve or MLP.
  Like static calibration, it does not guarantee exact test retention.

Initial calibration sets each head's expected validation retention to 15% or 30%,
choosing temperature by validation teacher-mass coverage. Tests demonstrated large
static-threshold drift, motivating the subsequent adaptive and moment stages.
These stages are exploratory follow-ups; all calibration still uses train-tail
text only. Report actual retention, not just the nominal budget.

## Training, numerical checks, and evaluation

Teacher extraction uses 32 spread-out disjoint 8k WT2 train windows, reserving the
last 65,536 train tokens as eight held-out windows. Eight query positions per window
are collected. All teacher block masses and weighted Value contributions are
computed offline. Two-context calibrations use the eight held-out queries at each
context; this is a small validation set and is an explicit limitation.

`distill.py` additionally performs four 1,500-step local output-distillation trials
(2k/8k x budgets15%/30%). Only mixture, bias and temperature are trained. It uses
hard Bernoulli masks with straight-through gradients and output NMSE plus a budget
penalty, on 32 frozen teacher queries/head/context. All four validation best steps
were step0. Consequently no newly trained checkpoint was promoted to the PPL
screen. This failed training attempt is retained in `distillation.json`; it is
not evidence against all possible output-distillation architectures/training.

There are 166 full-model test evaluations: 94 initial, 48 adaptive-budget and 24
moment-threshold. Stochastic runs use three seeds; deterministic runs one. At 2k,
32 windows x128 scored tokens (batch16); at 8k,16x128 (batch4), with matched evenly
spaced starts. These are sampled cached teacher-forced suffix PPLs, not full WT2.
Kernel checks cover partial-block incremental caches, validity of the min/max
bound and sparse output agreement with dense masked attention.

The Triton decode kernel loads and computes only selected K/V tiles. Full KV
storage remains allocated. Reported MACs omit summary maintenance, normalization,
comparisons, root finding, random generation, top-k, memory and launches. Separate
serial warmed-up GPU timings include selection and sparse execution; they are
single-layer kernel-path measurements, not full-model decoding throughput.

## Reproduction

Remote root: `/home/Hongjie_Zeng/pbit_router_metrics_20261007`.
Python: `/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python`.
Torch2.7.1+cu128, Transformers4.45.2, Triton3.3.1, RTX5090.
Symlink existing original model/data under `models/` and `data/`.

```bash
python experiments/router_metrics/collect.py
python experiments/router_metrics/verify.py
python experiments/router_metrics/calibrate.py
python experiments/router_metrics/run.py --stage screen
python experiments/router_metrics/distill.py
python experiments/router_metrics/run.py --stage adaptive
python experiments/router_metrics/calibrate_moment.py
python experiments/router_metrics/run.py --stage moment
python experiments/router_metrics/benchmark.py
```

The benchmark uses real layer12 Q/K/V snapshots retained from the preceding direct
router experiment (`artifacts/snapshot_ctx2048.pt` and `snapshot_ctx8192.pt`).
It repeatedly resets only the last summary sum (one extra subtraction), not the
whole cache. The baseline is Qwen repeat_kv+SDPA, not the best possible native-GQA
kernel. Run benchmarks after accuracy jobs finish. Launchers resume existing runs
and use only GPUs with <500MiB allocation; `ROUTER_GPUS` optionally restricts them.

Results are stored locally under `results/router_metrics_20261007/`, including a
Chinese method-to-result report and full CSV/JSON. Small parameter snapshots are
backed up under `artifacts/router_metrics_20261007/` (Git-ignored). The 1.8GiB
offline teacher data stays remote. This experiment does not test learned low-rank
projections, GQA-shared gating, end-to-end backbone adaptation or physical p-bits.
