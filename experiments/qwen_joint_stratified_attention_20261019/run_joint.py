"""Issue50: frozen-model joint FFN/finite-Ising behavior evaluation via Slurm."""
import argparse
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
OLD=ROOT.parent/'qwen_dual_iid_exact_20261018';RANGE=ROOT.parent/'qwen_dual_range_20261018'
for p in (REPO,OLD,RANGE):sys.path.insert(0,str(p))
from verify import verify,digest,write_json,source_manifest
from run import score
from run_ranges import load_model,test_ids

FFNS=('b2_t32','b4_t32','b4_t16');SEEDS=(0,1,2)
CAL_SHA='fefbb90c4f38c5f7a6d51a672550bd684ffe3a1415d36dc115a8ca5e05c5db0b'

def cases(phase='suffix'):
    rows=[]
    def add(ffn,mode,seed=0,samples=128,**kw):
        cfg=dict(name=f'{ffn}_{mode}_S{samples}_s{seed}',ffn=ffn,mode=mode,seed=seed,samples=samples,
            burn=16.,spacing=4.,selection='fixed',budget_blocks=8,target_fraction=.30,
            context=2048,decode=128,examples=32,batch=8,protocol='suffix',stride=1024)
        cfg.update(kw);rows.append(cfg)
    if phase=='pilot':
        for ffn,mode,s in [('none','sdpa',128),('none','digital_sdpa',128),('b4_t32','sdpa',128),
                ('b4_t32','digital_sdpa',128),('none','screen_ising',128),('b4_t32','screen_ising',128),
                ('b4_t32','screen_ising',512),('b4_t32','screen_iid',128)]:
            add(ffn,mode,samples=s,examples=4,decode=4,batch=4,capture_scored_logits_sha256=True)
    elif phase=='suffix':
        add('none','sdpa')
        for ffn in FFNS:
            for seed in SEEDS:add(ffn,'sdpa',seed)
        for samples in (128,512):
            for ffn in ('none',)+FFNS:
                for seed in SEEDS:add(ffn,'screen_ising',seed,samples)
        assert len(rows)==34
    elif phase=='fallback':
        for ffn in ('none',)+FFNS:
            for seed in SEEDS:add(ffn,'screen_iid',seed)
    else:raise ValueError('Unknown phase')
    assert len(rows)==len({r['name'] for r in rows})
    return rows

