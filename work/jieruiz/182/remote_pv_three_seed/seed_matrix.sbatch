#!/bin/bash
#SBATCH --job-name=pbit182-seeds
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --array=0-3%4
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
cases=(balanced_screen_pv balanced_screen_pv balanced_screen_rejection balanced_screen_rejection)
seeds=(1 2 1 2)
case_name="${cases[$SLURM_ARRAY_TASK_ID]}"
seed="${seeds[$SLURM_ARRAY_TASK_ID]}"
exec /usr/bin/python3 -B -u "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_fe3fc20f/source/work/jieruiz/182/run_memory_cases.py" "$case_name" --seed "$seed" --manifest "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_fe3fc20f/source/work/jieruiz/182/SOURCE_MANIFEST.json" --bridge "/home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit" --output "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_fe3fc20f/results/${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}_${case_name}_seed${seed}"
