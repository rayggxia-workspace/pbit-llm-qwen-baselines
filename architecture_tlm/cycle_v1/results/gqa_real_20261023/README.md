# Real seven-query shared-KV validation

Slurm CPU-only job **2782** completed with `ExitCode=0:0` in **2m57s**,
using 2 CPUs, 8 GiB allocation and `CUDA_VISIBLE_DEVICES=''`. Five CLI
configurations and six independent audit configurations passed. Every
configuration was executed in both cycle and event modes with full state,
trace, timing, actions and memory-response equivalence checks.

The private input is Qwen2.5-0.5B layer 12, query heads 0-6, one shared KV
head 0, head width 64, context 64, last-token queries with all 64 causal keys.
Model/projections are BF16; exported Q/K use the explicitly declared CPU
FP32 RoPE boundary. This is a real small GQA group, not a complete attention
layer, full model, PPL, RTL or physical PPA result.

CLI runs use S32 and seed 0 (per-head configured seeds differ). The default
has K/V row slots 2/2, operand slots 2, memory window 4. The narrow exact
case changes these four capacities to 1. All seven output hashes are
unchanged between the two exact cases.

| Configuration | Configured latency (ns) | Operations | Unique K rows | Unique V rows |
|---|---:|---:|---:|---:|
| exact | 41940 | 2116 | 64 | 64 |
| PV, S32 | 52100 | 2354 | 64 | 49 |
| winner, S32 | 55160 | 3423 | 64 | 40 |
| rejection, S32 | 66470 | 4483 | 64 | 42 |
| exact, narrow capacities | 97000 | 2116 | 64 | 64 |

Each K row is physically read once per group (16,384 bytes total), then
shared across all requesting queries. V bytes follow the retained physical
union; repeated sample contributions preserve their per-query mathematical
weights. These timings are conditional on configured, uncharacterized
compute/cache/clock contracts and are not a ranking or hardware advantage
claim. The modes implement different numerical/sampling contracts.

The production oracle uses a high-precision weighted-V reduction with a
documented FP32 tolerance: the largest exact-case absolute discrepancy was
`1.1920928955078125e-7`. The separate independent audit uses an explicit
scalar oracle with the simulator's FP32 boundaries. Its six S16 cases are
exact default/tight, PV default/tight, winner default, rejection default;
the tight audit case also changes the memory bank count to 1. All **42
case/head outputs** were bit-equal with zero error. The independent trace
review covered **12,776 operations**, **70,185 events**, and **636 shared
input-row payload checks** across the retained six event traces. All finite
credits returned. Sampled-mode arithmetic is checked conditional on observed
native sample trajectories; this is not a distribution or IID proof.

Pinned execution source is `f94c9db566b45a1c2f8db0fa8749366dde7f7450`, with
four independent audit files from `9f1122e04f272f34d3ca48e3314677721b49f8d5`.
All 74 staged source/data files were SHA-256 verified inside the allocation.
The private fixture SHA-256 is
`ee5722b38a1acb94daf4d09e49651c9a4610dbc9a9b0ac444b29bb1ef2280080`.

`PUBLIC_MANIFEST.json` covers the 10 exported report/log files. The transport
archive hash and source package are preserved with the [job records](../../../../work/amlink1219/116/gqa_validation_v1/).
The [capture receipt](../../../../work/amlink1219/116/gqa_capture_v1/README.md)
binds the input to GPU job 2781 and model/tokenizer/text hashes.

Raw fixture, logits, output arrays, sampled indices, native transcripts and
full traces remain under the user's server directory:
`/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/gqa_validation_v1`.
The public reports record their artifact hashes; they contain no raw tensor
payload. Automatic approval rejected downloading the raw activation fixture,
so validation ran in place and only these allowlisted receipts were copied.

A 2048-context extension was not run. Separate 64/128-token event execution
probes showed substantial superlinear software cost, making a 20-minute
budget unreliable. No full-context or full-model result is inferred here.
