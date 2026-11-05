#!/bin/bash
#SBATCH --job-name=pbit182-crossgate
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:05:00
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
exec /usr/bin/python3 -B -u "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_baf0aab1/smoke_full_decode.py" --source "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_baf0aab1/source" --bridge "/home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit" --output "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_baf0aab1/smoke/${SLURM_JOB_ID}"
