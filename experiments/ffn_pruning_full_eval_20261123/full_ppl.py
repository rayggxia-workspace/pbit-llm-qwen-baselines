"""Single-seed full WT2 with unchanged frozen pruning and matched controls."""
from contextlib import ExitStack
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser()
    for name in ['inputs','runtime','helpers','reference-source','mild-source','mild-gate','calibration','old-screen-root','output']:
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--case',required=True)
    a=ap.parse_args()
    if a.output.exists():raise FileExistsError('immutable output exists')
    a.output.mkdir(parents=True);(a.output/'data_protocol').mkdir()
    root=Path(__file__).parent
    plan=json.loads((root/'PLAN.json').read_bytes())
    own=json.loads((root/'EXECUTION_MANIFEST.json').read_bytes())
    for name,digest in own['files'].items():assert sha(root/name)==digest,name
    sys.path[1:1]=[str(a.mild_source),str(a.helpers),str(a.runtime),str(a.reference_source)]
    import torch
    import torch.nn.functional as F
    import run_quality as rq
    from run_wt2 import prepare,load_model
    from adapter import SamplingOverride
    from pruning import PrunedGU
    assert sha(a.mild_source/'EXECUTION_MANIFEST.json')==plan['mild_manifest_sha256']
    mild=json.loads((a.mild_source/'EXECUTION_MANIFEST.json').read_bytes())
    for name,digest in mild['files'].items():assert sha(a.mild_source/name)==digest,name
    reference=rq.verify_source(a.reference_source)
    assert reference['manifest_sha256']==plan['reference_manifest_sha256']
    gate=rq.verify_sealed(a.mild_gate);cal=rq.verify_sealed(a.calibration)
    assert sha(a.mild_gate)==plan['mild_gate_sha256']
    assert sha(a.calibration)==plan['calibration_sha256']==gate['calibration_sha256']
    assert cal['no_test_set_fit']
    inputs,tokens,ledger,protocol=prepare(a.inputs,a.runtime,a.output/'data_protocol')
    assert sha(a.inputs)==plan['inputs_sha256'] and protocol==gate['protocol']
    case=next(c for c in plan['ppl_cases'] if c['id']==a.case)
    native=case['kind']=='native'
    model,context,modules,identity=load_model(inputs,native=native)
    if not native:assert identity==gate['identity']
    baseline=dict(id='strat64',T_x=64,T_and=64,input_law='stratified_T',and_law='joint_grid',grid_g_sig_u=[4,4,4])
    prior_path=a.mild_gate.parent/'BF16_reference/RESULT.json' if native else a.old_screen_root/('seed'+str(plan['seed']))/case['id']/'RESULT.json'
    prior=rq.verify_sealed(prior_path)
    assert prior['protocol']==protocol and prior['identity']==identity
    expected=prior['result']['window_ledger'][0];assert expected['window_index']==0
    original_forward=rq.forward_logits
    first_check=[]
    def checked_forward(model,context,tokens,span,seed,window_index):
        logits,ids=original_forward(model,context,tokens,span,seed,window_index)
        if window_index==0:
            loss=logits.new_zeros((),dtype=torch.float32)
            for lo in range(0,len(ids)-1,128):
                hi=min(len(ids)-1,lo+128)
                loss+=F.cross_entropy(logits[lo:hi].float(),ids[lo+1:hi+1],reduction='sum')
            assert float(loss)==expected['nll'],'first WT2 window changed from sealed same-seed screen'
            first_check.append(True)
        return logits,ids
    rq.forward_logits=checked_forward
    started=time.time()
    with ExitStack() as stack:
        probe=None
        if not native:
            sampling=stack.enter_context(SamplingOverride(baseline));sampling.configure(modules)
            probe=stack.enter_context(PrunedGU(case,{},calibration=cal,encodings=cal['norm_encodings']))
        result=rq.score_windows(model,context,tokens,ledger,list(range(len(ledger))),plan['seed'],a.output,probe)
    assert len(first_check)==1 and result['targets']==299077 and result['windows']==292
    if not native:
        assert set(probe.stats)=={str(i) for i in range(36)} and probe.wd_calls==36*292
    value={'status':'completed','phase':'full_WT2','full_corpus':True,'seed':plan['seed'],'case':case,
        'source_commit':own['git_commit'],'source_manifest_sha256':sha(root/'EXECUTION_MANIFEST.json'),
        'plan_sha256':sha(root/'PLAN.json'),'reference':reference,'mild_source_manifest_sha256':sha(a.mild_source/'EXECUTION_MANIFEST.json'),
        'calibration_sha256':sha(a.calibration),'inputs_sha256':sha(a.inputs),'identity':identity,'protocol':protocol,
        'first_window_same_seed_NLL_bitwise':True,'prior_result_sha256':sha(prior_path),
        'result':result,'seconds':time.time()-started}
    rq.save(a.output/'RESULT.json',value,sealed=True)
    print(json.dumps({'status':'completed','case':case['id'],'ppl':result['ppl'],'seconds':value['seconds']}),flush=True)


if __name__=='__main__':main()
