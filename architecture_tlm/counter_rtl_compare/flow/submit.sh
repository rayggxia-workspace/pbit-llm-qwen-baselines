#!/usr/bin/env bash
set -euo pipefail
# Four formal A/B x SS/TT jobs; M64, T32, one reduction pipeline stage.
# Submit from the extracted package root: bash flow/submit.sh /absolute/new/run_root
root=$(cd "$(dirname "$0")/.." && pwd)
dest=${1:?new absolute result root required}
mode=${2:-all}
case "$mode" in smoke|all) ;; *) echo 'Mode must be smoke or all' >&2; exit 2;; esac
[[ $dest == /* && ! -e $dest ]] || { echo 'Result root must be absolute and new' >&2; exit 2; }
"${PYTHON_BIN:-python3}" "$root/package.py" --verify
mkdir -p "$dest/logs"
"${PYTHON_BIN:-python3}" "$root/package.py" --snapshot "$dest/source"
root="$dest/source"
sbatch --partition="${PARTITION:-v6_384}" --job-name=sc-counter-ab --array=0-3%2 --cpus-per-task="${CPUS:-4}" --mem="${MEMORY:-32G}" --time="${WALLTIME:-12:00:00}" \
 --output="$dest/logs/%A_%a.out" --error="$dest/logs/%A_%a.err" \
 --export=ALL,COUNTER_PACKAGE="$root",COUNTER_RESULTS="$dest",COUNTER_MODE="$mode" "$root/flow/job.sh"
