#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:10:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/gqa_capture_v1/capture-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/gqa_capture_v1/capture-%j.err
set -euo pipefail
export PYTHONIOENCODING=utf-8
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
task_root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/gqa_capture_v1
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$rc" > "$task_root/terminal.json"' EXIT
cd "$task_root"
source_commit=$(cat SOURCE_COMMIT.txt)
/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python -P -X utf8 "$task_root/capture_gqa_qwen.py" \
  --model /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/models/Qwen2.5-0.5B \
  --text /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/data/wikitext-2/wiki.test.raw \
  --baseline-manifest /home/Weican_Chen/projects/tlm-cycle-issue116-20261023/real_fixtures_v1/MANIFEST.json \
  --output "$task_root/private_fixture" --context 64 --execution-commit "$source_commit"
