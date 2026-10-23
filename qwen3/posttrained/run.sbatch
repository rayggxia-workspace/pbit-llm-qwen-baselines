#!/bin/bash
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=06:00:00
set -euo pipefail
ROOT="$1"
SRC="$2"
test "$ROOT" = /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-nonbase-20261023-issue158
export PBIT_PROJECT_ROOT="$ROOT" PYTHONPATH="$SRC" PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 TMPDIR="$ROOT/tmp"
export TRITON_CACHE_DIR="$ROOT/triton-cache-$SLURM_JOB_ID"
cd "$SRC"
/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python -u -m qwen3.posttrained.run --root "$ROOT" --stage pilot --index 0
