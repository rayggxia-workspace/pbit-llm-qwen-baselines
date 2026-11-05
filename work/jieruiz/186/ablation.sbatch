#!/bin/bash
#SBATCH --job-name=pbit186-w8pv
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=01:30:00
#SBATCH --array=0-5%6
set -euo pipefail
cd /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/w8_6b0df70b/source
exec /usr/bin/python3 -B -u work/jieruiz/186/run_schedule_case.py "$SLURM_ARRAY_TASK_ID" --matrix /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/ablation_6b0df70b/ATTENTION_ABLATION_MATRIX.json --manifest work/jieruiz/186/SOURCE.json --bridge /home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit --output /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/ablation_6b0df70b/results/case_"$SLURM_ARRAY_TASK_ID"
