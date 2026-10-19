#!/usr/bin/env bash
#SBATCH --job-name=qwen-tasks59
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=12:00:00
set -euo pipefail
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export OMP_NUM_THREADS=4
PROJECT="${PBIT_PROJECT_ROOT:?}"
SNAPSHOT="${PBIT_SNAPSHOT:?}"
SHA="${PBIT_CODE_COMMIT:?}"
ACTION="${PBIT_ACTION:?}"
cd "$SNAPSHOT"
PY=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
if [[ "$ACTION" == data ]]; then
  export CUDA_VISIBLE_DEVICES=""
  "$PY" -B experiments/qwen_task_accuracy_20261019/test_plan.py
  "$PY" -B experiments/qwen_task_accuracy_20261019/test_cached_score.py
fi
exec "$PY" -B experiments/qwen_task_accuracy_20261019/run_tasks.py "$ACTION" \
  --model /home/Hongjie_Zeng/pbit_llm/models/Qwen2.5-0.5B \
  --data /home/Hongjie_Zeng/pbit_llm/data/wikitext-2 \
  --task-data /home/Hongjie_Zeng/pbit_llm/data/full_benchmarks \
  --calibration "$PROJECT/assets/moment.pt" \
  --project-root "$PROJECT" --output "$PROJECT/outputs/$SHA" \
  --code-commit "$SHA" --index "${SLURM_ARRAY_TASK_ID:-0}"
