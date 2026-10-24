#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
old=${1:?original smoke result root required}
dest=${2:?new absolute result root required}
[[ $old == /* && -d $old && $dest == /* && ! -e $dest ]] || {
    echo 'Use existing absolute OLD root and a new absolute destination' >&2; exit 2;
}
for suffix in 0_A_ss 1_B_ss 2_A_tt 3_B_tt; do
    [[ -r "$old/38356996_${suffix}/EXECUTION.json" ]] || {
        echo "Missing old run: $old/38356996_${suffix}" >&2; exit 2;
    }
done
"${PYTHON_BIN:-python3}" "$root/package.py" --verify
mkdir -p "$dest/logs"
"${PYTHON_BIN:-python3}" "$root/package.py" --snapshot "$dest/source"
root="$dest/source"
sbatch --partition="${PARTITION:-v6_384}" --job-name=counter-pt-v4 --array=0-3%2 \
    --cpus-per-task="${CPUS:-2}" --mem="${MEMORY:-16G}" --time="${WALLTIME:-04:00:00}" \
    --output="$dest/logs/%A_%a.out" --error="$dest/logs/%A_%a.err" \
    --export=ALL,COUNTER_PACKAGE="$root",COUNTER_OLD="$old",COUNTER_RESULTS="$dest" \
    "$root/flow/resume_job.sh"
