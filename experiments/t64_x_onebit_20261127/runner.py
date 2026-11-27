"""One frozen-weight x-scale ablation: complete WT2 and two full tasks."""
import argparse
from contextlib import nullcontext
import gc,hashlib,json,os,sys,unittest
from pathlib import Path

OWN=Path(__file__).resolve().parent
SOURCE=OWN.parents[1]
TASK=OWN.parent/'t64_scale_task_accuracy_20261126'
HALF=OWN.parent/'t64_onebit_half_20261126'
PARENT=OWN.parent/'t64_dynamic_scale_20261125'
ONEBIT=OWN.parent/'t64_group64_onebit_20261126'
sys.path[:0]=[str(OWN),str(HALF),str(PARENT),str(ONEBIT)]
# Explicit file import avoids confusing this runner with the frozen task runner.
import importlib.util
spec=importlib.util.spec_from_file_location('frozen_task_runner',TASK/'runner.py')
tasks=importlib.util.module_from_spec(spec);spec.loader.exec_module(tasks)
from x_onebit import XOnebitOverride
from half import FractionOverride
from scale_patch import ScaleOverride as OriginalScale

def case(policy):
    return dict(id=policy+'_16_32',policy=policy,scale_policy=policy,T_x=16,T_and=32,
                input_law='stratified_T',and_law='joint_grid',grid_g_sig_u=[4,2,4])

def cases(plan):
    return [case('x64s2_gu64s2')]

class GUOnly(FractionOverride):
    def report(self):
        r=super().report()
        return dict(r['probability_codes'],group_scales=r['group_scales'],integer_backend=r['integer_backend'])

def scale_context(policy):
    if policy=='BF16':return nullcontext()
    if policy=='lane':return OriginalScale('lane')
    if policy=='x4_gu64s2':return GUOnly('gu_onebit64',1)
    if policy=='x64_gu64s2':return GUOnly('all64_onebit',1)
    if policy=='x64s2_gu64s2':return XOnebitOverride(True)
    raise ValueError(policy)

def configure():
    tasks.OWN=OWN;tasks.SOURCE=SOURCE;tasks.cases=cases;tasks.scale_context=scale_context

def cpu(settings,root):
    from score_reference import save
    suite=unittest.TestSuite()
    for folder,pattern in [(ONEBIT,'test_onebit.py'),(HALF,'test_half.py'),(PARENT,'test_dynamic.py'),(OWN,'test_x.py')]:
        suite.addTests(unittest.TestLoader().discover(str(folder),pattern=pattern))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful() and result.testsRun==19
    save(root/'CPU_PREFLIGHT.json',dict(status='completed',tests=result.testsRun))

