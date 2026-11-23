"""Train-only threshold calibration and GU-only mild-pruning quality screen."""
from pathlib import Path
import argparse
import gc
import hashlib
import json
import sys
import time


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(16<<20),b''):h.update(b)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--phase',choices=['gate','screen'],required=True)
    for name in ['inputs','runtime','helpers','reference-source','train-text','output']:
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--gate',type=Path)
    ap.add_argument('--seed',type=int,default=101)
    a=ap.parse_args()
    if a.output.exists():raise FileExistsError('immutable output already exists')
    a.output.mkdir(parents=True)
    (a.output/'data_protocol').mkdir()
    root=Path(__file__).parent
    plan=json.loads((root/'PLAN.json').read_bytes())
    own=json.loads((root/'EXECUTION_MANIFEST.json').read_bytes())
    for name,digest in own['files'].items():assert sha(root/name)==digest,name
    sys.path[1:1]=[str(a.helpers),str(a.runtime),str(a.reference_source)]
    import numpy as np
    import torch
    import run_quality as rq
    from run_wt2 import prepare,load_model
    from adapter import SamplingOverride
    from pruning import PrunedGU
    ref=rq.verify_source(a.reference_source)
    assert ref['manifest_sha256']==plan['reference_manifest_sha256']
    assert ref['git_commit']==plan['reference_source_commit']
    inputs,tokens,ledger,protocol=prepare(a.inputs,a.runtime,a.output/'data_protocol')
    assert sha(a.inputs)==plan['inputs_sha256']
    identity_ref={'source_commit':own['git_commit'],'source_manifest_sha256':sha(root/'EXECUTION_MANIFEST.json'),
                  'plan_sha256':sha(root/'PLAN.json'),'reference':ref,'inputs_sha256':sha(a.inputs),
                  'helpers':{name:sha(a.helpers/name) for name in ['run_wt2.py','adapter.py','sampling.py']}}
    baseline=dict(id='strat64',T_x=64,T_and=64,input_law='stratified_T',
                  and_law='joint_grid',grid_g_sig_u=[4,4,4])
    started=time.time()
    if a.phase=='gate':
        from gpu_checks import run
        checks=run()
        model,context,_,identity_native=load_model(inputs,native=True)
        native=rq.score_windows(model,context,tokens,ledger,plan['screen_window_indices'],101,a.output/'BF16_reference')
        rq.save(a.output/'BF16_reference/RESULT.json',dict(status='completed',phase='fresh_unchanged_BF16_screen',
                identity=identity_native,protocol=protocol,inputs=identity_ref,result=native),sealed=True)
        del model,context;gc.collect();torch.cuda.empty_cache()
        model,context,modules,identity=load_model(inputs)
        assert identity['export_manifest_sha256']==plan['export_manifest_sha256']
        versions={(i,n):(v.data_ptr(),v._version) for i,m in enumerate(modules) for n,v in m.named_buffers()}
        banks={}
        with SamplingOverride(baseline) as sampling:
            sampling.configure(modules)
            original,_=rq.forward_logits(model,context,tokens,ledger[0],101,0)
            original=original.cpu()
            with PrunedGU(plan['cases'][0],banks,verify_dense=True) as probe:
                actual,_=rq.forward_logits(model,context,tokens,ledger[0],101,0)
                assert torch.equal(original,actual.cpu()),'full2048 no-prune logits changed'
                del actual,original
            assert probe.dense_checks==36 and probe.wd_calls==36
            assert sha(a.train_text)==plan['train_text_sha256']
            from transformers import AutoTokenizer
            tokenizer=AutoTokenizer.from_pretrained(inputs['tokenizer'],local_files_only=True,trust_remote_code=False)
            train=np.asarray(tokenizer.encode(a.train_text.read_text(encoding='utf-8'),add_special_tokens=False),dtype='<u4')
            calibration_config=plan['calibration'];calib_spans=[]
            with PrunedGU(plan['cases'][0],banks,collect=True) as collector:
                for i in range(calibration_config['windows']):
                    begin=i*calibration_config['tokens_per_window'];end=begin+calibration_config['tokens_per_window']
                    assert end<=len(train)
                    logits,_=rq.forward_logits(model,context,train,(begin,end,begin+1),101,100000+i)
                    del logits
                    calib_spans.append({'start':begin,'end':end,'input_token_sha256':hashlib.sha256(train[begin:end].tobytes()).hexdigest()})
            calibration=collector.calibration_value(plan)
            calibration.update(status='completed',identity=identity,inputs=identity_ref,
                train_text_sha256=sha(a.train_text),train_token_sha256=hashlib.sha256(train.tobytes()).hexdigest(),
                train_tokens=len(train),calibration_spans=calib_spans)
            rq.save(a.output/'CALIBRATION.json',calibration,sealed=True)
            assert all((v.data_ptr(),v._version)==versions[i,n] for i,m in enumerate(modules) for n,v in m.named_buffers())
        result={'status':'completed','phase':'gate','inputs':identity_ref,'identity':identity,'protocol':protocol,
                'GPU_checks':checks,'full2048_no_prune_logits_bitwise':True,'dense_integer_layers':36,
                'unchanged_wd_layers':36,'weights_unchanged':True,'calibration_sha256':sha(a.output/'CALIBRATION.json'),
                'BF16_reference_sha256':sha(a.output/'BF16_reference/RESULT.json'),
                'seconds':time.time()-started}
    else:
        gate=rq.verify_sealed(a.gate);calib_path=a.gate.parent/'CALIBRATION.json'
        calibration=rq.verify_sealed(calib_path)
        assert gate['inputs']==identity_ref and gate['protocol']==protocol
        assert calibration['inputs']==identity_ref and sha(calib_path)==gate['calibration_sha256']
        assert a.seed in plan['deployment_seeds'] and calibration['no_test_set_fit']
        model,context,modules,identity=load_model(inputs)
        assert identity==gate['identity']==calibration['identity']
        banks={};completed=[]
        with SamplingOverride(baseline) as sampling:
            sampling.configure(modules)
            for case in plan['cases']:
                out=a.output/case['id']
                for m in modules:m.reset_runtime_audit()
                try:
                    with PrunedGU(case,banks,calibration=calibration,encodings=calibration['norm_encodings']) as probe:
                        r=rq.score_windows(model,context,tokens,ledger,plan['screen_window_indices'],a.seed,out,probe)
                    assert set(probe.stats)=={str(i) for i in range(36)} and probe.wd_calls==288
                    item={'status':'completed','phase':'screen','case':case,'seed':a.seed,'full_corpus':False,
                          'identity':identity,'inputs':identity_ref,'protocol':protocol,
                          'gate_sha256':sha(a.gate),'calibration_sha256':sha(calib_path),'result':r}
                except Exception as exc:
                    if case['kind']=='original':raise
                    item={'status':'failed','phase':'screen','case':case,'seed':a.seed,
                          'error_type':type(exc).__name__,'error':str(exc),'identity':identity,'inputs':identity_ref}
                    torch.cuda.empty_cache()
                rq.save(out/'RESULT.json',item,sealed=True)
                completed.append({'case':case['id'],'status':item['status'],'sha256':sha(out/'RESULT.json')})
        result={'status':'completed','phase':'screen','seed':a.seed,'case_results':completed,
                'inputs':identity_ref,'calibration_sha256':sha(calib_path),'seconds':time.time()-started}
    rq.save(a.output/'RESULT.json',result,sealed=True)
    print(json.dumps({k:result[k] for k in ['status','phase','seconds']}),flush=True)


if __name__=='__main__':main()
