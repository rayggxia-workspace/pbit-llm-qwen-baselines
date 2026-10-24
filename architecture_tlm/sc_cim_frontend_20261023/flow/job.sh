#!/usr/bin/env bash
set -euo pipefail
index=${SLURM_ARRAY_TASK_ID:?}; corner=ss; kind=$((index % 4)); m=64
[[ $index =~ ^[0-7]$ ]] || { echo 'Bad array index' >&2; exit 2; }
(( index >= 4 )) && corner=tt
export EDA_CORES=${SLURM_CPUS_PER_TASK:-4}
export CIM_SEEDS=${CIM_SEEDS:-1,17,74565}
export CIM_SMOKE=0
if [[ -n ${CIM_REUSE_ROOT:-} ]]; then
 export CIM_REUSE_RUN="$CIM_REUSE_ROOT/${CIM_REUSE_JOB:?}_${index}_kind${kind}_${corner}"
fi
if [[ $kind == 1 || $kind == 3 ]]; then m=1; fi
if [[ $CIM_MODE == smoke ]]; then m=1; export CIM_SEEDS=17 CIM_SMOKE=1; fi
if [[ $CIM_MODE == external ]]; then
 (( index < 4 )) || { echo 'External mode supports indices 0..3' >&2; exit 2; }
 kind=$((index % 2)); corner=ss; (( index >= 2 )) && corner=tt
 export CIM_EXT=1
 if [[ $kind == 1 ]]; then m=1; else m=64; fi
fi
exec bash "$CIM_PACKAGE/flow/run_one.sh" "$kind" "$corner" "$m" "$CIM_RESULTS/${SLURM_ARRAY_JOB_ID}_${index}_kind${kind}_${corner}"
