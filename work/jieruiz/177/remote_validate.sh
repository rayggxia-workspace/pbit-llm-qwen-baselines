#!/bin/bash
#SBATCH --job-name=and-train-test177
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --output=/home/Hongjie_Zeng/projects/pbit-trainable-and-20261024-issue177/validate-%j.log
set -euo pipefail
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
ROOT=/home/Hongjie_Zeng/projects/pbit-trainable-and-20261024-issue177
cd "$ROOT/snapshot-a3f5a4ac"
PY=/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python
OUT="$ROOT/results-$SLURM_JOB_ID"
mkdir "$OUT"
"$PY" -m unittest qwen3.and_direct.test_core qwen3.and_direct.test_multiscale qwen3.and_direct.test_short qwen3.training.stochastic_nonlinear.test_training -v > "$OUT/tests.txt" 2>&1
"$PY" -m qwen3.training.stochastic_nonlinear.gpu_check "$OUT/tiny_qwen3.json" > "$OUT/tiny_qwen3.log" 2>&1
"$PY" -m qwen3.training.stochastic_nonlinear.smoke --device cuda --out "$OUT/gpu_smoke.json" > "$OUT/gpu_smoke.log" 2>&1
"$PY" - "$OUT" "$ROOT" <<'PY'
import hashlib,json,pathlib,subprocess,sys,torch
out=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
payload=dict(status='completed',code_commit='a3f5a4ac',
  source_archive_sha256=sha(root/'source-a3f5a4ac.tar'),
  torch=str(torch.__version__),gpu=torch.cuda.get_device_name(),
  documents={p.name:sha(p) for p in out.iterdir() if p.is_file()},
  source_files={str(p):sha(p) for p in pathlib.Path('qwen3').rglob('*.py')})
(out/'COMPLETED.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
PY
