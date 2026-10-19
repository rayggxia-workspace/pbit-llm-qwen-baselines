#!/bin/bash
#SBATCH --job-name=llama2-download
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=2
#SBATCH --mem=2G
#SBATCH --time=02:00:00
set -euo pipefail
: "${SLURM_JOB_ID:?Use Slurm}"
: "${SOURCE_COMMIT:?Set exact source commit}"
: "${MODEL_OUTPUT:?Use a new absolute model directory}"
: "${MANIFEST_OUTPUT:?Use a new absolute manifest path}"
exec /home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python -u \
 architecture_tlm/llama2_7b/download_mirror.py --output "$MODEL_OUTPUT" --manifest-output "$MANIFEST_OUTPUT"
