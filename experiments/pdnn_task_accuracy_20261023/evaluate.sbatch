#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=10:00:00
set -euo pipefail
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
test "$(id -un)" = Weican_Chen
test -n "${CUDA_VISIBLE_DEVICES:-}"
test "$(realpath "$PDNN_PROJECT")" = /home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145
case "$(realpath "$PDNN_SNAPSHOT")" in "$PDNN_PROJECT"/snapshots/*) ;; *) exit 31 ;; esac
case "$(realpath "$PDNN_RUN")" in "$PDNN_PROJECT"/runs/*) ;; *) exit 32 ;; esac
test -x /opt/slurm/21.08.8/bin/srun
export HF_HOME="$PDNN_RUN/cache/huggingface"
export HF_DATASETS_CACHE="$PDNN_RUN/cache/datasets"
export XDG_CACHE_HOME="$PDNN_RUN/cache/xdg"
export PYTHONPATH="$PDNN_SNAPSHOT"
pbit_python=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/env-eval-v4/bin/python
cd "$PDNN_SNAPSHOT"
nvidia-smi --query-gpu=index,name,uuid,memory.total --format=csv
/opt/slurm/21.08.8/bin/srun "$pbit_python" experiments/pdnn_task_accuracy_20261023/runner.py smoke --project-root "$PDNN_PROJECT" --model /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/models/Qwen2.5-0.5B --task-data "$PDNN_PROJECT/data" --output "$PDNN_RUN" --config experiments/pdnn_task_accuracy_20261023/config.json --code-commit "$PDNN_COMMIT"
/opt/slurm/21.08.8/bin/srun "$pbit_python" experiments/pdnn_task_accuracy_20261023/runner.py run --project-root "$PDNN_PROJECT" --model /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/models/Qwen2.5-0.5B --task-data "$PDNN_PROJECT/data" --output "$PDNN_RUN" --config experiments/pdnn_task_accuracy_20261023/config.json --code-commit "$PDNN_COMMIT"
