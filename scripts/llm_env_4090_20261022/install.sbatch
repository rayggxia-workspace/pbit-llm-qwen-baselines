#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --job-name=llm-env-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=01:00:00
#SBATCH --output=/home/pwmat/projects/llm-env-bootstrap-20261022/logs/install-%j.out
#SBATCH --error=/home/pwmat/projects/llm-env-bootstrap-20261022/logs/install-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export NUMEXPR_NUM_THREADS=2
unset PYTHONPATH PYTHONHOME VIRTUAL_ENV
cd /home/pwmat/projects/llm-env-bootstrap-20261022
exec /share/app/conda/conda3/bin/python3 -I -B bootstrap_install.py

