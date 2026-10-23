"""Slurm-only identity gates and immutable Qwen PPL outputs, Issue141."""
import argparse,hashlib,json,os,sys,time,gc,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'experiments/qwen_dual_iid_exact_20261018'),str(ROOT/'experiments/qwen_dual_range_20261018')]
from verify import verify,digest,write_json
from run_ranges import load_model,test_ids
from experiments.qwen_dual_iid_exact_20261018.run import score
from .adapter import evaluate
CAL_SHA='fefbb90c4f38c5f7a6d51a672550bd684ffe3a1415d36dc115a8ca5e05c5db0b'


def plan(protocol='suffix'):
    cases=[]
    for name,ffn,mode,method,samples,seeds in [
        ('bf16','none','sdpa','none',128,[0]),
        ('ffn_only','b4_t32','sdpa','none',128,[0,1,2]),
        ('screen_exact','b4_t32','screen_exact','exact',128,[0,1,2]),
        ('ctmc128','b4_t32','screen_ising','ctmc',128,[0,1,2]),
        ('rejection128','b4_t32','screen_ising','rejection',128,[0,1,2]),
        ('winner1024','b4_t32','screen_ising','winner',1024,[0,1,2])]:
        for seed in seeds:
            cases.append(dict(name=name+'_s'+str(seed),ffn=ffn,mode=mode,sampler=method,seed=seed,samples=samples,
                burn=16.,spacing=4.,selection='fixed',budget_blocks=8,target_fraction=.30,
                context=2048,decode=128,examples=32,batch=8 if protocol=='suffix' else 32,
                protocol=protocol,stride=1024))
    return cases


def seal(path,data):
    if path.exists():raise FileExistsError(path)
    write_json(path,data)
    path.with_suffix(path.suffix+'.sha256').write_text(digest(path)+'\n',encoding='ascii')


def sources():
    return {str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in sorted((ROOT/'experiments').rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts}


def run_case(a,case,identity):
    import torch,transformers
    tok,model=load_model(a);ids=test_ids(a,tok,identity)[0]
    calibration=torch.load(a.calibration,map_location='cpu',weights_only=True)
    if 'parameter' not in calibration:calibration=calibration['2048_0.3_max4']
    torch.manual_seed(case['seed']);torch.cuda.reset_peak_memory_stats()
    result=evaluate(model,ids,case,calibration)
    result.update(status='completed',configuration=case,code_commit=a.code_commit,
        configuration_sha256=hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest(),
        identity_sha256=digest(Path(a.output)/'identity.json'),calibration_sha256=CAL_SHA,
        model_revision=identity['model_revision'],command=sys.argv,slurm_job_id=os.environ['SLURM_JOB_ID'],
        environment=dict(torch=torch.__version__,transformers=transformers.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name()),
        peak_allocated_bytes=torch.cuda.max_memory_allocated())
    del model,tok,ids;gc.collect();torch.cuda.empty_cache()
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','worker'])
    for name in ('project-root','output','model','data','calibration','code-commit'):p.add_argument('--'+name,required=True)
    p.add_argument('--phase',choices=['suffix','full'],default='suffix');p.add_argument('--index',type=int,default=0)
    a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('Slurm GPU allocation required')
    project=Path(a.project_root).resolve(strict=True);out=Path(a.output).resolve()
    if project.parent!=Path('/home/Hongjie_Zeng/projects') or project not in out.parents or ROOT in out.parents:
        raise ValueError('personal output outside immutable snapshot required')
    out.mkdir(parents=True,exist_ok=True)
    if digest(a.calibration)!=CAL_SHA:raise ValueError('calibration changed')
    snapshot=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text())
    if snapshot['code_commit']!=a.code_commit or snapshot['files']!=sources():raise ValueError('execution source changed')
    if a.action=='prepare':
        if (out/'identity.json').exists():raise FileExistsError('preparation already exists')
        identity=verify(a.model,a.data,out/'identity.json')
        from .validate import run
        seal(out/'kernel_validation.json',run())
        import torch
        tok,model=load_model(a);ids=test_ids(a,tok,identity)
        ref=score(model,ids,True)
        passed=ref['scored_tokens']==299077 and abs(ref['perplexity']-11.652735047455899)<1e-8
        seal(out/'bf16_vectorized_full.json',dict(ref,gate_passed=passed,code_commit=a.code_commit))
        if not passed:raise ValueError('unchanged BF16 gate failed')
        del model,tok,ids;gc.collect();torch.cuda.empty_cache()
        pilots=[]
        for case in [c for c in plan() if c['seed']==0]:
            cfg=dict(case,examples=2,decode=4,batch=2)
            result=run_case(a,cfg,identity);seal(out/'pilot'/(cfg['name']+'.json'),result);pilots.append(result)
            print(json.dumps(dict(event='pilot',name=cfg['name'],ppl=result['perplexity'],seconds=result['elapsed_seconds'])),flush=True)
        seal(out/'PLAN.json',dict(suffix=plan(),full=plan('full'),pilot_targets=8,
            full_targets=299077,ideal_rng=True,probability_quantization=None,
            source_sha256=digest(ROOT/'SOURCE_MANIFEST.json')))
        seal(out/'READY.json',dict(status='passed',code_commit=a.code_commit,
            identity_sha256=digest(out/'identity.json'),plan_sha256=digest(out/'PLAN.json'),
            validation_sha256=digest(out/'kernel_validation.json')))
    else:
        ready=json.loads((out/'READY.json').read_text());identity=json.loads((out/'identity.json').read_text())
        if ready['code_commit']!=a.code_commit or ready['identity_sha256']!=digest(out/'identity.json') or ready['plan_sha256']!=digest(out/'PLAN.json'):
            raise ValueError('preparation identity changed')
        cases=json.loads((out/'PLAN.json').read_text())[a.phase];case=cases[a.index]
        path=out/a.phase/(case['name']+'.json')
        if path.exists():raise FileExistsError(path)
        start=time.time();result=run_case(a,case,identity);seal(path,result)
        print(json.dumps(dict(event='completed',phase=a.phase,name=case['name'],ppl=result['perplexity'],seconds=time.time()-start)),flush=True)

if __name__=='__main__':main()
