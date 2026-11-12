# Fig5 fixed-weight evaluation handoff

Owner rayggxia; Issue198. Branch task/198-fig5-fixed-eval-20261112; base task/198-attention-followup-20261110 (PR253), pinned df266e93ef531309dacd908e2ed671bff0e56bdb. Dedicated minimal worktree: tmp/attention-fig5-eval-198-20261112. No changes to old job snapshots, PR199 hardware or other working trees.

User explicitly chose fixed existing K_WH64 weights and evaluation only. Public, self-contained delivery is qwen3/evaluation/fig5_fixed_weight_20261112/README_ZH.md: K128/K256/all × S32/64/128/256 × seeds0/1/2, plus five matched controls. Exact FFN; FP32 max-first U8/F4 floor-P8; GF64 candidates/Bivium ranks; full cached WT2 292 windows / 299077 targets. No retraining, GPU submission or new PPA.

Portable source includes fixed HF artifact access/hash checks, full scoring and coverage audit, actual routing, GF mapping, wide fair-rank port, CPU/GPU gates, resume and verified NLL aggregation. CPU source parsing, isolated package, 1024 GF map rows, scalar8/11-bit compatibility, window/target coverage and result aggregation checks passed (VALIDATION.json). GPU port/gate and all41 new full PPL runs remain pending at remote evaluator. Historical GPU checks do not certify this modified port.

Publication state: prepared for authorized GitHub task-branch delivery; exact pushed commit/PR and remote byte verification are recorded in the local PUBLICATION.json receipt after upload. PR remains pending review; no merge or remote experiment completion claimed. Projects cannot be updated through available connector; maintainers may sync the linked Issue. Historical progress/STATUS is outside this publication; only this task handoff and Issue comments report its public status, with the local personal STATUS updated separately.

Next operator: read all linked protocol/algorithm/return docs, freeze source, prepare assets, run CPU then GPU gate, unchanged BF16 full reference, controls, then36 stochastic cases. Return full per-window NLL/coverage/hash records and SUMMARY. Do not reuse historical signed12-first or different-weight curves as new data.
