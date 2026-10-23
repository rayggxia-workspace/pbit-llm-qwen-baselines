#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=01:10:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/framework-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/framework-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
export PIP_CACHE_DIR="$root/cache/pip"
export CONAN_USER_HOME="$root/cache/conan"
export TMPDIR="$root/tmp"
export PYTHONIOENCODING=utf-8
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR" "$CONAN_USER_HOME"
cd "$root"
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$root/framework-terminal.json"' EXIT
id -un
hostname
printf 'job=%s cpus=%s cuda=%s\n' "$SLURM_JOB_ID" "$SLURM_CPUS_PER_TASK" "$CUDA_VISIBLE_DEVICES"
stage=python_environment
/home/Weican_Chen/envs/cwc-sonogym-py310/bin/python -m venv "$root/env-framework"
"$root/env-framework/bin/python" -m pip install 'conan==1.57.0'
stage=source
 git clone --filter=blob:none --no-checkout https://github.com/PSAL-POSTECH/ONNXim.git "$root/ONNXim"
cd "$root/ONNXim"
git checkout a1e86296e080fa1c82f8ad3f1b6de1079c192afc
git submodule update --init --depth 1 extern/onnx extern/protobuf extern/booksim extern/ramulator2
git rev-parse HEAD > "$root/onnxim-source.txt"
git submodule status >> "$root/onnxim-source.txt"
stage=dependencies
mkdir -p build
cd build
"$root/env-framework/bin/conan" profile new default --detect
"$root/env-framework/bin/conan" install .. --build=missing
stage=configure
cmake .. -DCMAKE_BUILD_TYPE=Release
stage=build
cmake --build . --parallel "$SLURM_CPUS_PER_TASK"
stage=official_tests
ctest --output-on-failure
stage=done
