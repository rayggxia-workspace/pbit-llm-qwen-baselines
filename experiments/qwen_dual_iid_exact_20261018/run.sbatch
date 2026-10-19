#!/bin/bash
#SBATCH --job-name=qwen-dual-iid30
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
set -euo pipefail
: "${PBIT_PROJECT_ROOT:?absolute verified personal project directory required}"
: "${PBIT_SNAPSHOT:?absolute immutable snapshot experiment directory required}"
: "${PBIT_CODE_COMMIT:?exact committed code SHA required}"
export HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
PY=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
SRUN=/opt/slurm/21.08.8/bin/srun
cd "$PBIT_SNAPSHOT"
exec "$SRUN" "$PY" -B -u run.py all \
  --model "$PBIT_PROJECT_ROOT/models/Qwen2.5-0.5B" \
  --data "$PBIT_PROJECT_ROOT/data/wikitext-2" \
  --project-root "$PBIT_PROJECT_ROOT" \
  --output "$PBIT_PROJECT_ROOT/outputs/$PBIT_CODE_COMMIT" \
  --code-commit "$PBIT_CODE_COMMIT" --prefix-tokens 128
