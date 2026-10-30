"""Controlled same-GPU decode remeasurement. Replay energy is NOT additive.

Reuses the immutable Issue212 execution dependencies after checking all bytes.
The optional static/GQA path is restricted to batch-one, unpadded, single-token
decode. It is not a general-purpose attention implementation or serving engine.
"""
import argparse
import contextlib
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

DEPENDENCIES = {
    'meter.py': 'a976d6482edaf5a78002f04d0a370011adf1f08555ef076cc963e166b1229777',
    'instrument.py': 'a3a050171181ed91ad45d1f018334a1c395404aa87e27dc44aa0179b28b17e63',
    'run_decode.py': '94e29b382be6ae7b1f478bdf7f67c68eca2112598be03f64af956ae3afc6bd43',
}


def stable_temperature(states, tolerance=1):
    """Only a thermal screening rule, not an absolute accuracy guarantee."""
    values = [s['temperature_C'] for s in states[-5:]]
    return len(values) == 5 and max(values) - min(values) <= tolerance


def counter_result(e0, e1, t0, t1, count):
    if e1 <= e0 or t1 <= t0 or count <= 0:
        raise ValueError('invalid energy/time/count window')
    seconds = t1 - t0
    joules = (e1 - e0) / 1000
    return dict(iterations=count, wall_s=seconds, energy_J=joules,
                average_W=joules / seconds, energy_mJ_per_item=joules * 1000 / count,
                wall_ms_per_item=seconds * 1000 / count,
                energy_read_start_mJ=e0, energy_read_end_mJ=e1)


def load_dependencies(folder):
    for name, expected in DEPENDENCIES.items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected, name
    sys.path.insert(0, str(folder))
    global torch, q3, F, StaticCache, DynamicCache, Instrument, Nvml, summarize
    global verify, digest, tensor_hash, build_prefix, one, graph_callable, exclusive
    import torch
    import torch.nn.functional as F
    from transformers.models.qwen3 import modeling_qwen3 as q3
    from transformers.cache_utils import StaticCache, DynamicCache
    from instrument import Instrument
    from meter import Nvml, summarize
    from run_decode import verify, digest, tensor_hash, build_prefix, one, graph_callable, exclusive


def emit(value):
    print(json.dumps(value), flush=True)


def save(path, value):
    with path.open('x', encoding='utf-8') as out:
        json.dump(value, out, indent=2, allow_nan=False)
        out.write('\n')


def warm_stable(fn, meter, minimum=8., maximum=25.):
    started = time.perf_counter()
    states = []
    while True:
        sample_at = time.perf_counter() + 1.
        while time.perf_counter() < sample_at:
            for _ in range(16):
                result = fn()
            torch.cuda.synchronize()
        state = meter.state()
        state['elapsed_s'] = time.perf_counter() - started
        states.append(state)
        if state['elapsed_s'] >= minimum and stable_temperature(states):
            break
        if state['elapsed_s'] >= maximum:
            break
    return dict(seconds=time.perf_counter() - started, states=states,
                stable_temperature_screen_pass=stable_temperature(states),
                criterion='last five ~1s temperature samples span <=1C; clocks recorded, not locked')


