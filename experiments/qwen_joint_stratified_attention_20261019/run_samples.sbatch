#!/bin/bash
#SBATCH --job-name=qwen-ising-S50
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=06:00:00
set -euo pipefail
: "${PBIT_PROJECT_ROOT:?personal project}"
: "${PBIT_SNAPSHOT:?immutable source}"
: "${PBIT_CODE_COMMIT:?execution SHA}"
: "${PBIT_PRIOR_OUTPUT:?d61 preparation}"
export HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
PY=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
SRUN=/opt/slurm/21.08.8/bin/srun
cd "$PBIT_SNAPSHOT"
ARGS=(--model "$PBIT_PROJECT_ROOT/models/Qwen2.5-0.5B" --data "$PBIT_PROJECT_ROOT/data/wikitext-2"
 --calibration "$PBIT_PROJECT_ROOT/assets/moment.pt" --project-root "$PBIT_PROJECT_ROOT"
 --output "$PBIT_PROJECT_ROOT/outputs/$PBIT_CODE_COMMIT" --code-commit "$PBIT_CODE_COMMIT"
 --prior-output "$PBIT_PRIOR_OUTPUT")
if [[ "${PBIT_ACTION:-prepare}" == prepare ]]; then
 exec "$SRUN" "$PY" -B -u run_samples.py prepare "${ARGS[@]}"
else
 ARGS+=(--phase "${PBIT_PHASE:-suffix}" --index "$SLURM_ARRAY_TASK_ID")
 if [[ "${PBIT_PHASE:-suffix}" == full ]]; then ARGS+=(--full-gate-output "$PBIT_FULL_GATE_OUTPUT"); fi
 exec "$SRUN" "$PY" -B -u run_samples.py worker "${ARGS[@]}"
fi
