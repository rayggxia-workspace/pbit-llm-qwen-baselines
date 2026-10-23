#!/usr/bin/env bash
set -eo pipefail
# User's licensed tool setup is inherited; .bashrc is not altered here.
set -u
: "${PPA_SOURCE:?}" "${PPA_ROOT:?}" "${SLURM_ARRAY_TASK_ID:?}"
kinds=(0 2 4 5 6 7 8 21)
idx=$SLURM_ARRAY_TASK_ID
[[ $idx -ge 0 && $idx -lt 16 ]] || exit 2
export PPA_CORNER=ss
if [[ $idx -ge 8 ]]; then export PPA_CORNER=tt; fi
kind=${kinds[$((idx%8))]}
source "$PPA_SOURCE/environment.sh"
run=${REUSE_RUN:-$SLURM_ARRAY_JOB_ID}
[[ $run =~ ^[0-9]+$ ]] || { echo 'Invalid run id' >&2; exit 2; }
work="$PPA_ROOT/results/${run}_${idx}"
mkdir -p "$work"
# Lock is held across all stages; duplicate resumes cannot corrupt a checkpoint.
exec 9>"$work/.run.lock"
flock -n 9 || { echo "Already running: $work" >&2; exit 3; }
finish() {
    rc=$?
    trap - EXIT
    "$PYTHON_BIN" "$PPA_SOURCE/collect.py" "$work" || { echo 'RESULT_PACK_FAILED' >&2; [[ $rc != 0 ]] || rc=4; }
    exit "$rc"
}
trap finish EXIT
printf 'Start=%s Work=%s Snapshot=%s Kind=%s Corner=%s\n' "$(date)" "$work" "$PPA_SOURCE" "$kind" "$PPA_CORNER"
if [[ -n ${POWER_REUSE_BASE:-} ]]; then
    parent="${POWER_REUSE_BASE}_${idx}"
    [[ -d $parent ]] || { echo "Missing parent result: $parent" >&2; exit 2; }
    exec 8<"$parent/.run.lock"
    flock -n -s 8 || { echo 'Parent is still running' >&2; exit 3; }
    "$PYTHON_BIN" "$PPA_SOURCE/run.py" --work "$work" --kind "$kind" --corner "$PPA_CORNER" --reuse-from "$parent"
else
    "$PYTHON_BIN" "$PPA_SOURCE/run.py" --work "$work" --kind "$kind" --corner "$PPA_CORNER"
fi
printf 'End=%s\n' "$(date)"
