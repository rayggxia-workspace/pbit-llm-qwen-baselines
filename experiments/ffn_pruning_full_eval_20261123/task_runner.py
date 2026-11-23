"""Single-seed official downstream tasks; original vs pruned full P-FFN."""
from contextlib import ExitStack
from pathlib import Path
import argparse
import gc
import hashlib
import importlib.metadata
import json
import random
import sys
import time


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(path,value):
    from lm_eval.utils import handle_non_serializable
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False,default=handle_non_serializable)+'\n').encode()
    path.write_bytes(data);path.with_suffix('.sha256').write_bytes((hashlib.sha256(data).hexdigest()+'\n').encode())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['gate','tasks'],required=True)
    for name in ['inputs','runtime','helpers','reference-source','mild-source','mild-gate','calibration','data-root','output']:
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--task');ap.add_argument('--case');ap.add_argument('--task-gate',type=Path)
    a=ap.parse_args()
    if a.output.exists():raise FileExistsError('immutable output exists')
    a.output.mkdir(parents=True);(a.output/'data_protocol').mkdir()
    root=Path(__file__).parent;plan=json.loads((root/'PLAN.json').read_bytes())
    own=json.loads((root/'EXECUTION_MANIFEST.json').read_bytes())
    for name,digest in own['files'].items():assert sha(root/name)==digest,name
    sys.path[1:1]=[str(a.mild_source),str(a.helpers),str(a.runtime),str(a.reference_source)]
    import numpy as np
    import torch
    import run_quality as rq
    from run_wt2 import prepare,load_model
    from adapter import SamplingOverride
    from pruning import PrunedGU
    from transformers import AutoTokenizer
    from lm_eval.models.huggingface import HFLM
    from tasks import load_tasks,audit_requests,AuditedHFLM,evaluate,metrics
    assert sha(a.mild_source/'EXECUTION_MANIFEST.json')==plan['mild_manifest_sha256']
    mild=json.loads((a.mild_source/'EXECUTION_MANIFEST.json').read_bytes())
    for name,digest in mild['files'].items():assert sha(a.mild_source/name)==digest,name
    ref=rq.verify_source(a.reference_source);assert ref['manifest_sha256']==plan['reference_manifest_sha256']
    gate=rq.verify_sealed(a.mild_gate);cal=rq.verify_sealed(a.calibration)
    assert sha(a.mild_gate)==plan['mild_gate_sha256'] and sha(a.calibration)==plan['calibration_sha256']
    inputs,tokens,ledger,protocol=prepare(a.inputs,a.runtime,a.output/'data_protocol')
    assert sha(a.inputs)==plan['inputs_sha256']
    random.seed(plan['seed']);np.random.seed(plan['seed']);torch.manual_seed(plan['seed'])
    tokenizer=AutoTokenizer.from_pretrained(inputs['tokenizer'],local_files_only=True,trust_remote_code=False)
    task_map,task_identity,harness_sources=load_tasks(a.data_root,plan)
    requests={n:audit_requests(t,n,tokenizer) for n,t in task_map.items()}
    for name,d in requests.items():assert d['documents']==plan['tasks'][name]['count']
    provenance={'source_commit':own['git_commit'],'source_manifest_sha256':sha(root/'EXECUTION_MANIFEST.json'),
        'plan_sha256':sha(root/'PLAN.json'),'inputs_sha256':sha(a.inputs),'calibration_sha256':sha(a.calibration),
        'mild_manifest_sha256':sha(a.mild_source/'EXECUTION_MANIFEST.json'),'reference':ref,
        'task_identity':task_identity,'official_request_audit':requests,'harness_sources':harness_sources,
        'versions':{n:importlib.metadata.version(n) for n in ['torch','triton','transformers','lm_eval','datasets']}}
    baseline=dict(id='strat64',T_x=64,T_and=64,input_law='stratified_T',and_law='joint_grid',grid_g_sig_u=[4,4,4])
    started=time.time()
    if a.phase=='gate':
        model,context,_,identity_native=load_model(inputs,native=True);model.config.use_cache=False
        bare=HFLM(pretrained=model,tokenizer=tokenizer,backend='causal',batch_size=1,
                  max_length=2048,add_bos_token=False,logits_cache=False,truncation=False)
        checks={}
        for name,task in task_map.items():
            _,doc=next(task.doc_iterator());ctx=task.fewshot_context(doc,num_fewshot=0)
            request=task.construct_requests(doc,ctx,metadata=(name,0,1))[0]
            reference=bare.loglikelihood([request])
            wrapped=AuditedHFLM(model,tokenizer,context,plan['seed'],name)
            actual=wrapped.loglikelihood([request]);assert actual==reference,'native official HFLM likelihood changed'
            mini=evaluate(wrapped,task,name,limit=2)
            assert len(mini['samples'][name])==2
            checks[name]={'native_official_likelihood_exact':True,'pilot_documents':2,
                          'metrics':metrics(mini,name),'model_calls':wrapped.calls}
        del model,context,bare,wrapped;gc.collect();torch.cuda.empty_cache()
        model,context,modules,identity=load_model(inputs);model.config.use_cache=False
        assert identity==gate['identity']
        with SamplingOverride(baseline) as sampling:
            sampling.configure(modules)
            for case_id in ['original_strat64','input_p20']:
                case=next(c for c in plan['ppl_cases'] if c['id']==case_id)
                with PrunedGU(case,{},calibration=cal,encodings=cal['norm_encodings']) as probe:
                    for name,task in task_map.items():
                        lm=AuditedHFLM(model,tokenizer,context,plan['seed'],name)
                        mini=evaluate(lm,task,name,limit=2)
                        assert len(mini['samples'][name])==2 and lm.calls>0
                        checks[name][case_id]={'metrics':metrics(mini,name),'model_calls':lm.calls,'all36_full_sequence_checked':True}
                assert probe.wd_calls==36*sum(checks[n][case_id]['model_calls'] for n in task_map)
        value={'status':'completed','phase':'task_gate','provenance':provenance,
               'identity':identity,'native_identity':identity_native,'checks':checks,'seconds':time.time()-started}
    else:
        taskgate=rq.verify_sealed(a.task_gate);assert taskgate['provenance']==provenance
        assert a.task in task_map and a.case in plan['task_cases']
        task=task_map[a.task];case=next(c for c in plan['ppl_cases'] if c['id']==a.case)
        native=case['kind']=='native'
        model,context,modules,identity=load_model(inputs,native=native);model.config.use_cache=False
        assert identity==(taskgate['native_identity'] if native else taskgate['identity'])
        def progress(lm):
            p={'status':'running','task':a.task,'case':a.case,'model_calls':lm.calls,
               'input_tokens_per_layer':lm.tokens,'seconds':time.time()-started}
            (a.output/'PROGRESS.json').write_bytes((json.dumps(p)+'\n').encode())
        with ExitStack() as stack:
            probe=None
            if not native:
                sampling=stack.enter_context(SamplingOverride(baseline));sampling.configure(modules)
                probe=stack.enter_context(PrunedGU(case,{},calibration=cal,encodings=cal['norm_encodings']))
            lm=AuditedHFLM(model,tokenizer,context,plan['seed'],a.task,progress=progress)
            official=evaluate(lm,task,a.task,limit=None)
            assert len(official['samples'][a.task])==plan['tasks'][a.task]['count']
            if probe is not None:assert probe.wd_calls==36*lm.calls
            audit=lm.audit();audit['FFN_path']='BF16_all_positions' if native else 'PFFN_all_positions'
            addresses=probe.summary() if probe is not None else None
        save(a.output/'OFFICIAL_RESULT.json',official)
        value={'status':'completed','phase':'full_downstream_task','full_split':True,'task':a.task,'case':case,
             'seed':plan['seed'],'documents':len(official['samples'][a.task]),'metrics':metrics(official,a.task),
             'identity':identity,'provenance':provenance,'protocol':plan['task_protocol'],
             'official_result_sha256':sha(a.output/'OFFICIAL_RESULT.json'),'audit':audit,'addresses':addresses,
             'seconds':time.time()-started}
    save(a.output/'RESULT.json',value)
    print(json.dumps({k:value[k] for k in ['status','phase','seconds']}),flush=True)


if __name__=='__main__':main()
