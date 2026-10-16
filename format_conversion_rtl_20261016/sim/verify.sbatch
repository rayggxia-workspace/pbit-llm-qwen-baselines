#!/bin/bash
#SBATCH --job-name=pbit-format-rtl
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=verify-%j.log
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
dpkg-deb -x tools/iverilog_12.0-2build2_amd64.deb tools/iverilog
export IVERILOG="$PWD/tools/iverilog/usr/bin/iverilog"
export VVP="$PWD/tools/iverilog/usr/bin/vvp"
export IVERILOG_BASE=$(find "$PWD/tools/iverilog/usr/lib" -type d -name ivl | head -1)
bash sim/run.sh