def measure_window(fn, meter, seconds, repeat, telemetry=False):
    # Time-bounded batches remove the old 100,000-call cap on tiny operators.
    for _ in range(8):
        result = fn()
    torch.cuda.synchronize()
    start = time.perf_counter()
    for _ in range(32):
        result = fn()
    torch.cuda.synchronize()
    per_call = (time.perf_counter() - start) / 32
    batch = max(1, min(8192, math.ceil(.2 / max(per_call, 1e-7))))
    sampler = None
    if telemetry:
        from meter import PowerSampler
        sampler = PowerSampler(meter, interval=.05).start()
    before = meter.state()
    begin = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    e0 = meter.energy_mJ()
    t0 = time.perf_counter()
    begin.record()
    count = 0
    while time.perf_counter() - t0 < seconds:
        for _ in range(batch):
            result = fn()
        torch.cuda.synchronize()
        count += batch
    end.record()
    torch.cuda.synchronize()
    t1 = time.perf_counter()
    e1 = meter.energy_mJ()
    row = counter_result(e0, e1, t0, t1, count)
    row.update(repeat=repeat, gpu_ms=begin.elapsed_time(end),
               gpu_ms_per_item=begin.elapsed_time(end) / count,
               state_before=before, state_after=meter.state(),
               requested_window_s=seconds, synchronization_batch=batch,
               window_suitable=row['wall_s'] >= seconds)
    if sampler:
        from meter import integrate
        sampler.finish()
        assert not sampler.errors, sampler.errors
        integrated = integrate(sampler.samples, t0, t1)
        row.update(power_integral_J=integrated,
                   power_integral_relative_difference=(integrated / row['energy_J'] - 1),
                   power_samples=[[t-t0, p] for t, p in sampler.samples],
                   telemetry_note='same NVML sensor family; internal consistency, not external accuracy')
    emit(dict(event='window', **{k: row[k] for k in
                               ['repeat', 'wall_s', 'average_W', 'wall_ms_per_item', 'energy_mJ_per_item']}))
    return row


def series(fn, meter, seconds, repeats, warm_min, warm_max, telemetry=False):
    thermal = warm_stable(fn, meter, warm_min, warm_max)
    rows = [measure_window(fn, meter, seconds, i, telemetry=telemetry and i == 0)
            for i in range(repeats)]
    return dict(thermal=thermal, repeats=rows, summary=summarize(rows),
                method='NVML cumulative-energy difference; CUDA synchronized time-bounded batches')


class StaticGQA:
    """No K/V head expansion and no copying of the entire old KV prefix.

    The mask is unnecessary ONLY because exactly one unpadded token queries
    the already-written prefix. Slice to valid_length; never attend unused slots.
    Flash backend is forced, so a silent math fallback cannot inflate the result.
    """
    def __init__(self, model, legacy, total_length, native_gqa=False):
        self.model = model
        self.valid_length = total_length
        self.native_gqa = native_gqa
        self.cache = StaticCache(config=model.config, max_batch_size=1,
                                 max_cache_len=total_length, device='cuda', dtype=torch.bfloat16)
        positions = torch.arange(legacy[0][0].shape[-2], device='cuda')
        for idx, (key, value) in enumerate(legacy):
            self.cache.update(key, value, idx, {'cache_position': positions})
        self.position = torch.tensor([total_length - 1], device='cuda')

    def __enter__(self):
        registry = q3.ALL_ATTENTION_FUNCTIONS
        self.old_attention = registry['sdpa']
        self.old_mask = self.model.model._update_causal_mask
        owner = self

        def attention(module, query, key, value, attention_mask, dropout=0., scaling=None, **kwargs):
            assert query.shape[0] == 1 and query.shape[-2] == 1
            assert attention_mask is None and dropout == 0. and not module.training
            key = key[:, :, :owner.valid_length, :]
            value = value[:, :, :owner.valid_length, :]
            if not owner.native_gqa:
                return owner.old_attention(module, query, key, value, None,
                                            dropout=dropout, scaling=scaling, **kwargs)
            from torch.nn.attention import SDPBackend, sdpa_kernel
            with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                output = F.scaled_dot_product_attention(query, key, value,
                    attn_mask=None, dropout_p=0., is_causal=False,
                    scale=scaling, enable_gqa=True)
            return output.transpose(1, 2).contiguous(), None

        def mask(model, attention_mask, input_tensor, cache_position, past_key_values, output_attentions=False):
            assert input_tensor.shape[:2] == (1, 1)
            assert attention_mask is None and not output_attentions
            assert past_key_values is owner.cache
            return None

        if isinstance(registry, dict):
            registry['sdpa'] = attention
        else:
            registry.register('sdpa', attention)
        self.model.model._update_causal_mask = types.MethodType(mask, self.model.model)
        return self

    def __exit__(self, *args):
        registry = q3.ALL_ATTENTION_FUNCTIONS
        if isinstance(registry, dict):
            registry['sdpa'] = self.old_attention
        else:
            registry.register('sdpa', self.old_attention)
        self.model.model._update_causal_mask = self.old_mask

    def run(self, token):
        return self.model(input_ids=token, past_key_values=self.cache, use_cache=True,
                          cache_position=self.position, position_ids=self.position.unsqueeze(0),
                          return_dict=True, logits_to_keep=1)


