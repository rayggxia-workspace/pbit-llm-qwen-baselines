"""Frozen single-seed GU pruning sweep, full PPL, and official task runner."""
from contextlib import ExitStack
from pathlib import Path
import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setup(a):
    root = Path(__file__).parent
    plan = json.loads((root / 'PLAN.json').read_bytes())
    own = json.loads((root / 'EXECUTION_MANIFEST.json').read_bytes())
    for name, digest in own['files'].items():
        assert sha(root / name) == digest, name
    sys.path[1:1] = [str(a.full_source), str(a.mild_source), str(a.helpers),
                      str(a.runtime), str(a.reference_source)]
    import run_quality as rq
    from run_wt2 import prepare
    for path, key in [(a.full_source, 'full_source_manifest_sha256'),
                      (a.mild_source, 'mild_manifest_sha256'),
                      (a.reference_source, 'reference_manifest_sha256')]:
        assert rq.verify_source(path)['manifest_sha256'] == plan[key]
    old_gate = rq.verify_sealed(a.mild_gate)
    old_cal = rq.verify_sealed(a.old_calibration)
    assert sha(a.mild_gate) == plan['mild_gate_sha256']
    assert sha(a.old_calibration) == plan['calibration_sha256'] == old_gate['calibration_sha256']
    assert sha(a.prior_root / 'readback_completed_v1/SUMMARY.json') == plan['prior_summary_sha256']
    inputs, tokens, ledger, protocol = prepare(a.inputs, a.runtime, a.output / 'data_protocol')
    assert sha(a.inputs) == plan['inputs_sha256'] and protocol == old_gate['protocol']
    provenance = {'source_commit': own['git_commit'],
        'source_manifest_sha256': sha(root / 'EXECUTION_MANIFEST.json'),
        'plan_sha256': sha(root / 'PLAN.json'), 'inputs_sha256': sha(a.inputs),
        'old_calibration_sha256': sha(a.old_calibration),
        'full_source_manifest_sha256': sha(a.full_source / 'EXECUTION_MANIFEST.json'),
        'mild_source_manifest_sha256': sha(a.mild_source / 'EXECUTION_MANIFEST.json'),
        'reference_source_manifest_sha256': sha(a.reference_source / 'EXECUTION_MANIFEST.json')}
    return plan, provenance, inputs, tokens, ledger, protocol, old_gate, old_cal


def baseline_config():
    return dict(id='strat64', T_x=64, T_and=64, input_law='stratified_T',
                and_law='joint_grid', grid_g_sig_u=[4, 4, 4])


def task_inputs(a, plan, inputs):
    from transformers import AutoTokenizer
    from tasks import load_tasks, audit_requests
    tokenizer = AutoTokenizer.from_pretrained(inputs['tokenizer'], local_files_only=True, trust_remote_code=False)
    task_map, identity, sources = load_tasks(a.data_root, plan)
    requests = {name: audit_requests(task, name, tokenizer) for name, task in task_map.items()}
    import run_quality as rq
    old = rq.verify_sealed(a.prior_root / 'tasks-5df53bac765c/original_strat64/piqa/RESULT.json')['provenance']
    assert requests == old['official_request_audit'] and identity == old['task_identity']
    assert sources == old['harness_sources']
    info = {'task_identity': identity, 'official_request_audit': requests, 'harness_sources': sources,
            'versions': {n: importlib.metadata.version(n) for n in ['torch', 'triton', 'transformers', 'lm_eval', 'datasets']}}
    assert info['versions'] == old['versions']
    return tokenizer, task_map, info


