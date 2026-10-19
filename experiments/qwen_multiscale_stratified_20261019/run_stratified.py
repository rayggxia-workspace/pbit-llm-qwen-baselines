"""Issue46: fixed W8, multiscale inputs and coarse/fine randomized stratification."""
import argparse
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import subprocess,sys

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'qwen_dual_iid_exact_20261018'
RANGE=ROOT.parent/'qwen_dual_range_20261018'
sys.path.insert(0,str(OLD))
sys.path.insert(0,str(RANGE))
from verify import digest,verify,write_json,source_manifest
from run import score
from run_ranges import load_model,test_ids

SEEDS=(0,1,2)

def cases(phase='scan'):
    rows=[]
    def add(policy,mode='sampled',cycles=64,strata=1,seed=0):
        rows.append(dict(name=f'{policy}_{mode}_full_T{cycles}_K{strata}_s{seed}',policy=policy,
            mode=mode,cycles=cycles,strata=strata,seed=seed,full=True,input_tokens=None,
            probability_bits=8,sharing=64,bins=1 if policy=='dynamic64' else int(policy[3:]),
            exponent_spacing=2 if policy.startswith('pot') else None))
    def three(policy,t,k):
        for seed in SEEDS:add(policy,cycles=t,strata=k,seed=seed)
    # Complete missing IID64 bin counts. Existing dynamic64/pot4/pot8 results
    # are imported only after exact corpus, weight and unchanged-law checks.
    for p in ('pot1','pot2','pot3','pot6'):three(p,64,1)
    for p in ('dynamic64','pot1','pot2','pot3','pot4','pot6','pot8'):three(p,64,64)
    for t in (16,32):
        for p in ('pot2','pot4'):three(p,t,t)
    for p in ('dynamic64','pot4'):three(p,128,128)
    for k in (4,16):
        for p in ('pot2','pot4'):three(p,64,k)
    for p in ('pot1','pot2','pot3','pot6'):add(p,mode='mean')
    assert len(rows)==67 and len({r['name'] for r in rows})==67
    return rows


def sources():
    return {str(p.relative_to(ROOT.parent.parent)).replace('\\','/'):digest(p)
        for area in (ROOT,RANGE,ROOT.parent/'qwen_fixedw_multiscale_20261019') for p in sorted(area.iterdir())
        if p.is_file() and p.suffix in ('.py','.sbatch','.md')}

def checked_output(args):
    project=Path(args.project_root).resolve(strict=True)
    output=Path(args.output).resolve()
    if project not in output.parents or output==ROOT or ROOT in output.parents:
        raise ValueError('Outputs must stay under personal project, outside immutable snapshot')
    output.mkdir(parents=True,exist_ok=True)
    return output

def prepare(args):
    output=checked_output(args)
    if (output/'identity.json').exists():raise FileExistsError('Inspect existing execution; do not overwrite')
    identity=verify(args.model,args.data,output/'identity.json')
    identity.update(execution_commit=args.code_commit,multiscale_sources=sources(),
        randomness='K1 IID; K>1 equal-occupancy randomized stratification, with replacement within each stratum; exact shared64 count law')
    write_json(output/'identity.json',identity)
    for path in (ROOT/'test_stratified_core.py',ROOT.parent/'qwen_fixedw_multiscale_20261019/test_multiscale_core.py',RANGE/'test_range_core.py',OLD/'vendor/frozen/test_shared.py'):
        subprocess.run([sys.executable,'-B',str(path)],check=True)
    tokenizer,model=load_model(args)
    ids=test_ids(args,tokenizer,identity)
    for name,selected,full in [('bf16_full',ids,True),('bf16_n512',ids[:,:512],False)]:
        scored=score(model,selected,full)
        passed=not full or (scored['scored_tokens']==299077 and abs(scored['perplexity']-11.652735047455899)<.02)
        write_json(output/'runs'/(name+'.json'),dict(scored,configuration=dict(name=name,mode='baseline',full=full),
            baseline_gate_passed=passed,code_commit=args.code_commit,
            protocol='full_WT2_sliding_window' if full else 'WT2_fixed_test_prefix',
            token_ids_sha256=hashlib.sha256(selected.numpy().tobytes()).hexdigest(),
            slurm_job_id=os.environ.get('SLURM_JOB_ID')))
        if not passed:raise ValueError('Unchanged full BF16 failed; no replacement comparisons')
    suite=dict(scan=cases(),code_commit=args.code_commit,executed_phases=['scan'],
        created_utc=datetime.now(timezone.utc).isoformat(),attention='original BF16 SDPA',
        no_training=True,no_seed_selection=True,full_stage_requires_manual_runtime_review=False,
        selection='Fixed before new results: bins1/2/3/4/6/8, coarse K4/16 at T64 and fine K=T at T16/32/64/128; 67 full cases',
        mean_note='deterministic encoded-path control, not whole-network expectation',
        prior_results='Old original IID64 dynamic64/pot4/pot8 imported only with identical model/corpus/kernel equivalence; no test-based stopping')
    write_json(output/'suite.json',suite)
    write_json(output/'READY.json',dict(code_commit=args.code_commit,baseline_gate_passed=True,
        identity_sha256=digest(output/'identity.json'),suite_sha256=digest(output/'suite.json'),scan_cases=len(cases())))


