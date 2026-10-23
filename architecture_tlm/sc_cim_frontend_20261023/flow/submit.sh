#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
dest=${1:?new absolute result root required}; mode=${2:-smoke}
case "$mode" in smoke|all|external) ;; *) echo 'Mode: smoke|all|external' >&2; exit 2;; esac
[[ $dest == /* && ! -e $dest ]] || { echo 'Result root must be absolute and new' >&2; exit 2; }
"${PYTHON_BIN:-python3}" "$root/package.py" --verify
mkdir -p "$dest/logs"
"${PYTHON_BIN:-python3}" "$root/package.py" --snapshot "$dest/source"
array=0-7
[[ $mode == external ]] && array=0-3
sbatch --partition="${PARTITION:-v6_384}" --job-name=cim-frontend --array="${CIM_ARRAY:-$array}%${PARALLEL:-2}" \
 --cpus-per-task="${CPUS:-4}" --mem="${MEMORY:-32G}" --time="${WALLTIME:-12:00:00}" \
 --output="$dest/logs/%A_%a.out" --error="$dest/logs/%A_%a.err" \
 --export=ALL,CIM_PACKAGE="$dest/source",CIM_RESULTS="$dest",CIM_MODE="$mode" "$dest/source/flow/job.sh"
