#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
"$PYTHON_BIN" "$ROOT/ppa/package.py" --verify "$ROOT"
case "${1:-all}" in
 all) ARRAY=0-1;;
 TT) ARRAY=0;;
 SS) ARRAY=1;;
 *) echo 'Usage: bash ppa/submit.sh [all|TT|SS]' >&2;exit 2;;
esac
mkdir -p "$ROOT/snapshots" "$ROOT/logs" "$ROOT/results"
SNAP=$(mktemp -d "$ROOT/snapshots/submission.XXXXXXXX")
export EP_SUBMIT_ROOT="$ROOT" EP_SNAPSHOT="$SNAP" PYTHON_BIN
"$PYTHON_BIN" "$ROOT/ppa/snapshot.py" "$ROOT" "$SNAP"
sbatch --job-name=ffn_ppa100 --partition="${PARTITION:-v6_384}" \
  --nodes=1 --ntasks=1 --cpus-per-task="${CPUS:-4}" --mem="${MEMORY:-8G}" \
  --time="${JOB_TIME:-08:00:00}" --array="$ARRAY%2" \
  --output="$ROOT/logs/ppa-%A_%a.out" --error="$ROOT/logs/ppa-%A_%a.err" \
  --export=ALL "$SNAP/ppa/job.sh"
