#!/bin/bash
#SBATCH --job-name=llama2-7b-bf16-ppl
#SBATCH --partition=gpu5090
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=40G
#SBATCH --time=06:00:00

# Run from the immutable committed source snapshot; create log parent first.
# sbatch --chdir="$SNAPSHOT" --output="$RUN/logs/ppl-%j.log" \
#   --export=ALL,SOURCE_COMMIT="$SHA",MODEL_PATH="$MODEL",DATA_PATH="$DATA",IDENTITY_MANIFEST="$IDENTITY",OUTPUT_ROOT="$NEW_OUTPUT" \
#   baselines/llama2_7b/evaluate.sbatch
set -euo pipefail
: "${SLURM_JOB_ID:?Must execute through Slurm}"
: "${SOURCE_COMMIT:?Set exact committed source SHA}"
: "${MODEL_PATH:?Set verified official Llama-2-7b-hf local snapshot}"
: "${DATA_PATH:?Set original full wiki.test.raw}"
: "${IDENTITY_MANIFEST:?Set pinned model identity JSON}"
: "${OUTPUT_ROOT:?Set NEW absolute output directory}"
PYTHON=${PYTHON:-/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python}
test -x "$PYTHON"
test -f "$MODEL_PATH/config.json"
test -f "$DATA_PATH"
test -f "$IDENTITY_MANIFEST"
test ! -e "$OUTPUT_ROOT"
[[ "$OUTPUT_ROOT" = /* ]] || { echo 'OUTPUT_ROOT must be absolute' >&2; exit 2; }
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 CUBLAS_WORKSPACE_CONFIG=:4096:8
exec /opt/slurm/21.08.8/bin/srun "$PYTHON" -u baselines/llama2_7b/evaluate.py \
  --model "$MODEL_PATH" --data "$DATA_PATH" --identity-manifest "$IDENTITY_MANIFEST" \
  --output "$OUTPUT_ROOT" --windows 2048 4096 --stride 512 --seed 0
