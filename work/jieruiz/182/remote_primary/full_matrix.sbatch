#!/bin/bash
#SBATCH --job-name=pbit182-full
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --array=0-10%8
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
cases=(ddr4_old ddr4_wide balanced_e8 balanced_e16 balanced_e32 balanced_e64 balanced_single balanced_bf16 balanced_w8 balanced_screen_pv balanced_screen_rejection)
case_name="${cases[$SLURM_ARRAY_TASK_ID]}"
exec /usr/bin/python3 -B -u "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_7e44b6a4/source/work/jieruiz/182/run_memory_cases.py" "$case_name" --manifest "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_7e44b6a4/source/work/jieruiz/182/SOURCE_MANIFEST.json" --bridge "/home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit" --output "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_7e44b6a4/results/${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}_${case_name}"
