"""Run the numerical, native Qwen3 and hardware gates without touching CUDA."""
import argparse
import json
import os
from pathlib import Path
import sys
import unittest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='' or not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('CPU-only allocation required')
    import torch,transformers
    if transformers.__version__!='4.51.3':
        raise RuntimeError('native gates require pinned Transformers 4.51.3')
    torch.set_num_threads(4)
    suite=unittest.defaultTestLoader.loadTestsFromNames([
        'qwen3.sparq.test_core','qwen3.sparq.test_scoring','qwen3.sparq.test_run',
        'architecture_tlm.sparq_baseline.test_ledger'])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    passed=result.wasSuccessful() and not result.skipped and not torch.cuda.is_initialized()
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(passed=passed,tests=result.testsRun,
        skipped=result.skipped,failures=result.failures,errors=result.errors,
        job=os.environ['SLURM_JOB_ID'],torch=torch.__version__,transformers=transformers.__version__,
        cuda_initialized=torch.cuda.is_initialized()),default=str,indent=2)+'\n',encoding='utf-8')
    if not passed: sys.exit(1)


if __name__=='__main__':main()
