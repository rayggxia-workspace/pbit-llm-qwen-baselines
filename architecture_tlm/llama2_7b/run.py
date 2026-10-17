"""Llama 2 7B full-decode TLM; verified real trace or explicit synthetic workload."""
import argparse
import hashlib
import importlib.util
import json
import math
import platform
import re
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SHARED = ROOT.parent / 'llama7b'
RUNTIME = SHARED / 'runtime'
# Reuse the frozen LLaMA MHA engine, never an ambiguous import of another run.py.
sys.path.insert(0, str(RUNTIME))
from run_attention_v3 import configuration
from pv_stream_v6 import context_samples
from scatter_memory_v6 import ScatterDRAMSysExternal

_spec = importlib.util.spec_from_file_location('llama2_shared_mha_adapter', SHARED / 'attention_adapter.py')
_adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_adapter)

CASES = {
    'bf16_dense': ('digital_bf16', 'dense'),
    'int8_dense': ('digital_int8_ffn', 'dense'),
    'sc_dense': ('fixed_sc_exact', 'dense'),
    'sc_pv': ('fixed_sc_exact', 'pv'),
    'sc_screen_exact': ('fixed_sc_exact', 'screen_exact'),
    'sc_screen_pv': ('fixed_sc_exact', 'screen_pv'),
    'sc_ising': ('fixed_sc_exact', 'ising'),
    'sc_screen_ising': ('fixed_sc_exact', 'screen_ising'),
}
REAL_KIND = 'REAL_LLAMA2_7B_POST_ROPE_QK_LOGITS'
SYNTHETIC_KIND = 'SYNTHETIC_LLAMA2_SHAPE'
IDENTITY_REPOSITORY = 'meta-llama/Llama-2-7b-hf'
SHAPE_KEYS = ('model_type', 'hidden_size', 'intermediate_size', 'num_hidden_layers',
              'num_attention_heads', 'num_key_value_heads', 'max_position_embeddings', 'vocab_size',
              'rms_norm_eps', 'rope_theta', 'tie_word_embeddings', 'hidden_act', 'attention_bias')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_identity(path, shape):
    """Validate the identity declaration; capture separately verifies actual files."""
    data = read_json(path)
    if data.get('repository') != IDENTITY_REPOSITORY:
        raise ValueError('identity manifest must identify the official Llama 2 7B Base repository')
    if not re.fullmatch('[0-9a-f]{40}', data.get('revision', '')):
        raise ValueError('identity manifest needs an exact upstream revision')
    expected = {key: shape[key] for key in SHAPE_KEYS}
    if any(data.get('model_shape', {}).get(key) != value for key, value in expected.items()):
        raise ValueError('identity manifest model_shape mismatch')
    files = data.get('files', {})
    if not isinstance(files, dict) or not files:
        raise ValueError('identity manifest needs model and tokenizer file hashes')
    for name, row in files.items():
        if (not isinstance(row, dict) or not re.fullmatch('[0-9a-f]{64}', row.get('sha256', ''))
                or not isinstance(row.get('bytes'), int) or row['bytes'] < 1):
            raise ValueError('invalid model identity file: ' + name)
    if ('config.json' not in files
            or not any(name.endswith(('.safetensors', '.bin')) for name in files)
            or not any(name in files for name in ('tokenizer.model', 'tokenizer.json'))):
        raise ValueError('identity manifest must include config, weights and tokenizer')
    return data


