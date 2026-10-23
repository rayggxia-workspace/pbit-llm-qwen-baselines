#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -euo pipefail
test "$(id -un)" = Weican_Chen
test "$(getent passwd Weican_Chen | cut -d: -f6)" = /home/Weican_Chen
test "$(realpath -e /home/Weican_Chen)" = /home/Weican_Chen
test "$(stat -c %U /home/Weican_Chen)" = Weican_Chen
test "$(realpath -e /home/Weican_Chen/projects/sparq-qwen3-issue157)" = /home/Weican_Chen/projects/sparq-qwen3-issue157
test "$(stat -c %U /home/Weican_Chen/projects/sparq-qwen3-issue157)" = Weican_Chen

test "$(realpath -e /home/Weican_Chen/projects/sparq-qwen3-issue157/source-9626d590ca11)" = /home/Weican_Chen/projects/sparq-qwen3-issue157/source-9626d590ca11
export OMP_NUM_THREADS=4 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
export TMPDIR=/home/Weican_Chen/projects/sparq-qwen3-issue157/tmp
export HF_HOME=/home/Weican_Chen/projects/sparq-qwen3-issue157/cache/hf HF_DATASETS_CACHE=/home/Weican_Chen/projects/sparq-qwen3-issue157/cache/datasets
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
cd /home/Weican_Chen/projects/sparq-qwen3-issue157/source-9626d590ca11

export CUDA_VISIBLE_DEVICES=""
/opt/slurm/21.08.8/bin/srun env CUDA_VISIBLE_DEVICES="" /home/Weican_Chen/projects/sparq-qwen3-issue157/env-v2/bin/python -B -m qwen3.sparq.cpu_gate --output /home/Weican_Chen/projects/sparq-qwen3-issue157/prepared/cpu-final-9626d590ca11.json
/home/Weican_Chen/projects/sparq-qwen3-issue157/env-v2/bin/python -B -m qwen3.sparq.benchmark --self-test
