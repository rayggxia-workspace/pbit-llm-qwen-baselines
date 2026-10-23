#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=00:45:00
#SBATCH --output=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/framework-probe-%j.out
#SBATCH --error=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/logs/framework-probe-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=""
export CONAN_CPU_COUNT="$SLURM_CPUS_PER_TASK" CMAKE_BUILD_PARALLEL_LEVEL="$SLURM_CPUS_PER_TASK"
printf 'allocated_cpus=%s conan_cpu_count=%s cmake_parallel=%s\n' "$SLURM_CPUS_PER_TASK" "$CONAN_CPU_COUNT" "$CMAKE_BUILD_PARALLEL_LEVEL"
task_root=/home/Weican_Chen/projects/tlm-cycle-issue116-20261023
export PIP_CACHE_DIR="$task_root/cache/pip" CONAN_USER_HOME="$task_root/cache/conan" TMPDIR="$task_root/tmp"
stage=preflight
mirror_pid=""
finish() {
  rc=$?
  if test -n "$mirror_pid"; then kill "$mirror_pid" 2>/dev/null || true; fi
  printf '{"job_id":"%s","stage":"%s","exit_code":%d}\n' "$SLURM_JOB_ID" "$stage" "$rc" > "$task_root/framework-probe-$SLURM_JOB_ID-terminal.json"
}
trap finish EXIT
test "$(id -un)" = Weican_Chen
test "$(realpath "$task_root")" = "$task_root"
test "$(stat -c %U "$task_root")" = Weican_Chen
test -n "$SLURM_JOB_ID"
cd "$task_root/archives"
sha256sum -c dependencies.sha256
stage=loopback_source_mirror
port_file="$task_root/framework-http-$SLURM_JOB_ID.port"
"$task_root/env-framework/bin/python" "$task_root/serve_dependencies.py" "$task_root/archives" "$port_file" &
mirror_pid=$!
for attempt in $(seq 1 30); do test -s "$port_file" && break; sleep 1; done
test -s "$port_file"
"$task_root/env-framework/bin/python" "$task_root/patch_private_mirror.py" "$SLURM_JOB_ID" "$(cat "$port_file")"
stage=dependencies
cd "$task_root/ONNXim-archive/build"
"$task_root/env-framework/bin/conan" install .. --build=missing
stage=source_extension
"$task_root/env-framework/bin/python" "$task_root/prepare_probe.py"
stage=configure
cmake .. -DCMAKE_BUILD_TYPE=Release -Dprotobuf_BUILD_TESTS=OFF \
  -DFETCHCONTENT_SOURCE_DIR_YAML-CPP="$task_root/vendor/yaml-cpp" \
  -DFETCHCONTENT_SOURCE_DIR_SPDLOG="$task_root/vendor/spdlog" \
  -DFETCHCONTENT_SOURCE_DIR_ARGPARSE="$task_root/vendor/argparse"
stage=build
cmake --build . --parallel "$SLURM_CPUS_PER_TASK"
stage=official_tests
"$task_root/ONNXim-archive/Simulator_test" --gtest_filter="SystolicWSTileExecutionTest.*:SystolicWSTwoGemmExecutionTest.*" | tee "$task_root/framework-official-tests-$SLURM_JOB_ID.txt"
stage=custom_probe
export ONNXIM_PROBE_OUTPUT="$task_root/framework-probe-$SLURM_JOB_ID-results"
"$task_root/ONNXim-archive/Simulator_test" --gtest_filter="PBitThresholdTransportProbeTest.*" | tee "$task_root/framework-custom-tests-$SLURM_JOB_ID.txt"
stage=done
