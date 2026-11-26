"""Full-task scale ablations using pinned official full-sequence HFLM scoring."""
import argparse
from contextlib import contextmanager, nullcontext
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import MethodType

OWN=Path(__file__).resolve().parent
SOURCE=OWN.parents[1]
PARENT=OWN.parent/'t64_dynamic_scale_20261125'
ONEBIT=OWN.parent/'t64_group64_onebit_20261126'
sys.path[:0]=[str(OWN),str(PARENT),str(ONEBIT)]


def cases(plan):
    result=[dict(id='BF16',policy='BF16')]
    for (tx,ta),grid in zip(plan['budgets'],plan['grids']):
        for p in plan['policies']:
            result.append(dict(id=f'{p}_{tx}_{ta}',policy=p,T_x=tx,T_and=ta,
                input_law='stratified_T',and_law='joint_grid',grid_g_sig_u=grid))
    return result


def work_items(plan):
    result=[]
    for case in cases(plan):
        for name,task in plan['tasks'].items():
            for start in range(0,task['count'],plan['documents_per_shard']):
                end=min(start+plan['documents_per_shard'],task['count'])
                result.append(dict(id=f'{case["id"]}__{name}__{start:04d}_{end:04d}',
                    case=case,task=name,start=start,end=end))
    return result


def scale_context(policy):
    from dynamic import DynamicOverride
    from onebit import OnebitOverride
    from scale_patch import ScaleOverride
    if policy=='dynamic32':return DynamicOverride(32)
    if policy in ('gu_onebit64','all64_onebit'):return OnebitOverride(policy)
    if policy=='lane':return ScaleOverride('lane')
    if policy=='BF16':return nullcontext()
    raise ValueError(policy)


@contextmanager
def selected_docs(task,start,end):
    original=task.doc_iterator
    def iterator(self,*,rank=0,limit=None,world_size=1):
        assert rank==0 and world_size==1 and limit is None
        for index,doc in original(rank=rank,limit=limit,world_size=world_size):
            if index>=end:break
            if index>=start:yield index,doc
    task.doc_iterator=MethodType(iterator,task)
    try:yield
    finally:task.doc_iterator=original


