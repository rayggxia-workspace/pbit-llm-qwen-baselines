"""Run tests once and preserve a small reproducibility receipt (no model data)."""
import hashlib
import json
import platform
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path

import torch
from . import test_samplers


def main():
    root=Path(__file__).resolve().parents[2]
    here=Path(__file__).resolve().parent
    out=here/'results'
    out.mkdir(exist_ok=True)
    test_samplers.METRICS.clear()
    with (out/'UNITTEST.txt').open('w',encoding='utf-8',newline='\n') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromModule(test_samplers))
    sources=list(here.glob('*.py'))+[root/'experiments/pbit_sampler_qkv_20261021/samplers.py']
    receipt=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),
        source_files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        python=platform.python_version(),torch=torch.__version__,platform=platform.platform(),device='cpu',
        command='python -m experiments.trainable_pbit_attention.validate',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        metrics=test_samplers.METRICS,model=None,dataset=None,
        scope='synthetic numerical and gradient verification; no PPL, physical RNG or hardware PPA',
        artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   [out/'UNITTEST.txt',out/'TRAINING_SMOKE.json'] if p.exists()})
    with (out/'VALIDATION.json').open('w',encoding='utf-8',newline='\n') as f:
        json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps(receipt,indent=2))
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
