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
export PYTHONOPTIMIZE=0
test "$(id -un)" = Weican_Chen
test "$(realpath "$PDNN20_PROJECT")" = /home/Weican_Chen/projects/pbit-pdnn20-task-accuracy-issue151
case "$(realpath "$PDNN20_SNAPSHOT")" in "$PDNN20_PROJECT"/snapshots/*) ;; *) exit 31 ;; esac
case "$(realpath "$PDNN20_RUN")" in "$PDNN20_PROJECT"/runs/*) ;; *) exit 32 ;; esac
case "$(realpath -m "$PDNN20_CHECKPOINT_DIR")" in /home/Weican_Chen/*) ;; *) exit 33 ;; esac
mkdir -p "$PDNN20_PROJECT/tmp"
export TMPDIR="$PDNN20_PROJECT/tmp"
export PYTHONPATH="$PDNN20_SNAPSHOT"
test -x /opt/slurm/21.08.8/bin/srun
pbit_python=/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019/env-eval-v4/bin/python
cd "$PDNN20_SNAPSHOT"
/opt/slurm/21.08.8/bin/srun "$pbit_python" -m unittest discover -s experiments/pdnn_task_accuracy_20261023 -p test_pdnn_score.py -v
if test -f experiments/pdnn20_task_accuracy_20261023/test_preflight.py; then
 /opt/slurm/21.08.8/bin/srun "$pbit_python" -m unittest discover -s experiments/pdnn20_task_accuracy_20261023 -p test_preflight.py -v
fi
pbit_inspect=()
case "${PDNN20_INSPECT_ONLY:-0}" in
 0) ;;
 1) pbit_inspect=(--inspect-only) ;;
 *) exit 34 ;;
esac
/opt/slurm/21.08.8/bin/srun "$pbit_python" experiments/pdnn20_task_accuracy_20261023/runner.py preflight --project-root "$PDNN20_PROJECT" --model /home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/models/Qwen2.5-0.5B --task-data /home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145/data --reference-run /home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145/runs/f4eb25e53834_20261023T124307Z --checkpoint-dir "$PDNN20_CHECKPOINT_DIR" --output "$PDNN20_RUN" --config experiments/pdnn20_task_accuracy_20261023/config.json --code-commit "$PDNN20_COMMIT" "${pbit_inspect[@]}"
