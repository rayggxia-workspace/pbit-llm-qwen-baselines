#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT"
PYTHON_BIN=${PYTHON_BIN:-python3}
"$PYTHON_BIN" package.py
case "${1:-smoke}" in
  smoke) indices=7,15 ;;
  all) indices=0-15 ;;
  remaining) indices=0-6,8-14 ;;
  *) indices=$1; [[ $indices =~ ^[0-9,-]+$ ]] || { echo 'Use smoke/all/remaining/array indices' >&2; exit 2; } ;;
esac
mkdir -p logs snapshots results
PPA_SOURCE=$(mktemp -d "$ROOT/snapshots/submission.XXXXXXXX")
export PPA_SOURCE
"$PYTHON_BIN" snapshot.py "$ROOT" "$PPA_SOURCE"
export PPA_ROOT="$ROOT" PYTHON_BIN
export EDA_CORES="${EDA_CORES:-4}"
sbatch --job-name=dig8_ppa --partition="${PARTITION:-v6_384}" --nodes=1 --ntasks=1 \
  --cpus-per-task="$EDA_CORES" --mem="${MEMORY:-16G}" --time="${WALLTIME:-12:00:00}" \
  --array="${indices}%${MAX_PARALLEL:-2}" --export=ALL \
  --output="$ROOT/logs/dig8-%A_%a.out" --error="$ROOT/logs/dig8-%A_%a.err" "$PPA_SOURCE/job.sh"
