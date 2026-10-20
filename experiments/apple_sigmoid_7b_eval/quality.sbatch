#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/logs/quality-%j.out
#SBATCH --error=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/logs/quality-%j.err
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
export XDG_CACHE_HOME=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/cache
export HF_HOME="$XDG_CACHE_HOME/huggingface"
export TMPDIR=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/tmp
cd /home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019
exec env-eval-v4/bin/python -B source/gpu_worker_v1.py
