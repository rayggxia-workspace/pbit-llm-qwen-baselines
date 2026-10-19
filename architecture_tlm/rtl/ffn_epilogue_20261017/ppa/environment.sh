#!/usr/bin/env bash
export PVT="${PVT:-TT}"
export STD_ROOT="${STD_ROOT:-/public3/home/t6s011227/ICsprout_55LLULP1225_STD_0818/ICsprout55_SC9T_BASIC_SVT/0.1}"
case "$PVT" in
 TT) pattern='*tt*v1p2*25c*basic*nldm.db';;
 SS) pattern='*ss*v1p08*125c*basic*nldm.db';;
 *) echo 'PVT must be TT or SS' >&2;return 2;;
esac
if [[ -z ${STD_DB:-} ]];then
 candidates=()
 while IFS= read -r p;do candidates+=("$p");done < <(find "$STD_ROOT/lib" -type f -iname "$pattern" -print)
 [[ ${#candidates[@]} == 1 ]] || { echo "Need exactly one $PVT DB, or set STD_DB" >&2;return 2; }
 export STD_DB="${candidates[0]}"
fi
export STD_MODEL="${STD_MODEL:-$STD_ROOT/verilog/ICsprout55_9TSVT_basic.v}"
test -r "$STD_DB" && test -r "$STD_MODEL" || { echo 'Unreadable standard DB/model' >&2;return 2; }
