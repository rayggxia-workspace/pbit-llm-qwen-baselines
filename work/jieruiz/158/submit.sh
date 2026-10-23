#!/bin/bash
set -euo pipefail
ROOT=/home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-nonbase-20261023-issue158
SHA="$1"
PKG_SHA="$2"
test "${#SHA}" -eq 40
SRC="$ROOT/snapshots/$SHA"
test ! -e "$ROOT/SUBMITTED.txt"
test ! -e "$SRC"
printf '%s  %s\n' "$PKG_SHA" "$ROOT/incoming/source-v1.tar.gz" | sha256sum -c -
mkdir -p "$ROOT/snapshots" "$ROOT/logs" "$ROOT/tmp"
mkdir "$SRC"
tar -xzf "$ROOT/incoming/source-v1.tar.gz" -C "$SRC"
PY=/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python
export PYTHONPATH="$SRC" PYTHONDONTWRITEBYTECODE=1
"$PY" -c 'import sys; from qwen3.baselines.support import verify_source; a=verify_source(sys.argv[1]); b=verify_source(sys.argv[1]+"/qwen3/posttrained/baseline"); assert a["commit"]==b["commit"]==sys.argv[2]; print("SOURCE_SHA_PASS", len(a["files_sha256"]))' "$SRC" "$SHA"
bash -n "$SRC/qwen3/posttrained/prepare.sbatch"
bash -n "$SRC/qwen3/posttrained/run.sbatch"
"$PY" -m qwen3.posttrained.test_contract
CPU=$(/opt/slurm/21.08.8/bin/sbatch --parsable --job-name=qwen3-158-prepare --output="$ROOT/logs/prepare-%j.log" "$SRC/qwen3/posttrained/prepare.sbatch" "$ROOT" "$SRC")
printf 'CPU=%s\nSOURCE=%s\n' "$CPU" "$SHA" > "$ROOT/SUBMITTED.txt"
GPU=$(/opt/slurm/21.08.8/bin/sbatch --parsable --job-name=qwen3-158-pilot --gres=gpu:1 --dependency="afterok:$CPU" --kill-on-invalid-dep=yes --output="$ROOT/logs/pilot-%j.log" "$SRC/qwen3/posttrained/run.sbatch" "$ROOT" "$SRC")
printf 'GPU=%s\n' "$GPU" >> "$ROOT/SUBMITTED.txt"
cat "$ROOT/SUBMITTED.txt"
