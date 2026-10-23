#!/bin/bash
#SBATCH --job-name=qwen-sampler141
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=12:00:00
set -euo pipefail
: "${PBIT_PROJECT_ROOT:?}"
: "${PBIT_SNAPSHOT:?}"
: "${PBIT_CODE_COMMIT:?}"
export HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
export TRITON_CACHE_DIR="$PBIT_PROJECT_ROOT/triton_cache/$SLURM_JOB_ID"
export TMPDIR="$PBIT_PROJECT_ROOT/tmp/$SLURM_JOB_ID"
mkdir -p "$TMPDIR"
cd "$PBIT_SNAPSHOT"
ARGS=("${PBIT_ACTION:-prepare}" --project-root "$PBIT_PROJECT_ROOT" --output "$PBIT_PROJECT_ROOT/outputs/$PBIT_CODE_COMMIT"
 --model /home/Hongjie_Zeng/pbit_llm/models/Qwen2.5-0.5B --data /home/Hongjie_Zeng/pbit_llm/data/wikitext-2
 --calibration /home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50/assets/moment.pt --code-commit "$PBIT_CODE_COMMIT")
if [[ "${PBIT_ACTION:-prepare}" == worker ]]; then
 ARGS+=(--phase "${PBIT_PHASE:-suffix}" --index "$SLURM_ARRAY_TASK_ID")
fi
exec /opt/slurm/21.08.8/bin/srun /home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python -B -u -m experiments.qwen_parallel_sampler_ppl_20261023.run "${ARGS[@]}"
