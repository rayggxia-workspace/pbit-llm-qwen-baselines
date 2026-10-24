"""Issue168: frozen TRAIN tables and matched vectorized suffix pilot, Slurm only."""
import argparse
import gc
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

import torch
from torch.nn import functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

from qwen3.baselines.support import check_config, check_data, save, sha256, verify_files, verify_source
from qwen3.stochastic.vendor.scoring import suffix_plan, ids_sha256, target_positions
from .static_core import StaticFFN, _validated_scales, _scale_metadata

SOURCE = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name('config.json')


def sealed(path, obj):
    if path.exists():
        raise FileExistsError(path)
    save(path, obj)
    save(path.with_suffix('.sha256.json'), dict(file=path.name, sha256=sha256(path)))


def configure(model, mode, cycles, seed, tables=None, fixed_x=False, fixed_z=False):
    for i, layer in enumerate(model.model.layers):
        m = layer.mlp
        m.mode, m.cycles, m.strata, m.seed, m.calls = mode, cycles, cycles, seed, 0
        m.observer = None
        m.rng_input.manual_seed(700001 + seed * 1000 + i * 7)
        m.rng_product.manual_seed(700002 + seed * 1000 + i * 7)
        for signal, fixed in [('x', fixed_x), ('z', fixed_z)]:
            weight = m.gu_decoded if signal == 'x' else m.down_decoded
            table = _validated_scales(tables[str(i)][signal], weight.shape[1] // 64,
                                     weight.device) if fixed else None
            setattr(m, signal + '_scales', table)
            m.scale_metadata[signal] = _scale_metadata(table)
            for suffix in ['_stats', '_bins', '_clip_stats']:
                getattr(m, signal + suffix).zero_()


