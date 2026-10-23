#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=00:35:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/framework-recovery-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/framework-recovery-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
export PIP_CACHE_DIR="$root/cache/pip" CONAN_USER_HOME="$root/cache/conan" TMPDIR="$root/tmp"
stage=preflight
trap 'rc=$?; printf "{\"job_id\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d}\n" "$SLURM_JOB_ID" "$stage" "$rc" > "$root/framework-recovery-terminal.json"' EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$root")" = "$root"
test -n "$SLURM_JOB_ID"
cd "$root/archives"
sha256sum -c SHA256SUMS
stage=extract
src="$root/ONNXim-archive"
mkdir "$src"
tar -xzf onnxim.tar.gz --strip-components=1 -C "$src"
for name in booksim onnx protobuf ramulator2; do
  mkdir -p "$src/extern/$name"
  tar -xzf "$name.tar.gz" --strip-components=1 -C "$src/extern/$name"
done
mkdir -p "$root/vendor"
for name in yaml-cpp spdlog argparse googletest; do
  mkdir "$root/vendor/$name"
  tar -xzf "$name.tar.gz" --strip-components=1 -C "$root/vendor/$name"
done
# Only the GoogleTest download URL is redirected to the identical local archive.
sed -i "s|https://github.com/google/googletest/archive/release-1.8.1.zip|file://$root/archives/googletest.tar.gz|" "$src/tests/CMakeLists.txt"
stage=dependencies
cd "$src"
mkdir build
cd build
"$root/env-framework/bin/conan" profile new default --detect
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
