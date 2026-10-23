#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=00:35:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/framework-gcc13-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/framework-gcc13-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
export PIP_CACHE_DIR="$root/cache/pip" CONAN_USER_HOME="$root/cache/conan" TMPDIR="$root/tmp"
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$root/framework-gcc13-terminal.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$root")" = "$root"
test -n "$SLURM_JOB_ID"
# Extend only this task's private Conan compiler whitelist to the actual GCC.
# The compiler is still honestly reported as GCC 13, never relabeled GCC 12.
"$root/env-framework/bin/python" - <<'PY'
import os
from pathlib import Path
import yaml
p=Path(os.environ['CONAN_USER_HOME'])/'.conan/settings.yml'
data=yaml.safe_load(p.read_text())
versions=data['compiler']['gcc']['version']
if '13' not in versions: versions.append('13')
p.write_text(yaml.safe_dump(data,sort_keys=False),encoding='utf-8')
PY
stage=dependencies
cd "$root/ONNXim-archive/build"
"$root/env-framework/bin/conan" install .. --build=missing
stage=configure
cmake .. -DCMAKE_BUILD_TYPE=Release -Dprotobuf_BUILD_TESTS=OFF \
  -DFETCHCONTENT_SOURCE_DIR_YAML-CPP="$root/vendor/yaml-cpp" \
  -DFETCHCONTENT_SOURCE_DIR_SPDLOG="$root/vendor/spdlog" \
  -DFETCHCONTENT_SOURCE_DIR_ARGPARSE="$root/vendor/argparse"
stage=build
cmake --build . --parallel "$SLURM_CPUS_PER_TASK"
stage=official_tests
ctest --output-on-failure
stage=done
