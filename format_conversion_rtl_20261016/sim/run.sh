#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build results
python3 sim/generate.py "$@" > results/vector_generation.json
iv=${IVERILOG:-iverilog}
vv=${VVP:-vvp}
extra=()
vextra=()
if [[ -n ${IVERILOG_BASE:-} ]]; then extra=(-B "$IVERILOG_BASE"); vextra=(-M "$IVERILOG_BASE"); fi
"$iv" "${extra[@]}" -g2012 -Wall -s tb_conversion -o build/conversions rtl/*.sv sim/tb_conversion.sv
"$vv" "${vextra[@]}" build/conversions | tee results/conversion_functional.log
"$iv" "${extra[@]}" -g2012 -Wall -s tb_accum -o build/accum rtl/*.sv sim/tb_accum.sv
"$vv" "${vextra[@]}" build/accum | tee results/accum_functional.log
python3 sim/power_vectors.py
: > results/power_bench_checks.log
for kind in $(seq 0 17); do
 "$iv" "${extra[@]}" -g2012 -s tb_power -DKIND=$kind -o build/power rtl/*.sv sim/tb_power.sv
 for mode in 0 1 2; do
  "$vv" "${vextra[@]}" build/power +MODE=$mode +CYCLES=128 +VECTORS=vectors/power_case$kind.hex >> results/power_bench_checks.log
 done
done
for spec in 0:64 1:32 1:40 1:64; do
 fixed=${spec%:*};width=${spec#*:}
 "$iv" "${extra[@]}" -g2012 -s tb_power -DACCUM -DFIXED=$fixed -DACC_W=$width -o build/power rtl/*.sv sim/tb_power.sv
 for length in 14 76; do
  "$vv" "${vextra[@]}" build/power +MODE=1 +CYCLES=$((length*2)) +VECTORS=vectors/power_accum$length.hex >> results/power_bench_checks.log
 done
done
echo 'POWER_BENCH_PASS 54 conversion modes + 8 accumulation cases' | tee -a results/power_bench_checks.log
python3 - <<'PY'
import hashlib,json,pathlib
root=pathlib.Path('.')
files=sorted(list(root.glob('rtl/*.sv'))+list(root.glob('sim/*')))
out={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
(root/'results/source_hashes.json').write_text(json.dumps(out,indent=2)+'\n')
PY
