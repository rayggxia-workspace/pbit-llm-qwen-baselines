# SparQ result verification

- Derive required benchmark cases from the frozen protocol, never from the result's own case list. Reject empty, duplicate, missing-mode, or insufficient-repeat matrices before declaring a measurement complete.
- Recompute throughput from verified batch size, actual token counts and measured elapsed time. Agreement between a trial field and its aggregate alone is not independent verification.
- Preserve the execution source and experiment identity for an active quality job. Measurement-only fixes belong to a separately identified supplement and must not overwrite the original result directory.
