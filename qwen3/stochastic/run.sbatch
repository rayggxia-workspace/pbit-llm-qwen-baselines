#!/bin/bash
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
set -euo pipefail
ROOT="$1"
SRC="$2"
STAGE="$3"
INDEX="${4:-0}"
export PBIT_PROJECT_ROOT="$ROOT"
export PYTHONPATH="$SRC"
export PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
export TRITON_CACHE_DIR="$ROOT/triton-cache-$SLURM_JOB_ID"
cd "$SRC"
/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python -u -m qwen3.stochastic.run --root "$ROOT" --stage "$STAGE" --index "$INDEX"