def worker(args):
    import torch,transformers
    from stratified_core import StratifiedFFN
    output=checked_output(args)
    ready=json.loads((output/'READY.json').read_text(encoding='utf-8'))
    assert ready['baseline_gate_passed'] and ready['code_commit']==args.code_commit
    assert digest(output/'identity.json')==ready['identity_sha256']
    assert digest(output/'suite.json')==ready['suite_sha256']
    identity=json.loads((output/'identity.json').read_text(encoding='utf-8'))
    assert identity['multiscale_sources']==sources(),'Immutable execution source changed'
    assert identity['source_sha256']==source_manifest(),'Frozen scoring/shared-count dependency changed'
    cfg=cases(args.phase)[args.index]
    target=output/'runs'/(cfg['name']+'.json')
    if target.exists():raise FileExistsError(target)
    tokenizer,model=load_model(args)
    torch.manual_seed(cfg['seed'])
    ids=test_ids(args,tokenizer,identity)
    if not cfg['full']:ids=ids[:,:cfg['input_tokens']]
    attentions=[layer.self_attn for layer in model.model.layers]
    for i,layer in enumerate(model.model.layers):
        layer.mlp=StratifiedFFN(layer.mlp,policy=cfg['policy'],mode=cfg['mode'],cycles=cfg['cycles'],seed=cfg['seed'],layer=i,strata=cfg['strata'])
    assert all(layer.self_attn is attentions[i] for i,layer in enumerate(model.model.layers))
    torch.cuda.reset_peak_memory_stats()
    scored=score(model,ids,cfg['full'])
    write_json(target,dict(scored,status='completed',configuration=cfg,
        protocol='full_WT2_sliding_window' if cfg['full'] else 'WT2_fixed_test_prefix',
        token_ids_sha256=hashlib.sha256(ids.numpy().tobytes()).hexdigest(),
        full_test_token_ids_sha256=identity['tokens']['test']['ids_sha256'],identity_sha256=ready['identity_sha256'],
        model_revision=identity['model_revision'],code_commit=args.code_commit,
        configuration_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        ffn_layers=list(range(24)),attention='unchanged original BF16 SDPA',
        weights='Same old per64x64 symmetric INT8 decoded weights, no probability reencoding',
        stochastic_law='Exact shared64 IID for K1, or K independent equal strata with T/K draws each; no Gaussian; W fixed',
        nonlinearity='Continuous FP32 SiLU(g)*u, z independently encoded',
        accumulation='Exact linear count restoration in FP32; not finite-width RTL simulation',
        no_training=True,no_seed_selection=True,hardware='No new PPA/PT/TLM measurement',
        environment=dict(torch=torch.__version__,transformers=transformers.__version__,cuda=torch.version.cuda,
            gpu=torch.cuda.get_device_name(),python=sys.version),slurm_job_id=os.environ.get('SLURM_JOB_ID'),command=sys.argv,
        peak_allocated_bytes=torch.cuda.max_memory_allocated(),
        diagnostics={str(i):layer.mlp.diagnostics() for i,layer in enumerate(model.model.layers)}))
    print(json.dumps({'event':'completed','case':cfg['name'],**scored}),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['prepare','worker'])
    for key in ('model','data','project-root','output','code-commit'):p.add_argument('--'+key,required=True)
    p.add_argument('--index',type=int,default=0)
    p.add_argument('--phase',choices=['scan'],default='scan')

    a=p.parse_args()
    if len(a.code_commit)!=40:p.error('Exact execution SHA required')
    {'prepare':prepare,'worker':worker}[a.action](a)

if __name__=='__main__':main()
