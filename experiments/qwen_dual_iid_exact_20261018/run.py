"""Issue30: exact conditional IID two-stream short probe, accurate Attention."""
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
from verify import ROOT, digest, verify, write_json

LENGTHS = (64, 128, 256, 1024, 4096)
SEEDS = (0, 1, 2)


def cases():
    return [{'name': f'{kind}_T{cycles}_s{seed}', 'kind': kind,
             'cycles': cycles, 'seed': seed, 'bits': 8, 'sharing': 64}
            for cycles in LENGTHS for seed in SEEDS
            for kind in ('dual_binomial', 'dual_gaussian', 'fixed_exact')]


def case_config(name):
    if name in ('bf16_full', 'bf16_prefix'):
        return {'name': name, 'kind': 'baseline', 'cycles': 4096,
                'seed': 0, 'bits': 16, 'sharing': 0}
    return next(c for c in cases() if c['name'] == name)


def finite_ppl(nll):
    # Retain the NLL when an extremely poor low-T model exceeds FP64 exp range.
    return math.exp(nll) if nll <= math.log(sys.float_info.max) else None


def checked_output(args):
    project = Path(args.project_root).resolve(strict=True)
    output = Path(args.output).resolve()
    if output != project and project not in output.parents:
        raise ValueError('Output must stay inside the verified personal project directory')
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Outputs must not modify the immutable execution snapshot')
    output.mkdir(parents=True, exist_ok=True)
    return output


def score(model, ids, full):
    import torch
    from torch.nn import functional as F
    length = ids.shape[-1]
    total, scored, starts = 0., 0, []
    for begin in range(0, length, 1024):
        starts.append(begin)
        if min(begin + 2048, length) == length:
            break
    t0 = time.perf_counter()
    for index, begin in enumerate(starts):
        end = min(begin + 2048, length)
        window = ids[:, begin:end].cuda()
        with torch.inference_mode():
            logits = model(input_ids=window, use_cache=False).logits[:, :-1].float()
        if not bool(torch.isfinite(logits).all()):
            raise FloatingPointError('Nonfinite logits')
        threshold = begin + 1 if index == 0 else begin + 1024
        mask = torch.arange(begin + 1, end, device='cuda') >= threshold
        labels = window[:, 1:]
        loss = F.cross_entropy(logits[:, mask].reshape(-1, logits.shape[-1]),
            labels[:, mask].reshape(-1), reduction='sum')
        total += loss.item()
        scored += labels[:, mask].numel()
        if full and (index == 0 or (index + 1) % 25 == 0 or index + 1 == len(starts)):
            print(json.dumps({'event': 'baseline_progress', 'windows': index + 1,
                'total_windows': len(starts), 'running_ppl': math.exp(total / scored)}), flush=True)
    torch.cuda.synchronize()
    if scored != length - 1:
        raise AssertionError(f'Incorrect scoring coverage: {scored} != {length - 1}')
    nll = total / scored
    ppl = finite_ppl(nll)
    return {'scored_tokens': scored, 'input_tokens': length, 'windows': len(starts),
        'nll_sum': total, 'nll': nll, 'perplexity': ppl,
        'perplexity_status': 'finite' if ppl is not None else 'FP64_exp_overflow_NLL_retained',
        'forward_seconds': time.perf_counter() - t0}