def doc_identity(task,start,end):
    rows=[]
    for i in range(start,end):
        raw=(json.dumps(task.eval_docs[i],sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
        rows.append(dict(doc_id=i,sha256=hashlib.sha256(raw).hexdigest()))
    return dict(documents=rows,sha256=hashlib.sha256((json.dumps(rows,separators=(',',':'))+'\n').encode()).hexdigest())


def freeze_state(model,modules):
    from score_reference import snapshot
    return [(v,v.data_ptr(),v._version) for v in model.parameters()],snapshot(modules)


def check_state(state,modules):
    from score_reference import snapshot
    assert all(v.data_ptr()==p and v._version==version for v,p,version in state[0])
    assert state[1]==snapshot(modules),'frozen weight/table mutation'


def run_task(model,context,modules,tokenizer,task,name,case,seed,start,end,out,plain=False):
    import torch
    from adapter import SamplingOverride
    from vendor_tasks import AuditedHFLM,evaluate,metrics
    from score_reference import save,sha
    from lm_eval.utils import handle_non_serializable
    from lm_eval.models.huggingface import HFLM
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    def progress(lm):
        save(out/'PROGRESS.json',dict(status='running',model_calls=lm.calls,input_tokens=lm.tokens,
             seconds=time.monotonic()-started,case=case['id'],task=name,doc_start=start,doc_end=end))
    sampling=SamplingOverride(case) if case['policy']!='BF16' else nullcontext()
    if case['policy']!='BF16':sampling.configure(modules)
    scale=scale_context(case['policy'])
    state=freeze_state(model,modules)
    with sampling,scale,torch.no_grad():
        if plain:
            assert case['policy']=='BF16'
            lm=HFLM(pretrained=model,tokenizer=tokenizer,backend='causal',batch_size=1,max_length=2048,
                    add_bos_token=False,logits_cache=False,truncation=False)
        else:
            lm=AuditedHFLM(model,tokenizer,context,seed,name,progress=progress)
            lm.domain=f'scale-task:{name}:{start}'
        with selected_docs(task,start,end):result=evaluate(lm,task,name)
        audit={} if plain else lm.audit()
        if case['policy']!='BF16':
            assert all((m.last_arithmetic['T_x'],m.last_arithmetic['T_AND'])==(case['T_x'],case['T_and']) for m in modules)
            stats=scale.report()
            if case['policy']!='lane':assert all(stats[k]['elements']>0 for k in ('g','u'))
        else:stats={}
    check_state(state,modules)
    samples=result['samples'][name]
    assert len(samples)==end-start and {int(x['doc_id']) for x in samples}==set(range(start,end))
    measured=metrics(result,name)
    assert measured
    for key,value in measured.items():
        assert abs(sum(x[key.split(',')[0]] for x in samples)/len(samples)-value)<1e-12
    raw=(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False,default=handle_non_serializable)+'\n').encode()
    (out/'OFFICIAL_RESULT.json').write_bytes(raw)
    (out/'OFFICIAL_RESULT.sha256').write_bytes((hashlib.sha256(raw).hexdigest()+'\n').encode())
    value=dict(status='completed',case=case,seed=seed,task=name,doc_start=start,doc_end=end,
         documents=end-start,document_identity=doc_identity(task,start,end),metrics=measured,
         official_sha256=sha(out/'OFFICIAL_RESULT.json'),audit=audit,scale_statistics=stats,
         seconds=time.monotonic()-started,all_weights_tables_unchanged=True)
    save(out/'RESULT.json',value)
    print(json.dumps(dict(event='task_part_complete',case=case['id'],task=name,start=start,end=end,
                         seconds=value['seconds'],metrics=measured)),flush=True)
    del lm,result
    return value


def setup(settings,output):
    from reference import prepare
    from score_reference import sha
    manifest=json.loads((SOURCE/'EXECUTION_MANIFEST.json').read_bytes())
    for name,digest in manifest['files'].items():assert sha(SOURCE/name)==digest,name
    assert sha(settings['inputs'])==settings['inputs_sha256']
    inputs,tokens,ledger,protocol=prepare(Path(settings['inputs']),Path(settings['runtime']),output)
    from transformers import AutoTokenizer
    from vendor_tasks import load_tasks,audit_requests
    plan=json.loads((OWN/'PLAN.json').read_bytes())
    tokenizer=AutoTokenizer.from_pretrained(inputs['tokenizer'],local_files_only=True,trust_remote_code=False)
    tasks,identity,harness=load_tasks(Path(settings['data']),plan)
    for name,t in tasks.items():identity[name]['requests']=audit_requests(t,name,tokenizer)
    provenance=dict(source=manifest,protocol=protocol,plan_sha256=sha(OWN/'PLAN.json'),
                    task_identity=identity,harness=harness)
    return inputs,tokens,ledger,plan,tokenizer,tasks,provenance


def gate(settings,root):
    import torch
    import unittest
    from score_reference import save,score
    from reference import load_model
    from driver import kernel_gate
    from adapter import SamplingOverride
    from onebit import OnebitOverride
    out=root/'gate';out.mkdir(exist_ok=False)
    sys.path.insert(0,settings['runtime'])
    tests=unittest.TestLoader().discover(str(ONEBIT),pattern='test_onebit.py')
    tests.addTests(unittest.TestLoader().discover(str(PARENT),pattern='test_dynamic.py'))
    tested=unittest.TextTestRunner(verbosity=2).run(tests)
    assert tested.wasSuccessful() and tested.testsRun==9
    inputs,tokens,ledger,plan,tokenizer,tasks,provenance=setup(settings,out)
    integer=kernel_gate()
    model,context,modules,identity=load_model(inputs,native=True)
    native_identity=identity
    bf=score(model,context,modules,tokens,ledger,list(range(292)),101,out/'BF16_full')
    assert bf['targets']==299077 and abs(bf['ppl']-11.540139)<.05
    native=cases(plan)[0];checks=[]
    for name in tasks:
        a=run_task(model,context,modules,tokenizer,tasks[name],name,native,101,0,2,out/f'plain_{name}',plain=True)
        b=run_task(model,context,modules,tokenizer,tasks[name],name,native,101,0,2,out/f'audited_{name}')
        av=json.loads((out/f'plain_{name}'/'OFFICIAL_RESULT.json').read_bytes())['samples'][name]
        bv=json.loads((out/f'audited_{name}'/'OFFICIAL_RESULT.json').read_bytes())['samples'][name]
        assert [x['resps'] for x in av]==[x['resps'] for x in bv]
        assert a['document_identity']==b['document_identity']
        checks.append(dict(task=name,official_HFLM_scores_bitwise=True))
    del model,context,modules;gc.collect();torch.cuda.empty_cache()
    model,context,modules,identity=load_model(inputs)
    ids=torch.as_tensor(tokens[:128].astype('int64'),device='cuda')[None]
    for tx,ta in plan['budgets']:
        c=next(x for x in cases(plan) if x['policy']=='lane' and x['T_x']==tx)
        p=SamplingOverride(c);p.configure(modules)
        def probe(extra):
            context.seed=101;context.begin(0,0,domain='scale-task-wrapper-equivalence')
            with p,extra,torch.no_grad():return model(ids,use_cache=False).logits.detach().clone()
        expected=probe(nullcontext());actual=probe(OnebitOverride('equivalent_four'))
        assert torch.equal(expected,actual)
        assert torch.equal(expected,probe(nullcontext()))
    del expected,actual,ids
    pilots=[]
    for c in cases(plan)[1:]:
        for name in tasks:
            z=run_task(model,context,modules,tokenizer,tasks[name],name,c,101,0,2,out/f'{c["id"]}_{name}')
            pilots.append(dict(case=c['id'],task=name,documents=2,seconds=z['seconds'],metrics=z['metrics'],audit=z['audit']))
    save(out/'RESULT.json',dict(status='completed',tests=9,integer_kernel_oracle=integer,
         BF16_full=bf,identity=identity,native_identity=native_identity,provenance=provenance,native_task_checks=checks,
         four_bin_wrapper_bitwise=True,sampled_repeat_bitwise=True,pilots=pilots,
         job=os.environ['SLURM_JOB_ID'],device=torch.cuda.get_device_name(0)))


def worker(settings,root):
    import torch
    from score_reference import sealed,save
    from reference import load_model
    out=root/'workers'/os.environ['SLURM_JOB_ID'];out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,settings['runtime'])
    checked=sealed(root/'gate/RESULT.json');assert checked['status']=='completed'
    inputs,tokens,ledger,plan,tokenizer,tasks,provenance=setup(settings,out)
    assert provenance==checked['provenance']
    jobs=work_items(plan);pending=sorted(jobs,key=lambda x:(x['case']['policy']!='BF16',x['case']['id'],x['task'],x['start']))
    kind=None;model=context=modules=None;done=[]
    for item in pending:
        c=item['case'];target=root/'parts'/item['id']
        if (target/'RESULT.json').exists():sealed(target/'RESULT.json');continue
        claim=root/'claims'/item['id']
        try:claim.mkdir()
        except FileExistsError:continue
        save(claim/'OWNER.json',dict(job=os.environ['SLURM_JOB_ID'],item=item))
        try:
            native=c['policy']=='BF16'
            if kind is None or kind!=native:
                del model,context,modules;gc.collect();torch.cuda.empty_cache()
                model,context,modules,identity=load_model(inputs,native=native);kind=native
                if not native:assert identity==checked['identity']
            z=run_task(model,context,modules,tokenizer,tasks[item['task']],item['task'],c,
                       plan['seed'],item['start'],item['end'],target)
            z.update(provenance=provenance,identity=identity,job=os.environ['SLURM_JOB_ID'],
                     device=torch.cuda.get_device_name(0))
            save(target/'RESULT.json',z);done.append(item['id'])
            save(out/'PROGRESS.json',dict(status='running',completed=done))
        except BaseException as e:
            save(claim/'FAILED.json',dict(status='failed',error=repr(e),job=os.environ['SLURM_JOB_ID']))
            raise
    save(out/'RESULT.json',dict(status='completed',completed=done,job=os.environ['SLURM_JOB_ID']))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--settings',type=Path,required=True)
    ap.add_argument('--phase',choices=['gate','worker'],required=True);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    raw=a.settings.read_bytes();assert hashlib.sha256(raw).hexdigest()==a.settings.with_suffix('.sha256').read_text().strip()
    settings=json.loads(raw);root=a.settings.parent
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
    import torch
    torch.set_num_threads(4)
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
    globals()[a.phase](settings,root)


if __name__=='__main__':main()
