#!/usr/bin/env bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -euo pipefail
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
test "$(id -un)" = Weican_Chen
test "$(getent passwd Weican_Chen | cut -d: -f6)" = /home/Weican_Chen
test -n "${SLURM_JOB_ID:?}"
exec /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python \
  "${A37_SOURCE_ROOT:?}/architecture_tlm/attention_comparison/job.py" \
  --snapshot "$A37_SOURCE_ROOT" --output "${A37_OUTPUT:?}"
