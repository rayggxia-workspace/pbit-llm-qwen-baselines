"""Issue39: pre-registered clipping/static-PoT comparisons; original attention."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'qwen_dual_iid_exact_20261018'
RANGE = ROOT.parent / 'qwen_dual_range_20261018'
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(RANGE))
from verify import digest, verify, write_json
from run import score
from run_ranges import load_model, test_ids, calibration

POLICIES = {
 'control': dict(range_policy='dynamic', endpoint='legacy'),
 'dynamic075': dict(range_policy='dynamic', x_factor=.75, z_factor=.75),
 'dynamic050': dict(range_policy='dynamic', x_factor=.5, z_factor=.5),
 'dynamic_z050': dict(range_policy='dynamic', x_factor=1., z_factor=.5),
 'fixed999': dict(range_policy='fixed', percentile='q999'),
 'fixed9999': dict(range_policy='fixed', percentile='q9999'),
 'fixed9999_potA': dict(range_policy='fixed', percentile='q9999', pow2=True),
 'fixed9999_potAW': dict(range_policy='fixed', percentile='q9999', pow2=True, weight_pow2=True),
}
CONFIRM = ('control', 'dynamic075', 'fixed9999_potAW')


def cases():
    rows = []
    def add(policy, kind, tokens, cycles=256, seed=0):
        rows.append(dict(name=f'{policy}_{kind}_n{tokens}_T{cycles}_s{seed}',
            policy=policy, kind=kind, input_tokens=tokens, cycles=cycles, seed=seed,
            bits=8, input_sharing=64, scope='all', options=POLICIES[policy]))
    for p in POLICIES:
        add(p, 'mean', 512)
        for seed in (0, 1, 2):
            add(p, 'dual', 512, seed=seed)
    for p in CONFIRM:
        for seed in (0, 1, 2):
            add(p, 'dual', 512, cycles=128, seed=seed)
    # Chosen BEFORE any test results; never select the best test-prefix policy.
    for p in CONFIRM:
        add(p, 'mean', 2048)
        for seed in (0, 1, 2):
            add(p, 'dual', 2048, seed=seed)
    assert len(rows) == len({r['name'] for r in rows}) == 53
    return rows


def checked_output(args):
    project = Path(args.project_root).resolve(strict=True)
    output = Path(args.output).resolve()
    if project not in output.parents or output == ROOT or ROOT in output.parents:
        raise ValueError('Output must remain in personal project outside source snapshot')
    output.mkdir(parents=True, exist_ok=True)
    return output


def sources():
    return {str(p.relative_to(ROOT.parent.parent)).replace('\\', '/'): digest(p)
        for area in (ROOT, RANGE) for p in sorted(area.iterdir())
        if p.is_file() and p.suffix in ('.py', '.sbatch', '.md')}


def calibrate(args, model, tokenizer):
    """Exact train percentiles, pooling 8192 tokens x64 lanes within each group.

    These are offline static amplitude ceilings. No test text participates.
    Teacher x is captured; z recomputed with the original BF16 projections.
    Raw activations exist only in process memory and are never saved.
    """
    import torch
    from torch.nn import functional as F
    ids = tokenizer((Path(args.data)/'wiki.train.raw').read_text(encoding='utf-8'),
        add_special_tokens=False, return_tensors='pt').input_ids[:, :8192]
    checksum = hashlib.sha256(ids.numpy().tobytes()).hexdigest()
    capture = {i: [] for i in range(24)}
    handles = []
    for i, layer in enumerate(model.model.layers):
        def hook(module, inputs, i=i):
            capture[i].append(inputs[0].detach().reshape(-1, inputs[0].shape[-1]).clone())
        handles.append(layer.mlp.register_forward_pre_hook(hook))
    with torch.inference_mode():
        for start in range(0, 8192, 2048):
            model(input_ids=ids[:, start:start+2048].cuda(), use_cache=False)
    for h in handles:
        h.remove()
    layers = {}
    with torch.inference_mode():
        for i, layer in enumerate(model.model.layers):
            x = torch.cat(capture.pop(i), 0)
            z = F.silu(layer.mlp.gate_proj(x))*layer.mlp.up_proj(x)
            item = {}
            for name, value in (('x', x), ('z', z)):
                grouped = value.float().abs().reshape(8192, -1, 64).permute(1, 0, 2).reshape(value.shape[-1]//64, -1)
                qs = torch.quantile(grouped, torch.tensor([.999, .9999], device=value.device), dim=1).clamp_min(1e-20)
                item[name] = dict(q999=qs[0].tolist(), q9999=qs[1].tolist(),
                    maximum=grouped.amax(1).tolist(), rms=grouped.square().mean(1).sqrt().tolist())
            layers[str(i)] = item
            print(json.dumps({'event':'calibrated_layer', 'layer':i}), flush=True)
    return dict(layers=layers, train_tokens=8192, train_ids_sha256=checksum,
        group_size=64, quantiles=[.999, .9999], interpolation='linear',
        pooling='8192 train teacher tokens x64 channels, independent fixed ceiling per layer/group',
        value_dtype='Original BF16 teacher x and z; quantile calculated in FP32',
        raw_activations_saved=False, code_commit=args.code_commit)


def prepare(args):
    import torch
    output = checked_output(args)
    if (output/'identity.json').exists():
        raise FileExistsError('Existing prepare evidence; inspect rather than overwrite')
    identity = verify(args.model, args.data, output/'identity.json')
    identity.update(execution_commit=args.code_commit, clipping_sources=sources())
    write_json(output/'identity.json', identity)
    for path in (ROOT/'test_clip_core.py', RANGE/'test_range_core.py',
                 RANGE/'diagnostic_variance.py', OLD/'vendor/frozen/test_shared.py'):
        subprocess.run([sys.executable, '-B', str(path)], check=True)
    tokenizer, model = load_model(args)
    ids = test_ids(args, tokenizer, identity)
    for name, selected, full in [('bf16_full', ids, True),
                                ('bf16_n512', ids[:, :512], False),
                                ('bf16_n2048', ids[:, :2048], False)]:
        scored = score(model, selected, full)
        passed = not full or (scored['scored_tokens']==299077 and abs(scored['perplexity']-11.652735047455899)<.02)
        write_json(output/'runs'/(name+'.json'), dict(scored, baseline_gate_passed=passed,
            configuration=dict(name=name,kind='baseline',input_tokens=selected.shape[-1]),
            protocol='full_WT2_sliding_window' if full else 'WT2_fixed_test_prefix',
            token_ids_sha256=hashlib.sha256(selected.numpy().tobytes()).hexdigest(),
            code_commit=args.code_commit, slurm_job_id=os.environ.get('SLURM_JOB_ID')))
        if not passed:
            raise ValueError('Stop: unchanged full BF16 reference failed')
    cal = calibrate(args, model, tokenizer)
    assert cal['train_ids_sha256']==identity['tokens']['train']['first8192_ids_sha256']
    write_json(output/'static_calibration.json', cal)
    write_json(output/'suite.json', dict(cases=cases(), execution_commit=args.code_commit,
        created_utc=datetime.now(timezone.utc).isoformat(), attention='original BF16 SDPA',
        confirmation_policies_preselected=list(CONFIRM), no_training=True,
        calibration_data='train only; fixed quantiles declared before test execution',
        no_seed_selection=True, limitation='Replacement results are prefixes, not full WT2'))
    write_json(output/'READY.json', dict(baseline_gate_passed=True, code_commit=args.code_commit,
        identity_sha256=digest(output/'identity.json'),
        calibration_sha256=digest(output/'static_calibration.json'),
        suite_sha256=digest(output/'suite.json'), cases=len(cases())))


def worker(args):
    import torch
    import transformers
    from clip_core import ClipFFN
    output = checked_output(args)
    ready = json.loads((output/'READY.json').read_text(encoding='utf-8'))
    assert ready['baseline_gate_passed'] and ready['code_commit']==args.code_commit
    for file, key in [('identity.json','identity_sha256'),('static_calibration.json','calibration_sha256'),('suite.json','suite_sha256')]:
        assert digest(output/file)==ready[key], file
    identity=json.loads((output/'identity.json').read_text(encoding='utf-8'))
    assert sources()==identity['clipping_sources'], 'Execution snapshot changed'
    cfg=cases()[args.index]
    target=output/'runs'/(cfg['name']+'.json')
    if target.exists():
        raise FileExistsError(target)
    tokenizer,model=load_model(args)
    torch.manual_seed(cfg['seed'])
    ids=test_ids(args,tokenizer,identity)[:, :cfg['input_tokens']]
    old_a,old_z=calibration()
    cal=json.loads((output/'static_calibration.json').read_text(encoding='utf-8'))
    attentions=[layer.self_attn for layer in model.model.layers]
    for i,layer in enumerate(model.model.layers):
        options=dict(cfg['options'])
        percentile=options.pop('percentile',None)
        fixed=dict(fixed_x=cal['layers'][str(i)]['x'][percentile],
                   fixed_z=cal['layers'][str(i)]['z'][percentile]) if percentile else {}
        layer.mlp=ClipFFN(layer.mlp,old_a[str(i)],old_z[str(i)],
            **options,**fixed,kind=cfg['kind'],cycles=cfg['cycles'],seed=cfg['seed'],layer=i)
    assert all(layer.self_attn is attentions[i] for i,layer in enumerate(model.model.layers))
    torch.cuda.reset_peak_memory_stats()
    scored=score(model,ids,False)
    write_json(target,dict(scored,configuration=cfg,protocol='WT2_fixed_test_prefix',
        token_ids_sha256=hashlib.sha256(ids.numpy().tobytes()).hexdigest(),
        full_test_token_ids_sha256=identity['tokens']['test']['ids_sha256'],
        identity_sha256=ready['identity_sha256'],calibration_sha256=ready['calibration_sha256'],
        model_revision=identity['model_revision'],code_commit=args.code_commit,
        configuration_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        attention='unchanged BF16 SDPA',ffn_layers=list(range(24)),
        stochastic_law='exact conditional Binomial; A shared64 and independent perconnection W',
        nonlinearity='FP32 SiLU(g)*u after g/u restoration; z re-encoded',
        accumulation='exact signed counts, no OR',no_training=True,no_seed_selection=True,
        hardware='Numerical study only; no new RTL/PT/TLM power claim',
        environment=dict(torch=torch.__version__,transformers=transformers.__version__,
            cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),python=sys.version),
        slurm_job_id=os.environ.get('SLURM_JOB_ID'),command=sys.argv,
        peak_allocated_bytes=torch.cuda.max_memory_allocated(),
        diagnostics={str(i):layer.mlp.diagnostics() for i,layer in enumerate(model.model.layers)}))
    print(json.dumps({'event':'completed','case':cfg['name'],**scored}),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['prepare','worker'])
    for key in ('model','data','project-root','output','code-commit'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--index',type=int,default=0)
    a=p.parse_args()
    if len(a.code_commit)!=40:
        p.error('Exact commit required')
    {'prepare':prepare,'worker':worker}[a.action](a)


if __name__=='__main__':
    main()
