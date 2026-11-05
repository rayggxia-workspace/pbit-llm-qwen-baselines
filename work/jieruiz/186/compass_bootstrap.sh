#!/bin/bash
#SBATCH --job-name=compass-186-setup
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:15:00
set -euo pipefail
TASK=/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/compass_2e015fd2
cd "$TASK"
PY=/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python
mkdir -p deps
"$PY" -m pip install --disable-pip-version-check --no-deps --target deps scalesim==2.0.2
"$PY" - <<'PY'
import urllib.request, tarfile, io, hashlib, json
from pathlib import Path
sha='2e015fd2ee750e6cad8d7152df52551e5b41ef20'
p=Path('upstream'); p.mkdir(exist_ok=False)
url=f'https://codeload.github.com/PrincetonUniversity/LLMCompass/tar.gz/{sha}'
data=urllib.request.urlopen(url, timeout=120).read()
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tf:
 for m in tf.getmembers():
  parts=Path(m.name).parts[1:]
  if not parts:continue
  dst=p.joinpath(*parts)
  assert dst.resolve().is_relative_to(p.resolve())
  if m.isdir():dst.mkdir(parents=True,exist_ok=True)
  elif m.isfile():
   dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(tf.extractfile(m).read())
  else:raise ValueError('unsupported archive entry')
files={str(x.relative_to(p)):hashlib.sha256(x.read_bytes()).hexdigest() for x in p.rglob('*') if x.is_file()}
Path('UPSTREAM.json').write_text(json.dumps(dict(commit=sha,url=url,archive_sha256=hashlib.sha256(data).hexdigest(),files=files),indent=2)+'\n')
print('downloaded',len(data),'bytes',len(files),'files')
PY
PYTHONPATH="$TASK/deps:$TASK/upstream" "$PY" - <<'PY'
import torch,numpy,pandas,scalesim,scipy,importlib.metadata,json,sys
from pathlib import Path
from software_model.matmul import Matmul
from hardware_model.device import device_dict
from software_model.utils import Tensor,data_type_dict
op=Matmul(data_type_dict['fp16']);op(Tensor([1,2560]),Tensor([2560,4096]))
lat=op.compile_and_simulate(device_dict['A100_80GB_fp16'],'heuristic-GPU')
env=dict(python=sys.version,packages={x:importlib.metadata.version(x) for x in ['torch','numpy','pandas','scipy','scalesim']},gpu_used=False,smoke_seconds=lat)
Path('ENVIRONMENT.json').write_text(json.dumps(env,indent=2)+'\n');print(env)
PY