def worker(args):
    """A fresh process per configuration prevents mutable historical factory state."""
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    sys.path.insert(0, str(ROOT / 'vendor/frozen'))
    from run_shared import SharedFFN
    output = checked_output(args)
    identity_path = output / 'identity.json'
    identity = json.loads(identity_path.read_text(encoding='utf-8'))
    if identity['status'] != 'verified':
        raise ValueError('Identity gate has not passed')
    cfg = case_config(args.case)
    target = output / 'runs' / (cfg['name'] + '.json')
    if target.exists():
        raise FileExistsError(target)
    if cfg['kind'] != 'baseline':
        baseline = json.loads((output / 'runs/bf16_full.json').read_text(encoding='utf-8'))
        if not baseline['baseline_gate_passed']:
            raise ValueError('Unchanged full BF16 reference gate failed')
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.manual_seed(cfg['seed'])
    loaded_at = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda().eval()
    model.requires_grad_(False)
    ids = tokenizer((Path(args.data) / 'wiki.test.raw').read_text(encoding='utf-8'),
        add_special_tokens=False, return_tensors='pt').input_ids
    source_tokens = ids.shape[-1]
    full_ids_sha256 = hashlib.sha256(ids.numpy().tobytes()).hexdigest()
    if (source_tokens != identity['tokens']['test']['tokens'] or
            full_ids_sha256 != identity['tokens']['test']['ids_sha256']):
        raise ValueError('Worker full test token identity differs from the verified identity gate')
    if cfg['name'] != 'bf16_full':
        ids = ids[:, :args.prefix_tokens]
    installed = []
    if cfg['kind'] != 'baseline':
        old = json.loads((ROOT / 'vendor/frozen/results/calibration.json').read_text(encoding='utf-8'))
        sz = json.loads((ROOT / 'vendor/frozen/results/sz_calibration.json').read_text(encoding='utf-8'))
        backend = 'gaussian' if cfg['kind'] == 'dual_gaussian' else 'binomial'
        weight = 'fixed' if cfg['kind'] == 'fixed_exact' else 'dual'
        attentions = [layer.self_attn for layer in model.model.layers]
        for index, layer in enumerate(model.model.layers):
            layer.mlp = SharedFFN(layer.mlp, old['policies']['group_max'][str(index)],
                'fixed_exact' if weight == 'fixed' else 'dual_exact', bits=8,
                cycles=cfg['cycles'], seed=cfg['seed'], layer=index,
                variant='sz_group', backend=backend, sz=sz['fixed_group'][str(index)],
                sharing=64, weight=weight)
            installed.append(index)
        assert len(installed) == 24
        assert all(layer.self_attn is attentions[i] for i, layer in enumerate(model.model.layers))
    loading_seconds = time.perf_counter() - loaded_at
    torch.cuda.reset_peak_memory_stats()
    scored = score(model, ids, cfg['name'] == 'bf16_full')
    full = cfg['name'] == 'bf16_full'
    gate = (full and scored['scored_tokens'] == 299077 and scored['perplexity'] is not None
            and abs(scored['perplexity'] - 11.652735047455899) < .02)
    result = dict(scored, configuration=cfg,
        protocol='full_WT2_test_sliding_window' if full else 'WT2_test_first_128_token_probe' if args.prefix_tokens == 128 else 'WT2_test_prefix_probe',
        context=2048, stride=1024, source_tokens=source_tokens,
        token_ids_sha256=hashlib.sha256(ids.numpy().tobytes()).hexdigest(),
        full_test_token_ids_sha256=full_ids_sha256,
        attention='unchanged original BF16 SDPA; no PV sampling, Ising or screening',
        ffn_layers=installed, weight_format='symmetric INT8 per 64x64 tile',
        activation_format='A8 magnitude q/256 plus separate sign; frozen per64 Sx/Sz',
        stages='T samples for gate/up; exact FP32 SiLU(g)*u; fixed Sz reencode; fresh T samples for down',
        accumulation='exact signed spatial sum and temporal count; no OR or saturation model',
        weight_probability='abs(INT8 code)/127; restored event amplitude 127*tile_LSB',
        input_sharing='same IID uniform word per64 input channels; independent across token/group/layer/stage',
        weight_sharing='independent per connection and independent of input',
        physical_rng_replay=False, sequence_selection=False, trained=False,
        distribution='exact conditional Binomial weight counts' if cfg['kind'] == 'dual_binomial' else
            'conditional Gaussian residual approximation' if cfg['kind'] == 'dual_gaussian' else
            'exact joint shared-input count distribution and exact fixed-weight projection' if cfg['kind'] == 'fixed_exact' else 'unchanged BF16',
        baseline_gate_passed=bool(gate) if full else None, baseline_tolerance_abs_ppl=.02 if full else None,
        code_commit=args.code_commit, identity_sha256=digest(identity_path),
        configuration_sha256=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
        source_sha256=identity['source_sha256'],
        model_revision=identity['model_revision'], loading_seconds=loading_seconds,
        slurm_job_id=os.environ.get('SLURM_JOB_ID'), command=sys.argv,
        environment={'torch': torch.__version__, 'transformers': transformers.__version__,
            'python': sys.version, 'gpu': torch.cuda.get_device_name(),
            'cuda': torch.version.cuda, 'tf32': False},
        peak_allocated_bytes=torch.cuda.max_memory_allocated(),
        diagnostics={str(i): model.model.layers[i].mlp.diagnostics() for i in installed})
    if cfg['kind'] == 'baseline':
        result.update(weight_format='original checkpoint BF16 weights; no INT8 replacement',
            activation_format='original BF16 model activations; no probability encoding',
            stages='original BF16 Qwen FFN SiLU(gate_proj(x))*up_proj(x), then down_proj',
            accumulation='original unchanged BF16 model arithmetic',
            weight_probability=None, input_sharing=None, weight_sharing=None,
            ffn_scope='no FFN replacement; all 24 original FFNs')
    else:
        result['ffn_scope'] = 'all 24 FFNs replaced; attention unchanged'
    write_json(target, result)
    print(json.dumps({'case': cfg['name'], **scored, 'baseline_gate_passed': gate}), flush=True)
    if full and not gate:
        raise ValueError('Full BF16 baseline differs from historical reference; stop before comparisons')


