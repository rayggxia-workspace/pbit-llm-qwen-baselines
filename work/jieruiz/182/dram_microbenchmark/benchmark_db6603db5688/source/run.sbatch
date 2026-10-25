#!/bin/bash
#SBATCH --job-name=pbit182-dram-smoke
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
set -euo pipefail
exec /usr/bin/python3 -u "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/benchmark_db6603db5688/source/benchmark_dram.py" --source "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/benchmark_db6603db5688/source" --bridge "/home/Hongjie_Zeng/projects/pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit" --output "/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/benchmark_db6603db5688/results/${SLURM_/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/benchmark_db6603db5688_ID}"
