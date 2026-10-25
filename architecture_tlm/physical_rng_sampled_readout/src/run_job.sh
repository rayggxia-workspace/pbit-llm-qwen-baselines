#!/usr/bin/env bash
set -eo pipefail
: "${STUDY_SOURCE:?Use submit.sh}" "${STUDY_ROOT:?Use submit.sh}" "${SLURM_JOB_ID:?Use Slurm}"
export PYTHONDONTWRITEBYTECODE=1 PS1="${PS1-}"
work="$STUDY_ROOT/results/$SLURM_JOB_ID"
finish() {
    rc=$?
    trap - EXIT
    mkdir -p "$work"
    printf '%s\n' "$rc" > "$work/job_exit_status.txt"
    "$STUDY_PYTHON" -B "$STUDY_SOURCE/run_sampled.py" --pack "$work" || { if [[ "$rc" -eq 0 ]]; then rc=3; fi; }
    exit "$rc"
}
trap finish EXIT
set +u
source "$HOME/.bashrc"
set +u
set -eo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd "$STUDY_ROOT"
"$STUDY_PYTHON" -B "$STUDY_SOURCE/run_sampled.py" --out "$work" --workers "$STUDY_WORKERS" --max-hours "$STUDY_MAX_HOURS"
