[Llama 2 7B：完整WT2基线与当前TLM结果入口](llama2_7b/RESULTS_INDEX_ZH.md)

[最新中文总索引：Attention、FFN、多层随机源、外存与结果](WORKSPACE_LATEST_ZH.md)

[LLaMA-1 7B 独立 TLM：当前采样、随机源、SRAM/DRAM及结果](llama7b/README_ZH.md)

# Qwen2.5 transaction model with DRAMSys external memory

## Screening + compact Ising sampler macro v4 (2026-10-16)

New opt-in path: max4 probabilistic screening, optional fixed block-budget
repair, compact QK, an abstract timed Ising module, and direct sparse V addition.
The sampler supplies indices directly: no second Softmax/CDF or PV sampler.
The macro includes internal randomness and feedback; no double RNG charging.
See [design, interfaces and limits](SCREEN_ISING_TLM_V4_ZH.txt).

`python architecture_tlm/run_screen_ising_v4.py` runs fixed 512-slot and variable
candidate scenarios. Default sample values are ideal IID oracle addresses;
all Ising PPA/timing parameters are illustrative, not measured performance.
Fixed-budget selection changes the previous algorithm and has no new PPL claim.


## Fixed-resource ZigZag/LOMA memory scheduling (2026-10-15, opt-in)

Real ZigZag 3.8.5 LOMA/MemoryAllocator candidates, a separate bounded-buffer
scheduler, fixed-resource digital/SC comparisons, and DRAMSys before/after runs.
Arithmetic, RNG service and replay counts are retained. See the
[integration guide](MAPPING_OPTIMIZATION_ZH.md) and
[results](results/mapping_20261015/RESULTS_ZH.md).

```sh
python architecture_tlm/run_mapping_optimization.py
python architecture_tlm/exhaust_mapping_candidates.py
python architecture_tlm/checks/test_mapping_decode.py
```

Only the search requires `zigzag-dse==3.8.5` (Python >=3.11). The adapter projects
LOMA mappings onto supported DMA blocking/pinning/prefetch schedules; it does
not claim unrestricted whole-LLM mapping optimality. Previous results are kept.

## Explicit Attention transactions v3 (2026-10-15, opt-in)

`run_attention_v3.py` connects dense, PV sampling, serial random-scan Ising,
max4 screening and screening + PV sampling to the full decode scheduler.
It includes addressed KV/summary accesses, scratch bandwidth reservations,
finite V caching, CDF/index sampling, seed hierarchy and explicit Ising updates.
See [Chinese scope and limitations](ATTENTION_TLM_V3_ZH.txt).

Verified synthetic scenarios: [results](results/attention_v3_verified_20261015/RESULTS_ZH.txt),
[audit](results/attention_v3_verified_20261015/verification.json). These are not
quality-validated Qwen workload or measured PPA numbers.

Default inputs are **synthetic logits**, not measured Qwen traces or new PPL.
Hardware macro coefficients remain uncharacterized. The serial Ising mapping
is not an estimate of a parallel physical p-bit array. The new Attention paths
do not retroactively change any saved v1/v2 results.

```sh
python architecture_tlm/checks/test_attention_v3.py
python architecture_tlm/run_attention_v3.py --output architecture_tlm/results/attention_new
python architecture_tlm/audit_attention_v3.py architecture_tlm/results/attention_new
```

`--trace` imports per-query logits captured with `capture_attention_trace_v3.py`;
`--bridge` uses the existing DRAMSys backend. No default GPU or remote job runs.

## Local A8 share64 input RNG v2 (2026-10-15, opt-in)

Separate scheduler with one local input PRNG, 64-lane same-word comparison,
checkpoint regeneration instead of raw-word SRAM replay, and unchanged local
weight Bivium algorithms. Includes root refresh, child rekey and checkpoint
restore costs. Retains one existing input threshold frontend, with no additional
probability bank. Existing v1/default behavior and saved results are preserved.

- [Design, seed semantics and usage](LOCAL_SHARED_V2_ZH.txt)
- [18-case results](results/local_shared_v2/RESULTS_ZH.md)
- [Audit](results/local_shared_v2/verification.json)
- [Scheduler](system_decode_local_shared_v2.py), [RNG model](rng_local_shared_v2.py)

Run `python architecture_tlm/run_local_shared_v2.py` from the workspace root.
New default comparisons use the simplified Link backend; optional `--bridge`
retains DRAMSys support. Input LFSR cost coefficients are uncharacterized.

The new primary experiment is the **closed-loop DRAMSys backend**: actual
nonblocking SystemC/TLM-2.0 DRAM requests return completion times to the Python
compute scheduler. External energy uses DRAMPower at the complete decode
horizon. On-chip compute, SRAM and RNG costs remain parameterized macro models.

- [DRAMSys results and Chinese summary](results/dramsys/RESULTS_ZH.md)
- [All comparison metrics](results/dramsys/summary.csv)
- [Real SystemC integration checks](results/dramsys/integration_smoke.json)
- [DMA trace and result audits](results/dramsys/verification.json)
- [C++ bridge](dramsys/bridge.cpp), [Python memory backend](dramsys_backend.py)