@contextlib.contextmanager
def instrumented(model, capture=False, annotations=False):
    old = StaticCache.update
    with Instrument(model, capture=capture, annotations=annotations) as inst:
        def update(cache, key, value, idx, cache_kwargs=None):
            return inst.call('KV_append', str(idx)+'.static_index_copy', old,
                             cache, key, value, idx, cache_kwargs)
        StaticCache.update = update
        try:
            yield inst
        finally:
            StaticCache.update = old


def numerical_guard(reference, candidate):
    r, c = reference.float(), candidate.float()
    rel = ((r-c).norm() / r.norm()).item()
    top1 = bool(torch.equal(r.argmax(-1), c.argmax(-1)))
    result = dict(bitwise_equal=bool(torch.equal(reference, candidate)),
                  relative_L2=rel, max_abs=(r-c).abs().max().item(), top1_equal=top1,
                  threshold='relative_L2 <=0.01 and same top1; different BF16 reduction order allowed')
    assert rel <= .01 and top1, result
    return result


def profile(model, fn, reference, folder, steps=5):
    with instrumented(model, annotations=True):
        with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,
             torch.profiler.ProfilerActivity.CUDA]) as prof:
            for _ in range(steps):
                out = fn()
            torch.cuda.synchronize()
    assert torch.equal(out.logits, reference)
    prof.export_chrome_trace(str(folder / 'TRACE.json'))
    rows = []
    for event in prof.key_averages():
        if event.key.startswith('gpu212::') and str(event.device_type).endswith('CPU'):
            rows.append(dict(category=event.key.split('::')[1], calls=event.count,
                        GPU_kernel_ms_per_decode=event.device_time_total / 1000 / steps,
                        CPU_range_ms_per_decode=event.cpu_time_total / 1000 / steps))
    assert len(rows) == 14 and len({r['category'] for r in rows}) == 14
    expected = {'QKV_projection':108, 'Attention_core':36, 'KV_append':36,
                'FFN_gate_up':72, 'FFN_down':36, 'FFN_SwiGLU':72, 'Residual_add':72}
    for row in rows:
        if row['category'] in expected:
            assert row['calls'] == expected[row['category']] * steps, row
    kernels = [e.name for e in prof.events() if str(e.device_type).endswith('CUDA')]
    return dict(rows=rows, steps=steps, all_36_layers_covered=True,
                CUDA_kernel_count=len(kernels), CUDA_kernel_names=sorted(set(kernels)),
                FlashAttention_observed=any('flash' in name.lower() for name in kernels),
                meaning='CPU annotations linked kernel totals; not CUDA annotation span or wall time')


