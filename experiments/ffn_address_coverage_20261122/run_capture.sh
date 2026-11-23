#!/bin/bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export CUBLAS_WORKSPACE_CONFIG=:4096:8
TASK=/home/Hongjie_Zeng/projects/ffn-address-coverage-issue261-20261122
OLD=/home/Hongjie_Zeng/projects/ffn-stratified-validation-issue204-20261105
export TMPDIR=$TASK/tmp
export TRITON_CACHE_DIR=$TASK/triton-$SLURM_JOB_ID
cd "$TASK/source"
/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python -B capture_full.py \
  --helpers "$OLD/real_activity_source_7c8ee7deb401" \
  --inputs "$OLD/full_wt2_e42ad6ba9210/source/INPUTS.json" \
  --runtime "$OLD/runtime_original" \
  --legacy "$OLD/real_activity_result_7c8ee7deb401/capture.npz" \
  --output "$TASK/result"
