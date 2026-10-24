# Trainable stochastic nonlinear FFN

Start with [the remote-agent handoff (Chinese)](AGENT_HANDOFF_ZH.md).

This is a trainable reference for posttrained **Qwen/Qwen3-4B**, extending
PR174's sampled three-stream AND -> fixed Wd forward. It trains only FFN
gate/up/down weights with an explicitly biased surrogate backward. The hard
nonlinear forward is sampled in both train and eval modes. Wg/Wu scale
restoration remains an explicitly retained FP32 reference boundary.

- `core.py`: patching, hard forward, surrogate backward, replayable noise keys.
- `train.py`: local-checkpoint CE training / calibration, single GPU or DDP.
- `calibrate.py`: two-pass TRAIN-only fixed tables, frozen before training.
- `checkpoint.py`: strict FFN-only warm start and hash-bound resumable state.
- `diagnostics.py`: optional separate clipping/saturation/event diagnostic pass.
- `config_w8_t128.json`, `config_w8_t64.json`: initial training configurations.
- `test_training.py`, `gpu_check.py`, `ddp_check.py`, `smoke.py`: correctness and
  synthetic optimization checks, not pretrained model quality benchmarks.
- `validation/`: archived actual validation outputs; see `VALIDATION_ZH.md`.

```bash
python -m unittest qwen3.training.stochastic_nonlinear.test_training -v
python -m qwen3.training.stochastic_nonlinear.train --help
```

Keep the `noise_context` active through backward. Disable TF32. Use non-reentrant
activation checkpointing. Do not cast installed FP32 master parameters to BF16.
Do not interpret compressed exact-law event counts as conditional means.

Yesterday's full training checkpoint is still pending. No full 4B fine-tuning
or new PPL is claimed by this package. Existing jobs are not modified.
