#!/bin/bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
TASK=/home/Hongjie_Zeng/projects/ffn-address-coverage-issue261-20261122
cd "$(dirname "$0")"
PY=/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python
"$PY" -B test_coverage.py
"$PY" -B coverage.py --capture "$TASK/result/capture.npz" \
  --capture-result "$TASK/result/RESULT.json" --out "$TASK/analysis"
