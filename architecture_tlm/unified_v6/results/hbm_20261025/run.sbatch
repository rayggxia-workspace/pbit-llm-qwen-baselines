#!/bin/bash
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=01:30:00
#SBATCH --array=0-16%17
set -euo pipefail
cd /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/hbm_e7505ee4/source
exec /usr/bin/python3 -B -u work/jieruiz/186/run_schedule_case.py "$SLURM_ARRAY_TASK_ID" --matrix work/jieruiz/186/HBM_MATRIX.json --manifest work/jieruiz/186/SOURCE.json --bridge /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/hbm_e7505ee4/build/pbit_hbm_bridge --output /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/hbm_e7505ee4/results/case_"$SLURM_ARRAY_TASK_ID"
