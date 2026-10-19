#!/bin/bash
#SBATCH --job-name=llama2-ffn-precision
#SBATCH --partition=gpu5090
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=40G
#SBATCH --time=24:00:00
set -euo pipefail
: "${SLURM_JOB_ID:?}"
: "${SOURCE_COMMIT:?}"
: "${PROJECT:?}"
: "${ACTION:?}"
: "${CONFIG:?}"
: "${OUTPUT:?}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 CUBLAS_WORKSPACE_CONFIG=:4096:8
PYTHON=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
if [ "$ACTION" = test ]; then
  exec /opt/slurm/21.08.8/bin/srun "$PYTHON" -m unittest experiments.llama2_ffn_precision.test_numeric experiments.llama2_ffn_precision.test_pipeline -v
fi
extra=()
if [ "$ACTION" = evaluate ]; then
  extra+=(--calibration "$PROJECT/outputs/calibration/calibration.json")
fi
exec /opt/slurm/21.08.8/bin/srun "$PYTHON" -u experiments/llama2_ffn_precision/run.py "$ACTION" \
  --model /home/Hongjie_Zeng/pbit_llm/models/Llama-2-7b-hf \
  --identity-manifest architecture_tlm/llama2_7b/configs/model_identity.json \
  --data /home/Hongjie_Zeng/pbit_llm/data/wikitext-2/wiki.test.raw \
  --train /home/Hongjie_Zeng/pbit_llm/data/wikitext-2/wiki.train.raw \
  --config "$CONFIG" --output "$OUTPUT" "${extra[@]}"
