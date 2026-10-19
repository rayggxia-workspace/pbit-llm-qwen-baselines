#!/bin/bash
#SBATCH --job-name=llama2-report
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
set -euo pipefail
: "${SLURM_JOB_ID:?Use Slurm}"
: "${RUN_PROJECT:?Set original immutable result project}"
: "${REPORT_OUTPUT:?Set NEW report directory}"
: "${REPORT_SOURCE_COMMIT:?Set exact postprocessing source commit}"
python_bin=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
"$python_bin" architecture_tlm/llama2_7b/report.py --project "$RUN_PROJECT" --output "$REPORT_OUTPUT"
"$python_bin" architecture_tlm/llama2_7b/render_report.py "$REPORT_OUTPUT"
