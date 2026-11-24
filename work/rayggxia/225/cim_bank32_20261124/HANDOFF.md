# Issue225 CIM bank32 TLM handoff

Owner: rayggxia. Date: 2026-11-24, Asia/Shanghai. Branch `task/225-cim-bank32-20261124`, base main `206bf81f18ea88c4c625ce8d32edd18a58edd1cd`. This is the TLM follow-up to Issue204/PR265 documentation, not a change to matrix RTL or model-quality Issue263.

User selected16 banks/core,32 words x128bits/bank, one8KiB weight zone/core. New28nm/250MHz candidate defaults to5 cores. One core cannot compute while its weight zone is loading. Old32-slot capacity/free global dispatch are removed from this profile. Ordinary576KiB SRAM and finite16KiB DMA register holding remain; no full-tile ordinary SRAM staging or additional8KiB register copy.

Formal code and report: `architecture_tlm/process_28nm/cim_bank32_20261124/`; selection pointer `architecture_tlm/process_28nm/CURRENT_CIM.json`. `run.py` calls the existing PR249 whole-model host and installs a finite bank/actor overlay. Parent whole_model.py matches public eaf1ddcc56742c4c9f51899ecefb120574aeb5eb blob58bc7775d986e5f19928917814ee88aa254a0af9 after explicit LF text comparison; actual executed source byte SHA remains in SOURCE_INDEX.json. No parent source or frozen execution was edited.

Local inputs:

- process root: `C:/Users/86134/Documents/a_P_BIT/architecture_tlm/process_28nm`
- snapshot: `C:/Users/86134/Documents/a_P_BIT/tmp/cross-model245-20261106/work/rayggxia/245/mainline_20261108/revision2/snapshot`
- runtime: `C:/Users/86134/Documents/a_P_BIT/project_archives/ffn_sram_batch204_20261106/runtime`
- dependencies: `C:/Users/86134/Documents/a_P_BIT/project_archives/sram1216_225_20261106/dependencies`

Command: `python -B -X utf8 run.py --process-root <above> --snapshot <above> --runtime <above> --dependencies <above> --cores 5 --scope layer --backend analytic --out <new directory>`. Swap cores4/6 and scopeffn for the sweep. `--legacy-control --cores 3` is the old architecture at the same backend. `--scope full --backend native` runs the complete graph when native Linux runtime is available.

Completed: three contract tests; actual parent BeatSRAM timing test512words/16banks/32grants/128ns;4/5/6-core full single-layer FFN transaction sweeps; old3-core and new5-core entire first decoder-layer comparisons. Every case SEAL SHA, frame/MAC counts, pending/ingress drainage verified. First-layer budgets closed with explicit custom-CIM proxy. No GPU, PPL, RTL/STA/PT or full36-layer/native run.

FFN totals4/5/6:620.860/566.452/554.264us. First layer old/new1.094636/1.106372ms; area6.480303/6.776269mm2; on-chip0.344964/0.342181mJ. New effective SRAM616KiB versus832. 5-corev1 and4/6v2 actor/config SHA identical;v2 adds logging/provenance/report fields, preserved as separate identities.

Recovery archive: `C:/Users/86134/Documents/a_P_BIT/project_archives/cim_bank32_225_20261124/RAW_AND_EXECUTED_SOURCE.zip`,96928bytes,SHA256 `3d9880aa197ea40f85f46cfdb3b83411abb91e784a3c6ba687f40edf48ba8a4e`. It contains the five sealed rawcases and executed/delivered source. Member SHA index is formal SOURCE_INDEX.json. Do not rewrite archived rawcase bytes. Runtime/fixtures were not duplicated.

Limits:512B custom-bank PPA remains explicit capacity-equivalentS0 area/idle plus ordinary access-price proxy. SRAM port/geometry is executed, but custom taps/wire drivers are not newly characterized. First-layer timing is not complete TPOT. Existing full51.132604ms results remain historical. Extra cores increase logic area despite less SRAM. No remote job was submitted: localSSH helper's cryptography DLL fails in currentPython; task-only dependency installation also failed through invalid proxy. No credential was printed or committed.

Next executable actions: use existing EDA connection with a workingSSH environment, stage this small overlay beside the immutable PR249 host, run native first-layer4/5/6 comparisons through Slurm; only then run complete36-layer/native cases as needed. Do not resubmit healthy GPU/model tasks or change rawPPA. Review/merge only this task's PR; keep Issue225 open for its other work. Projects board sync requires a verified write route.

Publication state: local code and validation complete; branch/PR publication receipt will be appended after remote verification.