def gate(a, plan, provenance, inputs, tokens, ledger, protocol, old_gate, old_cal):
    import numpy as np
    import torch
    import run_quality as rq
    from run_wt2 import load_model
    from adapter import SamplingOverride
    from pruning import PrunedGU
    from prune_sweep import SweepGU
    from checks import run
    from lm_eval.models.huggingface import HFLM
    from tasks import AuditedHFLM, evaluate, metrics
    checks = run()
    tokenizer, task_map, task_info = task_inputs(a, plan, inputs)
    model, context, _, native_identity = load_model(inputs, native=True)
    native = rq.score_windows(model, context, tokens, ledger, plan['screen_window_indices'],
                              plan['seed'], a.output / 'BF16_reference')
    previous = rq.verify_sealed(a.mild_gate.parent / 'BF16_reference/RESULT.json')
    assert previous['identity'] == native_identity and previous['result']['nll'] == native['nll']
    rq.save(a.output / 'BF16_reference/RESULT.json', dict(status='completed', phase='fresh_BF16_reference',
        identity=native_identity, protocol=protocol, result=native, provenance=provenance), sealed=True)
    model.config.use_cache = False
    bare = HFLM(pretrained=model, tokenizer=tokenizer, backend='causal', batch_size=1,
                max_length=2048, add_bos_token=False, logits_cache=False, truncation=False)
    task_checks = {}
    for name, task in task_map.items():
        _, doc = next(task.doc_iterator())
        request = task.construct_requests(doc, task.fewshot_context(doc, num_fewshot=0), metadata=(name, 0, 1))[0]
        expected = bare.loglikelihood([request])
        lm = AuditedHFLM(model, tokenizer, context, plan['seed'], name)
        assert lm.loglikelihood([request]) == expected
        task_checks[name] = {'native_official_likelihood_bitwise': True}
    del model, context, bare, lm
    gc.collect(); torch.cuda.empty_cache()
    model, context, modules, identity = load_model(inputs)
    assert identity == old_gate['identity'] == old_cal['identity']
    versions = {(i, n): (v.data_ptr(), v._version) for i, m in enumerate(modules) for n, v in m.named_buffers()}
    banks = {}
    empty = {'thresholds': {str(i): {} for i in range(36)}}
    with SamplingOverride(baseline_config()) as sampling:
        sampling.configure(modules)
        original, _ = rq.forward_logits(model, context, tokens, ledger[0], plan['seed'], 0)
        original = original.cpu()
        with SweepGU(plan['cases'][0], banks, empty, verify_dense=True) as probe:
            actual, _ = rq.forward_logits(model, context, tokens, ledger[0], plan['seed'], 0)
            assert torch.equal(original, actual.cpu()), 'full2048 no-op logits changed'
            del original, actual
        assert probe.dense_checks == probe.wd_calls == 36
        assert sha(a.train_text) == plan['train_text_sha256']
        train = np.asarray(tokenizer.encode(a.train_text.read_text(encoding='utf-8'), add_special_tokens=False), dtype='<u4')
        spans = []
        with PrunedGU({'kind': 'original'}, banks, collect=True, encodings=old_cal['norm_encodings']) as collector:
            for i in range(4):
                start, end = i * 2048, (i + 1) * 2048
                logits, _ = rq.forward_logits(model, context, train, (start, end, start + 1), 101, 100000 + i)
                del logits
                spans.append({'start': start, 'end': end, 'input_token_sha256': hashlib.sha256(train[start:end].tobytes()).hexdigest()})
        thresholds = {}
        for layer, fields in collector.collected.items():
            values = torch.cat(fields['input']).flatten()
            thresholds[layer] = {str(p): int(values.kthvalue(math.ceil(values.numel() * p / 100)).values)
                                 for p in plan['calibration']['percentiles']}
            for p in ['10', '20']:
                assert thresholds[layer][p] == old_cal['thresholds'][layer]['input'][p]
        cal = dict(status='completed', thresholds=thresholds, no_test_set_fit=True,
                   identity=identity, provenance=provenance, calibration=plan['calibration'],
                   train_text_sha256=sha(a.train_text), train_token_sha256=hashlib.sha256(train.tobytes()).hexdigest(),
                   calibration_spans=spans, old10_20_thresholds_exact=True)
        assert spans == old_cal['calibration_spans'] and len(thresholds) == 36
        rq.save(a.output / 'CALIBRATION.json', cal, sealed=True)
        pilots = []
        for case in plan['cases']:
            with SweepGU(case, banks, cal) as probe:
                r = rq.score_windows(model, context, tokens, ledger, [0], 101, a.output / ('pilot_' + case['id']), probe)
            assert probe.wd_calls == 36 and len(probe.stats) == 36
            if case['id'] in ['original_strat64', 'input_p20']:
                prior = rq.verify_sealed(a.prior_root / 'full-f3e89e2bfc02' / case['id'] / 'RESULT.json')
                assert r['nll'] == prior['result']['window_ledger'][0]['nll']
            pilots.append({'case': case['id'], 'ppl': r['ppl'], 'seconds': r['seconds'],
                           'unique_address_ratio': r['addresses']['unique_address_ratio']})
            rq.save(a.output / 'PROGRESS.json', dict(status='running', pilots=pilots))
        with SweepGU(next(c for c in plan['cases'] if c['id'] == 'band20_40_half'), banks, cal) as probe:
            for name, task in task_map.items():
                lm = AuditedHFLM(model, tokenizer, context, 101, name)
                result = evaluate(lm, task, name, limit=2)
                assert len(result['samples'][name]) == 2
                task_checks[name].update(probability_pilot_documents=2, model_calls=lm.calls,
                                        all36_all_prompt_and_answer=True, metrics=metrics(result, name))
        assert probe.wd_calls == 36 * sum(v['model_calls'] for v in task_checks.values())
    assert all((v.data_ptr(), v._version) == versions[i, n] for i, m in enumerate(modules) for n, v in m.named_buffers())
    return dict(status='completed', phase='gate', identity=identity, native_identity=native_identity,
        provenance=provenance, protocol=protocol, checks=checks, full2048_noop_logits_bitwise=True,
        weights_unchanged=True, old_thresholds_10_20_exact=True, task_info=task_info,
        task_checks=task_checks, pilots=pilots, calibration_sha256=sha(a.output / 'CALIBRATION.json'),
        fresh_BF16_reference_sha256=sha(a.output / 'BF16_reference/RESULT.json'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['gate', 'screen', 'full', 'tasks'], required=True)
    for name in ['inputs', 'runtime', 'helpers', 'reference-source', 'mild-source', 'full-source',
                 'mild-gate', 'old-calibration', 'train-text', 'prior-root', 'data-root', 'output']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--gate', type=Path)
    ap.add_argument('--case')
    ap.add_argument('--task')
    ap.add_argument('--full-result', type=Path)
    a = ap.parse_args()
    assert not a.output.exists(), 'Use a new immutable output directory.'
    a.output.mkdir(parents=True)
    (a.output / 'data_protocol').mkdir()
    started = time.time()
    plan, provenance, inputs, tokens, ledger, protocol, old_gate, old_cal = setup(a)
    import run_quality as rq
    if a.phase == 'gate':
        value = gate(a, plan, provenance, inputs, tokens, ledger, protocol, old_gate, old_cal)
    else:
        from run_wt2 import load_model
        from adapter import SamplingOverride
        from prune_sweep import SweepGU
        g = rq.verify_sealed(a.gate)
        cal = rq.verify_sealed(a.gate.parent / 'CALIBRATION.json')
        assert g['provenance'] == provenance and sha(a.gate.parent / 'CALIBRATION.json') == g['calibration_sha256']
        assert cal['no_test_set_fit'] and g['old_thresholds_10_20_exact']
        case = next(c for c in plan['cases'] if c['id'] == a.case)
        model, context, modules, identity = load_model(inputs)
        assert identity == g['identity'] == old_gate['identity']
        if a.phase == 'tasks':
            from tasks import AuditedHFLM, evaluate, metrics
            proof = rq.verify_sealed(a.full_result)
            assert proof['phase'] == 'full' and proof['case'] == case and proof['provenance'] == provenance
            prior = rq.verify_sealed(a.prior_root / 'full-f3e89e2bfc02/original_strat64/RESULT.json')
            assert sha(a.prior_root / 'full-f3e89e2bfc02/original_strat64/RESULT.json') == plan['prior_full_PPL_sha256']
            assert proof['result']['ppl'] / prior['result']['ppl'] <= plan['promotion']['max_ppl_ratio']
            assert 1 - proof['result']['addresses']['unique_address_ratio'] / prior['result']['addresses']['unique_address_ratio'] >= plan['promotion']['minimum_relative_unique_address_reduction']
            tokenizer, task_map, task_info = task_inputs(a, plan, inputs)
            assert task_info == g['task_info'] and a.task in task_map
            model.config.use_cache = False
            def progress(lm):
                rq.save(a.output / 'PROGRESS.json', dict(status='running', phase='tasks', case=a.case, task=a.task,
                    calls=lm.calls, tokens=lm.tokens, seconds=time.time() - started))
            with SamplingOverride(baseline_config()) as sampling:
                sampling.configure(modules)
                with SweepGU(case, {}, cal) as probe:
                    lm = AuditedHFLM(model, tokenizer, context, 101, a.task, progress=progress)
                    official = evaluate(lm, task_map[a.task], a.task, limit=None)
                    assert len(official['samples'][a.task]) == plan['tasks'][a.task]['count']
                    assert probe.wd_calls == 36 * lm.calls
                    addresses, audit = probe.summary(), lm.audit()
            from lm_eval.utils import handle_non_serializable
            raw = (json.dumps(official, indent=2, ensure_ascii=False, allow_nan=False,
                              default=handle_non_serializable) + '\n').encode()
            p = a.output / 'OFFICIAL_RESULT.json'
            p.write_bytes(raw); p.with_suffix('.sha256').write_bytes((sha(p) + '\n').encode())
            value = dict(status='completed', phase='tasks', full_split=True, task=a.task,
                documents=len(official['samples'][a.task]), metrics=metrics(official, a.task),
                official_result_sha256=sha(p), audit=audit, addresses=addresses,
                identity=identity, case=case, seed=101, provenance=provenance,
                task_info=task_info, protocol=plan['task_protocol'], full_result_sha256=sha(a.full_result))
        else:
            indices = plan['screen_window_indices'] if a.phase == 'screen' else list(range(len(ledger)))
            with SamplingOverride(baseline_config()) as sampling:
                sampling.configure(modules)
                with SweepGU(case, {}, cal) as probe:
                    result = rq.score_windows(model, context, tokens, ledger, indices, 101, a.output, probe)
            assert len(probe.stats) == 36 and probe.wd_calls == 36 * len(indices)
            if a.phase == 'full':
                assert result['windows'] == 292 and result['targets'] == 299077
                screen_path = a.gate.parent.parent / 'screen' / case['id'] / 'RESULT.json'
                screen = rq.verify_sealed(screen_path)
                assert screen['provenance'] == provenance and screen['case'] == case
                assert result['window_ledger'][0]['nll'] == screen['result']['window_ledger'][0]['nll']
            if case['id'] in ['original_strat64', 'input_p20']:
                prior = rq.verify_sealed(a.prior_root / 'full-f3e89e2bfc02' / case['id'] / 'RESULT.json')
                for w in result['window_ledger']:
                    old = prior['result']['window_ledger'][w['window_index']]
                    assert w['nll'] == old['nll'] and w['target_token_sha256'] == old['target_token_sha256']
            value = dict(status='completed', phase=a.phase, full_corpus=a.phase == 'full', case=case,
                seed=101, identity=identity, provenance=provenance, protocol=protocol, result=result,
                gate_sha256=sha(a.gate), calibration_sha256=sha(a.gate.parent / 'CALIBRATION.json'))
    value['seconds'] = time.time() - started
    rq.save(a.output / 'RESULT.json', value, sealed=True)
    print(json.dumps({'status': 'completed', 'phase': a.phase, 'case': a.case,
                      'seconds': value['seconds']}), flush=True)


if __name__ == '__main__':
    main()
