#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:30:00
set -euo pipefail
test "$(id -un)" = Weican_Chen
test "$(getent passwd Weican_Chen | cut -d: -f6)" = /home/Weican_Chen
test "$(realpath -e /home/Weican_Chen)" = /home/Weican_Chen
test "$(stat -c %U /home/Weican_Chen)" = Weican_Chen
test "$(realpath -e /home/Weican_Chen/projects/sparq-qwen3-issue157)" = /home/Weican_Chen/projects/sparq-qwen3-issue157
test "$(stat -c %U /home/Weican_Chen/projects/sparq-qwen3-issue157)" = Weican_Chen

test "$(realpath -e /home/Weican_Chen/projects/sparq-qwen3-issue157/measurement-source-a430ca231792)" = /home/Weican_Chen/projects/sparq-qwen3-issue157/measurement-source-a430ca231792
test "$(stat -c %U /home/Weican_Chen/projects/sparq-qwen3-issue157/measurement-source-a430ca231792)" = Weican_Chen
test -x /opt/slurm/21.08.8/bin/srun
export OMP_NUM_THREADS=4 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
export TMPDIR=/home/Weican_Chen/projects/sparq-qwen3-issue157/tmp
export HF_HOME=/home/Weican_Chen/projects/sparq-qwen3-issue157/cache/hf HF_DATASETS_CACHE=/home/Weican_Chen/projects/sparq-qwen3-issue157/cache/datasets
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
cd /home/Weican_Chen/projects/sparq-qwen3-issue157/measurement-source-a430ca231792
/opt/slurm/21.08.8/bin/srun env CUDA_VISIBLE_DEVICES="" /home/Weican_Chen/projects/sparq-qwen3-issue157/env-v2/bin/python -B -m unittest qwen3.sparq.test_bench_only
/opt/slurm/21.08.8/bin/srun env CUDA_VISIBLE_DEVICES="" /home/Weican_Chen/projects/sparq-qwen3-issue157/env-v2/bin/python -B -m qwen3.sparq.benchmark --self-test
/opt/slurm/21.08.8/bin/srun /home/Weican_Chen/projects/sparq-qwen3-issue157/env-v2/bin/python -B -m qwen3.sparq.bench_only run --root /home/Weican_Chen/projects/sparq-qwen3-issue157 --parent-results /home/Weican_Chen/projects/sparq-qwen3-issue157/results/8d60abe4e7c5 --parent-identity-sha256 62ce870e86f248069d33adda3e6f16824363f9dbbd1c2c7259523f5ddb3cef2d
