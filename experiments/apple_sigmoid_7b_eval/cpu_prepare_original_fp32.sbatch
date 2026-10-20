#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --mem=64G
#SBATCH --output=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/logs/fp32-prepare-%j.out
#SBATCH --error=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/logs/fp32-prepare-%j.err
set -euo pipefail
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
export JAX_PLATFORMS=cpu
export TF_CPP_MIN_LOG_LEVEL=2
export XDG_CACHE_HOME=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/cache
export HF_HOME="$XDG_CACHE_HOME/huggingface"
export TMPDIR=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/tmp
P=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019
S=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/source/run-v6
E="$P/env-eval-v4/bin/python"
N="$P/env-native-v4/bin/python"
for kind in sigmoid softmax; do
  if [ ! -f "$P/converted-original-fp32/$kind/config.json" ]; then
  "$E" -B "$S/convert.py" --source "/home/Weican_Chen/models/apple-sigmoid-attention-7b/$kind/step_00250000" --output "$P/converted-original-fp32/$kind" --dtype float32
  fi
  for dtype in float32; do
    "$N" -B "$S/native_reference.py" --source "/home/Weican_Chen/models/apple-sigmoid-attention-7b/$kind/step_00250000" --tokenizer /home/Weican_Chen/models/apple-sigmoid-attention-7b/tokenizer/bpe_32k_c4.model --kind "$kind" --dtype "$dtype" --weight-dtype float32 --output "$P/reports/$kind-native-original-fp32.npz"
  done
  "$E" -B "$S/preflight.py" --converted "$P/converted-original-fp32/$kind" --kind "$kind" --reference "$P/reports/$kind-native-original-fp32.npz" --output "$P/reports/$kind-cpu-original-fp32.json" --device cpu --dtype float32
done
printf "CPU_PREPARATION_COMPLETE\n"
