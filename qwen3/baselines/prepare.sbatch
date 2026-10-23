#!/bin/bash
#SBATCH --job-name=qwen3-cpu-prepare
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=06:00:00
set -euo pipefail
ROOT="$1"
SRC="$2"
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export HF_HUB_DOWNLOAD_TIMEOUT=120 HF_HUB_ETAG_TIMEOUT=60
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4
export TMPDIR="$ROOT/tmp"
mkdir -p "$TMPDIR" "$ROOT/prepared" "$ROOT/results"
BASE=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
if [ ! -x "$ROOT/venv/bin/python" ]; then
    "$BASE" -m venv --system-site-packages "$ROOT/venv"
fi
PY="$ROOT/venv/bin/python"
"$PY" -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple transformers==4.51.3 tokenizers==0.21.4
"$PY" "$SRC/test_baseline.py" --project "$ROOT"
"$PY" -c 'import sys; sys.path.insert(0,sys.argv[1]); from support import save; save(sys.argv[2], {"passed":True,"tests":"coverage and native tiny Qwen3 reload", "transformers":"4.51.3"})' "$SRC" "$ROOT/prepared/cpu_tests_passed.json"
"$PY" "$SRC/prepare.py" --project "$ROOT" --index 0
"$PY" "$SRC/prepare.py" --project "$ROOT" --index 1
"$PY" -m pip freeze
