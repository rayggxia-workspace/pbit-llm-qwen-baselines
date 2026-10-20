#!/usr/bin/env bash
if [[ -f "$HOME/.bashrc" ]];then source "$HOME/.bashrc";fi
set -euo pipefail
: "${EP_SUBMIT_ROOT:?Missing submission root}" "${EP_SNAPSHOT:?Missing source snapshot}"
case "${SLURM_ARRAY_TASK_ID:?}" in
 0) export PVT=TT; export STD_DB="${STD_DB_TT:-}";;
 1) export PVT=SS; export STD_DB="${STD_DB_SS:-}";;
 *) exit 2;;
esac
PYTHON_BIN=${PYTHON_BIN:-python3}
WORK=${RESUME_WORK:-$EP_SUBMIT_ROOT/results/${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}}
export WORK
mkdir -p "$WORK"
finish() {
  rc=$?
  trap - EXIT
  echo "END exit=$rc work=$WORK"
  "$PYTHON_BIN" "$EP_SNAPSHOT/ppa/collect.py" "$WORK" || true
  exit "$rc"
}
trap finish EXIT
echo "START $(date) Node=$(hostname) PVT=$PVT WORK=$WORK SOURCE=$EP_SNAPSHOT"
"$PYTHON_BIN" "$EP_SNAPSHOT/ppa/package.py" --verify "$EP_SNAPSHOT"
source "$EP_SNAPSHOT/ppa/environment.sh"
"$PYTHON_BIN" "$EP_SNAPSHOT/ppa/run.py" --work "$WORK" --cycles "${CYCLES:-4096}"
