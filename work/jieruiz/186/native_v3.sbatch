#!/bin/bash
#SBATCH --job-name=pbit186-native3
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
exec /usr/bin/python3 -B -u /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/native_v3/input/build_and_run.py /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/native_v3/build
