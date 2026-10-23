#!/bin/bash
#SBATCH --job-name=qwen3-bf16-wt2
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=04:00:00
#SBATCH --array=0-1%2
set -euo pipefail
ROOT="$1"
SRC="$2"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export TMPDIR="$ROOT/tmp"
"$ROOT/venv/bin/python" "$SRC/evaluate.py" --project "$ROOT" --index "$SLURM_ARRAY_TASK_ID"
