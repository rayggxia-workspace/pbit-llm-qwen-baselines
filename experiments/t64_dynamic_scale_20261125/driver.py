"""Single-seed T64 pilot; dynamic block scales, accurate Attention, frozen W8."""
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


def kernel_gate():
    import torch
    from wide_wd import shifted_output
    rows=[]
    for r in [6,12,15,29]:
        gen=torch.Generator().manual_seed(17+r)
        c=torch.randint(129,(4,64),generator=gen)
        s=torch.randint(2,(4,64),generator=gen)*2-1
        h=torch.randint(r+1,(4,64),generator=gen)
        w=torch.randint(-127,128,(64,64),generator=gen).to(torch.int16)
        coeff=torch.ones((1,1),dtype=torch.int64)
        expected=((c<<(r-h))*s)@w.long().T
        actual=shifted_output(c.cuda(),s.cuda(),h.cuda(),w.cuda(),coeff.cuda(),128,r)
        assert torch.equal(actual.cpu(),expected),r
        rows.append(dict(alignment=r,integer_oracle_exact=True))
    return rows


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--assets',type=Path,required=True)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and not a.output.exists()
    a.output.mkdir(parents=True)
    own=Path(__file__).parent
    manifest=json.loads((own/'EXECUTION_MANIFEST.json').read_bytes())
    def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    for n,d in manifest['files'].items():assert sha(own/n)==d,n
    sys.path.insert(0,str(a.assets/'runtime'))
    import unittest
    import torch
    from score_reference import score,save,snapshot
    from reference import prepare,load_model
    from adapter import SamplingOverride
    import scale_patch
    from dynamic import DynamicOverride
    original_scale=scale_patch.ScaleOverride
    scale_patch.ScaleOverride=lambda policy:DynamicOverride(int(policy[7:])) if policy.startswith('dynamic') else original_scale(policy)
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(own),pattern='test_*.py'))
    assert tests.wasSuccessful() and tests.testsRun==4
    started=time.monotonic()
    inputs,tokens,ledger,protocol=prepare(a.inputs,a.assets/'runtime',a.output)
    kg=kernel_gate()
    model,context,modules,parent_id=load_model(inputs,native=True)
    baseline=score(model,context,modules,tokens,ledger,list(range(292)),101,a.output/'BF16_full')
    assert baseline['targets']==299077 and abs(baseline['ppl']-11.540139)<.05
    del model,context,modules;gc.collect();torch.cuda.empty_cache()
    model,context,modules,identity=load_model(inputs)
    assert identity['checkpoint_case']=='T64' and identity['trained_tokens']==100000000
    import numpy as np
    ids=torch.as_tensor(np.asarray(tokens[:256],dtype=np.int64),device='cuda')[None]
    context.seed=101
    def probe(patch):
        context.begin(0,0,domain='dynamic-native-noop')
        with patch,torch.no_grad():return model(ids,use_cache=False).logits.detach().clone()
    logits=probe(nullcontext());assert torch.equal(logits,probe(original_scale('lane')))
    del logits,ids
    windows=[0,41,83,125,166,208,250,290]
    results=[]
    def run(policy,tx,ta):
        case=dict(id=policy+'_%d_%d'%(tx,ta),scale_policy=policy,T_x=tx,T_and=ta,
                  input_law='stratified_T',and_law='joint_grid',grid_g_sig_u=[4,2,4] if ta==32 else [8,2,8])
        r=score(model,context,modules,tokens,ledger,windows,101,a.output/case['id'],case)
        row=dict(case=case,result=r)
        results.append(row)
        save(a.output/'PROGRESS.json',dict(status='running',results=results,baseline=baseline))
        return r
    controls={}
    for tx,ta in [(16,32),(64,128)]:
        controls[(tx,ta)]=run('lane',tx,ta)
        run('group64',tx,ta)
    dynamic=[]
    for tx,ta in [(16,32),(64,128)]:dynamic.append((tx,ta,run('dynamic64',tx,ta)))
    # 5% is a scheduling trigger for the small follow-up, not an acceptance criterion.
    followup=any(r['ppl']>1.05*controls[(tx,ta)]['ppl'] for tx,ta,r in dynamic)
    if followup:
        for group in [32,16]:
            for tx,ta in [(16,32),(64,128)]:run('dynamic'+str(group),tx,ta)
    result=dict(status='completed',scope='single-seed eight-window full-context WT2 pilot;not full WT2',
                source=manifest,protocol=protocol,identity=identity,parent_identity=parent_id,
                original_lane_noop_bitwise=True,cpu_tests=tests.testsRun,kernel_gate=kg,
                baseline_full_WT2=baseline,seed=101,windows=windows,results=results,
                fallback_triggered=followup,threshold_is_not_quality_acceptance=True,
                versions={n:importlib.metadata.version(n) for n in ['torch','triton','transformers','numpy']},
                peak_allocated_GiB=torch.cuda.max_memory_allocated()/2**30,
                slurm_job=os.environ['SLURM_JOB_ID'],seconds=time.monotonic()-started)
    save(a.output/'RESULT.json',result)
    print(json.dumps(dict(status='completed',seconds=result['seconds'])),flush=True)


if __name__=='__main__':main()
