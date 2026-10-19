"""Issue46: fixed historical INT8 weights, amplitude-binned IID inputs."""
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

POLICIES=('dynamic64','pot1','pot4','pot8')
SEEDS=(0,1,2)

def cases(phase):
    rows=[]
    def add(policy,mode,cycles=256,seed=0,full=False):
        tag='full' if full else 'n512'
        rows.append(dict(name=f'{policy}_{mode}_{tag}_T{cycles}_s{seed}',policy=policy,
            mode=mode,cycles=cycles,seed=seed,full=full,input_tokens=None if full else 512,
            probability_bits=8,sharing=64,bins=1 if policy in ('dynamic64','pot1') else int(policy[3:]),
            exponent_spacing=2 if policy.startswith('pot') else None))
    full=phase=='full'
    add('dynamic64','w8_only',full=full)
    if not full:
        for policy in POLICIES:
            add(policy,'mean')
            for cycles in (64,128,256):
                for seed in SEEDS:add(policy,'sampled',cycles,seed)
        assert len(rows)==41
    else:
        # Fixed BEFORE results. Run only after measured runtime is inspected.
        # Workers record explicit skip evidence for clearly bad screen cases.
        for policy in ('dynamic64','pot4','pot8'):
            add(policy,'mean',full=True)
            for cycles in (128,256):
                for seed in SEEDS:add(policy,'sampled',cycles,seed,full=True)
        assert len(rows)==22
    assert len(rows)==len({r['name'] for r in rows})
    return rows

def sources():
    return {str(p.relative_to(ROOT.parent.parent)).replace('\\','/'):digest(p)
        for area in (ROOT,RANGE) for p in sorted(area.iterdir())
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
    identity.update(execution_commit=args.code_commit,multiscale_sources=sources())
    write_json(output/'identity.json',identity)
    for path in (ROOT/'test_multiscale_core.py',RANGE/'test_range_core.py',OLD/'vendor/frozen/test_shared.py'):
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
    suite=dict(screen=cases('screen'),full=cases('full'),code_commit=args.code_commit,
        created_utc=datetime.now(timezone.utc).isoformat(),attention='original BF16 SDPA',
        no_training=True,no_seed_selection=True,full_stage_requires_manual_runtime_review=True,
        full_skip_gate='sampled configuration skipped if corresponding three-seed 512prefix mean PPL > 1.5 x W8_only prefix; skip is not a full PPL result',
        mean_note='mean is deterministic encoded-path control, not expectation of the nonlinear stochastic network',
        selection='full candidates dynamic64/pot4/pot8 at T128/T256 fixed before screen')
    write_json(output/'suite.json',suite)
    write_json(output/'READY.json',dict(code_commit=args.code_commit,baseline_gate_passed=True,
        identity_sha256=digest(output/'identity.json'),suite_sha256=digest(output/'suite.json'),screen_cases=41,full_cases=22))

def worker(args):
    import torch,transformers
    from multiscale_core import MultiScaleFFN
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
    if cfg['full'] and cfg['mode']=='sampled':
        screen=[json.loads((output/'runs'/(c['name']+'.json')).read_text(encoding='utf-8'))
            for c in cases('screen') if c['policy']==cfg['policy'] and c['mode']=='sampled' and c['cycles']==cfg['cycles']]
        ref=next(c for c in cases('screen') if c['mode']=='w8_only')
        baseline=json.loads((output/'runs'/(ref['name']+'.json')).read_text(encoding='utf-8'))
        average=sum(r['perplexity'] if r['perplexity'] is not None else float('inf') for r in screen)/len(screen)
        if average>1.5*baseline['perplexity']:
            write_json(target,dict(status='skipped_after_declared_screen_gate',configuration=cfg,
                screen_mean_ppl=None if average==float('inf') else average,screen_reference=baseline['perplexity'],
                code_commit=args.code_commit,protocol='no_full_PPL_computed',slurm_job_id=os.environ.get('SLURM_JOB_ID')))
            print(json.dumps({'event':'skipped','case':cfg['name']}),flush=True)
            return
    tokenizer,model=load_model(args)
    torch.manual_seed(cfg['seed'])
    ids=test_ids(args,tokenizer,identity)
    if not cfg['full']:ids=ids[:,:cfg['input_tokens']]
    attentions=[layer.self_attn for layer in model.model.layers]
    for i,layer in enumerate(model.model.layers):
        layer.mlp=MultiScaleFFN(layer.mlp,policy=cfg['policy'],mode=cfg['mode'],cycles=cfg['cycles'],seed=cfg['seed'],layer=i)
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
        stochastic_law='Exact shared64 natural IID R8 count distribution; W fixed; no Gaussian or stratification',
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
    p.add_argument('--phase',choices=['screen','full'],default='screen')
    a=p.parse_args()
    if len(a.code_commit)!=40:p.error('Exact execution SHA required')
    {'prepare':prepare,'worker':worker}[a.action](a)

if __name__=='__main__':main()