Build with `cmake -S architecture_tlm/dramsys -B build
-DCMAKE_BUILD_TYPE=Release` at repository root, then `cmake --build build -j 4`.
Run `python3 architecture_tlm/run_dramsys.py --bridge build/pbit_dram_bridge
--index 0` (indices 0..11). Linux C++17 and CMake>=3.25 are required. No GPU.
The bundled DDR4 example's IO voltage is zero; its interface energy is not
calibrated. These are simulation scenarios, not measured accelerator results.

## Retained simplified baseline

The default configuration retains the **global uniform random-word supply** model.
The published baseline RNG timing results apply to that mapping. An opt-in
hierarchical model now supplies local digital weight streams; it does not model
native physical probability-output p-bit arrays.

## Hierarchical RNG v1 (opt-in)

L2 block entropy budget -> root seed expansion/bus -> L1 shared input RNG and
L0 per-array Bivium banks. Startup and boundary reseeding, retry throughput,
update energy, leakage and area are explicit. Default new costs are illustrative,
not PDK measurements. Existing baseline configuration/results are retained.

```sh
python architecture_tlm/checks/test_rng_hierarchy.py
python architecture_tlm/run_rng_hierarchy.py
python architecture_tlm/check_rng_streams.py --samples 4096
python architecture_tlm/audit_rng_hierarchy.py
```

- [Chinese design and usage guide](RNG_HIERARCHY_V1_ZH.txt)
- [Macro model](rng_hierarchy.py), [bit-stream reference](rng_reference.py)
- [Replaceable parameters](configs/rng_hierarchy_v1.json)
- [Saved comparison](results/rng_hierarchy_v1/comparison.json)

`run_rng_hierarchy.py --small` runs a one-layer integration case; use `--output`
to keep it separate from the full comparison. Optional `--bridge` and
`--dramsys-config` reuse the existing DRAMSys backend. That path requires the
compiled external simulator and has not been exercised for this new mode here.

The retained simplified backend is a Python macro-level loosely timed model. The new external-memory backend uses real SystemC/TLM-2.0, while the compute scheduler remains Python. Both model batch-one decode through all 24 Qwen2.5-0.5B layers, dense accurate attention, FFN, residuals, normalization and the vocabulary output. Prefill and TTFT are not modeled.

Weights are exposed through a configurable storage macro: capacity, load bandwidth/latency, read/write energy, holding power and area. SRAM costs are scenario parameters. Stochastic fixed-weight core costs are derived from the supplied mapped-power evidence; dual-stream core power is an adjustable proxy.

## Run

Python 3.10 or newer; standard library only. No GPU, model weights, tokenized corpus or original local workspace is required.

```sh
cd architecture_tlm
python import_evidence.py
python checks/test_model.py
python checks/test_system_decode.py
python run_workbench.py
python run_system_sweep.py
python report_system.py
python audit_system_results.py
python checks/check_publication_metrics.py
```

The full sweep includes 96 scenarios. The single-core workbench remains available for storage/RNG checks.

## Configuration and results

- [Default system parameters](configs/system_decode_default.json)
- [Cost provenance and limitations](configs/cost_provenance.json)
- [Bundled Qwen configuration](configs/model_config.json)
- [Chinese implementation guide](SYSTEM_MODEL_ZH.txt)
- [Full Chinese bottleneck report](results/system_decode/完整decode宏模型与瓶颈分析.txt)
- [Scenario table](results/system_decode/summary.csv)
- [Sensitivity results](results/system_decode/sensitivity.json)
- [Consistency audit](results/system_decode/verification.json)

Scenario energies and areas are not measured chip values. The digital and stochastic resource configurations are not strictly area-matched. Numerical PPL references do not validate the hardware precision or random-stream correlations. In particular, do not transfer the global uniform-source bottleneck results to a native probability-output p-bit module without replacing its supply and cost contract.

Power CSVs and the RTL reference package are included in `evidence/`; their original bytes are preserved and checked by SHA256. No technology library, credentials, SSH configuration or model weights are included.

## Snapshot

The 96 simplified baseline scenarios are retained and verified unchanged. The DRAMSys scenarios are additional runs with a different external-memory backend; they do not claim unchanged timing or energy.
# SRAM organization exploration (2026-10-16)

See [Chinese SRAM modeling report](SRAM_FLEXIBLE_MODEL_ZH_20261016.txt).
Per-weight validity banks are excluded explicitly; full-tile initialization is required.
`cacti_memory.py` explores independent bank capacities/widths with official CACTI;
`results/cacti_memory_20261016` contains completed Slurm job 1581 outputs.
`run_screen_ising_v4.py --memory-cost-profile .../tlm_cost_b16.json` is an optional
**cost-only** sensitivity, not a foundry SS timing/area signoff or a Q-hold implementation.
