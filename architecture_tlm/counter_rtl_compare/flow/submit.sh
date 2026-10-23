#!/usr/bin/env bash
set -euo pipefail
# Four formal A/B x SS/TT jobs; M64, T32, one reduction pipeline stage.
# Submit from the extracted package root: bash flow/submit.sh /absolute/new/run_root
root=$(cd "$(dirname "$0")/.." && pwd)
dest=${1:?new absolute result root required}
[[ $dest == /* && ! -e $dest ]] || { echo 'Result root must be absolute and new' >&2; exit 2; }
mkdir -p "$dest/logs"
sbatch --job-name=sc-counter-ab --array=0-3%2 --cpus-per-task=4 --mem=32G --time=12:00:00 \
 --output="$dest/logs/%A_%a.out" --error="$dest/logs/%A_%a.err" \
 --export=ALL,COUNTER_PACKAGE="$root",COUNTER_RESULTS="$dest" "$root/flow/job.sh"
