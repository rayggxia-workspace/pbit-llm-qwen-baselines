#!/usr/bin/env bash
export STD_ROOT="${STD_ROOT:-/public3/home/t6s011227/ICsprout_55LLULP1225_STD_0818/ICsprout55_SC9T_BASIC_SVT/0.1}"
case "$PPA_CORNER" in
  ss) pattern='*ss*v1p08*125c*basic*nldm.db'; export STD_DB="${SS_DB:-}" ;;
  tt) pattern='*tt*v1p2*25c*basic*nldm.db'; export STD_DB="${TT_DB:-}" ;;
  *) echo 'Unsupported PVT' >&2; return 2 ;;
esac
if [[ -z $STD_DB ]]; then
    count=0
    while IFS= read -r p; do STD_DB=$p; count=$((count+1)); done < <(find "$STD_ROOT/lib" -type f -iname "$pattern" -print)
    [[ $count == 1 ]] || { echo "Set SS_DB/TT_DB explicitly; found $count libraries" >&2; return 2; }
    export STD_DB
fi
export STD_MODEL="${STD_MODEL:-$STD_ROOT/verilog/ICsprout55_9TSVT_basic.v}"
export PYTHON_BIN="${PYTHON_BIN:-python3}"
for p in "$STD_DB" "$STD_MODEL"; do
    [[ -r "$p" ]] || { echo "Required file is not readable: $p" >&2; return 2; }
done
for tool in dc_shell vcs pt_shell "$PYTHON_BIN"; do command -v "$tool" || return 2; done
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,6); print(sys.version)'
