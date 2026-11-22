"""Immutable T64 GU-only address/count quality screen and full-WT2 runner."""
from pathlib import Path
import argparse
import gc
import hashlib
import json
import math
import sys
import time


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(16 << 20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value, sealed=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))
    if sealed:
        path.with_suffix('.sha256').write_bytes((digest(path) + '\n').encode('ascii'))


def verify_sealed(path):
    path = Path(path)
    assert path.with_suffix('.sha256').read_text().strip() == digest(path)
    value = json.loads(path.read_bytes())
    assert value['status'] == 'completed'
    return value


def verify_source(source):
    manifest = source / 'EXECUTION_MANIFEST.json'
    m = json.loads(manifest.read_bytes())
    for name, sha in m['files'].items():
        assert digest(source / name) == sha, name
    return {'manifest_sha256': digest(manifest), 'git_commit': m['git_commit'], 'files': m['files']}


def before_forward(context, seed, window_index):
    context.seed = seed
    context.begin(0, window_index, domain='ffn-wt2-deployment')


def forward_logits(model, context, tokens, span, seed, window_index):
    import torch
    start, end, first = span
    ids = torch.as_tensor(tokens[start:end].astype('int64'), device='cuda')[None]
    before_forward(context, seed, window_index)
    with torch.no_grad():
        logits = model(ids, use_cache=False).logits[0]
    if not bool(torch.isfinite(logits).all()):
        raise FloatingPointError('nonfinite model logits')
    if len(context.coverage) != 36 or any(v['calls'] != 1 or v['tokens'] != end-start for v in context.coverage.values()):
        raise AssertionError('not all36 decoder layers executed exactly once')
    return logits, ids[0]


