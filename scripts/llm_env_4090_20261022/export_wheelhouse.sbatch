#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --job-name=llm-wheel-export
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:20:00
#SBATCH --output=/home/pwmat/projects/llm-env-bootstrap-20261022/logs/wheel-export-%j.out
#SBATCH --error=/home/pwmat/projects/llm-env-bootstrap-20261022/logs/wheel-export-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export NUMEXPR_NUM_THREADS=2
export PIP_CACHE_DIR=/home/pwmat/projects/llm-env-bootstrap-20261022/cache/pip
export TMPDIR=/home/pwmat/projects/llm-env-bootstrap-20261022/tmp
export PIP_CONFIG_FILE=/dev/null
export PIP_DISABLE_PIP_VERSION_CHECK=1
unset PYTHONPATH PYTHONHOME VIRTUAL_ENV
cd /home/pwmat/projects/llm-env-bootstrap-20261022
exec /home/pwmat/envs/llm-qwen-py312-cu118/bin/python -I -B export_wheelhouse.py
