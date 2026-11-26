"""Slurm-only matched PPL screening and bounded complete-WT2 continuation."""
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
sys.path.insert(0,str(PARENT))
sys.path.insert(0,str(OWN))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--phase',choices=['cpu','gpu'],required=True)
    for n in ['assets','inputs','output','old-pilot']:
        ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and not a.output.exists()
    a.output.mkdir(parents=True)
    manifest=json.loads((SOURCE/'EXECUTION_MANIFEST.json').read_bytes())
    for n,d in manifest['files'].items():
        assert hashlib.sha256((SOURCE/n).read_bytes()).hexdigest()==d,n
    sys.path.insert(0,str(a.assets/'runtime'))
    import torch
    from score_reference import score,save,sealed
    from onebit import OnebitOverride
    plan=json.loads((OWN/'PLAN.json').read_bytes())
    torch.set_num_threads(4)
    suite=unittest.TestLoader().discover(str(OWN),pattern='test_onebit.py')
    suite.addTests(unittest.TestLoader().discover(str(PARENT),pattern='test_dynamic.py'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful() and result.testsRun==9
    if a.phase=='cpu':
        save(a.output/'RESULT.json',dict(status='completed',tests=result.testsRun,source=manifest,phase='cpu'))
        return
    from driver import kernel_gate
    from reference import prepare,load_model
    from adapter import SamplingOverride
    import scale_patch
    start=time.monotonic()
    kernel=kernel_gate()
    inputs,tokens,ledger,protocol=prepare(a.inputs,a.assets/'runtime',a.output)
    old=sealed(a.old_pilot/'outputs/RESULT.json')
    assert old['status']=='completed'
    assert old['protocol']['text_sha256']==protocol['text_sha256']
    assert old['protocol']['token_sha256']==protocol['token_sha256']
    model,context,modules,parent_id=load_model(inputs,native=True)
    baseline=score(model,context,modules,tokens,ledger,list(range(292)),101,a.output/'BF16_full')
    assert baseline['targets']==299077 and abs(baseline['ppl']-11.540139)<.05
    del model,context,modules
    gc.collect();torch.cuda.empty_cache()
    model,context,modules,identity=load_model(inputs)
    assert identity==old['identity']
    original=scale_patch.ScaleOverride
    scale_patch.ScaleOverride=lambda p:original(p) if p=='lane' else OnebitOverride(p)
    import numpy as np
    ids=torch.as_tensor(np.asarray(tokens[:256],dtype=np.int64),device='cuda')[None]
    cases=[]
    for (tx,ta),grid in zip(plan['budgets'],plan['grids']):
        for policy in plan['policies']:
            cases.append(dict(id=policy+'_%d_%d'%(tx,ta),scale_policy=policy,T_x=tx,T_and=ta,
                input_law='stratified_T',and_law='joint_grid',grid_g_sig_u=grid))
    # The integer backend wrapper must reproduce the unchanged four-bin path,
    # including generator domains, sigmoid addresses and final BF16 rounding.
    for tx,ta in plan['budgets']:
        c=next(x for x in cases if x['scale_policy']=='lane' and x['T_x']==tx)
        patch=SamplingOverride(c);patch.configure(modules)
        def probe(override):
            context.seed=101;context.begin(0,0,domain='onebit-wrapper-equivalence')
            with patch,override,torch.no_grad():return model(ids,use_cache=False).logits.detach().clone()
        expected=probe(nullcontext())
        actual=probe(OnebitOverride('equivalent_four'))
        assert torch.equal(expected,actual),(tx,ta)
        del expected,actual
    del ids
    save(a.output/'GATE.json',dict(status='completed',cpu_tests=9,kernel_gate=kernel,
        wrapper_four_bin_logits_bitwise=True,budgets=plan['budgets'],identity=identity,
        baseline_full_WT2=baseline,protocol=protocol,source=manifest))
    rows=[]
    for case in cases:
        z=score(model,context,modules,tokens,ledger,plan['pilot_windows'],101,a.output/'pilot'/case['id'],case)
        if case['scale_policy']=='lane':
            previous=next(x['result'] for x in old['results'] if x['case']['id']==case['id'])
            assert z['records_sha256']==previous['records_sha256'],'Fresh lane pilot differs from sealed control'
        rows.append(dict(case=case,result=z))
        save(a.output/'PROGRESS.json',dict(status='pilot_running',rows=rows))
    save(a.output/'PILOT_SUMMARY.json',dict(status='completed',scope='8-window single-seed screening',rows=rows,
         protocol=protocol,identity=identity,baseline_full_WT2=baseline,old_lane_pilot_bitwise_records=True))
    print(json.dumps(dict(event='pilot_completed',rows=[dict(case=x['case']['id'],ppl=x['result']['ppl']) for x in rows])),flush=True)
    selected=[]
    for tx,ta in plan['budgets']:
        control=next(x for x in rows if x['case']['scale_policy']=='lane' and x['case']['T_x']==tx)
        candidates=[x for x in rows if x['case']['scale_policy'] in ['gu_onebit64','all64_onebit'] and x['case']['T_x']==tx]
        best=min(candidates,key=lambda x:x['result']['ppl'])
        eligible=best['result']['ppl']<=1.10*control['result']['ppl']
        selected.append(dict(case=best['case'],pilot_ppl=best['result']['ppl'],control_ppl=control['result']['ppl'],run_full=eligible,
                             trigger_is_resource_selection_not_quality_acceptance=True))
    save(a.output/'FULL_SELECTION.json',selected)
    full=[]
    for choice in selected:
        if not choice['run_full']:continue
        case=choice['case']
        for seed in plan['full_seeds']:
            z=score(model,context,modules,tokens,ledger,list(range(292)),seed,a.output/'full'/case['id']/('seed%d'%seed),case)
            full.append(dict(case=case,result=z))
            save(a.output/'FULL_PROGRESS.json',dict(status='running',results=full,selection=selected))
    save(a.output/'RESULT.json',dict(status='completed',source=manifest,protocol=protocol,identity=identity,
         parent_identity=parent_id,baseline_full_WT2=baseline,pilot=rows,selection=selected,full=full,
         wrapper_four_bin_logits_bitwise=True,old_lane_pilot_bitwise_records=True,
         full_lane_controls='Existing immutable 3-seed complete WT2, reference identity and pilot WINDOW bytes revalidated; not rerun here',
         accuracy_tasks_run=False,no_training=True,no_PPA=True,
         versions={n:importlib.metadata.version(n) for n in ['torch','triton','transformers','numpy']},
         peak_allocated_GiB=torch.cuda.max_memory_allocated()/2**30,
         seconds=time.monotonic()-start,slurm_job=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':main()
