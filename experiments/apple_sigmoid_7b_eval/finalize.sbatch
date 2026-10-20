#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --output=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/logs/finalize-%j.out
#SBATCH --error=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/logs/finalize-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=8
export XDG_CACHE_HOME=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/cache
export HF_HOME="$XDG_CACHE_HOME/huggingface"
export TMPDIR=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/tmp
/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python -B /home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/source/finalize_v1.py
