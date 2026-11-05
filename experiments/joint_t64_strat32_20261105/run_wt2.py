"""Frozen T64 checkpoint, original full-WT2 scorer, sampling-only ablations."""
from pathlib import Path
import argparse
import gc
import hashlib
import json
import math
import sys
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(16 << 20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def prepare(inputs_path, runtime, output):
    import numpy as np
    import torch
    from transformers import AutoTokenizer

    manifest = runtime / 'SOURCE_MANIFEST.json'
    assert sha(manifest) == 'eb23a172efbd18e3e56060a6b10d2bfcde33fc7a014c5b10949038921ffb9076'
    for name, digest in json.loads(manifest.read_bytes()).items():
        assert sha(runtime / name) == digest, name
    sys.path.insert(0, str(runtime))
    from qwen3.training.sc_qat.evaluate import TEXT_SHA, TOKEN_SHA, spans
    inputs = json.loads(inputs_path.read_bytes())
    assert inputs['actual_shared_files_authorized_by_user']
    for name, digest in inputs['parent_files_sha256'].items():
        assert sha(Path(inputs['parent_model']) / name) == digest, name
    assert sha(inputs['text']) == TEXT_SHA
    tokenizer = AutoTokenizer.from_pretrained(inputs['tokenizer'], local_files_only=True, trust_remote_code=False)
    tokens = np.asarray(tokenizer.encode(Path(inputs['text']).read_text(encoding='utf-8'),
                                        add_special_tokens=False), dtype='<u4')
    assert sha_array(tokens) == TOKEN_SHA and len(tokens) == 299078
    ledger = list(spans(len(tokens)))
    assert len(ledger) == 292 and sum(end - first for start, end, first in ledger) == 299077
    protocol = dict(kind='original_full_WT2_sliding_windows', window=2048, stride=1024,
                    windows=292, targets=299077, text_sha256=TEXT_SHA, token_sha256=TOKEN_SHA,
                    original_scorer_sha256=sha(runtime / 'qwen3/training/sc_qat/evaluate.py'),
                    chat_template=False, thinking_template=False,
                    scope='same trained100M T64 export/non_ffn;no retraining;ideal within-stratum jitter,not GF64 bit replay')
    save(output / 'PROTOCOL.json', protocol)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    return inputs, tokens, ledger, protocol


def sha_array(tokens):
    return hashlib.sha256(tokens.astype('<u4').tobytes()).hexdigest()


def load_model(inputs, native=False):
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM
    from qwen3.training.sc_qat.trainable_ffn import RunContext
    if native:
        from seven_evaluate import native_context
        model = AutoModelForCausalLM.from_pretrained(inputs['parent_model'], local_files_only=True,
                    trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda().eval()
        context = native_context(model, 101)
        modules = []
        identity = {'model': 'unchanged BF16 parent,not trained100M BF16 control',
                    'parent_files_sha256': inputs['parent_files_sha256']}
    else:
        from seven_deployment import load_ffn
        from seven_integration import Key
        deployment = Path(inputs['T64_deployment'])
        manifest = json.loads((deployment / 'export_complete.json').read_bytes())
        assert manifest['case'] == 'T64' and manifest['trained_tokens'] == 100000000 and manifest['complete']
        assert manifest['evaluation_source_sha256'] == 'eb23a172efbd18e3e56060a6b10d2bfcde33fc7a014c5b10949038921ffb9076'
        for name, digest in manifest['files'].items():
            assert sha(deployment / name) == digest, name
        config = AutoConfig.from_pretrained(inputs['tokenizer'], local_files_only=True, trust_remote_code=False)
        model = AutoModelForCausalLM.from_config(config, trust_remote_code=False,
                                               torch_dtype=torch.bfloat16, attn_implementation='sdpa')
        values = torch.load(deployment / 'non_ffn.pt', map_location='cpu', weights_only=True, mmap=True)
        missing = model.load_state_dict(values, strict=False)
        assert not missing.unexpected_keys and all('.mlp.' in name for name in missing.missing_keys)
        del values
        for i, layer in enumerate(model.model.layers):
            payload = torch.load(deployment / ('ffn_%02d.pt' % i), map_location='cpu', weights_only=True)
            layer.mlp = load_ffn(payload, device='cuda', backend='exact_int8')
            del payload
        model = model.cuda().eval()
        context = RunContext(101)
        for i, layer in enumerate(model.model.layers):
            def before(module, args, i=i):
                context.record(i, args[0])
                module.noise_key = Key(context.seed, context.step, context.micro, context.rank, context.call, context.domain)
            layer.mlp.register_forward_pre_hook(before)
        model.register_forward_pre_hook(context.root_pre_hook, with_kwargs=True)
        modules = [layer.mlp for layer in model.model.layers]
        identity = dict(checkpoint_case='T64', trained_tokens=100000000,
                        export_manifest_sha256=sha(deployment / 'export_complete.json'),
                        deployment_files_sha256=manifest['files'])
    context.rank = 0
    context.capture_replay = False
    model.requires_grad_(False)
    assert (model.config.num_hidden_layers, model.config.hidden_size, model.config.intermediate_size) == (36, 2560, 9728)
    return model, context, modules, identity


def verify_result(result, protocol):
    assert result['complete'] and result['window'] == 2048 and result['stride'] == 1024
    assert result['windows'] == protocol['windows'] and result['targets'] == protocol['targets']
    assert result['token_sha256'] == protocol['token_sha256']
    assert set(result['ffn_token_coverage']) == {str(i) for i in range(36)}
    assert len(set(result['ffn_token_coverage'].values())) == 1
    assert math.isfinite(result['ppl']) and result['ppl'] > 0


def gate(inputs, tokens, ledger, protocol, output, plan):
    import numpy as np
    import torch
    from torch.nn import functional as F
    from qwen3.training.sc_qat.evaluate import score
    from adapter import SamplingOverride

    started = time.time()
    model, context, modules, identity = load_model(inputs, native=True)
    reference = score(model, tokens, output / 'BF16_reference', context, 101)
    verify_result(reference, protocol)
    save(output / 'REFERENCE.json', dict(status='PASS', protocol=protocol, identity=identity, result=reference,
                                       historical_parent_PPL=11.540139,
                                       historical_difference=reference['ppl'] - 11.540139))
    # This is a numerical sanity check, not a requirement for bitwise equality
    # across the original training GPU and this GPU/software environment.
    assert abs(reference['ppl'] - 11.540139) < 0.05, 'unchanged full BF16 differs; inspect identity/protocol before comparison'
    del model, context, modules
    gc.collect()
    torch.cuda.empty_cache()
    load_start = time.time()
    model, context, modules, identity = load_model(inputs)
    load_seconds = time.time() - load_start
    versions = {(i, name): (value.data_ptr(), value._version)
                for i, module in enumerate(modules) for name, value in module.named_buffers()}
    start, end, first = ledger[0]
    ids = torch.as_tensor(tokens[start:end].astype(np.int64), device='cuda')[None]
    context.seed = 101
    context.begin(0, 0, domain='ffn-wt2-deployment')
    with torch.no_grad():
        original = model(ids, use_cache=False).logits[0].detach().clone()
    original_iid_exact = False
    timings = []
    for case in plan['cases']:
        patch = SamplingOverride(case)
        patch.configure(modules)
        windows = []
        torch.cuda.reset_peak_memory_stats()
        with patch, torch.no_grad():
            for wi, (start, end, first) in enumerate(ledger[:2]):
                ids = torch.as_tensor(tokens[start:end].astype(np.int64), device='cuda')[None]
                context.seed = 101
                context.begin(0, wi, domain='ffn-wt2-deployment')
                torch.cuda.synchronize()
                timed = time.time()
                logits = model(ids, use_cache=False).logits[0]
                assert torch.isfinite(logits).all()
                if case['id'] == 'iid64' and wi == 0:
                    assert torch.equal(original, logits), 'full2048 no-op IID64 changed'
                    original_iid_exact = True
                loss = logits.new_zeros((), dtype=torch.float32)
                for lo in range(first - start - 1, end - start - 1, 128):
                    hi = min(end - start - 1, lo + 128)
                    loss += F.cross_entropy(logits[lo:hi].float(), ids[0, lo + 1:hi + 1], reduction='sum')
                assert math.isfinite(float(loss))
                windows.append(time.time() - timed)
                assert len(context.coverage) == 36 and all(v['calls'] == 1 and v['tokens'] == 2048 for v in context.coverage.values())
                assert all((m.last_arithmetic['T_x'], m.last_arithmetic['T_AND']) == (case['T_x'], case['T_and']) for m in modules)
        assert all((value.data_ptr(), value._version) == versions[i, name]
                   for i, module in enumerate(modules) for name, value in module.named_buffers())
        estimate_seconds = load_seconds + windows[0] + 292 * windows[1] * 1.6 + 120
        timings.append(dict(case=case['id'], windows_seconds=windows, one_seed_estimated_seconds=estimate_seconds,
                            peak_allocated_GiB=torch.cuda.max_memory_allocated() / 2 ** 30))
        save(output / 'GATE_PROGRESS.json', dict(timings=timings, seconds=time.time() - started))
    result = dict(status='PASS', phase='preflight', protocol=protocol, identity=identity,
                  original_IID64_2048_bitwise=original_iid_exact, weights_unchanged=True,
                  load_seconds=load_seconds, timings=timings, seconds=time.time() - started)
    save(output / 'RESULT.json', result)
    return result


def evaluate(inputs, tokens, protocol, output, plan, case_id, seed, gate_path):
    from qwen3.training.sc_qat.evaluate import score
    from adapter import SamplingOverride
    assert seed in plan['deployment_seeds']
    preflight = json.loads(gate_path.read_bytes())
    assert preflight['status'] == 'PASS' and preflight['original_IID64_2048_bitwise']
    assert preflight['protocol'] == protocol
    case = next(case for case in plan['cases'] if case['id'] == case_id)
    model, context, modules, identity = load_model(inputs)
    assert identity == preflight['identity']
    context.seed = seed
    patch = SamplingOverride(case)
    patch.configure(modules)
    with patch:
        result = score(model, tokens, output / 'score', context, seed)
    verify_result(result, protocol)
    assert all((m.last_arithmetic['T_x'], m.last_arithmetic['T_AND']) == (case['T_x'], case['T_and']) for m in modules)
    value = dict(status='PASS', phase='full_WT2', case=case, seed=seed, protocol=protocol,
                 identity=identity, result=result, original_scorer_unchanged=True,
                 gate_result_sha256=sha(gate_path), no_training=True,
                 limitation='ideal independent within-cell jitter;not GF64/physicalpbit playback or saturating counter validation')
    save(output / 'RESULT.json', value)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['preflight', 'full'], required=True)
    parser.add_argument('--case')
    parser.add_argument('--seed', type=int, default=101)
    parser.add_argument('--gate', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    inputs, tokens, ledger, protocol = prepare(args.inputs, args.runtime, args.output)
    plan = json.loads(args.plan.read_bytes())
    if args.phase == 'preflight':
        value = gate(inputs, tokens, ledger, protocol, args.output, plan)
    else:
        value = evaluate(inputs, tokens, protocol, args.output, plan, args.case, args.seed, args.gate)
    print(json.dumps({k: value[k] for k in ('status', 'phase')}), flush=True)


if __name__ == '__main__':
    main()
