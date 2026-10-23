#!/usr/bin/env bash
set -euo pipefail
action="${1:?cpu, gpu or summary}"
for var in PDNN_EXPECTED_USER PDNN_EXPECTED_HOME PDNN_PROJECT PDNN_SOURCE PDNN_PYTHON PDNN_MODEL PDNN_DATA PDNN_WEIGHTS PDNN_RUN PDNN_CODE_COMMIT PDNN_SRUN; do
  test -n "${!var:-}" || { echo "missing explicit profile value: $var" >&2; exit 30; }
done
test "$(id -un)" = "$PDNN_EXPECTED_USER"
actual_home="$(getent passwd "$(id -u)" | cut -d: -f6)"
test "$(realpath "$actual_home")" = "$(realpath "$PDNN_EXPECTED_HOME")"
test "$(stat -c %u "$(realpath "$actual_home")")" = "$(id -u)"
test -n "${SLURM_JOB_ID:-}"
test -x "$PDNN_SRUN"
test -x "$PDNN_PYTHON"
project="$(realpath "$PDNN_PROJECT")"
source_dir="$(realpath "$PDNN_SOURCE")"
case "$project" in "$(realpath "$actual_home")"/*) ;; *) exit 31 ;; esac
case "$source_dir" in "$project"/*) ;; *) exit 32 ;; esac
test "$(stat -c %u "$project")" = "$(id -u)"
test "$(stat -c %u "$source_dir")" = "$(id -u)"
# A venv's python may point to a public base interpreter. Check its personal
# environment prefix and bin directory, rather than rejecting that valid link.
env_bin="$(realpath "$(dirname "$PDNN_PYTHON")")"
env_prefix="$(realpath "$env_bin/..")"
case "$env_prefix" in "$(realpath "$actual_home")"/*) ;; *) exit 37 ;; esac
test "$(stat -c %u "$env_prefix")" = "$(id -u)"
test "$(stat -c %u "$env_bin")" = "$(id -u)"
case "$(realpath -m "$PDNN_RUN")" in "$project"/runs/*) ;; *) exit 33 ;; esac
test "$(stat -c %u "$PDNN_RUN")" = "$(id -u)"
export PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 TOKENIZERS_PARALLELISM=false
export TMPDIR="$project/tmp" PIP_CACHE_DIR="$project/cache/pip"
for target in "$TMPDIR" "$PIP_CACHE_DIR"; do
  resolved="$(realpath -m "$target")"
  case "$resolved" in "$project"/*) ;; *) exit 36 ;; esac
  parent="$resolved"
  while test ! -e "$parent"; do parent="$(dirname "$parent")"; done
  test "$(stat -c %u "$parent")" = "$(id -u)"
done
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR"
test "$(realpath "$TMPDIR")" = "$project/tmp"
test "$(realpath "$PIP_CACHE_DIR")" = "$project/cache/pip"
cd "$source_dir"
runner="$source_dir/experiments/pdnn20_task_accuracy_20261023/portable_runner.py"
args=(--project-root "$project" --model "$PDNN_MODEL" --task-data "$PDNN_DATA"
  --checkpoint-dir "$PDNN_WEIGHTS" --output "$PDNN_RUN"
  --config "$source_dir/experiments/pdnn20_task_accuracy_20261023/config.json"
  --code-commit "$PDNN_CODE_COMMIT")
case "$action" in
  cpu)
    export CUDA_VISIBLE_DEVICES=''
    "$PDNN_SRUN" "$PDNN_PYTHON" -m unittest experiments.pdnn_task_accuracy_20261023.test_pdnn_score experiments.pdnn20_task_accuracy_20261023.test_portable
    "$PDNN_SRUN" "$PDNN_PYTHON" -P "$source_dir/experiments/pdnn20_task_accuracy_20261023/handoff/verify_bundle.py" --root "$source_dir"
    "$PDNN_SRUN" "$PDNN_PYTHON" -P "$runner" preflight "${args[@]}"
    ;;
  gpu)
    test -n "${CUDA_VISIBLE_DEVICES:-}" || { echo 'no allocated GPU visible' >&2; exit 34; }
    "$PDNN_SRUN" "$PDNN_PYTHON" -P "$runner" smoke "${args[@]}"
    "$PDNN_SRUN" "$PDNN_PYTHON" -P "$runner" run "${args[@]}"
    "$PDNN_SRUN" /usr/bin/env CUDA_VISIBLE_DEVICES='' "$PDNN_PYTHON" -P "$runner" summarize "${args[@]}"
    ;;
  summary)
    export CUDA_VISIBLE_DEVICES=''
    "$PDNN_SRUN" "$PDNN_PYTHON" -P "$runner" summarize "${args[@]}"
    ;;
  *) echo 'unknown action' >&2; exit 35 ;;
esac
