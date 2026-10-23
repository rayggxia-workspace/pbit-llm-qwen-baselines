"""Issue150: TRAIN-calibrated fixed scale ladders; original attention throughout."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
EXP = ROOT.parent
OLD = EXP / 'qwen_dual_iid_exact_20261018'
for area in (OLD, EXP/'qwen_dual_range_20261018', EXP/'qwen_multiscale_stratified_20261019'):
    sys.path.insert(0, str(area))
from verify import digest, verify, write_json
from run import score
from run_ranges import load_model, test_ids

SPLITS = {'fit': [0, 8192], 'selection': [16384, 24576], 'holdout': [32768, 40960]}
CANDIDATES = [{'name': 'd%d_h%d' % (d, h), 'gap': d, 'headroom': h}
              for d in (1, 2, 3) for h in (0, 1)]
AREAS = ('qwen_static_multiscale_20261023', 'qwen_multiscale_stratified_20261019',
         'qwen_fixedw_multiscale_20261019', 'qwen_dual_range_20261018',
         'qwen_dual_iid_exact_20261018')


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def source_hashes():
    return {str(p.relative_to(EXP.parent)).replace('\\', '/'): digest(p)
            for name in AREAS for p in sorted((EXP/name).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts
            and p.suffix in ('.py', '.json', '.md', '.sbatch')}


def signed_write(path, result):
    if path.exists():
        raise FileExistsError(path)
    write_json(path, result)
    write_json(path.with_suffix('.sha256.json'), {'file': path.name, 'sha256': digest(path)})


def read_signed(path):
    marker = json.loads(path.with_suffix('.sha256.json').read_text(encoding='utf-8'))
    if marker['sha256'] != digest(path):
        raise ValueError('Result bytes changed: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'))


def output_dir(args):
    project = Path(args.project_root).resolve(strict=True)
    out = Path(args.output).resolve()
    if project not in out.parents or EXP.parent == out or EXP.parent in out.parents:
        raise ValueError('Output must be below personal project and outside snapshot')
    out.mkdir(parents=True, exist_ok=True)
    return out


def cpu(args):
    out = output_dir(args)
    if any((out/name).exists() for name in ('identity.json', 'CPU_READY.json', 'READY.json')):
        raise FileExistsError('CPU preflight must use a fresh output directory')
    identity = verify(args.model, args.data, out/'identity.json')
    identity.update(execution_commit=args.code_commit, executed_source=source_hashes(),
                    attention='unchanged original BF16 SDPA', splits=SPLITS,
                    randomness='exact shared64 randomized stratification, not physical IID')
    write_json(out/'identity.json', identity)
    for test in (ROOT/'test_static_core.py', EXP/'qwen_multiscale_stratified_20261019/test_stratified_core.py',
                 EXP/'qwen_fixedw_multiscale_20261019/test_multiscale_core.py'):
        subprocess.run([sys.executable, '-B', str(test)], check=True)
    signed_write(out/'CPU_READY.json', {'status': 'completed', 'code_commit': args.code_commit,
                 'identity_sha256': digest(out/'identity.json'), 'source': source_hashes(),
                 'job_id': os.environ.get('SLURM_JOB_ID')})


def identity_check(args):
    out = output_dir(args)
    ready = read_signed(out/'CPU_READY.json')
    if ready['code_commit'] != args.code_commit or ready['source'] != source_hashes():
        raise ValueError('Immutable execution source changed')
    if ready['identity_sha256'] != digest(out/'identity.json'):
        raise ValueError('Identity changed')
    identity = json.loads((out/'identity.json').read_text(encoding='utf-8'))
    for name, entry in identity['files'].items():
        area, rel = name.split('/', 1)
        path = (Path(args.model) if area == 'model' else Path(args.data))/rel
        if path.resolve() != Path(entry['path']).resolve() or \
                path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError('Model/data no longer match preflight: ' + name)
    return out, identity


def patch(model, cfg, tables=None, observer=None):
    from static_core import StaticFFN
    attentions = [layer.self_attn for layer in model.model.layers]
    for i, layer in enumerate(model.model.layers):
        entry = None if tables is None else tables[str(i)]
        x = entry['x'] if entry is not None and cfg['scope'] in ('both', 'x') else None
        z = entry['z'] if entry is not None and cfg['scope'] in ('both', 'z') else None
        layer.mlp = StaticFFN(layer.mlp, x_scales=x, z_scales=z, mode=cfg['mode'],
                             cycles=cfg['cycles'], strata=cfg['cycles'], seed=cfg['seed'], layer=i)
        layer.mlp.observer = observer
    assert len(model.model.layers) == 24
    assert all(layer.self_attn is attentions[i] for i, layer in enumerate(model.model.layers))


def cfg(name, scope='both', mode='sampled', cycles=32, seed=0):
    return dict(name=name, scope=scope, mode=mode, cycles=cycles, strata=cycles, seed=seed,
                bins=4, group=64, probability_bits=8, weight='fixed historical W8/64x64')


def evaluate(args, ids, configuration, tables=None, full=False):
    import torch
    _, model = load_model(args)
    patch(model, configuration, tables)
    torch.cuda.reset_peak_memory_stats()
    measured = score(model, ids, full)
    diagnostics = {str(i): layer.mlp.diagnostics() for i, layer in enumerate(model.model.layers)}
    forwarded = sum(min(2048, ids.shape[-1]-1024*i) for i in range(measured['windows']))
    for i, layer in enumerate(model.model.layers):
        d = diagnostics[str(i)]
        if d['calls'] != measured['windows'] or \
                d['x_values'] != forwarded*layer.mlp.gu_decoded.shape[1] or \
                d['z_values'] != forwarded*layer.mlp.down_decoded.shape[1]:
            raise ValueError('FFN all-token scoring coverage mismatch at layer '+str(i))
    measured.update(diagnostics=diagnostics, peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    ffn_layers=list(range(24)), ffn_calls_per_layer=measured['windows'],
                    forwarded_tokens=forwarded, all_token_ffn_coverage_verified=True)
    del model
    torch.cuda.empty_cache()
    return measured


def prepare(args):
    import torch
    import transformers
    out, identity = identity_check(args)
    if (out/'CALIBRATION.json').exists():
        raise FileExistsError('Use a new output for a new execution, never overwrite calibration')
    tokenizer, model = load_model(args)
    ids = test_ids(args, tokenizer, identity)
    baseline = score(model, ids, True)
    if baseline['scored_tokens'] != 299077 or abs(baseline['perplexity']-11.652735047455899) >= .02:
        raise ValueError('Unmodified BF16 baseline gate failed')
    signed_write(out/'runs/bf16_full.json', dict(baseline, status='completed',
                 configuration={'name': 'bf16_full', 'mode': 'baseline'}, baseline_gate_passed=True,
                 code_commit=args.code_commit, identity_sha256=digest(out/'identity.json'),
                 token_ids_sha256=identity['tokens']['test']['ids_sha256'],
                 protocol='full_WT2_test_sliding_window_2048_1024', ffn_layers=[],
                 attention='unchanged original BF16 SDPA', job_id=os.environ.get('SLURM_JOB_ID')))
    text = (Path(args.data)/'wiki.train.raw').read_text(encoding='utf-8')
    train = tokenizer(text, add_special_tokens=False, return_tensors='pt').input_ids
    if hashlib.sha256(train.numpy().tobytes()).hexdigest() != identity['tokens']['train']['ids_sha256']:
        raise ValueError('TRAIN identity mismatch')
    del model
    torch.cuda.empty_cache()
    capture = {}
    def observer(layer, signal, values):
        key = str(layer) + ':' + signal
        grouped = values.detach().float().reshape(-1, values.shape[-1]//64, 64)
        maximum = grouped.abs().amax(dim=(0, 2)).cpu()
        if not bool(torch.isfinite(maximum).all()):
            raise FloatingPointError('Nonfinite calibration activations')
        if key not in capture:
            capture[key] = maximum
        else:
            capture[key] = torch.maximum(capture[key], maximum)
    # Capture both W8-continuous and deployed dynamic-sampled propagation.
    for mode in ('w8_only', 'sampled'):
        _, model = load_model(args)
        patch(model, cfg('capture_'+mode, mode=mode, seed=917), observer=observer)
        with torch.inference_mode():
            for start in range(*SPLITS['fit'], 2048):
                model(input_ids=train[:, start:start+2048].cuda(), use_cache=False)
        print(json.dumps({'event': 'captured', 'path': mode}), flush=True)
        del model
        torch.cuda.empty_cache()
    tables = {}
    for candidate in CANDIDATES:
        entries = {}
        for layer in range(24):
            entries[str(layer)] = {}
            for signal in ('x', 'z'):
                maximum = capture[str(layer)+':'+signal]
                mantissa, exponent = torch.frexp(maximum)
                exponent = exponent - (mantissa == .5).to(exponent.dtype)
                exponent = torch.where(maximum == 0, torch.zeros_like(exponent), exponent)
                top = exponent + candidate['headroom']
                exponents = top[:, None] - candidate['gap'] * torch.arange(4)
                entries[str(layer)][signal] = torch.ldexp(torch.ones_like(exponents).float(), exponents).tolist()
        tables[candidate['name']] = entries
    calibration = {'status': 'completed', 'code_commit': args.code_commit,
                   'identity_sha256': digest(out/'identity.json'),
                   'capture_paths': ['W8-only', 'dynamic_B4_T32_K32_seed917'],
                   'splits': {k: {'range': v, 'token_sha256': hashlib.sha256(train[:,v[0]:v[1]].numpy().tobytes()).hexdigest()}
                              for k,v in SPLITS.items()}, 'candidate_definitions': CANDIDATES,
                   'tables': tables, 'observed_maxima': {k:v.tolist() for k,v in capture.items()},
                   'selection_rule': 'minimum mean TRAIN-selection NLL over seeds101,102; tie by candidate name',
                   'test_used_for_calibration_or_selection': False, 'online_max': False}
    signed_write(out/'CALIBRATION.json', calibration)
    selection = []
    sid = train[:, SPLITS['selection'][0]:SPLITS['selection'][1]]
    for candidate in CANDIDATES:
        for seed in (101, 102):
            c = cfg(candidate['name']+'_select_s'+str(seed), seed=seed)
            result = evaluate(args, sid, c, tables[candidate['name']])
            signed_write(out/'selection'/(c['name']+'.json'), dict(result, status='completed', configuration=c,
                         candidate=candidate['name'], code_commit=args.code_commit,
                         calibration_sha256=digest(out/'CALIBRATION.json'),
                         protocol='WT2_TRAIN_selection_8192_tokens',
                         token_ids_sha256=calibration['splits']['selection']['token_sha256']))
            selection.append({'candidate': candidate['name'], 'seed': seed, 'nll': result['nll'],
                              'perplexity': result['perplexity']})
            print(json.dumps({'event': 'selection', **selection[-1]}), flush=True)
    ranked = sorted((sum(r['nll'] for r in selection if r['candidate']==c['name'])/2., c['name']) for c in CANDIDATES)
    selected = ranked[0][1]
    # Freeze before untouched holdout and test evaluation; neither can alter selection.
    signed_write(out/'SELECTED.json', {'status': 'completed', 'name': selected,
                 'code_commit': args.code_commit, 'selection_rows': selection, 'ranking': ranked,
                 'calibration_sha256': digest(out/'CALIBRATION.json'), 'tables': tables[selected],
                 'tables_sha256': canonical_sha(tables[selected]),
                 'selection_seeds': [101,102], 'fit_seed': 917,
                 'test_used_for_selection': False, 'online_max': False})
    hid = train[:, SPLITS['holdout'][0]:SPLITS['holdout'][1]]
    for scope in ('dynamic', 'both'):
        for seed in (201, 202):
            c = cfg('holdout_'+scope+'_s'+str(seed), scope=scope, seed=seed)
            result = evaluate(args, hid, c, tables[selected])
            signed_write(out/'holdout'/(c['name']+'.json'), dict(result, status='completed', configuration=c,
                         code_commit=args.code_commit, selected_sha256=digest(out/'SELECTED.json'),
                         protocol='WT2_TRAIN_holdout_8192_tokens',
                         token_ids_sha256=calibration['splits']['holdout']['token_sha256']))
    signed_write(out/'READY.json', {'status': 'completed', 'code_commit': args.code_commit,
                 'bf16_full_sha256': digest(out/'runs/bf16_full.json'),
                 'selected_sha256': digest(out/'SELECTED.json'), 'calibration_sha256': digest(out/'CALIBRATION.json'),
                 'identity_sha256': digest(out/'identity.json'), 'cases': cases(), 'cases_sha256': canonical_sha(cases()),
                 'environment': {'torch': torch.__version__, 'transformers': transformers.__version__,
                                 'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name()},
                 'job_id': os.environ.get('SLURM_JOB_ID')})
    print(json.dumps({'event': 'ready', 'selected': selected, 'full_cases': len(cases())}), flush=True)


def cases():
    result = [cfg('w8_only', mode='w8_only'), cfg('fixed_mean', mode='mean')]
    for scope, cycles in (('dynamic',32), ('both',32), ('x',32), ('z',32), ('dynamic',64), ('both',64)):
        for seed in (0,1,2):
            result.append(cfg('%s_T%d_s%d' % (scope,cycles,seed), scope=scope, cycles=cycles, seed=seed))
    return result


def worker(args):
    out, identity = identity_check(args)
    ready = read_signed(out/'READY.json')
    selected = read_signed(out/'SELECTED.json')
    baseline = read_signed(out/'runs/bf16_full.json')
    if not baseline['baseline_gate_passed'] or \
            ready['bf16_full_sha256'] != digest(out/'runs/bf16_full.json'):
        raise ValueError('Same-run BF16 evidence changed')
    if (ready['code_commit'] != args.code_commit or ready['cases_sha256'] != canonical_sha(cases()) or
        ready['selected_sha256'] != digest(out/'SELECTED.json') or
        ready['calibration_sha256'] != digest(out/'CALIBRATION.json')):
        raise ValueError('Frozen selection/configuration changed')
    configuration = cases()[args.index]
    target = out/'runs'/(configuration['name']+'.json')
    if target.exists():
        raise FileExistsError(target)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    ids = test_ids(args, tokenizer, identity)
    measured = evaluate(args, ids, configuration, selected['tables'], full=True)
    signed_write(target, dict(measured, status='completed', configuration=configuration,
                 code_commit=args.code_commit, configuration_sha256=canonical_sha(configuration),
                 identity_sha256=digest(out/'identity.json'), selected_sha256=digest(out/'SELECTED.json'),
                 calibration_sha256=digest(out/'CALIBRATION.json'),
                 scale_tables_sha256=selected['tables_sha256'], fixed_ladder=selected['name'],
                 token_ids_sha256=identity['tokens']['test']['ids_sha256'],
                 model_revision=identity['model_revision'], context=2048, stride=1024,
                 protocol='full_WT2_test_sliding_window_2048_1024',
                 attention='unchanged original BF16 SDPA; no screening, Ising or PV sampling',
                 physical_rng_replay=False, finite_width_bittrue=False, trained=False,
                 randomness='K=T randomized stratification, shared64 including across bins; not IID',
                 job_id=os.environ.get('SLURM_JOB_ID'), command=sys.argv))
    print(json.dumps({'event': 'completed', 'name': configuration['name'], 'ppl': measured['perplexity'],
                      'seconds': measured['forward_seconds']}), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=('cpu', 'prepare', 'worker'))
    for key in ('model', 'data', 'project-root', 'output', 'code-commit'):
        p.add_argument('--'+key, required=True)
    p.add_argument('--index', type=int, default=0)
    args = p.parse_args()
    if len(args.code_commit) != 40:
        p.error('exact execution SHA required')
    globals()[args.action](args)


if __name__ == '__main__':
    main()
