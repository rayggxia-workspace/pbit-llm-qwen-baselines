#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=01:30:00
#SBATCH --output=/home/Weican_Chen/projects/full-ffn-issue123-20261023/revision4/ffn-%j.out
#SBATCH --error=/home/Weican_Chen/projects/full-ffn-issue123-20261023/revision4/ffn-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
export PYTHONIOENCODING=utf-8
task_root=/home/Weican_Chen/projects/full-ffn-issue123-20261023/revision4
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$task_root/ffn-terminal-$SLURM_JOB_ID.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$task_root")" = "$task_root"
cd "$task_root"
sha256sum -c ffn_source.sha256
printf 'c4e8100441db57858fff8682af5acfb5ca06cb61fbd3b16e29a631bd230b640c  /home/Weican_Chen/projects/full-ffn-issue123-20261023/full_fixture/full_ffn.json\n' | sha256sum -c -
mkdir "ffn-run-$SLURM_JOB_ID"
tar -xzf ffn_source.tar.gz -C "ffn-run-$SLURM_JOB_ID"
cd "ffn-run-$SLURM_JOB_ID"
stage=full_ffn
/opt/slurm/21.08.8/bin/srun /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/.venv/bin/python -B -X utf8 -m architecture_tlm.cycle_v1.run_contract_ffn --fixture "/home/Weican_Chen/projects/full-ffn-issue123-20261023/full_fixture/full_ffn.json" --profile "$task_root/profile.json" --output "$task_root/ffn-results-$SLURM_JOB_ID" --expect-shape 896 4864 896
stage=archive
cd "$task_root"
tar -czf "ffn-results-$SLURM_JOB_ID.tar.gz" "ffn-results-$SLURM_JOB_ID"
sha256sum "ffn-results-$SLURM_JOB_ID.tar.gz" > "ffn-results-$SLURM_JOB_ID.sha256"
stage=done
