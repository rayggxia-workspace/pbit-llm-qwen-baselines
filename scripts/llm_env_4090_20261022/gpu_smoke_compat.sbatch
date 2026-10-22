#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --job-name=llm-env-gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --time=00:05:00
#SBATCH --output=/home/pwmat/projects/llm-env-bootstrap-20261022/logs/smoke-%j.out
#SBATCH --error=/home/pwmat/projects/llm-env-bootstrap-20261022/logs/smoke-%j.err
set -euo pipefail
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export NUMEXPR_NUM_THREADS=2
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export TMPDIR=/home/pwmat/projects/llm-env-bootstrap-20261022/tmp
export HF_HOME=/home/pwmat/projects/llm-env-bootstrap-20261022/cache/huggingface
unset PYTHONPATH PYTHONHOME VIRTUAL_ENV
cd /home/pwmat/projects/llm-env-bootstrap-20261022
exec /home/pwmat/envs/llm-qwen-py312-cu118/bin/llm-python -I -B gpu_smoke.py --output "/home/pwmat/projects/llm-env-bootstrap-20261022/gpu_smoke-${SLURM_JOB_ID}.json" --source-root /home/pwmat/projects/llm-env-bootstrap-20261022/smoke_source