def native_greedy(model, legacy, token, meter, context, steps, repeats):
    rows = []
    for repeat in range(repeats):
        cache = DynamicCache.from_legacy_cache(legacy)
        next_id = token.clone()
        generated = []
        torch.cuda.synchronize()
        before = meter.state()
        e0 = meter.energy_mJ()
        t0 = time.perf_counter()
        for _ in range(steps):
            out = model(input_ids=next_id, past_key_values=cache, use_cache=True,
                        return_dict=True, logits_to_keep=1)
            next_id = out.logits[:, -1].argmax(-1, keepdim=True)
            generated.append(next_id)
        torch.cuda.synchronize()
        t1 = time.perf_counter()
        e1 = meter.energy_mJ()
        row = counter_result(e0, e1, t0, t1, steps)
        row.update(repeat=repeat, state_before=before, state_after=meter.state(),
                   KV_length_first=context, KV_length_last=context+steps-1,
                   generated_ids_sha256=tensor_hash(torch.cat(generated, -1)),
                   boundary='autoregressive argmax included; prefill and token transfer excluded; no EOS stop')
        rows.append(row)
        emit(dict(event='native_greedy', context=context, repeat=repeat,
                  ms_per_token=row['wall_ms_per_item'], J_per_token=row['energy_mJ_per_item']/1000))
        del cache, generated, out
    assert len({r['generated_ids_sha256'] for r in rows}) == 1
    return dict(repeats=rows, summary=summarize(rows), deterministic_generated_ids=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--executed-code', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--contexts', type=int, nargs='+', default=[2048, 8192])
    p.add_argument('--smoke', action='store_true')
    a = p.parse_args()
    load_dependencies(a.executed_code)
    from transformers import AutoModelForCausalLM, AutoTokenizer, __version__ as tf_version
    assert 'SLURM_JOB_ID' in os.environ and torch.cuda.device_count() == 1
    assert not a.output.exists()
    a.output.mkdir(parents=True)
    prepared, model_path = verify(a.prepared)
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    ids = torch.tensor(tokenizer(Path(prepared['data']['wiki.test.raw']['path']).read_text(encoding='utf-8'),
                      add_special_tokens=False).input_ids, dtype=torch.long)
    assert tensor_hash(ids) == prepared['test_token_ids_sha256_le_int64']
    props = torch.cuda.get_device_properties(0)
    uuid = str(props.uuid)
    if not uuid.startswith('GPU-'):
        uuid = 'GPU-' + uuid
    exclusive(uuid)
    meter = Nvml(uuid)
    model = AutoModelForCausalLM.from_pretrained(str(model_path), torch_dtype=torch.bfloat16,
                    attn_implementation='sdpa', local_files_only=True).eval().to('cuda')
    env = dict(status='running', job=os.environ['SLURM_JOB_ID'],
               model_id=prepared['model']['id'], revision=prepared['revision'],
               prepared_sha256=digest(a.prepared), dependency_sha256=DEPENDENCIES,
               source_sha256=digest(Path(__file__)), torch=torch.__version__, transformers=tf_version,
               gpu=props.name, uuid_sha256=hashlib.sha256(uuid.encode()).hexdigest(),
               input_sha256=tensor_hash(ids), model_files_sha256={f['name']: f['sha256'] for f in prepared['files']},
               batch=1, weight_dtype='BF16', no_quantization=True, chat_template=False,
               prefill_excluded=True, contexts=a.contexts, smoke=a.smoke,
               isolation=[line for line in subprocess.check_output(['nvidia-smi', '--query-gpu=uuid,name,driver_version,power.limit,clocks.max.sm,temperature.gpu',
                      '--format=csv,noheader,nounits'], text=True).splitlines() if line.startswith(uuid)],
               notes=['No GPU clock/power-limit changes.', 'Module replay changes cache/order and is not additive.',
                      'Fixed CUDA Graph forward is not continuous generation.',
                      'Thermal pass/failure is recorded, never silently filtered.',
                      'Static KV uses unchanged original SDPA helper, retaining head replication.',
                      'Native GQA exploratory gate failed at 8K (1.42698% logit relative L2); excluded from formal baseline.'])
    save(a.output / 'ENVIRONMENT.json', env)
    for context in a.contexts:
        exclusive(uuid)
        folder = a.output / str(context)
        folder.mkdir()
        legacy, token, prefill_s = build_prefix(model, ids[:context-1].unsqueeze(0).to('cuda'))
        original = lambda: one(model, legacy, token)
        reference = original().logits.clone()
        emit(dict(event='context_start', context=context))
        save(folder/'INPUT.json', dict(context=context, prefix_token_sha256=tensor_hash(ids[:context-1]),
            first_decode_token_sha256=tensor_hash(token), prefill_wall_s_excluded=prefill_s))
        # Run both contexts through numerical/capture gates before any formal submission.
        optimized = StaticGQA(model, legacy, context)
        with optimized:
            work = lambda: optimized.run(token)
            guard = numerical_guard(reference, work().logits)
            assert guard['bitwise_equal'], 'static-KV-only optimization must preserve logits exactly'
            graph, output = graph_callable(work)
            assert torch.equal(output.logits, work().logits)
            with instrumented(model, capture=True) as captured:
                captured_out = work()
            assert torch.equal(captured_out.logits, output.logits)
            inventory = captured.inventory()
            assert inventory['QKV_projection']['calls_per_decode'] == 108
            save(folder/'NUMERICAL_GUARD.json', guard)
            save(folder/'INVENTORY_STATIC_GQA.json', inventory)
            emit(dict(event='optimized_guard_passed', context=context, guard=guard))
            if not a.smoke:
                idle = series(lambda: time.sleep(.05), meter, 10., 3, 8., 25., telemetry=True)
                idle['scope'] = 'resident-model idle board floor, diagnostic only; active clocks differ'
                save(folder/'IDLE_LOADED_MODEL.json', idle)
                result = series(graph.replay, meter, 10., 3, 15., 60., telemetry=True)
                result['scope'] = 'static KV/original SDPA fixed-forward CUDA Graph; no argmax or growing KV'
                save(folder/'WHOLE_STATIC_KV_GRAPH.json', result)
                time_rows = profile(model, work, output.logits, folder)
                save(folder/'PROFILE_STATIC_GQA.json', time_rows)
                # Small operators have >=5s windows too. No old iteration cap.
                for category in captured.calls:
                    emit(dict(event='module_start', context=context, category=category))
                    replay = lambda c=category: captured.replay(c)
                    mg, mo = graph_callable(replay)
                    result = series(mg.replay, meter, 5., 3, 8., 25.)
                    result['scope'] = 'isolated replay of every captured occurrence across 36 layers; NOT in-situ rail energy'
                    save(folder/('REPLAY_'+category+'.json'), result)
                    del mg, mo
            del graph, output, captured, captured_out, work
        del optimized
        gc.collect()
        torch.cuda.empty_cache()
        og, oo = graph_callable(original)
        assert torch.equal(reference, oo.logits)
        if not a.smoke:
            save(folder/'WHOLE_ORIGINAL_GRAPH.json', series(og.replay, meter, 10., 3, 15., 60., telemetry=True))
            save(folder/'WHOLE_ORIGINAL_EAGER.json', series(original, meter, 10., 3, 15., 60., telemetry=True))
            # This is the actual autoregressive reference, separate from fixed graphs.
            native = native_greedy(model, legacy, token, meter, context, 256, 3)
            save(folder/'NATIVE_GREEDY.json', native)
        del og, oo, original, legacy, token, reference
        gc.collect()
        torch.cuda.empty_cache()
        emit(dict(event='context_completed', context=context))
    exclusive(uuid)
    manifest = {str(f.relative_to(a.output)):dict(sha256=digest(f), bytes=f.stat().st_size)
                for f in a.output.rglob('*') if f.is_file()}
    save(a.output/'ARTIFACT_MANIFEST.json', manifest)
    save(a.output/'COMPLETED.json', dict(status='completed', job=os.environ['SLURM_JOB_ID'],
         manifest_sha256=digest(a.output/'ARTIFACT_MANIFEST.json'), contexts=a.contexts,
         source_sha256=digest(Path(__file__))))
    emit(dict(event='all_completed', contexts=a.contexts))


if __name__ == '__main__':
    # Restores inference-mode tensor semantics for captured/replayed native kernels.
    import torch as _torch
    with _torch.inference_mode():
        main()
