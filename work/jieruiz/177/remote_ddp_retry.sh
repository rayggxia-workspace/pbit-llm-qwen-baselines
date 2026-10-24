#!/bin/bash
#SBATCH --job-name=and-ddp-test177
#SBATCH --partition=gpu5090
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:05:00
#SBATCH --output=/home/Hongjie_Zeng/projects/pbit-trainable-and-20261024-issue177/ddp-%j.log
set -euo pipefail
export NCCL_P2P_DISABLE=1 NCCL_DEBUG=INFO
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
ROOT=/home/Hongjie_Zeng/projects/pbit-trainable-and-20261024-issue177
cd "$ROOT/snapshot-4ab8350e"
PY=/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python
OUT="$ROOT/ddp-results-$SLURM_JOB_ID"
mkdir "$OUT"
"$PY" -m torch.distributed.run --standalone --nproc_per_node=2 \
  -m qwen3.training.stochastic_nonlinear.ddp_check "$OUT/ddp.json" > "$OUT/ddp.log" 2>&1
"$PY" - "$OUT" "$ROOT" <<'PY'
import hashlib,json,pathlib,sys
out=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
payload=dict(status='completed',code_commit='4ab8350e',source_archive_sha256=sha(root/'source-4ab8350e.tar'),
  documents={p.name:sha(p) for p in out.iterdir() if p.is_file()})
(out/'COMPLETED.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
PY
