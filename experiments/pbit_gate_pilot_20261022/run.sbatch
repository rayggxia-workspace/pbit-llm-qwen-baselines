#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:25:00
set -euo pipefail
test "$(id -un)" = Weican_Chen
test -n "${SLURM_JOB_ID:-}"
test -d "$GATE_SNAPSHOT"
test -f "$GATE_CONFIG"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$GATE_SNAPSHOT"
cd "$GATE_SNAPSHOT"
if [ "$GATE_STAGE" = cpu_preflight ]; then
  export CUDA_VISIBLE_DEVICES=""
  "$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.preflight --config "$GATE_CONFIG" --output "$GATE_OUTPUT"
elif [ "$GATE_STAGE" = cpu_tests ]; then
  export CUDA_VISIBLE_DEVICES=""
  mkdir -p "$GATE_OUTPUT"
  "$GATE_PYTHON" -P -u -m unittest discover -s experiments/pbit_gate_pilot_20261022 -p 'test_*.py' -v
elif [ "$GATE_STAGE" = gpu_pilot ]; then
  "$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.run --config "$GATE_CONFIG" --output "$GATE_OUTPUT"
elif [ "$GATE_STAGE" = cpu_selection ]; then
  export CUDA_VISIBLE_DEVICES=""
  "$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.selection_preflight --config "$GATE_CONFIG" --output "$GATE_OUTPUT"
elif [ "$GATE_STAGE" = gpu_optimize ]; then
  "$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.optimize_driver --config "$GATE_CONFIG" --output "$GATE_OUTPUT"
elif [ "$GATE_STAGE" = gpu_refine ]; then
  "$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.refine_driver --config "$GATE_CONFIG" --output "$GATE_OUTPUT"
elif [ "$GATE_STAGE" = gpu_baseline_ext ]; then
  "$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.baseline_driver --config "$GATE_CONFIG" --output "$GATE_OUTPUT"
elif [ "$GATE_STAGE" = gpu_blind ]; then
  "$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.blind_driver --config "$GATE_CONFIG" --output "$GATE_OUTPUT"
elif [ "$GATE_STAGE" = cpu_freeze ]; then
  export CUDA_VISIBLE_DEVICES=""
  "$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.freeze_driver --config "$GATE_CONFIG" --output "$GATE_OUTPUT"
elif [ "$GATE_STAGE" = cpu_package ]; then
  export CUDA_VISIBLE_DEVICES=""
  "$GATE_PYTHON" -P -u -m experiments.pbit_gate_pilot_20261022.package_optimization --config "$GATE_CONFIG" --output "$GATE_OUTPUT"
else
  exit 2
fi
