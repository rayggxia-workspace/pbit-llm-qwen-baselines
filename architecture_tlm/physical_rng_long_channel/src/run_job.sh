#!/usr/bin/env bash
set -eo pipefail
: "${STUDY_ROOT:?Use submit.sh}" "${STUDY_SOURCE:?Use submit.sh}" "${STUDY_STAGE:?Use submit.sh}"
: "${STUDY_WORKERS:?Use submit.sh}" "${STUDY_EFFECTIVE_SECONDS:?Use submit.sh}" "${SLURM_JOB_ID:?Use Slurm}"
: "${SLURM_CPUS_PER_TASK:?Missing allocation}"
if (( SLURM_CPUS_PER_TASK < STUDY_WORKERS )); then printf 'Worker count exceeds CPU allocation\n' >&2; exit 2; fi
work="$STUDY_ROOT/results/${SLURM_JOB_ID}_${STUDY_STAGE}"
if [[ -e "$work" ]]; then printf 'Refusing existing results %s\n' "$work" >&2; exit 2; fi
finish() {
    rc=$?
    trap - EXIT
    mkdir -p "$work"
    printf '%s\n' "$rc" > "$work/job_exit_status.txt"
    if python3 -B "$STUDY_SOURCE/run_long.py" --pack "$work"; then
        printf 'PACKING=SUCCESS; read summary.json, not just this marker\n'
    else
        printf 'PACKING=FAILED; all results preserved\n' >&2
        if [[ "$rc" -eq 0 ]]; then rc=3; fi
    fi
    exit "$rc"
}
trap finish EXIT
export PS1="${PS1-}"
set +u
source "$HOME/.bashrc"
set +u
set -eo pipefail
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd "$STUDY_ROOT"
printf 'HOST=%s JOB=%s STAGE=%s CPUS=%s WORKERS=%s SOURCE=%s\n' \
    "$(hostname)" "$SLURM_JOB_ID" "$STUDY_STAGE" "$SLURM_CPUS_PER_TASK" "$STUDY_WORKERS" "$STUDY_SOURCE"
args=(--stage "$STUDY_STAGE" --workers "$STUDY_WORKERS" --effective-seconds "$STUDY_EFFECTIVE_SECONDS" --out "$work")
if [[ -n "${STUDY_PARENT:-}" ]]; then args+=(--parent "$STUDY_PARENT"); fi
python3 -B "$STUDY_SOURCE/run_long.py" "${args[@]}"
