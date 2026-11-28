"""Frozen T64, paired scale-policy WT2 evaluation; submitted through Slurm."""
import argparse
from contextlib import nullcontext
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(16 << 20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    path.write_bytes(raw)
    path.with_suffix('.sha256').write_bytes((hashlib.sha256(raw).hexdigest() + '\n').encode())


def sealed(path):
    assert sha(path) == path.with_suffix('.sha256').read_text().strip()
    return json.loads(path.read_bytes())


def snapshot(modules):
    return {(i, n): (v.data_ptr(), v._version) for i, m in enumerate(modules)
            for n, v in m.named_buffers() if n.startswith('frozen_') or n in
            ('x_scales', 'g_top', 'u_top', 'lut', 'gu_weight_exponents', 'down_weight_exponents')}


def scales(modules):
    import torch
    rows = []
    for i, m in enumerate(modules):
        assert m.x_scales.shape == (40, 4)
        assert torch.equal(m.x_scales, m.x_scales[:, :1] * m.x_scales.new_tensor([1., .25, .0625, .015625]))
        row = {'layer': i}
        for name, table in [('x', m.x_scales), ('g', m.g_top[:, None] * m.g_top.new_tensor([1., .25, .0625, .015625])),
                            ('u', m.u_top[:, None] * m.u_top.new_tensor([1., .25, .0625, .015625]))]:
            v = table.float().cpu().contiguous()
            mantissa, e = torch.frexp(v)
            assert bool((mantissa == .5).all())
            row[name] = {'exponents': (e-1).tolist(),
                         'float32_le_sha256': hashlib.sha256(v.numpy().astype('<f4').tobytes()).hexdigest()}
        rows.append(row)
    return rows


def score(model, context, modules, tokens, ledger, windows, seed, out, case=None, capture=False):
    import numpy as np
    import torch
    from torch.nn import functional as F
    from adapter import SamplingOverride
    from scale_patch import ScaleOverride
    selected = set(windows)
    assert selected and len(selected) == len(windows) and selected <= set(range(292))
    state = snapshot(modules)
    context.seed = seed
    patch = SamplingOverride(case) if case else nullcontext()
    if case:
        patch.configure(modules)
    scale = ScaleOverride(case['scale_policy']) if case else nullcontext()
    records, coverage = [], {}
    started = time.monotonic()
    digest = hashlib.sha256()
    with patch, scale, torch.no_grad():
        for wi in sorted(selected):
            start, end, first = ledger[wi]
            ids = torch.as_tensor(np.asarray(tokens[start:end], dtype=np.int64), device='cuda')[None]
            context.begin(0, wi, domain='ffn-wt2-deployment')
            logits = model(ids, use_cache=False).logits[0]
            assert bool(torch.isfinite(logits).all())
            a, b = first-start-1, end-start-1
            loss = logits.new_zeros((), dtype=torch.float32)
            for lo in range(a, b, 128):
                hi = min(b, lo+128)
                loss += F.cross_entropy(logits[lo:hi].float(), ids[0, lo+1:hi+1], reduction='sum')
            assert len(context.coverage) == 36
            assert all(v['calls'] == 1 and v['tokens'] == end-start for v in context.coverage.values())
            for layer in context.coverage:
                coverage[str(layer)] = coverage.get(str(layer), 0) + end-start
            if case:
                assert all((m.last_arithmetic['T_x'], m.last_arithmetic['T_AND']) == (case['T_x'], case['T_and']) for m in modules)
            row = dict(window=wi, start=start, end=end, first_scored=first, targets=end-first,
                       nll_sum=float(loss), target_token_sha256=hashlib.sha256(np.asarray(tokens[first:end], dtype='<u4').tobytes()).hexdigest())
            assert math.isfinite(row['nll_sum'])
            records.append(row)
            if capture:
                digest.update(logits.detach().float().cpu().contiguous().numpy().tobytes())
            save(out / 'PROGRESS.json', dict(status='running', records=records, seconds=time.monotonic()-started))
            print(json.dumps(dict(window=wi, ppl=math.exp(row['nll_sum']/row['targets']), seconds=time.monotonic()-started)), flush=True)
            del logits, loss, ids
    assert snapshot(modules) == state, 'frozen weights/table mutation'
    n = sum(r['targets'] for r in records)
    nll = sum(r['nll_sum'] for r in records)
    save(out / 'WINDOWS.json', records)
    return dict(status='completed', scope='complete WT2' if len(records)==292 else 'WT2 window subset',
                windows=len(records), targets=n, nll_sum=nll, ppl=math.exp(nll/n), seed=seed,
                records_sha256=sha(out / 'WINDOWS.json'), ffn_token_coverage=coverage,
                seconds=time.monotonic()-started, scale_statistics=scale.report() if case else {},
                logits_sha256=digest.hexdigest() if capture else None,
                weights_tables_unchanged=True, physical_PPA=None)


def gate(args, inputs, tokens, ledger, plan):
    import numpy as np
    import torch
    import seven_forward as sf
    from reference import load_model
    from adapter import SamplingOverride
    from scale_patch import ScaleOverride
    model, context, modules, parent_id = load_model(inputs, native=True)
    bf = score(model, context, modules, tokens, ledger, [0, 146], 101, args.output / 'bf16_pilot', capture=True)
    # Independent scorer, unchanged original model, one same window.
    from qwen3.training.sc_qat.evaluate import spans
    assert list(spans(len(tokens))) == ledger
    del model, context, modules
    gc.collect(); torch.cuda.empty_cache()
    model, context, modules, identity = load_model(inputs)
    table_rows = scales(modules)
    save(args.output / 'SCALE_TABLES.json', table_rows)
    ids = torch.as_tensor(np.asarray(tokens[:256], dtype=np.int64), device='cuda')[None]
    context.seed = 101
    def probe(patch):
        context.begin(0, 0, domain='group64-native-noop')
        with patch, torch.no_grad():
            return model(ids, use_cache=False).logits.detach().clone()
    original = probe(nullcontext())
    assert torch.equal(original, probe(ScaleOverride('lane'))), 'lane no-op changed native T64'
    native_case = dict(id='native_iid64', T_x=64, T_and=64, input_law='original_IID', and_law='original_IID')
    p = SamplingOverride(native_case); p.configure(modules)
    assert torch.equal(original, probe(p)), 'native T64 IID64 config/replay changed'
    del original, ids
    pilots = []
    for case in plan['cases']:
        r = score(model, context, modules, tokens, ledger, [0, 146], 101, args.output / ('pilot_' + case['id']), case)
        pilots.append(dict(case=case['id'], result=r,
                           estimated_shard_seconds=180 + r['seconds'] / 2 * math.ceil(292 / plan['shards']) * 1.5))
    # Brief diagnostic isolates x-sharing and g/u-sharing without another full WT2 sweep.
    diagnostics = []
    for policy in ['x64', 'gu64']:
        case = dict(plan['cases'][0], id=policy+'_16_32', scale_policy=policy)
        r = score(model, context, modules, tokens, ledger, [0], 101, args.output / ('diagnostic_'+policy), case)
        diagnostics.append(dict(case=case, result=r))
    return dict(status='completed', phase='gate', identity=identity, parent_identity=parent_id,
                native_lane_noop_bitwise=True, native_iid64_noop_bitwise=True,
                bf16_pilot=bf, pilots=pilots, diagnostics=diagnostics,
                scale_tables_sha256=sha(args.output / 'SCALE_TABLES.json'),
                peak_allocated_GiB=torch.cuda.max_memory_allocated()/2**30)


def main():
    parser = argparse.ArgumentParser()
    for name in ['runtime', 'inputs', 'output']:
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--phase', choices=['cpu', 'gate', 'full', 'merge'], required=True)
    parser.add_argument('--case', default='bf16')
    parser.add_argument('--seed', type=int, default=101)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--gate', type=Path)
    args = parser.parse_args()
    assert 'SLURM_JOB_ID' in os.environ
    own = Path(__file__).resolve().parent
    manifest = json.loads((own/'EXECUTION_MANIFEST.json').read_bytes())
    for name, digest in manifest['files'].items():
        assert sha(own/name) == digest, name
    assert not args.output.exists(), 'immutable output; choose a new run'
    args.output.mkdir(parents=True)
    if args.phase == 'cpu':
        import unittest
        sys.path.insert(0, str(args.runtime))
        suite = unittest.defaultTestLoader.discover(str(own), pattern='test_*.py')
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        assert result.wasSuccessful() and result.testsRun >= 6
        save(args.output/'RESULT.json', dict(status='completed', phase='cpu', tests=result.testsRun,
                                             manifest_sha256=sha(own/'EXECUTION_MANIFEST.json')))
        return
    if args.phase == 'merge':
        merge(args.output.parent)
        return
    from reference import prepare, load_model
    inputs, tokens, ledger, protocol = prepare(args.inputs, args.runtime, args.output)
    plan = json.loads((own/'PLAN.json').read_bytes())
    assert protocol['text_sha256']==plan['test_text_sha256'] and protocol['token_sha256']==plan['test_token_sha256']
    started = time.monotonic()
    provenance = dict(source_manifest_sha256=sha(own/'EXECUTION_MANIFEST.json'),
                      code_commit=manifest['git_commit'], plan_sha256=sha(own/'PLAN.json'),
                      inputs_sha256=sha(args.inputs), runtime_manifest_sha256=sha(args.runtime/'SOURCE_MANIFEST.json'),
                      protocol=protocol, versions={n: importlib.metadata.version(n) for n in ['torch','transformers','triton']})
    if args.phase == 'gate':
        result = gate(args, inputs, tokens, ledger, plan)
    else:
        g = sealed(args.gate)
        assert g['status']=='completed' and g['provenance']==provenance
        assert g['native_lane_noop_bitwise'] and g['native_iid64_noop_bitwise']
        native = args.case=='bf16'
        model, context, modules, identity = load_model(inputs, native=native)
        if not native:
            assert identity == g['identity'] and identity['export_manifest_sha256'] == plan['export_manifest_sha256']
        case = None if native else next(c for c in plan['cases'] if c['id']==args.case)
        assert native or args.seed in plan['seeds']
        indices = list(range(292)) if native else list(range(args.shard, 292, plan['shards']))
        result = dict(status='completed', phase='full', case=args.case, case_config=case, seed=args.seed,
                      shard=None if native else args.shard, identity=identity,
                      result=score(model, context, modules, tokens, ledger, indices, args.seed, args.output/'score', case),
                      gate_sha256=sha(args.gate))
    result.update(provenance=provenance, service_seconds=time.monotonic()-started,
                  slurm_job_id=os.environ['SLURM_JOB_ID'], no_training=True, no_recalibration=True)
    save(args.output/'RESULT.json', result)
    print(json.dumps(dict(status='completed', phase=args.phase, seconds=result['service_seconds'])), flush=True)


def merge(root):
    plan = json.loads((Path(__file__).parent/'PLAN.json').read_bytes())
    outputs = []
    reference = sealed(root/'bf16/RESULT.json')
    assert reference['status']=='completed' and reference['result']['targets']==299077
    assert abs(reference['result']['ppl']-11.540139) < .05
    for case in plan['cases']:
        for seed in plan['seeds']:
            rows, provenance, identity, coverage = [], None, None, {}
            sources = []
            for shard in range(plan['shards']):
                folder = root/'full'/case['id']/str(seed)/str(shard)
                result = sealed(folder/'RESULT.json')
                assert result['status']=='completed' and result['case_config']==case and result['seed']==seed
                if provenance is None:
                    provenance, identity = result['provenance'], result['identity']
                assert result['provenance']==provenance and result['identity']==identity
                assert provenance == reference['provenance']
                rows_path = folder/'score/WINDOWS.json'
                assert sha(rows_path)==result['result']['records_sha256']
                part = json.loads(rows_path.read_bytes())
                assert [r['window'] for r in part]==list(range(shard,292,plan['shards']))
                rows += part
                for k, v in result['result']['ffn_token_coverage'].items():
                    coverage[k] = coverage.get(k,0)+v
                sources.append(dict(path=str(folder/'RESULT.json'), sha256=sha(folder/'RESULT.json')))
            rows.sort(key=lambda r:r['window'])
            assert [r['window'] for r in rows]==list(range(292))
            cursor=1
            for row in rows:
                assert row['first_scored']==cursor
                cursor=row['end']
            assert cursor==299078 and sum(r['targets'] for r in rows)==299077
            assert set(coverage)==set(map(str,range(36))) and len(set(coverage.values()))==1
            nll=sum(r['nll_sum'] for r in rows)
            outputs.append(dict(case=case['id'], seed=seed, ppl=math.exp(nll/299077), targets=299077,
                                windows=292, coverage=coverage, sources=sources))
    save(root/'SUMMARY.json',dict(status='completed', baseline_ppl=reference['result']['ppl'],
                                  results=outputs, plan=plan, provenance=reference['provenance']))


if __name__=='__main__':
    main()
