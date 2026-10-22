#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:25:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/capture-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/capture-%j.err
set -euo pipefail
export PYTHONIOENCODING=utf-8
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$rc" > "$root/capture-terminal.json"' EXIT
cd "$root"
/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python -P -X utf8 "$root/capture_qwen.py" --model /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/models/Qwen2.5-0.5B --text /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/data/wikitext-2/wiki.test.raw --output "$root/real_fixtures_v1" --context 2048