def score(model, ids, config):
    """Every input prefix is processed by the selected FFN, accurate causal SDPA."""
    plan = suffix_plan(len(ids), config['context'], config['decode'], config['examples'])
    layers = model.model.layers
    calls, tokens, seen = [0] * len(layers), [0] * len(layers), []
    handles = []
    for i, layer in enumerate(layers):
        def hook(module, args, i=i):
            seen.append(i)
            calls[i] += 1
            tokens[i] += args[0].shape[0] * args[0].shape[1]
        handles.append(layer.mlp.register_forward_pre_hook(hook))
    rows = []
    start = time.monotonic()
    try:
        with torch.inference_mode():
            for row in plan:
                seen.clear()
                values = ids[row['begin']:row['end']].unsqueeze(0).to(next(model.parameters()).device)
                hidden = model.model(input_ids=values[:, :-1], use_cache=False).last_hidden_state
                first = row['first_target'] - row['begin']
                logits = model.lm_head(hidden[:, first - 1:]).float()
                targets = values[:, first:]
                losses = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1), reduction='none')
                nll = losses.double().sum().item()
                assert seen == list(range(len(layers))) and targets.numel() == config['decode']
                assert math.isfinite(nll)
                rows.append(dict(row, nll_sum=nll))
                del hidden, logits, targets, values, losses
    finally:
        for handle in handles:
            handle.remove()
    n = sum(r['scored_tokens'] for r in rows)
    nll = math.fsum(r['nll_sum'] for r in rows)
    assert n == config['examples'] * config['decode']
    assert calls == [len(plan)] * len(layers)
    return dict(status='completed', protocol='vectorized suffix; not full WT2; no chat template',
                scored_tokens=n, nll_sum=nll, perplexity=math.exp(nll / n), rows=rows,
                target_positions_sha256=ids_sha256(p for r in plan for p in target_positions(r)),
                all_layer_calls=calls, all_layer_input_tokens=tokens,
                seconds=time.monotonic() - start)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    args = p.parse_args()
    root = Path(args.root).resolve()
    assert str(root) == '/home/Hongjie_Zeng/projects/pbit-qwen3-fixed-scale-20261024-issue168'
    assert os.environ.get('SLURM_JOB_ID')
    config = json.loads(CONFIG.read_text())
    source = verify_source(SOURCE)
    prepared_path = Path(config['prepared'])
    prepared = json.loads(prepared_path.read_text())
    assert prepared['model'] == config['model'] and prepared['cpu_prepare_ok']
    verify_files(prepared)
    data = check_data(config)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.manual_seed(0)
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    tokenizer = AutoTokenizer.from_pretrained(prepared['local_path'], local_files_only=True)
    def tokenize(split):
        return tokenizer(Path(data[split]['path']).read_bytes().decode('utf-8'),
                         return_tensors='pt', add_special_tokens=False).input_ids[0]
    test_ids, train_ids = tokenize('wiki.test.raw'), tokenize('wiki.train.raw')
    assert ids_sha256(test_ids.tolist()) == prepared['test_token_ids_sha256_le_int64']
    provenance = dict(model=config['model'], data=data, prepared_sha256=sha256(prepared_path),
        test_tokens_sha256=ids_sha256(test_ids.tolist()), train_tokens_sha256=ids_sha256(train_ids.tolist()),
        source=source, config_sha256=sha256(CONFIG), command=[sys.executable, *sys.argv],
        environment=dict(torch=torch.__version__, cuda=torch.version.cuda, gpu=torch.cuda.get_device_name(),
                         host=platform.node(), slurm_job_id=os.environ['SLURM_JOB_ID']))
    sealed(root / 'results/provenance.json', provenance)
    model = AutoModelForCausalLM.from_pretrained(prepared['local_path'], local_files_only=True,
                torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda().eval()
    check_config(model.config, config['model'])
    assert len(model.model.layers) == 36
    result = score(model, test_ids, config)
    result.update(case='bf16', provenance_sha256=sha256(root / 'results/provenance.json'))
    sealed(root / 'results/bf16.json', result)
    print('BF16', result['perplexity'], result['seconds'], flush=True)
    for i, layer in enumerate(model.model.layers):
        layer.mlp = StaticFFN(layer.mlp, mode='w8_only', layer=i).eval()
    gc.collect()
    torch.cuda.empty_cache()
    immutable = [(t, t._version, t.data_ptr()) for t in model.parameters()]
    immutable += [(getattr(layer.mlp, name), getattr(layer.mlp, name)._version,
                   getattr(layer.mlp, name).data_ptr()) for layer in model.model.layers
                  for name in ('gu_codes', 'gu_decoded', 'gu_tile_lsb',
                               'down_codes', 'down_decoded', 'down_tile_lsb')]
    # TRAIN-only top ranges cover both W8-continuous and dynamic-sampled paths.
    maxima = {}
    def observe(layer, signal, value):
        maximum = value.float().reshape(-1, value.shape[-1] // 64, 64).abs().amax(dim=(0, 2))
        key = (layer, signal)
        maxima[key] = torch.maximum(maxima[key], maximum) if key in maxima else maximum
    length = config['calibration_length']
    starts = [round((len(train_ids) - length) * i / (config['calibration_examples'] - 1))
              for i in range(config['calibration_examples'])]
    for mode in ['w8_only', 'sampled']:
        configure(model, mode, 32, 917)
        for layer in model.model.layers:
            layer.mlp.observer = observe
        with torch.inference_mode():
            for start in starts:
                model.model(input_ids=train_ids[start:start + length].unsqueeze(0).cuda(), use_cache=False)
        print('CALIBRATION', mode, flush=True)
    tables = {}
    for (i, signal), maximum in maxima.items():
        mantissa, exponent = torch.frexp(maximum)
        exponent -= (mantissa == .5).to(exponent.dtype)
        exponent = torch.where(maximum == 0, torch.zeros_like(exponent), exponent)
        top = torch.ldexp(torch.ones_like(maximum), exponent)
        tables.setdefault(str(i), {})[signal] = torch.stack([top / 4**j for j in range(4)], -1).cpu().tolist()
    sealed(root / 'results/calibration.json', dict(status='completed', tables=tables,
        train_starts=starts, train_length=length, paths=['w8_only', 'dynamic_T32_K32_seed917'],
        calibration_train_tokens_per_path=length * len(starts), rule='maxabs ceilPoT; d2; no headroom',
        provenance_sha256=sha256(root / 'results/provenance.json')))
    del maxima
    cases = [('w8_only', 'w8_only', 32, 0, False, False), ('fixed_mean', 'mean', 32, 0, True, True)]
    for label, cycles, fx, fz in [('dynamic32', 32, False, False), ('fixed32', 32, True, True),
                                 ('dynamic64', 64, False, False), ('fixed64', 64, True, True),
                                 ('fixed_x32', 32, True, False)]:
        cases.extend((label, 'sampled', cycles, seed, fx, fz) for seed in config['seeds'])
    for label, mode, cycles, seed, fx, fz in cases:
        print('START', label, seed, flush=True)
        configure(model, mode, cycles, seed, tables, fx, fz)
        torch.cuda.reset_peak_memory_stats()
        result = score(model, test_ids, config)
        assert all(t._version == version and t.data_ptr() == ptr for t, version, ptr in immutable)
        assert all(getattr(layer.mlp, s + '_scales') is None or
                   _scale_metadata(getattr(layer.mlp, s + '_scales')) == layer.mlp.scale_metadata[s]
                   for layer in model.model.layers for s in ('x', 'z'))
        result.update(case=label, seed=seed, cycles=cycles, strata=cycles, fixed_x=fx, fixed_z=fz,
            mode=mode, scale_bins=4, exponent_spacing=2,
            provenance_sha256=sha256(root / 'results/provenance.json'),
            calibration_sha256=sha256(root / 'results/calibration.json'),
            diagnostics={str(i): layer.mlp.diagnostics() for i, layer in enumerate(model.model.layers)},
            peak_allocated_bytes=torch.cuda.max_memory_allocated())
        assert all(layer.mlp.calls == config['examples'] for layer in model.model.layers)
        sealed(root / 'results' / (label + '_s' + str(seed) + '.json'), result)
        print('COMPLETE', label, seed, result['perplexity'], result['seconds'], flush=True)
    sealed(root / 'results/complete.json', dict(status='completed', cases=len(cases) + 1,
        provenance_sha256=sha256(root / 'results/provenance.json'),
        documents={f.name: sha256(f) for f in sorted((root / 'results').glob('*.json'))
                   if not f.name.endswith('.sha256.json')}))


if __name__ == '__main__':
    main()
