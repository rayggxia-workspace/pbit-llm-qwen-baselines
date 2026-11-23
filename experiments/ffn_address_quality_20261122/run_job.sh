#!/bin/bash
set -euo pipefail
PHASE=$1
SEED=$2
OUTPUT=$3
GATE=${4:-}
CASE=${5:-}
TASK=/home/Hongjie_Zeng/projects/ffn-address-quality-issue261-20261122
OLD=/home/Hongjie_Zeng/projects/ffn-stratified-validation-issue204-20261105
SOURCE=$(cd "$(dirname "$0")" && pwd)
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export TMPDIR=$TASK/tmp-$SLURM_JOB_ID
export TRITON_CACHE_DIR=$TASK/triton-$SLURM_JOB_ID
mkdir -p "$TMPDIR" "$TRITON_CACHE_DIR"
cd "$SOURCE"
ARGS=(--phase "$PHASE" --seed "$SEED" --output "$OUTPUT"
      --inputs "$OLD/full_wt2_e42ad6ba9210/source/INPUTS.json"
      --runtime "$OLD/runtime_original"
      --helpers "$OLD/real_activity_source_7c8ee7deb401"
      --plan "$SOURCE/PLAN.json")
if [ -n "$GATE" ]; then ARGS+=(--gate "$GATE"); fi
if [ -n "$CASE" ]; then ARGS+=(--case "$CASE"); fi
if [ "$PHASE" = gate ]; then
  /home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python -B "$SOURCE/test_math.py"
fi
/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python -B "$SOURCE/run_quality.py" "${ARGS[@]}"
