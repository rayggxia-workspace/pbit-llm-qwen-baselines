#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/rtl-contract-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/rtl-contract-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
task_root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$task_root/rtl-contract-$SLURM_JOB_ID-terminal.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$task_root")" = "$task_root"
test -n "$SLURM_JOB_ID"
test -x "$task_root/tools/bin/iverilog"
test -x "$task_root/tools/bin/vvp"
cd "$task_root/archives"
sha256sum -c rtl_snapshot.sha256
run_root="$task_root/rtl-contract-$SLURM_JOB_ID"
mkdir "$run_root"
tar -xzf rtl_snapshot.tar.gz -C "$run_root"
cd "$run_root"
stage=python_preflight
python3 -m venv --without-pip "$run_root/python"
"$run_root/python/bin/python" -c 'import sys; assert sys.version_info >= (3, 10); print(sys.version)'
stage=validate
"$run_root/python/bin/python" -m architecture_tlm.cycle_v1.rtl.validate_rtl --iverilog "$task_root/tools/bin/iverilog" --vvp "$task_root/tools/bin/vvp" --out "$run_root/results"
stage=archive
tar -czf "$task_root/rtl-contract-$SLURM_JOB_ID-results.tar.gz" -C "$run_root" results
sha256sum "$task_root/rtl-contract-$SLURM_JOB_ID-results.tar.gz" > "$task_root/rtl-contract-$SLURM_JOB_ID-results.tar.gz.sha256"
stage=done