def gate(settings,root):
    import torch
    from score_reference import sealed,save,score
    from reference import load_model
    from driver import kernel_gate
    from adapter import SamplingOverride
    out=root/'gate';out.mkdir(exist_ok=False)
    assert sealed(root/'CPU_PREFLIGHT.json')['tests']==19
    inputs,tokens,ledger,plan,tokenizer,ts,provenance=tasks.setup(settings,out)
    oldroot=Path(settings['reference_root']);old=sealed(oldroot/'gate/RESULT.json')
    for k in ['protocol','task_identity','harness']:assert provenance[k]==old['provenance'][k],k
    integer=kernel_gate()
    model,context,modules,native=load_model(inputs,native=True)
    assert native==old['native_identity']
    bf=score(model,context,modules,tokens,ledger,list(range(292)),101,out/'BF16_full')
    assert bf['targets']==299077 and abs(bf['ppl']-old['BF16_full']['ppl'])<.000001
    del model,context,modules;gc.collect();torch.cuda.empty_cache()
    model,context,modules,identity=load_model(inputs);assert identity==old['identity']
    ids=torch.as_tensor(tokens[:128].astype('int64'),device='cuda')[None]
    c=case('x64_gu64s2');sampling=SamplingOverride(c);sampling.configure(modules)
    def probe(extra):
        context.seed=101;context.begin(0,0,domain='x-onebit-noop')
        with sampling,extra,torch.no_grad():return model(ids,use_cache=False).logits.detach().clone()
    assert torch.equal(probe(GUOnly('all64_onebit',1)),probe(XOnebitOverride(False)))
    new=probe(XOnebitOverride(True));assert torch.equal(new,probe(XOnebitOverride(True)))
    del ids,new
    pilots=[]
    for name in ts:
        z=tasks.run_task(model,context,modules,tokenizer,ts[name],name,c,101,0,2,out/f'control_{name}')
        oldpart=oldroot/'gate'/f'S2_all64_onebit_16_32_{name}'
        previous=sealed(oldpart/'RESULT.json')
        for k in ['document_identity','metrics','audit']:assert z[k]==previous[k],k
        actual=sealed(out/f'control_{name}'/'OFFICIAL_RESULT.json')['samples'][name]
        expected=sealed(oldpart/'OFFICIAL_RESULT.json')['samples'][name]
        assert [x['resps'] for x in actual]==[x['resps'] for x in expected]
        z2=tasks.run_task(model,context,modules,tokenizer,ts[name],name,cases(plan)[0],101,0,2,out/f'candidate_{name}')
        assert z2['audit']==z['audit'] and z2['document_identity']==z['document_identity']
        assert z2['scale_statistics']['x']['elements']>0
        pilots.append(dict(task=name,old_S2_task_scores_bitwise=True,new_metrics=z2['metrics']))
    save(out/'RESULT.json',dict(status='completed',tests=19,integer_kernel_oracle=integer,
         BF16_full=bf,identity=identity,native_identity=native,provenance=provenance,
         disabled_x_bit_logits_bitwise=True,new_repeat_bitwise=True,pilots=pilots,
         job=os.environ['SLURM_JOB_ID'],device=torch.cuda.get_device_name(0)))

def ppl(settings,root):
    import torch,scale_patch
    from score_reference import sealed,save,score
    from reference import load_model
    checked=sealed(root/'gate/RESULT.json');assert checked['status']=='completed'
    out=root/'ppl';out.mkdir(exist_ok=False)
    inputs,tokens,ledger,plan,tokenizer,ts,provenance=tasks.setup(settings,out)
    assert provenance==checked['provenance']
    model,context,modules,identity=load_model(inputs);assert identity==checked['identity']
    previous=scale_patch.ScaleOverride
    scale_patch.ScaleOverride=scale_context
    rows=[]
    try:
        for policy in ['lane','x4_gu64s2','x64_gu64s2','x64s2_gu64s2']:
            c=case(policy)
            z=score(model,context,modules,tokens,ledger,plan['pilot_windows'],101,out/('pilot_'+policy),c)
            rows.append(dict(case=c,result=z));save(out/'PROGRESS.json',dict(status='running',pilot=rows))
        full=[]
        for policy in ['lane','x64s2_gu64s2']:
            c=case(policy)
            z=score(model,context,modules,tokens,ledger,list(range(292)),101,out/('full_'+policy),c)
            assert z['targets']==299077
            full.append(dict(case=c,result=z))
        save(out/'RESULT.json',dict(status='completed',pilot=rows,full=full,identity=identity,
             provenance=provenance,seed=101,job=os.environ['SLURM_JOB_ID']))
    finally:scale_patch.ScaleOverride=previous

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--settings',type=Path,required=True)
    ap.add_argument('--phase',choices=['cpu','gate','ppl','worker'],required=True);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    raw=a.settings.read_bytes();assert hashlib.sha256(raw).hexdigest()==a.settings.with_suffix('.sha256').read_text().strip()
    settings=json.loads(raw);root=a.settings.parent
    sys.path.insert(0,settings['runtime']);configure()
    import torch;torch.set_num_threads(4)
    if a.phase!='cpu':assert torch.cuda.is_available() and torch.cuda.device_count()==1
    if a.phase=='worker':tasks.worker(settings,root)
    else:globals()[a.phase](settings,root)

if __name__=='__main__':main()
