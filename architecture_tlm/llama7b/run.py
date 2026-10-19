"""Isolated LLaMA-1 7B full-decode TLM; no numeric/PPL claim."""
import argparse
import copy
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime'))
from run_attention_v3 import configuration
from memory_schedule_v5 import BankedDigitalDecode
from pv_stream_v6 import StreamPVDecode, StreamDigitalDecode, context_samples
from scatter_memory_v6 import ScatterDRAMSysExternal

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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(context, seed, tokens=1, mode='dense', trace=None, sram_mib=8, engines=8, samples=4096):
    cfg, evidence, _ = configuration()
    shape = json.loads((ROOT / 'configs/model.json').read_text(encoding='utf-8'))
    cfg.update(context_tokens=context, decode_tokens=tokens, sc_engines=engines, samples=samples)
    cfg['description'] = 'LLaMA-1 7B isolated transaction scenario, not hardware measurement'
    if context + tokens - 1 > shape['max_position_embeddings']:
        raise ValueError('native context limit exceeded; no silent long-context extrapolation')
    cfg['external_memory'].update(backend='link', burst_bytes=64)
    # Link remains an explicitly uncalibrated comparison; DRAMSys overrides below.
    cfg['attention_v3'].update(mode=mode,
        seed=seed, calibration_file=None, trace_file=str(Path(trace).resolve()) if trace else None,
        record_transactions=False, summary_initialization='prefill_prebuilt')
    cfg['pv_stream_v6'] = json.loads((ROOT / 'runtime/configs/pv_stream_v6.json').read_text())
    cfg['attention_v3']['samples'] = context_samples(context, cfg['pv_stream_v6'])
    cfg['llama_attention_mode'] = mode
    cfg['llama_ising'] = json.loads((ROOT / 'runtime/configs/screen_ising_v4.json').read_text())['ising']
    cfg['llama_ising_capacity'] = context + tokens - 1
    cfg['llama_attention'] = {'ising_macro': cfg['llama_ising'],
        'ising_capacity': context + tokens - 1, 'selector': 'max4',
        'prefill_prebuilt': True}
    plan = json.loads((ROOT / 'configs/sram_plan.json').read_text())
    plan.update(unified_bytes=sram_mib*2**20, weight_bytes=sram_mib*2**20, scratch_bytes=sram_mib*2**20)
    plan['chunk_bytes'] = max(plan['chunk_bytes'], engines * 4096)
    calibration = json.loads((ROOT / 'runtime/results/sram_calibration_v1_20261016/calibration.json').read_text())
    return cfg, evidence, shape, plan, calibration


def simulate(args):
    variant, mode = CASES[args.case]
    cfg, evidence, shape, plan, calibration = build(args.context, args.seed, args.tokens, mode,
        args.trace, args.sram_mib, args.engines, args.samples)
    if args.output.exists():
        raise ValueError('refusing to overwrite result: ' + str(args.output))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.bridge:
        if not args.dram_config:
            raise ValueError('--bridge requires explicit source-audited --dram-config')
        cfg['external_memory'].update(backend='dramsys', bridge_executable=str(args.bridge.resolve()),
            configuration=str(args.dram_config.resolve()), max_pending=32,
            output_prefix=str(args.output.with_suffix('').resolve()) + '_dram')
    from attention_adapter import LlamaLocalDecode, LlamaDigitalDecode
    cls = LlamaDigitalDecode if variant.startswith('digital') else LlamaLocalDecode
    start = time.monotonic()
    with patch('dramsys_backend.DRAMSysExternal', ScatterDRAMSysExternal):
        model = cls(cfg, variant, evidence, shape, calibration, plan)
    try:
        result = model.run()
    finally:
        if hasattr(model.ext, 'close'):
            model.ext.close()
    elapsed = time.monotonic() - start
    # Remove Qwen-specific inherited numerical quality numbers at every entry.
    for key in ('quality_reference', 'inherited_ffn_only_quality_reference'):
        result.pop(key, None)
    result['quality_reference_ppl'] = None
    result['quality_warning'] = 'LLaMA TLM has no new PPL validation. A8/share64, proportional PV, max4 and abstract Ising are not the old LLaMA numeric experiment.'
    result['scope'] = 'LLaMA-1 7B full32-layer batch1 decode including independent embedding, RMS affine reads and lm_head; prefill excluded'
    result['actual_shape'] = shape
    result['case'] = args.case
    result['context'] = args.context
    result['seed'] = args.seed
    result['wall_seconds'] = elapsed
    result['environment'] = {'python': platform.python_version(), 'platform': platform.platform()}
    result['source_hashes']['llama7b/run.py'] = sha(__file__)
    result['source_hashes']['llama7b/configs/model.json'] = sha(ROOT / 'configs/model.json')
    if (ROOT / 'attention_adapter.py').exists():
        result['source_hashes']['llama7b/attention_adapter.py'] = sha(ROOT / 'attention_adapter.py')
    result['configuration_sha256'] = hashlib.sha256(json.dumps({'config': cfg, 'plan': plan, 'shape': shape}, sort_keys=True).encode()).hexdigest()
    execution_manifest = ROOT / 'EXECUTION_MANIFEST.json'
    if execution_manifest.exists():
        result['execution_manifest_sha256'] = sha(execution_manifest)
        result['execution_source_commit'] = json.loads(execution_manifest.read_text())['code_commit']
    result['invocation'] = sys.argv
    result['backend_label'] = 'DRAMSys closed-loop / source-backed current scenario' if args.bridge else 'Simplified Link: uncalibrated external energy; architectural comparison only'
    result['validation'] = {'new_model_inference': False, 'PPL_measured': False,
        'random_stream_SRAM_bytes': result['bounds'].get('random_word_replay_bytes', 0),
        'energy_ledger_closed': math.isclose(sum(result['energy_J'].values()) * 1000 / args.tokens,
            result['metrics']['scenario_mJ_per_token'], rel_tol=1e-10)}
    assert result['validation']['energy_ledger_closed']
    assert result['memory_v5']['work_peak_bytes'] <= model.work_mem.capacity
    result['events_count'] = len(result.pop('events', []))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'case': args.case, 'context': args.context, 'seed': args.seed, 'wall_seconds': elapsed,
        'metrics': result['metrics'], 'work_peak_bytes': result['memory_v5']['work_peak_bytes']}, ensure_ascii=True), flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=CASES, required=True)
    p.add_argument('--context', type=int, default=2048)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--tokens', type=int, default=1)
    p.add_argument('--trace', type=Path)
    p.add_argument('--sram-mib', type=int, default=8)
    p.add_argument('--engines', type=int, default=8)
    p.add_argument('--samples', type=int, default=4096)
    p.add_argument('--bridge', type=Path)
    p.add_argument('--dram-config', type=Path)
    p.add_argument('--output', type=Path, required=True)
    return p


if __name__ == '__main__':
    simulate(parser().parse_args())
