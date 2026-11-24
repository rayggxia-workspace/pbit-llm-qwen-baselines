"""Frozen equal-budget AND-grid inference experiment; never trains a model."""
import argparse
from contextlib import contextmanager, nullcontext
import gc
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time
from types import MethodType

from scoring import Engine, save, score_ppl, task_lm


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(16 << 20), b''):
            h.update(block)
    return h.hexdigest()


def sealed(path):
    path = Path(path)
    assert sha(path) == path.with_suffix('.sha256').read_text().strip()
    d = json.loads(path.read_bytes())
    assert d['status'] == 'completed'
    return d


@contextmanager
def selected_docs(task, start, end):
    original = task.doc_iterator
    def iterator(self, *, rank=0, limit=None, world_size=1):
        assert rank == 0 and world_size == 1 and (limit is None or limit >= end)
        for idx, doc in original(rank=rank, limit=limit, world_size=world_size):
            if idx >= end:
                break
            if idx >= start:
                yield idx, doc
    task.doc_iterator = MethodType(iterator, task)
    try:
        yield
    finally:
        task.doc_iterator = original


def snapshot(model):
    return [(v, v.data_ptr(), v._version) for v in model.parameters()] + [
        (v, v.data_ptr(), v._version) for layer in model.model.layers for v in layer.mlp.buffers()]


def unchanged(state):
    assert all(v.data_ptr() == ptr and v._version == version for v, ptr, version in state)


def overlay(model, identity, record, plan, actual_path=None):
    import torch
    path = Path(actual_path or record['path'])
    assert path.stat().st_size == plan['overlay_bytes'] and sha(path) == plan['overlay_sha256']
    assert identity['export_manifest_sha256'] == plan['parent_export_manifest_sha256']
    assert record['revision'] == plan['overlay_revision']
    old = {n: (v.data_ptr(), v._version) for n, v in model.named_parameters()}
    buffers = [(v, v.data_ptr(), v._version) for layer in model.model.layers for v in layer.mlp.buffers()]
    checkpoint = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
    values, params = checkpoint['projections'], dict(model.named_parameters())
    names = {f'model.layers.{i}.self_attn.{proj}.weight' for i in range(36)
             for proj in ['q_proj', 'k_proj', 'v_proj', 'o_proj']}
    assert set(values) == names and len(names) == 144
    with torch.no_grad():
        for name in names:
            assert values[name].shape == params[name].shape and values[name].dtype == params[name].dtype
            params[name].copy_(values[name])
    assert all((v.data_ptr(), v._version) == old[n] for n, v in params.items() if n not in names)
    unchanged(buffers)
    return {'revision': record['revision'], 'sha256': plan['overlay_sha256'],
            'parent_export_manifest_sha256': identity['export_manifest_sha256'], 'changed_tensors': 144,
            'other_parameters_and_FFN_buffers_unchanged': True}


def task_metadata(a, plan, inputs):
    from transformers import AutoTokenizer
    from tasks import load_tasks
    tokenizer = AutoTokenizer.from_pretrained(inputs['tokenizer'], local_files_only=True, trust_remote_code=False)
    tasks, identity, harness = load_tasks(a.data_root, plan)
    return tokenizer, tasks, {'identity': identity, 'harness_sources': harness}


def run_task(model, context, case, tokenizer, task, name, seed, start, end, out):
    Path(out).mkdir(parents=True, exist_ok=True)
    from lm_eval import evaluator
    from lm_eval.utils import handle_non_serializable
    lm = task_lm(model, tokenizer, context, case, seed, name, start, out)
    with selected_docs(task, start, end):
        result = evaluator.evaluate(lm=lm, task_dict={name: task}, limit=None, bootstrap_iters=0,
            cache_requests=False, rewrite_requests_cache=False, write_out=True, log_samples=True,
            apply_chat_template=False, fewshot_as_multiturn=False)
    samples = result['samples'][name]
    assert len(samples) == end - start
    assert {int(x['doc_id']) for x in samples} == set(range(start, end))
    raw = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False,
                      default=handle_non_serializable) + '\n').encode()
    p = Path(out) / 'OFFICIAL_RESULT.json'
    p.write_bytes(raw); p.with_suffix('.sha256').write_bytes((hashlib.sha256(raw).hexdigest() + '\n').encode())
    metrics = {k: float(v) for k, v in result['results'][name].items() if k in ['acc,none', 'acc_norm,none']}
    for key, value in metrics.items():
        assert abs(sum(x[key.split(',')[0]] for x in samples) / len(samples) - value) < 1e-12
    audit = {'requests': lm.requests_audit, 'targets': lm.targets, 'reports': lm.reports,
             'request_ledger_sha256': hashlib.sha256((json.dumps(lm.requests_audit, separators=(',', ':')) + '\n').encode()).hexdigest()}
    value = {'task': name, 'doc_start': start, 'doc_end': end, 'documents': len(samples), 'metrics': metrics,
             'audit': audit, 'official_sha256': hashlib.sha256(raw).hexdigest()}
    del lm
    return value


