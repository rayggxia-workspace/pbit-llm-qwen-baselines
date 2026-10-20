#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --mem=64G
#SBATCH --output=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/logs/prep-v5-%j.out
#SBATCH --error=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/logs/prep-v5-%j.err
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
S=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/source/run-v5
E="$P/env-eval-v4/bin/python"
N="$P/env-native-v4/bin/python"
for kind in sigmoid softmax; do
  if [ ! -f "$P/converted-v2/$kind/config.json" ]; then
  "$E" -B "$S/convert.py" --source "/home/Weican_Chen/models/apple-sigmoid-attention-7b/$kind/step_00250000" --output "$P/converted-v2/$kind"
  fi
  for dtype in float32 bfloat16; do
    "$N" -B "$S/native_reference.py" --source "/home/Weican_Chen/models/apple-sigmoid-attention-7b/$kind/step_00250000" --tokenizer /home/Weican_Chen/models/apple-sigmoid-attention-7b/tokenizer/bpe_32k_c4.model --kind "$kind" --dtype "$dtype" --output "$P/reports/$kind-native-$dtype-v5.npz"
  done
  "$E" -B "$S/preflight.py" --converted "$P/converted-v2/$kind" --kind "$kind" --reference "$P/reports/$kind-native-float32-v5.npz" --output "$P/reports/$kind-cpu-parity-v5.json" --device cpu --dtype float32
done
printf "CPU_PREPARATION_COMPLETE\n"
