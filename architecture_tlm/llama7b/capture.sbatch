#!/bin/bash
#SBATCH --job-name=llama7b-qk-trace
#SBATCH --partition=gpu5090
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --time=00:30:00

# Submit from an immutable source snapshot. Caller supplies absolute paths:
# sbatch --chdir="$SNAPSHOT" --output="$RUN_ROOT/logs/trace-%j.log" \
#   --export=ALL,SOURCE_COMMIT="$SHA",OUTPUT_ROOT="$RUN_ROOT/traces" \
#   architecture_tlm/llama7b/capture.sbatch
# Root creates logs/ before sbatch. No GPU execution outside Slurm.
set -euo pipefail
: "${SLURM_JOB_ID:?Must execute in a Slurm allocation}"
: "${SOURCE_COMMIT:?Set the exact 40-character source commit}"
: "${OUTPUT_ROOT:?Set a NEW absolute output directory}"

PYTHON=${PYTHON:-/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python}
MODEL_PATH=${MODEL_PATH:-/home/Hongjie_Zeng/pbit_llm/models/LLaMA-7B}
DATA_PATH=${DATA_PATH:-/home/Hongjie_Zeng/pbit_llm/data/wikitext-2/wiki.test.raw}
test -x "$PYTHON"
test -f "$MODEL_PATH/config.json"
test -f "$DATA_PATH"
test ! -e "$OUTPUT_ROOT"
[[ "$OUTPUT_ROOT" = /* ]] || { echo 'OUTPUT_ROOT must be absolute' >&2; exit 2; }
export TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 CUBLAS_WORKSPACE_CONFIG=:4096:8

exec /opt/slurm/21.08.8/bin/srun "$PYTHON" -u architecture_tlm/llama7b/capture_trace.py \
  --model "$MODEL_PATH" --data "$DATA_PATH" --output "$OUTPUT_ROOT" \
  --contexts 512 1024 2048 --decode-tokens 1 --seed 0 --atol 0 --rtol 0
