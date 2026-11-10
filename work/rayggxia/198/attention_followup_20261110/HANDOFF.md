# Attention follow-up evaluation handoff

Owner rayggxia; Issue198. Branch task/198-attention-followup-20261110, baseline42ae2fea657224896e3e7301a193b9c249dbe2b7, PR base task/198-eval-publication-20261109 (PR252 dependency). Scope is new Attention-only quality evaluations; hardware PR199 and other jobs remain untouched.

The public plan and numerical sampler patch are in qwen3/results/attention_followup_20261110. CPU17 checks and both GPU gates passed; two full unchanged references running at observation. Full14 results pending. Source identity d2502db7c13a5f00800fc5a2e0b4d9ad2ffdaa13bb5bef3b1657c9ca6dc1b7c1 is a manifest hash, not a Git commit. Model/corpus/runtime and full runner are private indexed dependencies. Local ops.py status inspects only this batch. Do not resubmit healthy work or infer completion from queue exit.

Next collect full results and verify source/provenance/complete/part checksums, scoring coordinates, all36-layer coverage and NLL-to-PPL. Combine logit seed1/2 only with the matching accepted seed0, keeping the2K/8K protocols distinct. No quality result, training, final benchmark run, new PPA or TLM change is claimed. PR submission/merge and Projects sync remain separate states.
