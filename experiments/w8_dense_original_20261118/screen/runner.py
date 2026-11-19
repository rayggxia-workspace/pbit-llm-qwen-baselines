"""Matched cached full-WT2 digital controls; no stochastic FFN or attention."""
from pathlib import Path
import argparse
from contextlib import contextmanager
import json
import math
import os
import sys
import time
import unittest
import w8_original_reference as base

HERE = Path(__file__).resolve().parent


def verify():
    manifest = json.loads((HERE / 'SOURCE_MANIFEST.json').read_bytes())
    for name, digest in manifest.items():
        assert base.sha(HERE / name) == digest, name
    return manifest


def prepare():
    import numpy as np
    import torch
    from transformers import AutoTokenizer
    from wt2_reference import TEXT_SHA, TOKEN_SHA
    d = json.loads((HERE / 'INPUTS.json').read_bytes())
    for name, digest in d['parent_files_sha256'].items():
        assert base.sha(Path(d['parent_model']) / name) == digest, name
    assert base.sha(d['text']) == TEXT_SHA
    tok = AutoTokenizer.from_pretrained(d['parent_model'], local_files_only=True, trust_remote_code=False)
    ids = tok.encode(Path(d['text']).read_text(encoding='utf-8'), add_special_tokens=False)
    import hashlib
    assert len(ids) == 299078 and hashlib.sha256(np.asarray(ids, dtype='<u4').tobytes()).hexdigest() == TOKEN_SHA
    torch.set_num_threads(4)
    torch.manual_seed(101)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    return d, torch.tensor(ids, dtype=torch.long)


