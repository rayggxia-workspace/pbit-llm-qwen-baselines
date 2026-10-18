#!/usr/bin/env bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:45:00
# No GPU is requested here. Add --gres=gpu:1 ONLY for baseline_capture.
set -euo pipefail
: "${E01_PYTHON:?Set verified personal Python absolute path}"
: "${E01_CONFIG:?Set reviewed run configuration absolute path}"
: "${E01_SOURCE_MANIFEST:?Set immutable snapshot source manifest absolute path}"
: "${E01_SOURCE_COMMIT:?Set exact source commit}"
: "${E01_SOURCE_ROOT:?Set immutable snapshot root}"
: "${E01_STAGE:?preflight, baseline_capture, micro_pilot or micro_full}"
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
if [[ "$E01_STAGE" != baseline_capture ]]; then
    export CUDA_VISIBLE_DEVICES=''
fi
cd -- "$E01_SOURCE_ROOT"
exec "$E01_PYTHON" -u experiments/attention_e01/run.py \
    --stage "$E01_STAGE" --config "$E01_CONFIG" \
    --source-manifest "$E01_SOURCE_MANIFEST" --source-commit "$E01_SOURCE_COMMIT"
