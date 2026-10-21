#!/bin/bash
#SBATCH --job-name=qwen-ising78
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
set -euo pipefail
: "${PBIT_PROJECT_ROOT:?}"
: "${PBIT_SNAPSHOT_ROOT:?}"
: "${PBIT_CODE_COMMIT:?}"
export HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
PY=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
cd "$PBIT_SNAPSHOT_ROOT"
EXP=experiments/qwen_ising_broadcast_20261021
if [[ "${PBIT_ACTION:-prepare}" == diagnose ]]; then
  "$PY" -B "$EXP/test_sampler.py"
  exec "$PY" -B -u "$EXP/diagnose.py" --reference --output "$PBIT_PROJECT_ROOT/outputs/$PBIT_CODE_COMMIT/synthetic.json"
elif [[ "${PBIT_ACTION:-prepare}" == worker ]]; then
  exec "$PY" -B -u "$EXP/run_model.py" worker --project "$PBIT_PROJECT_ROOT" --commit "$PBIT_CODE_COMMIT" --index "$SLURM_ARRAY_TASK_ID"
else
  exec "$PY" -B -u "$EXP/run_model.py" prepare --project "$PBIT_PROJECT_ROOT" --commit "$PBIT_CODE_COMMIT"
fi
