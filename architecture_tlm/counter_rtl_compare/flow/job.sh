#!/usr/bin/env bash
set -euo pipefail
index=${SLURM_ARRAY_TASK_ID:?};arch=A;corner=ss
(( index % 2 == 1 )) && arch=B
(( index >= 2 )) && corner=tt
export EDA_CORES=${SLURM_CPUS_PER_TASK:-4}
m=64
if [[ ${COUNTER_MODE:-all} == smoke ]]; then
    m=1
    export SC_PROFILES=mixed SC_SEEDS=17 SC_POWER_FRAMES=4
fi
exec bash "$COUNTER_PACKAGE/flow/run_one.sh" "$arch" "$corner" "$m" 32 1 "$COUNTER_RESULTS/${SLURM_ARRAY_JOB_ID}_${index}_${arch}_${corner}"
