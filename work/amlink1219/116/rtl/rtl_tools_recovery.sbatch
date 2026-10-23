#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --mem=12G
#SBATCH --time=00:20:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/rtl-recovery-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/rtl-recovery-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
task_root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
tool_prefix="$task_root/tools"
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$task_root/rtl-recovery-$SLURM_JOB_ID-terminal.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$task_root")" = "$task_root"
test "$(stat -c %U "$task_root")" = Weican_Chen
test -n "$SLURM_JOB_ID"
test -x "$tool_prefix/bin/bison"
test -x "$tool_prefix/bin/flex"
export PATH="$tool_prefix/bin:$PATH"
cd "$task_root/archives"
sha256sum -c gperf.sha256
stage=gperf
mkdir -p "$task_root/rtl-tool-src/gperf"
tar -xzf gperf-3.1.tar.gz --strip-components=1 -C "$task_root/rtl-tool-src/gperf"
cd "$task_root/rtl-tool-src/gperf"
./configure --prefix="$tool_prefix"
make -j "$SLURM_CPUS_PER_TASK"
make install
stage=iverilog
cd "$task_root/rtl-tool-src/iverilog"
sh autoconf.sh
./configure --prefix="$tool_prefix"
make -j "$SLURM_CPUS_PER_TASK"
make install
stage=tool_preflight
"$tool_prefix/bin/iverilog" -V
"$tool_prefix/bin/vvp" -V
sha256sum "$tool_prefix/bin/iverilog" "$tool_prefix/bin/vvp" "$tool_prefix/bin/gperf" > "$task_root/rtl-tools-built.sha256"
stage=done
