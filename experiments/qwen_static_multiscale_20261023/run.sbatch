#!/bin/bash
#SBATCH --job-name=qwen-fixedscale150
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=03:00:00
set -euo pipefail
: "${PBIT_PROJECT_ROOT:?personal project}"
: "${PBIT_SNAPSHOT:?immutable source}"
: "${PBIT_CODE_COMMIT:?execution commit}"
export HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$PBIT_SNAPSHOT"
ARGS=(--model /home/Hongjie_Zeng/pbit_llm/models/Qwen2.5-0.5B
 --data /home/Hongjie_Zeng/pbit_llm/data/wikitext-2
 --project-root "$PBIT_PROJECT_ROOT" --output "$PBIT_PROJECT_ROOT/outputs/$PBIT_CODE_COMMIT"
 --code-commit "$PBIT_CODE_COMMIT")
exec /opt/slurm/21.08.8/bin/srun /home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python -B -u \
 experiments/qwen_static_multiscale_20261023/run_static.py "${PBIT_ACTION:?action}" \
 "${ARGS[@]}" --index "${SLURM_ARRAY_TASK_ID:-0}"
