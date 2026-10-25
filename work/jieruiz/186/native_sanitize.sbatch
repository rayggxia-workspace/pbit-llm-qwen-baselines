#!/bin/bash
#SBATCH --job-name=pbit186-native-asan
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
TASK=/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/native_sanitize
mkdir -p "$TASK/tmp"
export TMPDIR="$TASK/tmp"
cd /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/native_v3/build
g++ -std=c++20 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -DFMT_HEADER_ONLY -Isrc -Ideps/spdlog/include -Ideps/json/include -Ideps/robin/include probe.cc src/Core.cc src/Sram.cc src/SystolicWS.cc src/SystolicOS.cc -o "$TASK/probe" -pthread
"$TASK/probe" "$TASK/RESULT.json"
python3 - <<'PY'
import pathlib,json,hashlib
p=pathlib.Path('/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/native_sanitize')
r=json.loads((p/'RESULT.json').read_text());old=json.loads((p.parent/'native_v3/build/RESULT.json').read_text())
assert r==old
(p/'MANIFEST.json').write_text(json.dumps(dict(status='completed',scope='ASan/UBSan recheck of unchanged native probe; 25 cases byte-equivalent JSON values',files={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ('RESULT.json','probe')}),indent=2)+'\n')
PY
