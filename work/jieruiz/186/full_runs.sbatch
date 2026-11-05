#!/bin/bash
#SBATCH --job-name=pbit186-full
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=01:30:00
#SBATCH --array=0-30%20
set -euo pipefail
cd /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/full_bab9721d/source
exec /usr/bin/python3 -B -u work/jieruiz/186/run_schedule_case.py "$SLURM_ARRAY_TASK_ID" --matrix work/jieruiz/186/RUN_MATRIX.json --manifest work/jieruiz/186/SOURCE.json --bridge /home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit --output /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/full_bab9721d/results/case_"$SLURM_ARRAY_TASK_ID"