def summarize(output):
    rows = []
    for p in sorted((output / 'runs').glob('*.json')):
        d = json.loads(p.read_text(encoding='utf-8'))
        rows.append({'file': str(p.relative_to(output)), 'sha256': digest(p),
            **d['configuration'], 'protocol': d['protocol'], 'ppl': d['perplexity'],
            'nll': d['nll'], 'tokens': d['scored_tokens'], 'seconds': d['forward_seconds']})
    groups = []
    for kind in ('dual_binomial', 'dual_gaussian', 'fixed_exact'):
        for cycles in LENGTHS:
            found = [r for r in rows if r['kind'] == kind and r['cycles'] == cycles]
            values = [r['ppl'] for r in found if r['ppl'] is not None]
            groups.append({'kind': kind, 'cycles': cycles, 'completed_seeds': len(found),
                'finite_ppl_seeds': len(values), 'overflow_seeds': len(found) - len(values),
                'ppl_mean': statistics.mean(values) if values else None,
                'ppl_population_std': statistics.pstdev(values) if values else None})
    write_json(output / 'summary.json', {'rows': rows, 'groups': groups,
        'expected_cases': 47, 'completed_cases': len(rows),
        'warning': 'Only bf16_full is full WT2 PPL; all sampled results are fixed test-prefix probes, not full WT2 PPL.'})
    lines = ['# Qwen双随机IID精确短片段核查', '',
        '只有原BF16参考为完整WT2；所有随机配置为相同测试前缀，不作为完整WT2 PPL。', '',
        '| 方案 | T | 短片段PPL均值±总体标准差 | 已完成seed |', '|---|---:|---:|---:|']
    for row in groups:
        val = ('PPL指数溢出，NLL已保存' if row['overflow_seeds'] else '未完成') if row['ppl_mean'] is None else f"{row['ppl_mean']:.6g} ± {row['ppl_population_std']:.6g}"
        if row['ppl_mean'] is not None and row['overflow_seeds']:
            val += f"（仅有限值；另{row['overflow_seeds']}项溢出）"
        lines.append(f"| {row['kind']} | {row['cycles']} | {val} | {row['completed_seeds']} |")
    (output / 'RESULTS_ZH.md').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


def orchestrate(args):
    output = checked_output(args)
    if any((output / name).exists() for name in ('identity.json', 'suite.json')):
        raise FileExistsError('Use a fresh output directory; do not overwrite execution evidence')
    verify(args.model, args.data, output / 'identity.json')
    write_json(output / 'suite.json', {'code_commit': args.code_commit,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'argv': sys.argv,
        'prefix_tokens': args.prefix_tokens, 'cases': cases(), 'seeds_predeclared': list(SEEDS),
        'no_sequence_or_seed_selection': True})
    # Existing independent sampler/nonlinear scale tests run before any full inference.
    subprocess.run([sys.executable, '-B', str(ROOT / 'vendor/frozen/test_shared.py')], check=True)
    subprocess.run([sys.executable, '-B', str(ROOT / 'vendor/frozen/test_sz.py')], check=True)
    names = ['bf16_full', 'bf16_prefix'] + [c['name'] for c in cases()]
    try:
        for name in names:
            command = [sys.executable, '-B', str(ROOT / 'run.py'), 'worker',
                '--model', args.model, '--data', args.data, '--project-root', args.project_root,
                '--output', str(output), '--code-commit', args.code_commit,
                '--prefix-tokens', str(args.prefix_tokens), '--case', name]
            print(json.dumps({'event': 'start_case', 'name': name}), flush=True)
            subprocess.run(command, check=True)
    finally:
        summarize(output)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=('all', 'worker', 'summarize'))
    p.add_argument('--model', required=True)
    p.add_argument('--data', required=True)
    p.add_argument('--project-root', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--code-commit', required=True)
    p.add_argument('--prefix-tokens', type=int, choices=(128, 256), default=128)
    p.add_argument('--case', default='bf16_full')
    a = p.parse_args()
    if len(a.code_commit) != 40 or any(c not in '0123456789abcdef' for c in a.code_commit):
        p.error('--code-commit must be the exact 40-character execution source commit')
    if a.action == 'all':
        orchestrate(a)
    elif a.action == 'worker':
        worker(a)
    else:
        summarize(checked_output(a))


if __name__ == '__main__':
    main()
