#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=/home/Weican_Chen/projects/encoding-restore-issue121-20261023/revision2/rtl-%j.out
#SBATCH --error=/home/Weican_Chen/projects/encoding-restore-issue121-20261023/revision2/rtl-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
task_root=/home/Weican_Chen/projects/encoding-restore-issue121-20261023/revision2
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$task_root/terminal-$SLURM_JOB_ID.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$task_root")" = "$task_root"
test -n "$SLURM_JOB_ID"
cd "$task_root"
sha256sum -c rtl_source.sha256
mkdir "run-$SLURM_JOB_ID"
tar -xzf rtl_source.tar.gz -C "run-$SLURM_JOB_ID"
cd "run-$SLURM_JOB_ID"
python3 -m venv --without-pip python
stage=rtl_validation
python/bin/python -B architecture_tlm/encoding_restore_contract/sim/validate_ready_valid.py --iverilog /home/Weican_Chen/projects/tlm-cycle-issue116-20261023/tools/bin/iverilog --vvp /home/Weican_Chen/projects/tlm-cycle-issue116-20261023/tools/bin/vvp --build-dir build --out evidence
stage=archive
tar -czf "$task_root/results-$SLURM_JOB_ID.tar.gz" evidence
sha256sum "$task_root/results-$SLURM_JOB_ID.tar.gz" > "$task_root/results-$SLURM_JOB_ID.sha256"
stage=done
