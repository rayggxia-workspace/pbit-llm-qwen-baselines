#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=00:30:00
#SBATCH --output=/home/Weican_Chen/projects/full-ffn-issue123-20261023/capture-%j.out
#SBATCH --error=/home/Weican_Chen/projects/full-ffn-issue123-20261023/capture-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
export PYTHONIOENCODING=utf-8
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
task_root=/home/Weican_Chen/projects/full-ffn-issue123-20261023
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$rc" > "$task_root/capture-terminal-$SLURM_JOB_ID.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$task_root")" = "$task_root"
cd "$task_root"
sha256sum -c capture.sha256
/opt/slurm/21.08.8/bin/srun /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python -B -P -X utf8 capture_full_ffn.py --model /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/models/Qwen2.5-0.5B --text /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/data/wikitext-2/wiki.test.raw --output "$task_root/full_fixture" --context 64 --layer 0
