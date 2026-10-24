#!/bin/bash
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --gres=gpu:1
#SBATCH --array=0-2
#SBATCH --time=03:00:00
set -euo pipefail
ROOT="$1"
SRC="$2"
test "$ROOT" = /home/Hongjie_Zeng/projects/pbit-qwen3-and-short-20261024-issue173
export PYTHONPATH="$SRC" PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 TMPDIR="$ROOT/tmp"
export TRITON_CACHE_DIR="$ROOT/triton-$SLURM_JOB_ID"
cd "$SRC"
PY=/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python
"$PY" -m unittest qwen3.and_direct.test_short qwen3.and_direct.test_multiscale qwen3.and_direct.test_core qwen3.nonlinear_width.test_core qwen3.fixed_scale.test_runner -v
"$PY" -u -m qwen3.and_direct.short_run --root "$ROOT" --shard "$SLURM_ARRAY_TASK_ID"
