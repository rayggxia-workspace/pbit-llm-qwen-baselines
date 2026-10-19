#!/bin/bash
#SBATCH --job-name=qwen-joint50-full
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=06:00:00
set -euo pipefail
: "${PBIT_PROJECT_ROOT:?verified personal project}"
: "${PBIT_SNAPSHOT:?immutable full source}"
: "${PBIT_CODE_COMMIT:?full execution commit}"
: "${PBIT_PRIOR_OUTPUT:?immutable d61 preparation output}"
export HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
PY=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
SRUN=/opt/slurm/21.08.8/bin/srun
cd "$PBIT_SNAPSHOT"
ARGS=(--model "$PBIT_PROJECT_ROOT/models/Qwen2.5-0.5B" --data "$PBIT_PROJECT_ROOT/data/wikitext-2"
 --calibration "$PBIT_PROJECT_ROOT/assets/moment.pt" --project-root "$PBIT_PROJECT_ROOT"
 --output "$PBIT_PROJECT_ROOT/outputs/$PBIT_CODE_COMMIT" --code-commit "$PBIT_CODE_COMMIT"
 --prior-output "$PBIT_PRIOR_OUTPUT")
if [[ "${PBIT_ACTION:-prepare}" == prepare ]]; then
 exec "$SRUN" "$PY" -B -u run_full.py --action prepare "${ARGS[@]}"
else
 exec "$SRUN" "$PY" -B -u run_full.py --action worker "${ARGS[@]}" --index "$SLURM_ARRAY_TASK_ID"
fi