def sources():
    areas=[ROOT,ROOT.parent/'qwen_multiscale_stratified_20261019',RANGE,ROOT.parent/'qwen_fixedw_multiscale_20261019']
    files=[p for area in areas for p in sorted(area.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.sbatch','.md','.json')]
    return {str(p.relative_to(REPO)).replace('\\','/'):digest(p) for p in files}

def output_dir(a):
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('Allocated Slurm GPU required')
    project=Path(a.project_root).resolve(strict=True);out=Path(a.output).resolve()
    if project not in out.parents or ROOT==out or ROOT in out.parents:raise ValueError('Invalid output path')
    if project.parent!=Path('/home/Hongjie_Zeng/projects') or Path.home()!=Path('/home/Hongjie_Zeng'):
        raise ValueError('Verified personal project required')
    out.mkdir(parents=True,exist_ok=True);return out

def calibration(a):
    p=Path(a.calibration).resolve(strict=True)
    if Path(a.project_root).resolve() not in p.parents or digest(p)!=CAL_SHA:raise ValueError('Calibration identity mismatch')
    import torch
    outer=torch.load(p,map_location='cpu',weights_only=True)
    return outer if 'parameter' in outer else outer['2048_0.3_max4']

def evaluate(a,cfg,identity):
    import torch,transformers
    from experiments.qwen_joint_stratified_attention_20261019.joint_evaluate import evaluate_case
    tokenizer,model=load_model(a);ids=test_ids(a,tokenizer,identity)[0]
    torch.manual_seed(cfg['seed']);torch.cuda.reset_peak_memory_stats()
    result=evaluate_case(model,ids,cfg,calibration(a))
    result.update(configuration=cfg,configuration_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        code_commit=a.code_commit,identity_sha256=digest(Path(a.output)/'identity.json'),model_revision=identity['model_revision'],
        environment=dict(torch=torch.__version__,transformers=transformers.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),python=sys.version),
        slurm_job_id=os.environ['SLURM_JOB_ID'],command=sys.argv,peak_allocated_bytes=torch.cuda.max_memory_allocated(),status='completed')
    return result

def prepare(a):
    out=output_dir(a)
    if (out/'identity.json').exists():raise FileExistsError('Do not overwrite preparation')
    identity=verify(a.model,a.data,out/'identity.json')
    identity.update(execution_commit=a.code_commit,joint_sources=sources(),calibration_sha256=CAL_SHA,
        randomness='FFN equal-range stratified shared64 counts; independent Attention selector and finite-time CTMC streams',
        attention_upstream_commit='11f1d6eea2776e201f2021081f8b0fbae2cc455e')
    write_json(out/'identity.json',identity)
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='')
    tests=[([sys.executable,'-B',str(ROOT/'test_upstream.py')],'upstream'),
        ([sys.executable,'-B',str(ROOT/'test_joint_evaluate.py')],'joint'),
        ([sys.executable,'-B',str(ROOT.parent/'qwen_multiscale_stratified_20261019/test_stratified_core.py')],'ffn')]
    for cmd,label in tests:
        result=subprocess.run(cmd,cwd=REPO,env=env,text=True,capture_output=True)
        (out/(label+'_tests.stdout.txt')).write_text(result.stdout,encoding='utf-8',newline='\n')
        (out/(label+'_tests.stderr.txt')).write_text(result.stderr,encoding='utf-8',newline='\n')
        result.check_returncode()
    tokenizer,model=load_model(a);ids=test_ids(a,tokenizer,identity)
    ref=score(model,ids,True)
    passed=ref['scored_tokens']==299077 and abs(ref['perplexity']-11.652735047455899)<1e-8
    write_json(out/'bf16_vectorized_full.json',dict(ref,code_commit=a.code_commit,baseline_gate_passed=passed,protocol='original_vectorized_full_WT2_2048_1024'))
    if not passed:raise ValueError('Original BF16 mismatch')
    del model
    import torch
    torch.cuda.empty_cache()
    pilots=[]
    for cfg in cases('pilot'):
        r=evaluate(a,cfg,identity);write_json(out/'pilot'/(cfg['name']+'.json'),r);pilots.append(r)
        print(json.dumps(dict(event='pilot',name=cfg['name'],ppl=r['perplexity'],seconds=r.get('elapsed_seconds'))),flush=True)
    # Same-format SDPA wrapper must retain exact scored logits, with and without
    # stochastic FFN. Manual FP32 QK is intentionally not this equivalence test.
    for left,right in ((0,1),(2,3)):
        key='scored_logits_sha256'
        assert pilots[left].get(key) and pilots[left][key]==pilots[right][key], 'SDPA wrapper changed scored logits'
    suite=dict(code_commit=a.code_commit,created_utc=datetime.now(timezone.utc).isoformat(),suffix=cases('suffix'),fallback=cases('fallback'),
        pre_registered_phases=['suffix'],full_confirmation='Choose only after measured decode runtime; protocol and fresh controls must match',
        attention_samples='S128 approx initial 2K/16; S512 conservative high-budget control, not same sparse ratio',
        prefill='original SDPA Attention; selected stochastic FFN active for prefill and decode',no_training=True)
    write_json(out/'suite.json',suite)
    write_json(out/'READY.json',dict(code_commit=a.code_commit,baseline_gate_passed=True,sdpa_wrapper_bitwise_passed=True,
        identity_sha256=digest(out/'identity.json'),suite_sha256=digest(out/'suite.json'),suffix_cases=34))

def worker(a):
    out=output_dir(a);ready=json.loads((out/'READY.json').read_text(encoding='utf-8'))
    assert ready['baseline_gate_passed'] and ready['sdpa_wrapper_bitwise_passed'] and ready['code_commit']==a.code_commit
    assert ready['identity_sha256']==digest(out/'identity.json') and ready['suite_sha256']==digest(out/'suite.json')
    identity=json.loads((out/'identity.json').read_text(encoding='utf-8'))
    assert identity['joint_sources']==sources() and identity['source_sha256']==source_manifest()
    cfg=cases(a.phase)[a.index];path=out/a.phase/(cfg['name']+'.json')
    if path.exists():raise FileExistsError(path)
    result=evaluate(a,cfg,identity);write_json(path,result)
    print(json.dumps(dict(event='completed',name=cfg['name'],ppl=result['perplexity'],seconds=result.get('elapsed_seconds'))),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','worker'])
    for key in ('model','data','calibration','project-root','output','code-commit'):p.add_argument('--'+key,required=True)
    p.add_argument('--phase',choices=['suffix','fallback'],default='suffix');p.add_argument('--index',type=int,default=0)
    a=p.parse_args()
    if len(a.code_commit)!=40:p.error('Exact SHA required')
    {'prepare':prepare,'worker':worker}[a.action](a)
if __name__=='__main__':main()
