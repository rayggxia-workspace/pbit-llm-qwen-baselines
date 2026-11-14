#!/bin/bash
set -euo pipefail
phase="$1"
root="$2"
source_dir="$3"
python_bin=/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python
export PYTHONPATH="$source_dir" PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TMPDIR="$root/tmp"
export TRITON_CACHE_DIR="$root/triton-$SLURM_JOB_ID"
if [[ "$phase" == cpu ]]; then export CUDA_VISIBLE_DEVICES=""; fi
cd "$source_dir"
srun "$python_bin" -B -u -m experiments.attention_trained_gapfill_20261114.run \
  --root "$root" --phase "$phase" --index "${SLURM_ARRAY_TASK_ID:-0}"