def model(d):
    import torch
    from transformers import AutoModelForCausalLM
    m = AutoModelForCausalLM.from_pretrained(d['parent_model'], local_files_only=True,
        trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda().eval()
    m.requires_grad_(False)
    assert (m.config.num_hidden_layers, m.config.hidden_size, m.config.intermediate_size) == (36, 2560, 9728)
    return m


def quantize_model(m):
    rows = []
    untouched = {n: (p.data_ptr(), p._version) for n, p in m.named_parameters() if '.mlp.' not in n}
    for i, layer in enumerate(m.model.layers):
        for name in ['gate_proj', 'up_proj', 'down_proj']:
            p = getattr(layer.mlp, name).weight
            q, e, decoded = base.quantize(p)
            rows.append(dict(layer=i, projection=name, codes_sha256=base.tensor_sha(q),
                exponents_sha256=base.tensor_sha(e), decoded_sha256=base.tensor_sha(decoded)))
            p.copy_(decoded)
    assert len(rows) == 108
    assert all((p.data_ptr(), p._version) == untouched[n] for n, p in m.named_parameters() if n in untouched)
    return rows


@contextmanager
def forbid_sampling():
    import torch
    names = ['rand', 'randn', 'randint', 'rand_like', 'randn_like', 'multinomial', 'bernoulli']
    originals = {n: getattr(torch, n) for n in names}
    def rejected(*args, **kwargs):
        raise AssertionError('A random sampling call reached a digital-only evaluation')
    try:
        for n in names:
            setattr(torch, n, rejected)
        yield
    finally:
        for n, v in originals.items():
            setattr(torch, n, v)


def cpu(output):
    import torch
    torch.set_num_threads(1)
    base.preflight(output / 'CPU_QUANTIZER.json')
    suite = unittest.defaultTestLoader.loadTestsFromName('experiments.sparq_ising_20261028.test_core.Tests')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    from experiments.sparq_ising_20261028.vendor.plans import full_window_plan
    rows = full_window_plan(299078, 2048, 1024)
    assert len(rows) == 292 and sum(r['scored_tokens'] for r in rows) == 299077
    base.save(output / 'CPU_GATE.json', dict(status='PASS', tests=result.testsRun,
        cached_plan_matches_full_WT2=True, quantizer_gate=True))


def gate(output):
    import torch
    from wt2_reference import score as vector_score
    from experiments.sparq_ising_20261028.scoring import score
    from experiments.sparq_ising_20261028.core import Config
    assert json.loads((output / 'CPU_GATE.json').read_bytes())['status'] == 'PASS'
    d, ids = prepare()
    m = model(d)
    # Same-environment unchanged full reference, preserving the old anchor.
    reference = vector_score(m, ids.numpy(), output / 'BF16_vector_anchor', base.Coverage(m), 101)
    assert abs(reference['ppl'] - 11.537160373065971) < .02
    q = quantize_model(m)
    base.save(output / 'W8_MAPS.json', q)
    # Same dtype/operator reference before testing the separate FP32 sparse core.
    opts = dict(protocol='suffix', context=64, decode=8, examples=2, batch=2, capture=True)
    with forbid_sampling():
        native = score(m, ids, None, native=True, **opts)
        wrapper = score(m, ids, None, native=False, **opts)
    assert native['logits_sha256'] == wrapper['logits_sha256'], 'native SDPA dispatch changed'
    cfg = Config(r=32, k=128, local=32, samples=1, burn=0, mode='exact')
    started = time.monotonic()
    with forbid_sampling():
        sparse = score(m, ids, cfg, protocol='suffix', context=256, decode=8,
                       examples=2, batch=2, native=False)
    assert sparse['scored_tokens'] == 16
    assert all(x == 16 for x in sparse['tokens_per_layer'])
    assert all(v['sampled_head_rows'] == 0 and v['decode_queries'] == 16 and v['route_elements'] > 0
               for v in sparse['audit']['layers'].values())
    base.save(output / 'GPU_GATE.json', dict(status='PASS', native_wrapper_bitwise_equal=True,
        screened_query_rows_per_layer=16, scored_layers=36, no_random_calls=True,
        BF16_anchor_PPL=reference['ppl'], sparse_pilot_seconds=time.monotonic()-started,
        maps_sha256=base.sha(output/'W8_MAPS.json'),
        numeric='BF16 inputs/outputs;FP32 selector and exact candidate QK/softmax/PV;no quantized sampler'))


def full(output, index):
    import torch
    from experiments.sparq_ising_20261028.scoring import score
    from experiments.sparq_ising_20261028.core import Config
    plan = json.loads((HERE / 'PLAN.json').read_bytes())
    mode = plan['modes'][index]
    assert json.loads((output / 'GPU_GATE.json').read_bytes())['status'] == 'PASS'
    dest = output / mode
    dest.mkdir(exist_ok=False)
    d, ids = prepare()
    m = model(d)
    if mode != 'BF16_dense':
        weights = quantize_model(m)
        assert weights == json.loads((output / 'W8_MAPS.json').read_bytes())
    cfg = Config(r=32, k=128, local=32, samples=1, burn=0, mode='exact') if index == 2 else None
    def progress(records):
        base.save(dest / 'PROGRESS.json', dict(completed_windows=len(records),
            completed_targets=sum(r['scored_tokens'] for r in records), seconds=time.monotonic()-started))
    started = time.monotonic()
    with forbid_sampling():
        result = score(m, ids, cfg, seed=101, protocol='full', batch=32,
                       native=index != 2, progress=progress)
    assert result['scored_tokens'] == 299077 and len(result['records']) == 292
    assert all(n == 299077 for n in result['tokens_per_layer'])
    if index == 2:
        assert all(v['sampled_head_rows'] == 0 and v['decode_queries'] == 299077
                   for v in result['audit']['layers'].values())
    result.update(status='completed', mode=mode, original_ffn=index == 0,
        W8_only_FFN=index != 0, original_attention_projections=True,
        no_training=True, no_sampling=True, no_trained_overlay=True,
        screening=dict(r=32,k=128,recent=32,shared_Q_per_KV=4) if index == 2 else None,
        hardware_bittrue=False, source_sha256=verify(), job=os.environ['SLURM_JOB_ID'],
        weights_map_sha256=base.sha(output/'W8_MAPS.json') if index != 0 else None)
    result['audit']['original_ffn'] = index == 0
    result['audit']['rng'] = 'none;production random calls forbidden'
    result['audit']['ideal_sigmoid_source'] = False
    base.save(dest / 'RESULT.json', result)
    base.save(dest / 'COMPLETE.json', dict(status='completed',result_sha256=base.sha(dest/'RESULT.json'),
        mode=mode,PPL=result['perplexity'],targets=299077,windows=292,layers=36))
    print(json.dumps(dict(mode=mode,PPL=result['perplexity'],seconds=result['seconds'])),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['cpu','gate','full'],required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int,default=0)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);verify()
    if a.phase=='cpu':cpu(a.output)
    else:
        import torch
        with torch.no_grad():
            gate(a.output) if a.phase=='gate' else full(a.output,a.index)
