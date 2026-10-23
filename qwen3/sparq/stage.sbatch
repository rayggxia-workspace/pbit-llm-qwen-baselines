#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=06:00:00
set -euo pipefail
task_root=/home/Weican_Chen/projects/sparq-qwen3-issue157
test "$(id -un)" = Weican_Chen
test "$(realpath -e "$task_root")" = "$task_root"
test "$(stat -c %U "$task_root")" = Weican_Chen
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=4 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
export HF_HUB_DISABLE_XET=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export HF_HUB_DOWNLOAD_TIMEOUT=120 HF_HUB_ETAG_TIMEOUT=60
export PIP_CACHE_DIR="$task_root/cache/pip" HF_HOME="$task_root/cache/hf"
export TMPDIR="$task_root/tmp"
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR" "$HF_HOME" "$task_root/prepared"
base_python=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/env-eval-v4/bin/python
test ! -e "$task_root/env"
"$base_python" -m venv "$task_root/env"
printf '%s\n' /home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/env-eval-v4/lib/python3.12/site-packages > "$task_root/env/lib/python3.12/site-packages/personal_base_readonly.pth"
"$task_root/env/bin/python" -m pip install --no-deps --index-url https://pypi.tuna.tsinghua.edu.cn/simple transformers==4.51.3 tokenizers==0.21.4
/opt/slurm/21.08.8/bin/srun "$task_root/env/bin/python" -B "$task_root/staging-v1/stage.py" --root "$task_root" --identity "$task_root/staging-v1/HF_MODEL.json"
