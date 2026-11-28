"""One single-GPU, single-seed PPL pilot comparing S/S2 with frozen S/S4."""
import argparse
from contextlib import nullcontext
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import unittest

OWN=Path(__file__).resolve().parent
SOURCE=OWN.parents[1]
PARENT=OWN.parent/'t64_dynamic_scale_20261125'
ONEBIT=OWN.parent/'t64_group64_onebit_20261126'
sys.path[:0]=[str(OWN),str(PARENT),str(ONEBIT)]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['cpu','gpu'],required=True)
    for n in ['assets','inputs','output','old-pilot']:ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();assert os.environ.get('SLURM_JOB_ID') and not a.output.exists()
    a.output.mkdir(parents=True)
    manifest=json.loads((SOURCE/'EXECUTION_MANIFEST.json').read_bytes())
    for n,d in manifest['files'].items():assert hashlib.sha256((SOURCE/n).read_bytes()).hexdigest()==d,n
    sys.path.insert(0,str(a.assets/'runtime'))
    import torch
    from score_reference import save,sealed,score
    from half import FractionOverride
    from onebit import OnebitOverride
    torch.set_num_threads(4)
    suite=unittest.TestLoader().discover(str(OWN),pattern='test_half.py')
    suite.addTests(unittest.TestLoader().discover(str(ONEBIT),pattern='test_onebit.py'))
    suite.addTests(unittest.TestLoader().discover(str(PARENT),pattern='test_dynamic.py'))
    tested=unittest.TextTestRunner(verbosity=2).run(suite)
    assert tested.wasSuccessful() and tested.testsRun==14
    if a.phase=='cpu':
        save(a.output/'RESULT.json',dict(status='completed',tests=14,source=manifest,phase='CPU Slurm no GPU'))
        return
    cpu=sealed(a.output.parent/'cpu/RESULT.json')
    assert cpu['status']=='completed' and cpu['source']==manifest and cpu['tests']==14
    from reference import prepare,load_model
    from driver import kernel_gate
    from adapter import SamplingOverride
    import scale_patch
    plan=json.loads((OWN/'PLAN.json').read_bytes())
    started=time.monotonic();integer=kernel_gate()
    inputs,tokens,ledger,protocol=prepare(a.inputs,a.assets/'runtime',a.output)
    old=sealed(a.old_pilot/'outputs/PILOT_SUMMARY.json')
    assert old['status']=='completed'
    assert old['protocol']['text_sha256']==protocol['text_sha256']
    assert old['protocol']['token_sha256']==protocol['token_sha256']
    model,context,modules,parent_id=load_model(inputs,native=True)
    baseline=score(model,context,modules,tokens,ledger,list(range(292)),101,a.output/'BF16_full')
    assert baseline['targets']==299077 and abs(baseline['ppl']-11.540139)<.05
    del model,context,modules;gc.collect();torch.cuda.empty_cache()
    model,context,modules,identity=load_model(inputs);assert identity==old['identity']
    cases=[]
    for (tx,ta),grid in zip(plan['budgets'],plan['grids']):
        for policy in plan['policies']:
            for step in plan['step_bits']:
                cases.append(dict(id=f'S{1<<step}_{policy}_{tx}_{ta}',scale_policy=policy,step_bits=step,
                    T_x=tx,T_and=ta,input_law='stratified_T',and_law='joint_grid',grid_g_sig_u=grid))
    import numpy as np
    ids=torch.as_tensor(np.asarray(tokens[:256],dtype=np.int64),device='cuda')[None]
    for c in [x for x in cases if x['step_bits']==2]:
        p=SamplingOverride(c);p.configure(modules)
        def probe(extra):
            context.seed=101;context.begin(0,0,domain='onebit-half-wrapper-equivalence')
            with p,extra,torch.no_grad():return model(ids,use_cache=False).logits.detach().clone()
        expected=probe(OnebitOverride(c['scale_policy']))
        actual=probe(FractionOverride(c['scale_policy'],2))
        assert torch.equal(expected,actual),c['id']
        half1=probe(FractionOverride(c['scale_policy'],1))
        half2=probe(FractionOverride(c['scale_policy'],1))
        assert torch.equal(half1,half2),c['id']
        del expected,actual,half1,half2
    del ids
    save(a.output/'GATE.json',dict(status='completed',cpu_tests=14,integer_kernel_oracle=integer,
         S4_wrapper_logits_bitwise=True,S2_repeat_logits_bitwise=True,baseline_full=baseline,
         identity=identity,protocol=protocol,source=manifest))
    rows=[]
    for c in cases:
        scale_patch.ScaleOverride=lambda policy:FractionOverride(policy,c['step_bits'])
        z=score(model,context,modules,tokens,ledger,plan['pilot_windows'],101,a.output/c['id'],c)
        if c['step_bits']==2:
            ref=next(x['result'] for x in old['rows'] if x['case']['scale_policy']==c['scale_policy'] and x['case']['T_x']==c['T_x'])
            assert z['records_sha256']==ref['records_sha256'],'Fresh S4 pilot differs from frozen S4'
        rows.append(dict(case=c,result=z))
        save(a.output/'PROGRESS.json',dict(status='running',rows=rows))
    save(a.output/'RESULT.json',dict(status='completed',scope='8-window PPL pilot only',rows=rows,
         source=manifest,protocol=protocol,identity=identity,parent_identity=parent_id,baseline_full=baseline,
         old_S4_records_bitwise=True,no_training=True,no_task_accuracy=True,no_PPA=True,
         versions={n:importlib.metadata.version(n) for n in ['torch','triton','transformers','numpy']},
         seconds=time.monotonic()-started,slurm_job=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':main()
