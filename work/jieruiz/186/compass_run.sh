#!/bin/bash
#SBATCH --job-name=compass-qwen-186
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:30:00
#SBATCH --array=0-4%5
set -euo pipefail
ROOT=/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/compass_2e015fd2
RUN="$1"
cd "$RUN"
export PYTHONPATH="$ROOT/deps:$ROOT/upstream"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
cases=(a100_native small_native_hbm256 small_native_hbm186 small_fabric32 small_native_ddr)
"$PY" source/test_contract.py source/model_qwen3_4b.json "$ROOT/upstream" > "tests-${SLURM_ARRAY_TASK_ID}.out" 2>&1
"$PY" source/qwen_decode.py --upstream "$ROOT/upstream" --config source/model_qwen3_4b.json \
  --case "${cases[$SLURM_ARRAY_TASK_ID]}" --context 2048 --output "results/${cases[$SLURM_ARRAY_TASK_ID]}"
