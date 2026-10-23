# Bounded probe of the published PR125 scheduler candidate

This local diagnostic loads `ActiveMemoryKernel` from the public commit
`d944081a22dc346a3a50d505633e5d15c857ba78`, path
`architecture_tlm/ffn_cycle_integration/active_memory.py`. The bytes were
read using `git show` against that exact commit object in the local `fi23`
repository, never from its working file. Candidate Git blob:
`17d400e9e58fa271127eb0fdb1a3ef93ac6f9087`; SHA-256:
`7e4c9534e40b493956a2ae94b6b6b1cd97e4a0d6052e6aff75637828941d4296`.

The GQA/runtime baseline is the SHA-verified 74-file snapshot used by job
2782, core commit `f94c9db566b45a1c2f8db0fa8749366dde7f7450`. The caller-owned
kernel is injected through `build_gqa`; no production kernel/GQA source is
modified. Each child process has a hard 60-second timeout. The source copy
and `RESULT.json` are diagnostic evidence, not adoption of PR125.

Inputs are deterministic synthetic sine-valued FP32 vectors: seven queries,
one shared KV head, D/Dv64, all context positions as candidates, exact mode,
default group resources and memory window 4. The configured samples field is
32; exact mode draws no samples.

| Context | Kernel event host run (s) | Candidate event host run (s) | Operations | Configured finish (ns) |
|---|---:|---:|---:|---:|
| 64 | 3.2831 | 0.9949 | 2116 | 41940 |
| 128 | 12.5284 | 3.6679 | 4164 | 82810 |
| 256 | 48.2095 | 14.6916 | 8260 | 164790 |

Before these probes, context8 compared original/candidate × cycle/event
in memory: full equivalence payload, actual read bytes and complete group
state were equal in all four executions. Context64 and128 original/candidate
event executions then matched full payload/state/output hashes, operation
counts and simulated finish times. Every run returned all finite credits.
The result preserves per-case build/run wall time and visited edges.

The separately authorized256-token extension in `RESULT256.json` also
finished within each60-second limit, with matching full payload/state/output
hashes at the same shape. No timed-out run is omitted. The extension helper
is `work/amlink1219/116/probe_active_gqa_256.py`; it verifies the same frozen
source snapshot and candidate before launching either child process.

The candidate improves host execution by approximately 3.4× at128 here;
doubling context64→128 still increases its wall time approximately3.69×.
The128→256 candidate growth is4.006×, consistent with quadratic software
cost over this measured interval. A quadratic extrapolation from256 gives roughly15.7 minutes for2048 on
this local runtime. Applying the observed original-Kernel64 ratio between
the earlier server run (5.096 seconds) and this local run (3.283 seconds)
gives roughly24.3 minutes. This cross-environment estimate is uncertain,
not a completed2048 run or a promise that a20-minute allocation suffices.
No new server job, GPU capture, private input, numerical quality claim or
hardware PPA inference is part of this diagnostic.

Reproduce from repository root with fresh output/extraction directories:

```text
python -P -X utf8 work/amlink1219/116/probe_active_gqa.py --snapshot ../gqa-active-snapshot-new --published-repository ../fi23 --output work/amlink1219/116/active_gqa_probe_new
```

The `--published-repository` must contain the pinned public Git object. The
script verifies every baseline snapshot member and records the candidate
object ID and raw SHA before running any probe.
