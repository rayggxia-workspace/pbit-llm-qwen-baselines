#!/bin/bash
#SBATCH --job-name=llama2-ffn-ppl
#SBATCH --partition=gpu5090
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=40G
#SBATCH --time=24:00:00
#SBATCH --array=0-25%2
set -euo pipefail
: "${SLURM_ARRAY_TASK_ID:?}"
: "${PROJECT:?}"
PYTHON=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
CASE=$($PYTHON -c 'import json,os; print(json.load(open("experiments/llama2_ffn_precision/configs/cases.json"))[int(os.environ["SLURM_ARRAY_TASK_ID"])])')
export ACTION=evaluate
export CONFIG="experiments/llama2_ffn_precision/configs/$CASE.json"
export OUTPUT="$PROJECT/outputs/$CASE"
exec bash experiments/llama2_ffn_precision/run.sbatch
