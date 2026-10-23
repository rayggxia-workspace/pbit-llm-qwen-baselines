#!/bin/bash
#SBATCH --job-name=cwc
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
set -euo pipefail
export CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
test "$(id -un)" = Weican_Chen
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
/opt/slurm/21.08.8/bin/srun "$pbit_python" -m unittest discover -s experiments/pdnn_task_accuracy_20261023 -p 'test_pdnn_score.py' -v
/opt/slurm/21.08.8/bin/srun "$pbit_python" experiments/pdnn_task_accuracy_20261023/cpu_preflight.py --project-root "$PDNN_PROJECT" --config experiments/pdnn_task_accuracy_20261023/config.json --output "$PDNN_RUN/CPU_PREFLIGHT.json"
/opt/slurm/21.08.8/bin/srun "$pbit_python" experiments/pdnn_task_accuracy_20261023/runner.py data --project-root "$PDNN_PROJECT" --model /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/models/Qwen2.5-0.5B --task-data "$PDNN_PROJECT/data" --output "$PDNN_RUN" --config experiments/pdnn_task_accuracy_20261023/config.json --code-commit "$PDNN_COMMIT"
