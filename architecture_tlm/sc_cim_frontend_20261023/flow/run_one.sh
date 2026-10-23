#!/usr/bin/env bash
set -euo pipefail
# KIND ss|tt M /absolute/new/result. N=64; override T/K/EXT via environment.
[[ $# == 4 ]] || { echo 'KIND(0..3) ss|tt M /absolute/new/result'; exit 2; }
export CIM_ROOT="$(cd "$(dirname "$0")/.." && pwd)" CIM_KIND=$1 PPA_CORNER=$2 CIM_M=$3
export CIM_N="${CIM_N:-64}" CIM_T="${CIM_T:-32}" CIM_K="${CIM_K:-32}" CIM_EXT="${CIM_EXT:-0}"
export LOAD_PF="${LOAD_PF:-0.002}" INPUT_SLEW_NS="${INPUT_SLEW_NS:-0.1}"
export PPA_SOURCE="$CIM_ROOT/flow"
: "${STD_DB:?absolute SS or TT standard-cell .db required}"
: "${STD_MODEL:?matching standard-cell Verilog model required}"
: "${BUF_REF:?set actual non-inverting buffer cell, e.g. verified library BUF reference}"
exec "${PYTHON_BIN:-python3}" "$PPA_SOURCE/run.py" --out "$4"