def validate_workload(trace, identity_manifest, synthetic, context, tokens, shape):
    """Reject a same-shape LLaMA-1 trace and unverified/hybrid provenance."""
    if context < 2 or tokens < 1 or context + tokens - 1 > shape['max_position_embeddings']:
        raise ValueError('invalid/native context limit exceeded; no long-context extrapolation')
    if synthetic:
        if trace or identity_manifest:
            raise ValueError('--synthetic cannot be combined with model/trace identity')
        return dict(kind=SYNTHETIC_KIND, real_model_trace=False,
                    warning='Gaussian workload addresses only; not measured Llama 2 attention, PPL or quality')
    if trace is None or identity_manifest is None:
        raise ValueError('use --trace with --identity-manifest, or explicitly request --synthetic')
    identity = validate_identity(identity_manifest, shape)
    data = read_json(trace)
    provenance = data.get('provenance', {})
    if provenance.get('kind') != REAL_KIND:
        raise ValueError('trace must be a verified Llama 2 7B post-RoPE QK trace; LLaMA-1 is not interchangeable')
    if provenance.get('model_identity') != identity:
        raise ValueError('trace model/tokenizer identity does not match identity manifest')
    if provenance.get('identity_manifest_sha256') != sha(identity_manifest):
        raise ValueError('trace identity manifest byte hash mismatch')
    if any(provenance.get('model_shape', {}).get(key) != shape[key] for key in SHAPE_KEYS):
        raise ValueError('trace model_shape mismatch')
    if provenance.get('context') != context or provenance.get('decode_tokens') != tokens:
        raise ValueError('trace context/decode count mismatch')
    checks = provenance.get('validation', [])
    if (len(checks) != tokens or any(check.get('token') != token
            or check.get('bitwise_equal') is not True
            or check.get('max_abs_difference') != 0 for token, check in enumerate(checks))):
        raise ValueError('trace needs unchanged BF16 reference with bitwise-equal output for every token')
    expected_rows = tokens * shape['num_hidden_layers'] * shape['num_attention_heads']
    rows = data.get('rows', [])
    if len(rows) != expected_rows:
        raise ValueError('incomplete trace rows')
    seen = set()
    for row in rows:
        token, layer, head = row.get('token'), row.get('layer'), row.get('head')
        if (not isinstance(token, int) or not isinstance(layer, int) or not isinstance(head, int)
                or not 0 <= token < tokens or not 0 <= layer < shape['num_hidden_layers']
                or not 0 <= head < shape['num_attention_heads'] or (token, layer, head) in seen):
            raise ValueError('duplicate or invalid trace row identity')
        seen.add((token, layer, head))
        values = row.get('logits', [])
        if len(values) != context + token or not all(isinstance(x, (float, int)) and math.isfinite(x) for x in values):
            raise ValueError('invalid trace logits/cache length')
    return dict(kind=REAL_KIND, real_model_trace=True, trace_sha256=sha(trace),
                identity_manifest_sha256=sha(identity_manifest), model_identity=identity,
                bf16_capture_bitwise_equal=True, PPL_measured=False)


def build(context, seed, tokens=1, mode='dense', trace=None, sram_mib=8, engines=8, samples=4096):
    cfg, evidence, _ = configuration()
    shape = read_json(ROOT / 'configs/model.json')
    if context < 2 or tokens < 1 or context + tokens - 1 > shape['max_position_embeddings']:
        raise ValueError('native context limit exceeded; no silent long-context extrapolation')
    if sram_mib < 1 or engines < 1 or samples < 1:
        raise ValueError('positive SRAM, engine and sample counts are required')
    cfg.update(context_tokens=context, decode_tokens=tokens, sc_engines=engines, samples=samples)
    cfg['description'] = 'Llama 2 7B isolated transaction scenario, not hardware measurement'
    cfg['external_memory'].update(backend='link', burst_bytes=64)
    cfg['attention_v3'].update(mode=mode, seed=seed, calibration_file=None,
        trace_file=str(Path(trace).resolve()) if trace else None,
        record_transactions=False, summary_initialization='prefill_prebuilt')
    cfg['pv_stream_v6'] = read_json(RUNTIME / 'configs/pv_stream_v6.json')
    cfg['attention_v3']['samples'] = context_samples(context, cfg['pv_stream_v6'])
    cfg['llama_attention_mode'] = mode
    cfg['llama_ising'] = read_json(RUNTIME / 'configs/screen_ising_v4.json')['ising']
    cfg['llama_ising_capacity'] = context + tokens - 1
    cfg['llama_attention'] = dict(ising_macro=cfg['llama_ising'], ising_capacity=context + tokens - 1,
        selector='max4', prefill_prebuilt=True)
    plan = read_json(ROOT / 'configs/sram_plan.json')
    plan.update(unified_bytes=sram_mib*2**20, weight_bytes=sram_mib*2**20, scratch_bytes=sram_mib*2**20)
    plan['chunk_bytes'] = max(plan['chunk_bytes'], engines * 4096)
    calibration = read_json(RUNTIME / 'results/sram_calibration_v1_20261016/calibration.json')
    return cfg, evidence, shape, plan, calibration


