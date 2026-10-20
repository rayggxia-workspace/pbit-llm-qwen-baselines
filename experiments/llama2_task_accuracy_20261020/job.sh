#!/bin/bash
set -euo pipefail
export PATH=/opt/slurm/21.08.8/bin:$PATH
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$SNAPSHOT"
cd "$SNAPSHOT"
PY=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
ARGS=(--model /home/Hongjie_Zeng/pbit_llm/models/Llama-2-7b-hf
 --identity-manifest /home/Hongjie_Zeng/projects/pbit-llama2-7b-20261017-issue14/model_identity.json
 --data /home/Hongjie_Zeng/pbit_llm/data/wikitext-2/wiki.test.raw
 --task-data /home/Hongjie_Zeng/pbit_llm/data/full_benchmarks
 --project-root "$PROJECT" --output "$OUTPUT" --code-commit "$SOURCE_COMMIT" --batch 4)
case "$ACTION" in
 cpu)
  "$PY" -B -m unittest experiments.llama2_task_accuracy_20261020.test_adapter -v
  "$PY" -B -m experiments.llama2_task_accuracy_20261020.run data "${ARGS[@]}"
  ;;
 prepare) "$PY" -B -m experiments.llama2_task_accuracy_20261020.run prepare "${ARGS[@]}" ;;
 worker) "$PY" -B -m experiments.llama2_task_accuracy_20261020.run worker "${ARGS[@]}" --index "$SLURM_ARRAY_TASK_ID" ;;
 *) exit 2;;
esac
