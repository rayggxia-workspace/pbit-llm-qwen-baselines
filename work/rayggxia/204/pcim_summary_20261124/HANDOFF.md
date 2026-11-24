# Issue204 P-CIM summary, 2026-11-24

Owner: rayggxia. Documentation-only subtask; Issue204 remains open for its broader matrix work. Isolated sparse worktree: `tmp/pcim-summary-issue204-20261124`; branch `task/204-pcim-summary-20261124`; base main `206bf81f18ea88c4c625ce8d32edd18a58edd1cd`.

Deliverable: `docs/P_CIM_SUMMARY_ZH_20261124.md`. Same-byte local reading copy: `C:/Users/86134/Documents/a_P_BIT/P_CIM_SUMMARY_ZH_20261124.md`. This is the file requested for other conversations. Sources and checks: `SOURCES_AND_VALIDATION.json` in this directory.

The document explains fixed sign-magnitude W8, P8 endpoint/sign storage, sampling equations, direct three-stream SwiGLU-to-Wd, exact reduction and C19/C21 bounds, resident tiles versus ordinary SRAM, spatial and temporal parallelism, measured logic-only PPA, and current functional integration. It explicitly separates the model calibration path from dynamic g/u encoding in the latest RTL, and distinguishes the different 128-sample joint grids. No assumption that the latest functional RTL has new PPA or matches a model's PPL.

Validation: UTF-8/LF, root-mirror byte identity, 14 existing local source SHA-256 entries, accumulator bounds, Qwen tile arithmetic, primary PPA report values, and explicit grid differences. No new GPU, Slurm, RTL, synthesis, STA, PT or PPL experiment. Original source modules, frozen snapshots, TLM defaults and running jobs unchanged. No credentials, model data or foundry library bodies copied.

Publication must include only this document, this task's manifest/handoff, and the new entry in the owner's existing STATUS. Do not upload mixed root directories or source evidence archives. Some paths are local evidence pointers and are labeled accordingly. Published source libraries are not implied by a local path existing. Keep the document and local reading copy byte-identical after future revisions.

Next: use the summary as the handoff entry, then read the relevant dated source contract before changing an interface or reusing a PPA value. Formal model quality for the new 128-cell configuration belongs to Issue263/PR264. This document task does not take over or close that experiment or Issue204's other work. No automatic PR merge; Projects board sync remains pending without a verified write route.

## Publication

Core document/source-index publication:25b5dddef1495a7ed8949eb7eb2eb7ba342e0082. PR265 targets main,ready/open,not merged. All4 blob hashes verified; remote document raw bytes matched the local summary/root mirror. No data or source archives uploaded. The document SHA256 is e9d986eb832b03a5d79991f712d214aba9f68b57f08fe96acc151709fea65558. Publication receipt and memo navigation check remain local operational metadata.
