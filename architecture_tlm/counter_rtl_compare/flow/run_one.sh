#!/usr/bin/env bash
set -euo pipefail
# Usage: bash flow/run_one.sh A ss 1 32 1 /absolute/new/result
[[ $# == 6 ]] || { echo 'A|B ss|tt M T PIPE /absolute/new/result' >&2; exit 2; }
case "$1" in A) export SC_ARCH=0;;B)export SC_ARCH=1;;*)exit 2;;esac
export PPA_CORNER=$2 SC_M=$3 SC_T=$4 SC_PIPE=$5
export SC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PPA_SOURCE="$SC_ROOT/flow" EDA_CORES="${EDA_CORES:-4}" SC_PERIOD_NS="${SC_PERIOD_NS:-10}"
source "$PPA_SOURCE/environment.sh"
exec "$PYTHON_BIN" "$PPA_SOURCE/run.py" --out "$6"
