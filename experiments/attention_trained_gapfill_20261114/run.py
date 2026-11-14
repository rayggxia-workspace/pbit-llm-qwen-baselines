"""Slurm-only, immutable full-WT2 experiment. Every scored target is audited."""
import argparse
from dataclasses import asdict
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import unittest
import torch
from .methods import CASES, Patch, configuration
from experiments.sparq_ising_20261028.scoring import score
from experiments.sparq_ising_20261028.run import seal, read_sealed
from experiments.sparq_ising_20261028.vendor.support import sha256, verify_files, check_config
from experiments.sparq_ising_20261028.vendor.plans import full_window_plan, summarize_records, ids_sha256


def sampler_gate():
    from experiments.sparq_ising_20261028 import core
    from experiments.sparq_ising_20261028.vendor import kernels
    checked = []
    gen = torch.Generator(device='cuda').manual_seed(1981106)
    for n in (1, 64, 127, 128, 129, 256):
        for s in (16, 32, 64, 128):
            case = dict(name='gate', k=128 if n <= 128 else 256, samples=s, seed=0)
            z = torch.randn((2, n), device='cuda', generator=gen)*3+12
            words = torch.randint(256, (2, s, n), device='cuda', generator=gen)
            words[:, 0] = 255  # Explicit all-zero frame must retain initial slot0.
            raw = torch.full((2, s), 2**31, device='cuda', dtype=torch.int64)
            coin = torch.zeros((2, s), device='cuda')
            with Patch(case) as patch:
                p = patch.probabilities(z, 'winner')[:, 0]
                bits = words.float()/256 < p[:, None, :]
                ranks = raw % bits.sum(-1).clamp_min(1)
                expected = core.torch_winner_replay(bits, ranks,
                    torch.zeros(2, device='cuda', dtype=torch.long), 0)
                actual, stats = kernels.sample(z, s, 'winner', seed=0, burn=0,
                                               replay=(words.float()/256, raw, coin))
            assert torch.equal(expected, actual), (n, s)
            assert bool((actual[:, 0] == 0).all())
            assert bool((stats[:, 0] == s).all()) and bool((stats[:, 1] == s).all())
            checked.append(dict(n=n, samples=s, rows=2))
    return checked


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--phase', choices=['cpu', 'gate', 'reference', 'full'], required=True)
    p.add_argument('--index', type=int, default=0)
    a = p.parse_args()
    root = Path(a.root).resolve(strict=True)
    assert root.parent == Path.home()/'projects' and root.stat().st_uid == os.getuid()
    assert os.environ.get('SLURM_JOB_ID')
    source = Path(__file__).resolve().parents[2]
    manifest = json.loads((source/'execution.json').read_bytes())
    for rel, digest in manifest['files_sha256'].items():
        assert sha256(source/rel) == digest, rel
    config = json.loads((source/'experiments/sparq_ising_20261028/config.json').read_bytes())
    prep_path = Path(config['prepared'])
    prep = json.loads(prep_path.read_bytes())
    assert prep['model'] == config['model']
    verify_files(prep)
    for rel, digest in config['data_sha256'].items():
        assert sha256(Path(config['data_root'])/rel) == digest, rel
    assert importlib.metadata.version('transformers') == '4.51.3'
    torch.set_num_threads(2)
    torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(prep['local_path'], local_files_only=True, trust_remote_code=False)
    ids = tok((Path(config['data_root'])/'wiki.test.raw').read_bytes().decode('utf-8'),
              return_tensors='pt', add_special_tokens=False).input_ids[0]
    assert ids_sha256(ids.tolist()) == prep['test_token_ids_sha256_le_int64']
    plan = full_window_plan(len(ids), 2048, 1024)
    dest = root/'results'/manifest['commit'][:12]
    if a.phase == 'cpu':
        assert os.environ.get('CUDA_VISIBLE_DEVICES') == '' and not torch.cuda.is_initialized()
        suite = unittest.defaultTestLoader.loadTestsFromNames([
            'experiments.attention_trained_gapfill_20261114.test_sweep',
            'experiments.attention_gap_accuracy_20261102.test_methods',
            'experiments.sparq_ising_20261028.test_core'])
        tests = unittest.TextTestRunner(verbosity=2).run(suite)
        assert tests.wasSuccessful()
        seal(dest/'cpu.json', dict(passed=True, tests=tests.testsRun, cases=CASES,
             segments=len(plan), targets=len(ids)-1, plan=plan, original_ffn=True,
             prepared_sha256=sha256(prep_path), token_ids_sha256=ids_sha256(ids.tolist()),
             data_sha256=config['data_sha256']))
        return
    assert read_sealed(dest/'cpu.json')['passed']
    assert torch.cuda.device_count() == 1
    model = AutoModelForCausalLM.from_pretrained(prep['local_path'], local_files_only=True,
        trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda().eval()
    check_config(model.config, config['model'])
    immutable = [(v, v._version, v.data_ptr()) for v in model.parameters()]
    provenance = dict(source=manifest, model=config['model'], model_files=prep['files'],
        prepared_sha256=sha256(prep_path), data_sha256=config['data_sha256'],
        token_ids_sha256=ids_sha256(ids.tolist()), command=sys.argv,
        versions={n: importlib.metadata.version(n) for n in ('torch', 'transformers', 'triton')},
        job=os.environ['SLURM_JOB_ID'], gpu=torch.cuda.get_device_name(),
        original_ffn=True, original_projections=False, original_weights=False, posttrained=True, trained_overlay_candidates=['k_wh128'], hf_revision='9ab262b60915a2711caff2af2937e89aa67072ad',
        chat_template=False, BOS=False, training=False,
        protocol='full WT2, window2048/stride1024, native dense unscored prefix; every scored query patched',
        numeric='RNE/clamp signed12 F4 -> integer max-minus-score -> saturating U8 F4 -> frozen floor-P8',
        sampler='winner-hold, initial slot0, burn0, spacing1; independent Philox, not GF64/physical bittrue',
        rng_keys='seed:partStart / layer / call / Config; independent configurations, not nested S prefixes',
        screening='FP32 SparQ r32, k64/128/256 including recent32, 4Q shared candidate set; no mean-V',
        batch=32, chunk_windows=32, CPU_threads=2)

    from safetensors.torch import load_file
    weights_root=Path('/home/Hongjie_Zeng/projects/attention-trained-weights-20261106/9ab262b60915')
    receipt=json.loads((weights_root/'DOWNLOAD_RECEIPT.json').read_bytes())
    assert receipt['revision']=='9ab262b60915a2711caff2af2937e89aa67072ad'
    records={r['file']:r for r in receipt['files']}
    active=[None]
    baseline_immutable=immutable
    def execute(case, **options):
        overlay=case['overlay']
        if overlay!=active[0]:
            assert overlay is not None,'new model load required to restore parent'
            rel='models/'+overlay+'/projections.safetensors'
            row=records[rel];path=Path(row['path'])
            assert sha256(path)==row['sha256']
            weights=load_file(str(path),device='cpu')
            expected={f'model.layers.{i}.self_attn.{proj}.weight' for i in range(36) for proj in ('q_proj','k_proj','v_proj','o_proj')}
            assert set(weights)==expected and all(v.dtype==torch.bfloat16 for v in weights.values())
            params=dict(model.named_parameters())
            with torch.no_grad():
                for name,value in weights.items():
                    assert params[name].shape==value.shape
                    params[name].copy_(value)
            assert all(torch.equal(params[n].detach().cpu(),v) for n,v in weights.items())
            for name,value in model.named_parameters():
                if name not in expected:
                    old_value,version,pointer=next(t for t in baseline_immutable if t[0] is value)
                    assert value._version==version and value.data_ptr()==pointer
            del weights
            active[0]=overlay
        immutable=[(v,v._version,v.data_ptr()) for v in model.parameters()]
        torch.cuda.reset_peak_memory_stats()
        with Patch(case) as patch:
            result = score(model, ids, configuration(case), seed=case['seed'], **options)
            result['numeric'] = patch.report()
        assert all(v._version == ver and v.data_ptr() == ptr for v, ver, ptr in immutable)
        result.update(overlay=overlay, overlay_sha256=records['models/'+overlay+'/projections.safetensors']['sha256'] if overlay else None, case=case, effective_config=asdict(configuration(case)) if case['k'] else None,
                      peak_memory_bytes=torch.cuda.max_memory_allocated())
        # Original adapter's generic label is replaced with the effective numeric law.
        result['audit']['ideal_sigmoid_source'] = False if case['samples'] else None
        result['audit']['front_end'] = result['numeric']['numeric']
        return result

    if a.phase == 'gate':
        replay = sampler_gate()
        opt = dict(context=320, decode=3, examples=2, batch=2, capture=True)
        native = score(model, ids, None, native=True, **opt)
        wrapper = execute(CASES[0], **opt)
        assert native['logits_sha256'] == wrapper['logits_sha256']
        assert native['nll_sum'] == wrapper['nll_sum']
        probes = []
        for case in CASES[1:]:
            value = execute(case, **opt)
            probes.append(dict(case=case, ppl=value['perplexity'], seconds=value['seconds']))
        worst = next(c for c in CASES if c['k']==256 and c['samples']==128)
        memory = execute(worst, context=2048, decode=2, examples=32, batch=32)
        assert memory['peak_memory_bytes'] < 28*1024**3
        # Full WT2 starts with no prefill; exercise actual N=1 through all36 layers.
        from experiments.sparq_ising_20261028 import scoring
        original = scoring.full_window_plan
        try:
            scoring.full_window_plan = lambda *args: [dict(segment_id=0, begin=0, end=3,
                first_target=1, last_target_exclusive=3, prefill_tokens=0, scored_tokens=2)]
            cold = execute(worst, protocol='full', batch=1)
        finally:
            scoring.full_window_plan = original
        seal(dest/'gate.json', dict(passed=True, native_wrapper_bitwise=True, sampler_replay=replay,
             model_probes=probes, production_memory=memory['peak_memory_bytes'],
             cold_start_targets=cold['tokens_per_layer'], provenance=provenance))
        print('GATE_PASS', memory['peak_memory_bytes'], flush=True)
        return
    assert read_sealed(dest/'gate.json')['passed']
    index = 0 if a.phase == 'reference' else a.index
    assert 0 <= index < len(CASES)
    if a.phase == 'full':
        assert index > 0
        assert read_sealed(dest/'cases/00_bf16_seed0/complete.json')['status'] == 'completed'
        reference = read_sealed(dest/'cases/00_bf16_seed0/RESULT.json')
        assert abs(reference['perplexity'] - 11.538153433607206) < 1e-5, reference['perplexity']
    case = CASES[index]
    out = dest/'cases'/f"{index:02d}_{case['name']}_seed{case['seed']}"
    out.mkdir(parents=True, exist_ok=True)
    if not (out/'provenance.json').exists():
        seal(out/'provenance.json', dict(provenance, selected_case=case, original_projections=case['overlay'] is None, original_weights=case['overlay'] is None))
    started = time.perf_counter()
    for start in range(0, len(plan), 32):
        path = out/f'part_{start:04d}.json'
        if path.exists():
            read_sealed(path)
            continue
        print('PART_START', index, start, flush=True)
        value = execute(case, protocol='full', batch=32,
                        plan_slice=(start, min(start+32, len(plan))), rng_stream=start,
                        progress=lambda rows: print('WINDOW_PROGRESS', index, start,
                            len(rows), round(time.perf_counter()-started, 2), flush=True))
        seal(path, value)
        print('PART_DONE', index, start, value['perplexity'], value['seconds'], flush=True)
    parts = [read_sealed(out/f'part_{start:04d}.json') for start in range(0, len(plan), 32)]
    rows = [row for part in parts for row in part['records']]
    assert len(rows) == len(plan)
    assert all(all(row[k] == planned[k] for k in planned) for row, planned in zip(rows, plan))
    assert sum(r['scored_tokens'] for r in rows) == len(ids)-1
    assert [sum(p['tokens_per_layer'][i] for p in parts) for i in range(36)] == [len(ids)-1]*36
    if case['samples']:
        for part in parts:
            assert all(layer['sampled_head_rows'] == part['scored_tokens']*32
                       for layer in part['audit']['layers'].values())
    seal(out/'RESULT.json', dict(**summarize_records(rows), records=rows, case=case,
         scope='full_WT2_2048_1024', complete=True, original_ffn=True,
         seconds=sum(p['seconds'] for p in parts),
         token_ids_sha256=ids_sha256(ids.tolist()), provenance_sha256=sha256(out/'provenance.json'),
         targets_per_layer=[len(ids)-1]*36,
         parts_sha256={p.name: sha256(p) for p in out.glob('part_*.json')}))
    if a.phase == 'reference':
        assert abs(read_sealed(out/'RESULT.json')['perplexity'] - 11.538153433607206) < 1e-5
    seal(out/'complete.json', dict(status='completed', result_sha256=sha256(out/'RESULT.json')))
    print('FULL_COMPLETE', case, read_sealed(out/'RESULT.json')['perplexity'], flush=True)


if __name__ == '__main__':
    main()