def gate(a, plan, inputs, tokens, provenance):
    import torch
    from adapter import SamplingOverride
    from checks import device_checks
    from run_wt2 import load_model
    from sampling import shared_input_counts
    checks = device_checks('cuda')
    model, context, modules, identity = load_model(inputs, native=True)
    # Native cached no-op wrapper equivalence; same forward shape and cache use.
    ids = torch.tensor([tokens[:24].astype('int64').tolist()], device='cuda')
    context.seed = 101
    with torch.no_grad():
        context.begin(0, 0, domain='native-noop')
        ref = model(ids, use_cache=True, logits_to_keep=1).logits
        with Engine(model, context, None, 101, 'native-noop') as engine:
            actual = engine.forward(ids, None, True).logits
        assert torch.equal(ref, actual)
    del ref, actual, ids, engine
    native_ref = score_ppl(model, context, None, tokens, 101, a.output / 'native_reference', [0], suffix=True, batch=8)
    save(a.output / 'native_reference/RESULT.json', {'status': 'completed', 'identity': identity,
         'provenance': provenance, 'result': native_ref})
    del model, context, modules
    gc.collect(); torch.cuda.empty_cache()
    model, context, modules, identity = load_model(inputs)
    applied = overlay(model, identity, json.loads((a.reference_source / 'ADAPTATION_WEIGHT.json').read_bytes()), plan, a.overlay)
    tokenizer, tasks, task_info = task_metadata(a, plan, inputs)
    pilots, fingerprints, task_pilots = [], [], []
    for index in [0, 0, 1]:
        case = plan['cases'][index]
        patch = SamplingOverride(case)
        patch.configure(modules)
        state = snapshot(model)
        with patch:
            g = torch.Generator(device='cuda').manual_seed(123)
            q = torch.randint(257, (2, 128), device='cuda', generator=g)
            g0 = torch.Generator(device='cuda').manual_seed(456)
            g1 = torch.Generator(device='cuda').manual_seed(456)
            import seven_forward as sf
            assert torch.equal(sf.iid_shared64_counts(q, 64, g0), shared_input_counts(q, 64, g1))
            # Small full-context suffix, rather than treating a tiny context as production.
            r = score_ppl(model, context, case, tokens, 101, a.output / ('pilot_%d' % len(pilots)),
                          [0], suffix=True, batch=8, capture=True)
        unchanged(state)
        fingerprints.append(r['logits_sha256'])
        pilots.append({'case': case['id'], 'ppl': r['ppl'], 'targets': r['targets'], 'seconds': r['seconds'],
                       'audits': r['audits'], 'peak_allocated_GiB': torch.cuda.max_memory_allocated() / 2**30})
    assert fingerprints[0] == fingerprints[1]
    for case in plan['cases']:
        patch = SamplingOverride(case); patch.configure(modules)
        state = snapshot(model)
        with patch:
            for name in tasks:
                start = time.monotonic()
                r = run_task(model, context, case, tokenizer, tasks[name], name, 101, 0, 2,
                             a.output / ('task_pilot_' + case['id'] + '_' + name))
                task_pilots.append({'case': case['id'], 'task': name, 'documents': 2,
                                    'targets': r['audit']['targets'], 'seconds': time.monotonic() - start,
                                    'metrics': r['metrics']})
        unchanged(state)
    assert torch.cuda.max_memory_allocated() < 0.95 * torch.cuda.get_device_properties(0).total_memory
    return {'status': 'completed', 'phase': 'gate', 'checks': checks, 'native_cached_noop_bitwise': True,
            'coarse_repeat_logits_bitwise': True, 'front_shared64_unchanged': True,
            'weights_unchanged_after_scoring': True, 'native_reference': native_ref,
            'identity': identity, 'overlay': applied, 'provenance': provenance, 'task_info': task_info,
            'pilots': pilots, 'task_pilots': task_pilots}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['gate', 'ppl', 'task'], required=True)
    for key in ['reference-source', 'runtime', 'task-source', 'data-root', 'output']:
        ap.add_argument('--' + key, type=Path, required=True)
    ap.add_argument('--case', choices=['coarse32', 'fine128', 'bf16'], default='coarse32')
    ap.add_argument('--seed', type=int, default=101)
    ap.add_argument('--shard', type=int, default=0)
    ap.add_argument('--task', default='piqa')
    ap.add_argument('--gate', type=Path)
    ap.add_argument('--inputs', type=Path, help='Relocated input paths; original identity fields must match.')
    ap.add_argument('--overlay', type=Path, help='Relocated, SHA-identical QKVO checkpoint.')
    a = ap.parse_args()
    assert not a.output.exists(), 'Use a fresh immutable result directory.'
    a.output.mkdir(parents=True)
    assert 'SLURM_JOB_ID' in __import__('os').environ
    started = time.monotonic()
    own = Path(__file__).parent
    plan = json.loads((own / 'PLAN.json').read_bytes())
    manifest = own / 'EXECUTION_MANIFEST.json'
    for name, checksum in json.loads(manifest.read_bytes())['files'].items():
        assert sha(own / name) == checksum
    ref_manifest = a.reference_source / 'execution.json'
    ref = json.loads(ref_manifest.read_bytes())
    assert ref['identity'] == plan['reference_identity']
    for name, checksum in ref['files_sha256'].items():
        assert sha(a.reference_source / name) == checksum
    task_manifest = a.task_source / 'EXECUTION_MANIFEST.json'
    assert sha(task_manifest) == '807238c8e2d1e995aba9f75eb949899aa63b5178189d9f774ae788560a507d1f'
    for name, checksum in json.loads(task_manifest.read_bytes())['files'].items():
        assert sha(a.task_source / name) == checksum
    # Keep reference import precedence explicit; no copy or mutation of its files.
    sys.path[1:1] = [str(a.reference_source / 'ffn'), str(a.reference_source), str(a.task_source)]
    from run_wt2 import prepare, load_model
    from adapter import SamplingOverride
    (a.output / 'protocol').mkdir()
    original_inputs = a.reference_source / 'ffn/INPUTS.json'
    actual_inputs = a.inputs or original_inputs
    if a.inputs:
        before, after = json.loads(original_inputs.read_bytes()), json.loads(a.inputs.read_bytes())
        locations = {'parent_model', 'tokenizer', 'T64_deployment', 'text'}
        assert set(before) == set(after)
        assert all(before[k] == after[k] for k in before if k not in locations)
    inputs, tokens, ledger, protocol = prepare(actual_inputs, a.runtime, a.output / 'protocol')
    assert protocol['text_sha256'] == plan['test_text_sha256'] and protocol['token_sha256'] == plan['test_token_sha256']
    provenance = {'source_commit': json.loads(manifest.read_bytes())['git_commit'],
                  'source_manifest_sha256': sha(manifest), 'plan_sha256': sha(own / 'PLAN.json'),
                  'reference_identity': ref['identity'], 'reference_manifest_sha256': sha(ref_manifest),
                  'inputs_sha256': sha(a.reference_source / 'ffn/INPUTS.json'),
                  'effective_inputs_sha256': sha(actual_inputs),
                  'task_source_manifest_sha256': sha(task_manifest), 'protocol': protocol,
                  'versions': {x: importlib.metadata.version(x) for x in ['torch', 'transformers', 'triton', 'lm_eval', 'datasets', 'accelerate']}}
    native = a.phase == 'gate' or a.case == 'bf16'
    if a.phase == 'gate':
        result = gate(a, plan, inputs, tokens, provenance)
    else:
        model, context, modules, identity = load_model(inputs, native=native)
        g = sealed(a.gate)
        assert g['provenance'] == provenance and g['native_cached_noop_bitwise']
        assert g['coarse_repeat_logits_bitwise'] and g['front_shared64_unchanged']
        case = None if native else next(c for c in plan['cases'] if c['id'] == a.case)
        applied = None if native else overlay(model, identity, json.loads((a.reference_source / 'ADAPTATION_WEIGHT.json').read_bytes()), plan, a.overlay)
        if not native:
            assert identity == g['identity'] and applied == g['overlay']
        patch = nullcontext() if native else SamplingOverride(case)
        if not native:
            patch.configure(modules)
        state = snapshot(model)
        with patch:
            if a.phase == 'ppl':
                assert 0 <= a.shard < plan['ppl']['shards']
                parts = list(range(0, 292, 8))[a.shard::plan['ppl']['shards']]
                data = score_ppl(model, context, case, tokens, a.seed, a.output, parts, batch=8)
                result = {'status': 'completed', 'phase': 'ppl', 'case': a.case, 'seed': a.seed,
                          'shard': a.shard, 'parts': parts, 'result': data}
            else:
                assert not native and a.seed in plan['task_seeds']
                tokenizer, tasks, info = task_metadata(a, plan, inputs)
                assert info == g['task_info'] and a.task in tasks
                total = plan['tasks'][a.task]['count']
                n = plan['task_shards']; assert 0 <= a.shard < n
                start, end = total * a.shard // n, total * (a.shard + 1) // n
                data = run_task(model, context, case, tokenizer, tasks[a.task], a.task, a.seed, start, end, a.output)
                result = dict(status='completed', phase='task', case=a.case, seed=a.seed,
                              shard=a.shard, task_info=info, task_protocol=plan['task_protocol'], **data)
        unchanged(state)
        result.update(identity=identity, overlay=applied, provenance=provenance,
                      case_config=case, gate_sha256=sha(a.gate), no_training=True)
    result['service_seconds'] = time.monotonic() - started
    save(a.output / 'RESULT.json', result)
    print(json.dumps({'status': 'completed', 'phase': a.phase, 'case': a.case,
                      'seconds': result['service_seconds']}), flush=True)


if __name__ == '__main__':
    main()
