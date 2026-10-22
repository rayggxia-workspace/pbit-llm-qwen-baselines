#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --mem=12G
#SBATCH --time=00:30:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/rtl-tools-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/rtl-tools-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
prefix="$root/tools"
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$root/rtl-tools-terminal.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$root")" = "$root"
test -n "$SLURM_JOB_ID"
command -v m4
cd "$root/archives"
sha256sum -c SHA256SUMS
mkdir "$root/rtl-tool-src"
for name in bison flex iverilog; do mkdir "$root/rtl-tool-src/$name"; done
tar -xJf bison.tar.xz --strip-components=1 -C "$root/rtl-tool-src/bison"
tar -xzf flex.tar.gz --strip-components=1 -C "$root/rtl-tool-src/flex"
tar -xzf iverilog.tar.gz --strip-components=1 -C "$root/rtl-tool-src/iverilog"
export PATH="$prefix/bin:$PATH"
stage=bison
cd "$root/rtl-tool-src/bison"
./configure --prefix="$prefix"
make -j "$SLURM_CPUS_PER_TASK"
make install
stage=flex
cd "$root/rtl-tool-src/flex"
./configure --prefix="$prefix"
make -j "$SLURM_CPUS_PER_TASK"
make install
stage=iverilog
cd "$root/rtl-tool-src/iverilog"
sh autoconf.sh
./configure --prefix="$prefix"
make -j "$SLURM_CPUS_PER_TASK"
make install
"$prefix/bin/iverilog" -V
"$prefix/bin/vvp" -V
stage=done