def simulate(args):
    variant, mode = CASES[args.case]
    cfg, evidence, shape, plan, calibration = build(args.context, args.seed, args.tokens, mode,
        args.trace, args.sram_mib, args.engines, args.samples)
    workload = validate_workload(args.trace, args.identity_manifest, args.synthetic, args.context, args.tokens, shape)
    if args.output.exists():
        raise ValueError('refusing to overwrite result: ' + str(args.output))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.bridge:
        if not args.dram_config:
            raise ValueError('--bridge requires explicit source-audited --dram-config')
        cfg['external_memory'].update(backend='dramsys', bridge_executable=str(args.bridge.resolve()),
            configuration=str(args.dram_config.resolve()), max_pending=32,
            output_prefix=str(args.output.with_suffix('').resolve()) + '_dram')
    cls = _adapter.LlamaDigitalDecode if variant.startswith('digital') else _adapter.LlamaLocalDecode
    start = time.monotonic()
    with patch('dramsys_backend.DRAMSysExternal', ScatterDRAMSysExternal):
        model = cls(cfg, variant, evidence, shape, calibration, plan)
    try:
        # The shared Gaussian oracle remains intentionally explicit in synthetic runs.
        if args.synthetic:
            model.source.provenance.update(kind=SYNTHETIC_KIND, model='Llama 2 7B dimensions only',
                warning=workload['warning'])
        result = model.run()
    finally:
        if hasattr(model.ext, 'close'):
            model.ext.close()
    for key in ('quality_reference', 'inherited_ffn_only_quality_reference'):
        result.pop(key, None)
    result['quality_reference_ppl'] = None
    result['quality_warning'] = 'No new joint SC-FFN numeric inference/PPL; capture identity and routing diagnostics do not establish model quality.'
    result['scope'] = 'Llama 2 7B full32-layer batch1 decode including untied embedding, RMS affine and lm_head; prefill excluded'
    result.update(actual_shape=shape, case=args.case, context=args.context, seed=args.seed,
                  wall_seconds=time.monotonic()-start, workload=workload)
    # Shared macro warnings remain, but an old Qwen fixture label must not
    # obscure whether the *current* address workload came from verified QK.
    limitations = result.get('memory_v5', {}).get('limitations', [])
    result.get('memory_v5', {})['limitations'] = [
        ('BF16 Llama 2 routing oracle only; no joint sampled-model PPL' if workload['real_model_trace']
         else 'Explicit synthetic Llama 2 shape workload; not real model attention or PPL')
        if item == 'synthetic Attention trajectory, not real Qwen trace or PPL' else item
        for item in limitations]
    result['environment'] = dict(python=platform.python_version(), platform=platform.platform())
    result['source_hashes']['llama2_7b/run.py'] = sha(__file__)
    result['source_hashes']['llama2_7b/configs/model.json'] = sha(ROOT / 'configs/model.json')
    result['source_hashes']['llama2_7b/configs/sram_plan.json'] = sha(ROOT / 'configs/sram_plan.json')
    result['source_hashes']['llama7b/attention_adapter.py'] = sha(SHARED / 'attention_adapter.py')
    result['configuration_sha256'] = hashlib.sha256(json.dumps(dict(config=cfg, plan=plan, shape=shape), sort_keys=True).encode()).hexdigest()
    execution_manifest = ROOT / 'EXECUTION_MANIFEST.json'
    if execution_manifest.exists():
        result['execution_manifest_sha256'] = sha(execution_manifest)
        result['execution_source_commit'] = read_json(execution_manifest)['code_commit']
    result['invocation'] = sys.argv
    result['backend_label'] = ('DRAMSys closed-loop / source-backed current scenario' if args.bridge
        else 'Simplified Link: uncalibrated external energy; architectural comparison only')
    result['validation'] = dict(new_model_inference=False, PPL_measured=False,
        real_BF16_routing_trace=workload['real_model_trace'],
        random_stream_SRAM_bytes=result['bounds'].get('random_word_replay_bytes', 0),
        energy_ledger_closed=math.isclose(sum(result['energy_J'].values())*1000/args.tokens,
            result['metrics']['scenario_mJ_per_token'], rel_tol=1e-10))
    assert result['validation']['energy_ledger_closed']
    assert result['memory_v5']['work_peak_bytes'] <= model.work_mem.capacity
    result['events_count'] = len(result.pop('events', []))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(case=args.case, context=args.context, seed=args.seed,
        workload_kind=workload['kind'], wall_seconds=result['wall_seconds'], metrics=result['metrics'],
        work_peak_bytes=result['memory_v5']['work_peak_bytes']), ensure_ascii=True), flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=CASES, required=True)
    p.add_argument('--context', type=int, default=4096)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--tokens', type=int, default=1)
    p.add_argument('--trace', type=Path)
    p.add_argument('--identity-manifest', type=Path)
    p.add_argument('--synthetic', action='store_true')
    p.add_argument('--sram-mib', type=int, default=8)
    p.add_argument('--engines', type=int, default=8)
    p.add_argument('--samples', type=int, default=4096)
    p.add_argument('--bridge', type=Path)
    p.add_argument('--dram-config', type=Path)
    p.add_argument('--output', type=Path, required=True)
    return p


if __name__ == '__main__':
    simulate(parser().parse_args())
