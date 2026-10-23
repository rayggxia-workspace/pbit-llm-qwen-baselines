#!/bin/bash
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=06:00:00
set -euo pipefail
ROOT="$1"
SRC="$2"
test "$ROOT" = /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-nonbase-20261023-issue158
export HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export HF_HUB_DOWNLOAD_TIMEOUT=120 HF_HUB_ETAG_TIMEOUT=60
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE
export PYTHONPATH="$SRC" PYTHONDONTWRITEBYTECODE=1 PBIT_PROJECT_ROOT="$ROOT"
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false TMPDIR="$ROOT/tmp"
mkdir -p "$ROOT/tmp" "$ROOT/prepared" "$ROOT/results"
test ! -e "$ROOT/preflight.json"
PY=/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python
cd "$SRC"
"$PY" -u "$SRC/qwen3/posttrained/baseline/test_baseline.py" --project "$ROOT"
"$PY" -u "$SRC/qwen3/posttrained/baseline/prepare.py" --project "$ROOT" --index 0
"$PY" -c 'import sys; from qwen3.baselines.support import save; save(sys.argv[1], {"passed":True,"tests":"coverage and native Qwen3 reload","transformers":"4.51.3"})' "$ROOT/prepared/cpu_tests_passed.json"
"$PY" -u -m qwen3.posttrained.run --root "$ROOT" --stage cpu