def score_windows(model, context, tokens, ledger, indices, seed, output, probe=None):
    import torch
    import torch.nn.functional as F
    rows, total_nll, total_targets = [], 0., 0
    started = time.time()
    for wi in indices:
        start, end, first = ledger[wi]
        torch.cuda.synchronize()
        tick = time.time()
        logits, ids = forward_logits(model, context, tokens, (start, end, first), seed, wi)
        loss = logits.new_zeros((), dtype=torch.float32)
        for lo in range(first-start-1, end-start-1, 128):
            hi = min(end-start-1, lo+128)
            loss += F.cross_entropy(logits[lo:hi].float(), ids[lo+1:hi+1], reduction='sum')
        value = float(loss)
        if not math.isfinite(value):
            raise FloatingPointError('nonfinite NLL')
        target_count = end-first
        total_nll += value
        total_targets += target_count
        torch.cuda.synchronize()
        rows.append(dict(window_index=wi, start=start, end=end, first_target=first,
            targets=target_count, nll=value, seconds=time.time()-tick,
            target_token_sha256=hashlib.sha256(tokens[first:end].astype('<u4').tobytes()).hexdigest()))
        del logits, ids, loss
        save(output/'PROGRESS.json', dict(status='running', windows=rows, elapsed_seconds=time.time()-started,
             addresses=None if probe is None else probe.summary()))
    ce = total_nll/total_targets
    return dict(nll=total_nll, targets=total_targets, mean_nll=ce,
        ppl=math.exp(ce) if ce < 709 else None, ppl_overflow=ce >= 709,
        windows=len(rows), window_ledger=rows, seconds=time.time()-started,
        addresses=None if probe is None else probe.summary())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['gate', 'screen', 'full'], required=True)
    ap.add_argument('--inputs', type=Path, required=True)
    ap.add_argument('--runtime', type=Path, required=True)
    ap.add_argument('--helpers', type=Path, required=True)
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--gate', type=Path)
    ap.add_argument('--seed', type=int, default=101)
    ap.add_argument('--case')
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError('immutable result directory already exists')
    args.output.mkdir(parents=True)
    (args.output/'data_protocol').mkdir()
    started = time.time()
    source = verify_source(Path(__file__).parent)
    plan = json.loads(args.plan.read_bytes())
    assert args.seed in plan['deployment_seeds']
    sys.path.insert(0, str(args.helpers))
    from run_wt2 import prepare, load_model
    from adapter import SamplingOverride
    import torch
    inputs, tokens, ledger, protocol = prepare(args.inputs, args.runtime, args.output/'data_protocol')
    identity_ref = dict(source=source, plan_sha256=digest(args.plan), inputs_sha256=digest(args.inputs),
                        helper_sha256={p.name:digest(p) for p in [args.helpers/'run_wt2.py',args.helpers/'adapter.py',args.helpers/'sampling.py']})
    assert identity_ref['inputs_sha256'] == '84302bdff04a6bd78216dc03df24ebec309c666207879e2f3a468b057111bc5a'
    baseline = dict(id='strat64', T_x=64, T_and=64, input_law='stratified_T',
                    and_law='joint_grid', grid_g_sig_u=[4,4,4])
    if args.phase == 'gate':
        from gpu_checks import run
        from gu_adapter import GUOverride
        checks = run()
        model, context, _, identity = load_model(inputs, native=True)
        native = score_windows(model, context, tokens, ledger, plan['screen_window_indices'], 101,
                               args.output/'BF16_reference')
        save(args.output/'BF16_reference/RESULT.json', dict(status='completed', kind='unchanged_BF16_8window_reference',
             identity=identity, protocol=protocol, inputs=identity_ref, result=native), sealed=True)
        del model, context
        gc.collect();torch.cuda.empty_cache()
        model, context, modules, identity = load_model(inputs)
        assert identity['export_manifest_sha256'] == '187fa827daa5e162b0753ffd4b2687c11a17eea289193cdead614c8a722556ff'
        versions = {(i,n):(v.data_ptr(),v._version) for i,m in enumerate(modules) for n,v in m.named_buffers()}
        with SamplingOverride(baseline) as sampling:
            sampling.configure(modules)
            reference, _ = forward_logits(model,context,tokens,ledger[0],101,0)
            reference = reference.cpu()
            banks = {}
            with GUOverride(plan['cases'][0],banks,verify_dense=True) as witness:
                actual, _ = forward_logits(model,context,tokens,ledger[0],101,0)
                assert torch.equal(actual.cpu(),reference), 'full2048 no-op logits differ'
                del actual, reference
            assert witness.dense_checks == 36 and witness.wd_calls == 36
            timings=[]
            # One full window per candidate measures dispatch, finite logits,
            # actual active rows and realistic screen duration before arrays.
            for case in plan['cases']:
                for m in modules:m.reset_runtime_audit()
                with GUOverride(case,banks) as probe:
                    r=score_windows(model,context,tokens,ledger,[0],101,args.output/('pilot_'+case['id']),probe)
                assert set(probe.stats)=={str(i) for i in range(36)}
                assert probe.wd_calls==36
                timings.append(dict(case=case,result=r))
                save(args.output/'GATE_PROGRESS.json',dict(status='running',pilots=timings))
        assert all((v.data_ptr(),v._version)==versions[i,n] for i,m in enumerate(modules) for n,v in m.named_buffers())
        result=dict(status='completed',phase='gate',gpu_checks=checks,full2048_original_logits_bitwise=True,
            dense_integer_witness_layers=36,unchanged_wd_layers=36,weights_unchanged=True,
            identity=identity,protocol=protocol,inputs=identity_ref,pilots=timings,
            native_reference_sha256=digest(args.output/'BF16_reference/RESULT.json'),seconds=time.time()-started)
    else:
        from gu_adapter import GUOverride
        gate=verify_sealed(args.gate)
        assert gate['phase']=='gate' and gate['inputs']==identity_ref and gate['protocol']==protocol
        assert gate['full2048_original_logits_bitwise'] and gate['weights_unchanged']
        model,context,modules,identity=load_model(inputs)
        assert identity==gate['identity']
        banks={}
        cases=plan['cases'] if args.phase=='screen' else [next(c for c in plan['cases'] if c['id']==args.case)]
        indices=plan['screen_window_indices'] if args.phase=='screen' else list(range(len(ledger)))
        completed=[]
        with SamplingOverride(baseline) as sampling:
            sampling.configure(modules)
            for case in cases:
                output=args.output/case['id']
                for m in modules:m.reset_runtime_audit()
                try:
                    with GUOverride(case,banks) as probe:
                        r=score_windows(model,context,tokens,ledger,indices,args.seed,output,probe)
                    assert set(probe.stats)=={str(i) for i in range(36)}
                    assert probe.wd_calls==36*len(indices)
                    if args.phase=='full':assert r['targets']==299077 and r['windows']==292
                    item=dict(status='completed',phase=args.phase,case=case,seed=args.seed,
                        full_corpus=args.phase=='full',identity=identity,protocol=protocol,
                        inputs=identity_ref,gate_sha256=digest(args.gate),result=r)
                except Exception as exc:
                    if case['kind']=='original':raise
                    item=dict(status='failed',phase=args.phase,case=case,seed=args.seed,
                              error_type=type(exc).__name__,error=str(exc),identity=identity,inputs=identity_ref)
                    torch.cuda.empty_cache()
                save(output/'RESULT.json',item,sealed=True)
                completed.append(dict(case=case['id'],status=item['status'],result_path=str(output/'RESULT.json'),sha256=digest(output/'RESULT.json')))
        result=dict(status='completed',phase=args.phase,seed=args.seed,case_results=completed,
            inputs=identity_ref,identity=identity,protocol=protocol,seconds=time.time()-started)
    save(args.output/'RESULT.json',result,sealed=True)
    print(json.dumps({k:result[k] for k in ['status','phase','seconds']}),flush=True)


if __name__=='__main__':
    main()
