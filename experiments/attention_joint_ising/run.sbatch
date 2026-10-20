#!/usr/bin/env bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=04:00:00
# Add --gres=gpu:1 only for GPU stages. CPU preflight uses --time=00:15:00.
set -euo pipefail
: "${AJ48_PYTHON:?}"
: "${AJ48_CONFIG:?}"
: "${AJ48_SOURCE_MANIFEST:?}"
: "${AJ48_SOURCE_COMMIT:?}"
: "${AJ48_SOURCE_ROOT:?}"
: "${AJ48_STAGE:?}"
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1
if [[ "$AJ48_STAGE" == cpu_preflight ]]; then
    export CUDA_VISIBLE_DEVICES=''
fi
cd -- "$AJ48_SOURCE_ROOT"
exec "$AJ48_PYTHON" -B -X utf8 -u -m experiments.attention_joint_ising.job \
    --stage "$AJ48_STAGE" --config "$AJ48_CONFIG" \
    --source-manifest "$AJ48_SOURCE_MANIFEST" --source-commit "$AJ48_SOURCE_COMMIT"
