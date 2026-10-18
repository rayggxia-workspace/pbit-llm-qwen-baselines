"""Issue32: paired range-factor ablation, unchanged Qwen attention, no training."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'qwen_dual_iid_exact_20261018'
sys.path.insert(0, str(OLD))
from verify import digest, verify, write_json
from run import score

VARIANTS = {
    'old': ('legacy', 'legacy'),
    'input': ('dynamic64', 'legacy'),
    'weight': ('legacy', 'row64'),
    'both': ('dynamic64', 'row64'),
}
SEEDS = (0, 1, 2)


def cases():
    rows = []
    def add(variant, kind, cycles=256, seed=0, scope='all'):
        rows.append(dict(name=f'{variant}_{kind}_{scope}_T{cycles}_s{seed}',
                         variant=variant, kind=kind, cycles=cycles, seed=seed,
                         scope=scope, bits=8, input_sharing=64))
    for variant in VARIANTS:
        add(variant, 'mean')
        for seed in SEEDS:
            add(variant, 'dual', seed=seed)
    for variant in ('old', 'both'):
        for seed in SEEDS:
            add(variant, 'fixed', seed=seed)
    for cycles in (64, 128, 1024):
        for seed in SEEDS:
            add('both', 'dual', cycles, seed)
    for scope in ('gu', 'down'):
        for seed in SEEDS:
            add('both', 'dual', seed=seed, scope=scope)
    assert len(rows) == len({r['name'] for r in rows}) == 37
    return rows


def checked_output(args):
    project = Path(args.project_root).resolve(strict=True)
    output = Path(args.output).resolve()
    if project not in output.parents or ROOT == output or ROOT in output.parents:
        raise ValueError('Output must stay below personal project, outside snapshot')
    output.mkdir(parents=True, exist_ok=True)
    return output


def load_model(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda().eval()
    model.requires_grad_(False)
    return tokenizer, model


def test_ids(args, tokenizer, identity):
    ids = tokenizer((Path(args.data) / 'wiki.test.raw').read_text(encoding='utf-8'),
                    add_special_tokens=False, return_tensors='pt').input_ids
    token_hash = hashlib.sha256(ids.numpy().tobytes()).hexdigest()
    if token_hash != identity['tokens']['test']['ids_sha256']:
        raise ValueError('Worker test token identity mismatch')
    return ids


def calibration():
    a = json.loads((OLD / 'vendor/frozen/results/calibration.json').read_text(encoding='utf-8'))
    z = json.loads((OLD / 'vendor/frozen/results/sz_calibration.json').read_text(encoding='utf-8'))
    return a['policies']['group_max'], z['fixed_group']


def expand_scale(values, width, device):
    import torch
    scale = torch.tensor(values, dtype=torch.float32, device=device)
    if scale.numel() == 1:
        return scale.expand(width)
    return scale.repeat_interleave(64) if scale.numel() == width // 64 else scale


def prepare(args):
    import torch
    output = checked_output(args)
    if (output / 'identity.json').exists():
        raise FileExistsError('New execution output required')
    identity = verify(args.model, args.data, output / 'identity.json')
    identity['range_source_sha256'] = {p.name: digest(p) for p in sorted(ROOT.iterdir())
        if p.is_file() and p.suffix in ('.py', '.md', '.sbatch')}
    identity['range_execution_commit'] = args.code_commit
    write_json(output / 'identity.json', identity)
    subprocess.run([sys.executable, '-B', str(ROOT / 'test_range_core.py')], check=True)
    subprocess.run([sys.executable, '-B', str(ROOT / 'diagnostic_variance.py')], check=True)
    subprocess.run([sys.executable, '-B', str(OLD / 'vendor/frozen/test_shared.py')], check=True)
    tokenizer, model = load_model(args)
    ids = test_ids(args, tokenizer, identity)
    for name, selected, full in [('bf16_full', ids, True),
            ('bf16_prefix', ids[:, :args.prefix_tokens], False)]:
        scored = score(model, selected, full)
        passed = not full or (scored['scored_tokens'] == 299077
            and abs(scored['perplexity'] - 11.652735047455899) < .02)
        write_json(output / 'runs' / (name + '.json'), dict(scored,
            configuration={'name': name, 'kind': 'baseline'},
            baseline_gate_passed=passed, code_commit=args.code_commit,
            protocol='full_WT2_sliding_window' if full else 'WT2_fixed_test_prefix',
            slurm_job_id=os.environ.get('SLURM_JOB_ID')))
        if not passed:
            raise ValueError('Unchanged BF16 reference failed; stop before comparisons')
    write_json(output / 'suite.json', dict(created_utc=datetime.now(timezone.utc).isoformat(),
        execution_commit=args.code_commit, prefix_tokens=args.prefix_tokens,
        cases=cases(), no_training=True, no_seed_selection=True,
        attention='unchanged original BF16 SDPA',
        weight_mean_note='row64 is reencoded from the SAME old W8 decoded weights; mean controls isolate extra rounding'))
    # Capture unmodified teacher states, from train only. No activations published.
    captures, handles = {}, []
    for index, layer in enumerate(model.model.layers):
        def capture(module, inputs, index=index):
            captures[index] = inputs[0].detach().reshape(-1, inputs[0].shape[-1])[:16].clone()
        handles.append(layer.mlp.register_forward_pre_hook(capture))
    train_ids = tokenizer((Path(args.data) / 'wiki.train.raw').read_text(encoding='utf-8'),
        add_special_tokens=False, return_tensors='pt').input_ids[:, :128].cuda()
    with torch.inference_mode():
        model(input_ids=train_ids, use_cache=False)
    for handle in handles:
        handle.remove()
    projection_diagnostics(args, model, captures, output)
    write_json(output / 'READY.json', dict(code_commit=args.code_commit,
        baseline_gate_passed=True, identity_sha256=digest(output / 'identity.json'),
        diagnostic_sha256=digest(output / 'projection_diagnostics.json'),
        cases=len(cases())))


def projection_diagnostics(args, model, captures, output):
    import torch
    from torch.nn import functional as F
    sys.path.insert(0, str(OLD / 'vendor/frozen'))
    from range_core import encode_input, make_matrix_spec
    from diagnostic_variance import projection_variances
    a_cal, z_cal = calibration()
    rows = []
    with torch.inference_mode():
        for index, layer in enumerate(model.model.layers):
            x = captures[index]
            mlp = layer.mlp
            z = (F.silu(mlp.gate_proj(x)) * mlp.up_proj(x)).float()
            for projection, values, weight, fixed in [
                ('gate', x.float(), mlp.gate_proj.weight, a_cal[str(index)]['x']),
                ('up', x.float(), mlp.up_proj.weight, a_cal[str(index)]['x']),
                ('down', z, mlp.down_proj.weight, z_cal[str(index)])]:
                scale = expand_scale(fixed, values.shape[-1], values.device)
                target = F.linear(values, weight.float())
                power = target.square().mean().item()
                policies = list(VARIANTS.items()) + [('both_idealW', ('dynamic64', 'row64_ideal'))]
                for variant, (ap, wp) in policies:
                    p, decoded, sa = encode_input(values, scale, ap)
                    spec = make_matrix_spec(weight, wp)
                    mean = F.linear(decoded, spec.decoded)
                    va, vw = projection_variances(p, values.sign(), sa, spec, 256)
                    rows.append(dict(layer=index, projection=projection, variant=variant,
                        activation_policy=ap, weight_policy=wp, tokens=values.shape[0],
                        input_mean_probability=p.mean().item(),
                        input_zero_fraction=(p == 0).float().mean().item(),
                        clipping_fraction=(values.abs() > sa).float().mean().item(),
                        input_encoding_nmse=(decoded-values).square().sum().item()/max(values.square().sum().item(), 1e-30),
                        weight_mean_probability=spec.probability.mean().item(),
                        weight_reencoding_nmse=(spec.decoded-spec.reference_decoded).square().sum().item()/max(spec.reference_decoded.square().sum().item(), 1e-30),
                        target_mean_square=power,
                        deterministic_projection_nmse=(mean-target).square().mean().item()/max(power, 1e-30),
                        input_variance_nmse_T256=va.mean().item()/max(power, 1e-30),
                        extra_weight_variance_nmse_T256=vw.mean().item()/max(power, 1e-30),
                        dual_total_mse_nmse_T256=((mean-target).square()+va+vw).mean().item()/max(power, 1e-30)))
            print(json.dumps({'event':'diagnostic_layer','layer':index}), flush=True)
    write_json(output / 'projection_diagnostics.json', dict(rows=rows,
        source='Unchanged BF16 teacher: first16 MLP inputs within first128 train tokens, all24 layers',
        model_revision='060db6499f32faf8b98477b0a26969ef7d8b9987', code_commit=args.code_commit,
        variance='Analytical exact IID law at T256; input covariance for shared64 retained; not Monte Carlo',
        note='Pure local linear projection at identical teacher input; not propagated full-network error or test-tuned range'))


def worker(args):
    import torch
    import transformers
    from range_core import RangeFFN
    output = checked_output(args)
    ready = json.loads((output / 'READY.json').read_text(encoding='utf-8'))
    if ready['code_commit'] != args.code_commit or not ready['baseline_gate_passed']:
        raise ValueError('Preparation gate mismatch')
    identity = json.loads((output / 'identity.json').read_text(encoding='utf-8'))
    if digest(output / 'identity.json') != ready['identity_sha256']:
        raise ValueError('Identity evidence changed')
    for name, checksum in identity['range_source_sha256'].items():
        if digest(ROOT / name) != checksum:
            raise ValueError(f'Execution source changed: {name}')
    cfg = cases()[args.index]
    target = output / 'runs' / (cfg['name'] + '.json')
    if target.exists():
        raise FileExistsError(target)
    torch.manual_seed(cfg['seed'])
    tokenizer, model = load_model(args)
    ids = test_ids(args, tokenizer, identity)[:, :args.prefix_tokens]
    a_cal, z_cal = calibration()
    ap, wp = VARIANTS[cfg['variant']]
    attentions = [layer.self_attn for layer in model.model.layers]
    for i, layer in enumerate(model.model.layers):
        layer.mlp = RangeFFN(layer.mlp, a_cal[str(i)], z_cal[str(i)],
            activation_policy=ap, weight_policy=wp, kind=cfg['kind'],
            cycles=cfg['cycles'], seed=cfg['seed'], layer=i, scope=cfg['scope'])
    assert all(layer.self_attn is attentions[i] for i, layer in enumerate(model.model.layers))
    torch.cuda.reset_peak_memory_stats()
    scored = score(model, ids, False)
    result = dict(scored, configuration=cfg, activation_policy=ap, weight_policy=wp,
        protocol='WT2_fixed_test_prefix', context=2048, stride=1024,
        token_ids_sha256=hashlib.sha256(ids.numpy().tobytes()).hexdigest(),
        full_test_token_ids_sha256=identity['tokens']['test']['ids_sha256'],
        identity_sha256=ready['identity_sha256'], code_commit=args.code_commit,
        configuration_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        model_revision=identity['model_revision'], attention='unchanged BF16 SDPA',
        ffn_layers=list(range(24)), accumulation='exact signed counts; no OR',
        stochastic_law='exact conditional Binomial; input shared64; W perconnection independent',
        no_training=True, no_seed_selection=True,
        dynamic_range_cost='Online pertoken/group64 absmax and new scale restore, NOT included in hardware PPA',
        weight_range_cost='row64 uses 64x more scale metadata than legacy tile64x64',
        environment=dict(torch=torch.__version__,transformers=transformers.__version__,
            cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),python=sys.version),
        slurm_job_id=os.environ.get('SLURM_JOB_ID'), command=sys.argv,
        diagnostics={str(i):layer.mlp.diagnostics() for i,layer in enumerate(model.model.layers)})
    write_json(target, result)
    print(json.dumps({'case':cfg['name'],**scored}), flush=True)


def summarize(args):
    output = checked_output(args)
    rows = []
    for path in sorted((output / 'runs').glob('*.json')):
        value = json.loads(path.read_text(encoding='utf-8'))
        rows.append(dict(file=str(path.relative_to(output)),sha256=digest(path),
            **value['configuration'],ppl=value['perplexity'],nll=value['nll'],
            tokens=value['scored_tokens'],seconds=value['forward_seconds']))
    groups = []
    # Post-execution summary-only fix: full/prefix references are different
    # protocols and must never be averaged together. Sampled groups only.
    keys = sorted({(r.get('variant',''),r['kind'],r.get('scope',''),r.get('cycles',0))
                   for r in rows if r['kind'] != 'baseline'})
    for variant, kind, scope, cycles in keys:
        selected = [r for r in rows if (r.get('variant',''),r['kind'],r.get('scope',''),r.get('cycles',0)) == (variant,kind,scope,cycles)]
        values = [r['ppl'] for r in selected if r['ppl'] is not None]
        groups.append(dict(variant=variant,kind=kind,scope=scope,cycles=cycles,
            completed=len(selected),ppl_mean=statistics.mean(values) if values else None,
            ppl_std=statistics.pstdev(values) if values else None))
    write_json(output / 'summary.json',dict(rows=rows,groups=groups,
        references=[r for r in rows if r['kind'] == 'baseline'],
        expected=39,completed=len(rows),prefix_tokens=args.prefix_tokens,
        warning='Only bf16_full is full WT2. All replacement PPL results are a fixed test-prefix diagnostic.'))
    print(json.dumps({'completed':len(rows),'expected':39,'groups':groups}),flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action',choices=('prepare','worker','summarize'))
    p.add_argument('--model',required=True)
    p.add_argument('--data',required=True)
    p.add_argument('--project-root',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--code-commit',required=True)
    p.add_argument('--prefix-tokens',type=int,default=128)
    p.add_argument('--index',type=int,default=0)
    args = p.parse_args()
    if len(args.code_commit) != 40:
        p.error('Exact execution commit required')
    {'prepare':prepare,'worker':worker,'summarize':summarize}[args.action](args)


if __name__ == '__main__':
    main()
