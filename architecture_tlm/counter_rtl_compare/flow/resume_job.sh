#!/usr/bin/env bash
set -euo pipefail
index=${SLURM_ARRAY_TASK_ID:?}
case "$index" in
    0) suffix=0_A_ss;; 1) suffix=1_B_ss;;
    2) suffix=2_A_tt;; 3) suffix=3_B_tt;; *) exit 2;;
esac
export PPA_SOURCE="$COUNTER_PACKAGE/flow"
export EDA_CORES=${SLURM_CPUS_PER_TASK:-2}
command -v pt_shell
"${PYTHON_BIN:-python3}" "$COUNTER_PACKAGE/package.py" --verify
exec "${PYTHON_BIN:-python3}" -B "$COUNTER_PACKAGE/flow/resume_power.py" \
    --old "$COUNTER_OLD/38356996_${suffix}" \
    --out "$COUNTER_RESULTS/${SLURM_ARRAY_JOB_ID}_${suffix}"
