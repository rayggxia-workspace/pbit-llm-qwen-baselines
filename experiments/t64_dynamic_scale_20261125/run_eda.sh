#!/bin/bash
set -euo pipefail
PROJECT=$1
module load deepmdkit/v3.2.0b0_pt_4090_5090
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
NODE_ROOT=/tmp/zhj/$USER/t64_dynamic225_$SLURM_JOB_ID
mkdir -p "$NODE_ROOT/assets" "$NODE_ROOT/tmp" "$NODE_ROOT/triton" "$NODE_ROOT/overlay"
export TMPDIR=$NODE_ROOT/tmp TRITON_CACHE_DIR=$NODE_ROOT/triton
python - "$PROJECT" "$NODE_ROOT" <<'PY'
from pathlib import Path
import json,os,shutil,socket,sys
p,r=Path(sys.argv[1]),Path(sys.argv[2])
assert r.is_absolute() and r.parent.name==os.environ['USER']
data=dict(status='waiting_for_assets',job=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),
          node_root=str(r),python=sys.executable,free_bytes=shutil.disk_usage(r).free,
          visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'))
assert data['free_bytes']>25*1024**3
(p/'NODE_READY.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data),flush=True)
PY
python -m pip install --no-index --find-links "$PROJECT/wheels" --target "$NODE_ROOT/overlay" --no-cache-dir transformers==4.51.3
export PYTHONPATH=$NODE_ROOT/overlay${PYTHONPATH:+:$PYTHONPATH}
python - "$PROJECT" <<'PY'
import json,sys,torch,transformers,triton
from pathlib import Path
d=dict(status='imports_passed',torch=torch.__version__,transformers=transformers.__version__,
       triton=triton.__version__,python=sys.version)
(Path(sys.argv[1])/'ENVIRONMENT.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps(d),flush=True)
PY
for attempt in $(seq 1 1440); do
    if test -f "$NODE_ROOT/ASSETS_READY.json"; then break; fi
    sleep 5
done
test -f "$NODE_ROOT/ASSETS_READY.json"
python -B "$PROJECT/source/driver.py" --assets "$NODE_ROOT/assets" --inputs "$NODE_ROOT/INPUTS.json" --output "$PROJECT/results_$SLURM_JOB_ID"
