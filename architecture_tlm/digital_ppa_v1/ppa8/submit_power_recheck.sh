#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ $# != 1 ]]; then
    echo 'Usage: bash submit_power_recheck.sh /absolute/v1/results/38339971' >&2
    exit 2
fi
[[ $1 == /* ]] || { echo 'Use an absolute parent result prefix' >&2; exit 2; }
export POWER_REUSE_BASE=$1
unset REUSE_RUN
for idx in 7 15; do
    [[ -r ${POWER_REUSE_BASE}_${idx}/FLOW_COMPLETE ]] || { echo "Missing completed parent ${POWER_REUSE_BASE}_${idx}" >&2; exit 2; }
done
bash "$ROOT/submit.sh" smoke
