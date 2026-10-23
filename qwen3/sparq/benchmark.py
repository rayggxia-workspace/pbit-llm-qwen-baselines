"""Real-model paired CUDA benchmark, with optional UUID-bound board telemetry.

Call run_benchmark(model, fixed_token_ids, config=...) inside an existing GPU
allocation. This module neither loads models nor allocates scheduler resources.
CPU-only helper tests: python -m qwen3.sparq.benchmark --self-test

CUDA events follow https://docs.pytorch.org/docs/stable/generated/torch.cuda.Event.html
NVML semantics: https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html
NVML is optional (nvidia-ml-py/pynvml). No driver, clock, power-limit or process
configuration is changed. Sampled board power is not process-exclusive energy.
"""
from contextlib import nullcontext
from dataclasses import asdict, is_dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import struct
import threading
import time

import torch


_POWER_SCOPE = "GPU board telemetry estimate; includes idle/other work; no idle subtraction"
_SENSOR_SEMANTICS = "NVML GetPowerUsage: 1s average on Ampere except GA100 and newer; instantaneous on older/GA100"


def _uuid_key(value):
    if isinstance(value, bytes):
        value = value.decode("ascii")
    value = str(value).lower()
    if value.startswith("gpu-"):
        value = value[4:]
    return value if re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value) else None


def _max_sample_gap(samples, start, end):
    # Include full bracketing intervals: clipping a long missing-data interval
    # to the phase boundary must not make that gap appear well sampled.
    return max((right[0] - left[0] for left, right in zip(samples, samples[1:])
                if right[0] > start and left[0] < end), default=None)


def _integrate_power(samples, start, end, *, max_gap_s=None):
    """Trapezoidal integration clipped/interpolated at measured wall boundaries."""
    if (end <= start or len(samples) < 3 or samples[0][0] > start
            or samples[-1][0] < end or not any(start < t < end for t, _ in samples)):
        raise ValueError("insufficient samples bracketing and inside timing window")
    if max_gap_s is not None:
        if not math.isfinite(max_gap_s) or max_gap_s <= 0:
            raise ValueError("max_gap_s must be finite and positive")
        observed_gap = _max_sample_gap(samples, start, end)
        if observed_gap is None or observed_gap > max_gap_s:
            raise ValueError(f"power sample gap {observed_gap}s exceeds allowed {max_gap_s}s")
    energy = 0.0
    for (t0, p0), (t1, p1) in zip(samples, samples[1:]):
        if t1 <= t0 or not all(math.isfinite(x) for x in (t0, t1, p0, p1)) or min(p0, p1) < 0:
            raise ValueError("invalid/nonmonotonic power sample")
        a, b = max(t0, start), min(t1, end)
        if b > a:
            pa = p0 + (p1 - p0) * (a - t0) / (t1 - t0)
            pb = p0 + (p1 - p0) * (b - t0) / (t1 - t0)
            energy += .5 * (pa + pb) * (b - a)
    return energy


class _PowerWindow:
    def __init__(self, reader, interval):
        self.reader, self.interval = reader, interval
        self.samples, self.error, self.thread = [], None, None
        self.stop_event = threading.Event()

    def _sample(self):
        try:
            # Timestamp midway across the NVML read; the sensor's own averaging
            # period is hardware-dependent and is NOT inferred from polling rate.
            before = time.perf_counter()
            watts = float(self.reader()) / 1000.0
            after = time.perf_counter()
            if not math.isfinite(watts) or watts < 0:
                raise ValueError("invalid power reading")
            self.samples.append(((before + after) / 2, watts))
        except Exception as error:
            self.error = f"{type(error).__name__}: {error}"
            self.stop_event.set()

    def start(self):
        if self.reader is None:
            return
        self._sample()
        if self.error:
            return
        def poll():
            while not self.stop_event.wait(self.interval):
                self._sample()
        self.thread = threading.Thread(target=poll, name="sparq-nvml-power", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        if self.reader is not None and self.error is None:
            self._sample()

    def report(self, start, end, unavailable_reason):
        reason = unavailable_reason or self.error
        samples = [[t - start, p] for t, p in self.samples]
        observed_gap = _max_sample_gap(self.samples, start, end)
        allowed_gap = max(.25, 5 * self.interval)
        if not reason and end - start < 1.0:
            reason = "phase shorter than conservative 1s NVML averaging bound; raw samples retained"
        if not reason:
            try:
                joules = _integrate_power(self.samples, start, end, max_gap_s=allowed_gap)
            except ValueError as error:
                reason = str(error)
        return dict(power=None if reason else dict(
                        sampled_board_energy_j=joules, average_board_power_w=joules / (end - start)),
                    power_unavailable_reason=reason, power_samples_relative_s_w=samples,
                    power_scope=_POWER_SCOPE,
                    power_poll_interval_s=self.interval,
                    max_sample_gap_s=observed_gap, max_allowed_sample_gap_s=allowed_gap,
                    sensor_update_period_s=None,
                    sensor_semantics=_SENSOR_SEMANTICS,
                    phase_energy_attribution_validated=False)


class _NvmlSession:
    def __init__(self, device_uuid, requested_uuid):
        self.module, self.reader = None, None
        self.reason, self.uuid = "power_gpu_uuid not explicitly supplied", None
        if requested_uuid is None:
            return
        expected, actual = _uuid_key(requested_uuid), _uuid_key(device_uuid)
        if (not isinstance(requested_uuid, str) or expected is None or actual is None or expected != actual):
            self.reason = "requested GPU UUID does not match torch model device UUID; no index fallback"
            return
        # Torch exposes a bare UUID on some versions. Normalize only a fully
        # validated GPU UUID; numeric ordinals/MIG IDs still fail the check above.
        canonical_uuid = "GPU-" + expected
        try:
            import pynvml
            pynvml.nvmlInit()
            self.module = pynvml
            handle = pynvml.nvmlDeviceGetHandleByUUID(canonical_uuid.encode("ascii"))
            observed = pynvml.nvmlDeviceGetUUID(handle)
            if _uuid_key(observed) != actual:
                raise ValueError("NVML handle UUID differs from allocated torch device")
            self.reader = lambda: pynvml.nvmlDeviceGetPowerUsage(handle)
            self.uuid, self.reason = canonical_uuid, None
        except Exception as error:
            self.reason = f"NVML unavailable: {type(error).__name__}: {error}"
            self.close()

    def close(self):
        if self.module is not None:
            try:
                self.module.nvmlShutdown()
            except Exception as error:
                detail = f"NVML shutdown failed: {type(error).__name__}: {error}"
                self.reason = f"{self.reason}; {detail}" if self.reason else detail
            finally:
                self.module, self.reader = None, None


def _snapshot(model):
    # Detect replacement/in-place updates, not a full checkpoint byte hash.
    return ({name: (id(p), p.data_ptr(), p._version, tuple(p.shape), str(p.dtype), str(p.device))
             for name, p in model.named_parameters()},
            tuple((id(layer.mlp), getattr(layer.mlp.forward, "__func__", layer.mlp.forward))
                  for layer in model.model.layers))


def _check_model(model):
    devices = {p.device for p in model.parameters()} | {b.device for b in model.buffers()}
    if len(devices) != 1 or next(iter(devices)).type != "cuda":
        # This guard is before any CUDA API: CPU inputs must not initialize CUDA.
        raise ValueError("benchmark requires a model on one already allocated CUDA device")
    device = next(iter(devices))
    layers = list(model.model.layers)
    if (type(model).__name__ != "Qwen3ForCausalLM" or model.config.model_type != "qwen3"
            or model.config._attn_implementation != "sdpa" or not layers
            or len(layers) != model.config.num_hidden_layers
            or any(module.training for module in model.modules())
            or any(type(layer.mlp).__name__ != "Qwen3MLP" for layer in layers)
            or any(hasattr(layer.self_attn, flag) for layer in layers
                   for flag in ("_sparq_owner", "_joint_attention_owner"))):
        raise ValueError("fresh eval Qwen3ForCausalLM/SDPA with all original FFNs required")
    for layer in layers:
        forward = getattr(layer.mlp.forward, "__func__", layer.mlp.forward)
        if forward.__module__ != "transformers.models.qwen3.modeling_qwen3":
            raise ValueError("FFN forward was patched")
    return device


def _measure(fn, device, telemetry, interval):
    torch.cuda.synchronize(device)
    first, last = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    window = _PowerWindow(telemetry.reader, interval)
    start = end = None
    try:
        window.start()
        start = time.perf_counter()
        first.record()
        value = fn()
        last.record()
        last.synchronize()
        end = time.perf_counter()
        cuda_ms = first.elapsed_time(last)
    finally:
        # Stop/join sampler even when model execution or synchronization fails.
        window.stop()
    return value, dict(wall_seconds=end-start, cuda_event_seconds=cuda_ms/1000,
                       **window.report(start, end, telemetry.reason))


def _trial(model, tokens, context, decode, mode, config, device, telemetry, interval, timed):
    from .adapter import SparQController
    controller, cache, output, logits = None, None, None, None
    before = _snapshot(model)
    try:
        if mode != "native":
            controller = SparQController(mode, config)
            controller.install(model)

        def prefill():
            scope = controller.prefill() if controller else nullcontext()
            with scope:
                out = model.model(input_ids=tokens[:, :context], use_cache=True, return_dict=True)
            last_logits = model.lm_head(out.last_hidden_state[:, -1])
            return out.past_key_values, last_logits

        def decoding():
            nonlocal cache, output, logits
            for step in range(decode):
                output = model.model(input_ids=tokens[:, context+step:context+step+1],
                                     past_key_values=cache, use_cache=True, return_dict=True)
                cache = output.past_key_values
                logits = model.lm_head(output.last_hidden_state[:, -1])
            return logits

        if timed:
            (cache, logits), prefill_result = _measure(prefill, device, telemetry, interval)
            logits, decode_result = _measure(decoding, device, telemetry, interval)
        else:
            cache, logits = prefill()
            logits = decoding()
            torch.cuda.synchronize(device)
        if not bool(torch.isfinite(logits).all()):
            raise RuntimeError("nonfinite last decode logits")
        if not timed:
            return None
        b = tokens.shape[0]
        for phase, count in ((prefill_result, context), (decode_result, decode)):
            phase["input_tokens"] = b * count
            phase["tokens_per_wall_second"] = b * count / phase["wall_seconds"]
        decode_result["wall_seconds_per_decode_step"] = decode_result["wall_seconds"] / decode
        return dict(prefill=prefill_result, decode=decode_result,
                    controller=controller.stats() if controller else None,
                    last_decode_logits_finite=True)
    finally:
        try:
            if controller is not None:
                controller.close()
        finally:
            cache, output, logits = None, None, None
            if before != _snapshot(model):
                raise RuntimeError("model parameters or original FFNs changed during benchmark")


def run_benchmark(model, token_ids, *, config=None, contexts=(128, 512, 2048),
                  decode_lengths=(64, 128), modes=("native", "dense", "sparq"),
                  warmup=1, repeats=3, power_gpu_uuid=None, power_interval_s=.02,
                  model_provenance=None, progress=None):
    """Benchmark the SAME model and fixed teacher-forced input IDs, original FFN.

    token_ids: CPU or model-device int64 [L] / [B,L], no padding. Every case
    consumes its first context+decode IDs. Prefill consumes `context` tokens;
    decode consumes the NEXT `decode` fixed tokens (not generated argmax tokens).
    First/last decode cache lengths are context+1 / context+decode.
    Full backbone plus last-position LM head runs in BOTH measured phases.

    Power is enabled only for an explicit GPU UUID matching this torch device's
    own UUID. Bare UUIDs are normalized to GPU-UUID after validation. No CUDA
    ordinal -> physical NVML index conversion is used; MIG IDs remain rejected.
    This function assumes the caller has a valid scheduler GPU allocation; it
    does not infer ownership from device visibility or submit any job.
    """
    device = _check_model(model)
    from .core import SparQConfig
    if config is None:
        config = SparQConfig()
    elif isinstance(config, dict):
        config = SparQConfig(**config)
    elif not isinstance(config, SparQConfig):
        raise ValueError("config must be SparQConfig or its field dictionary")
    contexts, decode_lengths, modes = tuple(contexts), tuple(decode_lengths), tuple(modes)
    if (not contexts or not decode_lengths or not modes
            or any(type(x) is not int or x < 1 for x in (*contexts, *decode_lengths, warmup, repeats))
            or len(set(modes)) != len(modes) or set(modes) - {"native", "dense", "sparq"}
            or not math.isfinite(power_interval_s) or power_interval_s < .01):
        raise ValueError("positive dimensions/warmup/repeats, unique known modes, polling >=10ms required")
    if token_ids.ndim == 1:
        token_ids = token_ids.unsqueeze(0)
    if (token_ids.ndim != 2 or token_ids.dtype != torch.long or token_ids.shape[0] < 1
            or token_ids.shape[1] < max(contexts) + max(decode_lengths)):
        raise ValueError("enough fixed unpadded int64 [B,L] tokens required")
    ids = token_ids.detach().cpu().contiguous()
    if int(ids.min()) < 0 or int(ids.max()) >= model.config.vocab_size:
        raise ValueError("token outside vocabulary")
    if model_provenance is not None:
        json.dumps(model_provenance, allow_nan=False)
    digest = hashlib.sha256(struct.pack("<QQ", *ids.shape) + ids.numpy().astype("<i8", copy=False).tobytes()).hexdigest()
    tokens = ids.to(device)
    rows, order = [], []
    properties = torch.cuda.get_device_properties(device)
    device_uuid = getattr(properties, "uuid", None)
    telemetry = _NvmlSession(device_uuid, power_gpu_uuid)
    try:
        with torch.cuda.device(device), torch.inference_mode():
            for context in contexts:
                for decode in decode_lengths:
                    for mode in modes:
                        for _ in range(warmup):
                            _trial(model, tokens, context, decode, mode, config, device, telemetry, power_interval_s, False)
                    for repeat in range(repeats):
                        # Deterministic rotation reduces fixed mode-order drift;
                        # identical teacher-forced tokens/cache lengths remain paired.
                        rotation = repeat % len(modes)
                        for mode in modes[rotation:] + modes[:rotation]:
                            row = _trial(model, tokens, context, decode, mode, config, device, telemetry, power_interval_s, True)
                            row.update(context_tokens=context, decode_steps=decode, mode=mode, repeat=repeat,
                                       batch=ids.shape[0], first_decode_cache_tokens=context+1,
                                       last_decode_cache_tokens=context+decode)
                            rows.append(row)
                            order.append([context, decode, repeat, mode])
                            if progress is not None:
                                progress(dict(kind="benchmark_trial", completed=len(rows),
                                              total=len(contexts)*len(decode_lengths)*repeats*len(modes), record=row))
    finally:
        telemetry.close()
    summaries = []
    for context in contexts:
        for decode in decode_lengths:
            for mode in modes:
                selected = [r for r in rows if (r["context_tokens"], r["decode_steps"], r["mode"]) == (context, decode, mode)]
                summary = dict(context_tokens=context, decode_steps=decode, mode=mode)
                for phase in ("prefill", "decode"):
                    summary[phase] = {key: statistics.median(r[phase][key] for r in selected)
                                      for key in ("wall_seconds", "cuda_event_seconds", "tokens_per_wall_second")}
                    powers = [r[phase]["power"] for r in selected]
                    summary[phase]["power"] = ({key: statistics.median(p[key] for p in powers)
                                                 for key in ("sampled_board_energy_j", "average_board_power_w")}
                                                if all(p is not None for p in powers) else None)
                    gaps = [r[phase]["max_sample_gap_s"] for r in selected
                            if r[phase]["max_sample_gap_s"] is not None]
                    summary[phase].update(power_scope=_POWER_SCOPE,
                        sensor_semantics=_SENSOR_SEMANTICS, sensor_update_period_s=None,
                        phase_energy_attribution_validated=False,
                        max_sample_gap_s=max(gaps, default=None),
                        max_allowed_sample_gap_s=max(.25, 5 * power_interval_s),
                        power_unavailable_reasons=sorted({r[phase]["power_unavailable_reason"]
                            for r in selected if r[phase]["power_unavailable_reason"] is not None}))
                summaries.append(summary)
    source = {"qwen3/sparq/" + name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
              for name in ("benchmark.py", "adapter.py", "core.py") if Path(__file__).with_name(name).is_file()}
    result = dict(test="qwen3_sparq_real_model_reference_benchmark", schema=1,
        model_provenance=model_provenance, model_name=getattr(model.config, "_name_or_path", None),
        model_config_commit=getattr(model.config, "_commit_hash", None),
        torch_version=torch.__version__, model_device=str(device), gpu_name=properties.name,
        torch_device_uuid=str(device_uuid) if device_uuid is not None else None,
        nvml_requested_uuid=str(power_gpu_uuid) if power_gpu_uuid is not None else None,
        nvml_gpu_uuid=telemetry.uuid, nvml_unavailable_reason=telemetry.reason,
        parameter_dtypes=sorted({str(p.dtype) for p in model.parameters()}),
        attention_config=asdict(config) if is_dataclass(config) else config,
        token_ids_shape=list(ids.shape), token_ids_shape_and_le_int64_sha256=digest,
        contexts=list(contexts), decode_lengths=list(decode_lengths), modes=list(modes),
        warmup_trials_per_case_mode=warmup, measured_repeats=repeats, execution_order=order,
        scope="same real Qwen3 model; original FFN; native prefill; full backbone plus last-position LM head",
        input_protocol="fixed teacher-forced tokens, no sampling/argmax or tokenization inside timing",
        timing_protocol="sync before phase; CUDA events on current model-device stream; event sync before wall stop",
        telemetry_timing="first/last NVML reads outside timed window; polling-thread overhead inside when enabled",
        diagnostics_overhead_included=True, original_ffn_guard_passed=True,
        speed_claim="actual PyTorch reference timings only; not optimized sparse-kernel performance",
        physical_PPA=None, source_files_sha256=source, trials=rows, summaries=summaries)
    json.dumps(result, allow_nan=False)
    return result


def _self_test():
    import sys
    from types import SimpleNamespace
    import unittest
    from unittest.mock import Mock, patch

    class Helpers(unittest.TestCase):
        def test_uuid_fail_closed(self):
            uid = "GPU-12345678-1234-1234-1234-123456789abc"
            self.assertEqual(_uuid_key(uid.encode()), _uuid_key(uid[4:]))
            self.assertIsNone(_uuid_key("MIG-" + uid))
            self.assertIsNone(_uuid_key("0"))
            session = _NvmlSession(uid, "GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
            self.assertIsNone(session.reader)
            self.assertIn("does not match", session.reason)

        def test_power_clipping_and_linear_interpolation(self):
            self.assertAlmostEqual(_integrate_power([(0, 10), (1, 20), (2, 30)], .5, 1.5), 20)
            with self.assertRaises(ValueError):
                _integrate_power([(0, 10), (2, 30)], .5, 1.5)
            with self.assertRaises(ValueError):
                _integrate_power([(0, 10), (1, 20), (2, 30)], -.5, 1.5)

        def test_short_phase_power_is_null(self):
            sample = _PowerWindow(lambda: 20000, .02)
            sample.samples = [(0., 20.), (.3, 20.), (.6, 20.)]
            report = sample.report(.1, .5, None)
            self.assertIsNone(report["power"])
            self.assertIn("1s", report["power_unavailable_reason"])
            sample.samples = [(i / 10, 20.) for i in range(21)]
            report = sample.report(.1, 1.9, None)
            self.assertAlmostEqual(report["power"]["sampled_board_energy_j"], 36)
            self.assertFalse(report["phase_energy_attribution_validated"])

        def test_missing_samples_fail_gap_gate(self):
            # Brackets and an interior sample alone used to accept this hole.
            sample = _PowerWindow(lambda: 20000, .02)
            sample.samples = [(0., 20.), (.1, 20.), (5., 20.), (5.1, 20.)]
            report = sample.report(.05, 5.05, None)
            self.assertIsNone(report["power"])
            self.assertIn("exceeds allowed", report["power_unavailable_reason"])
            self.assertAlmostEqual(report["max_sample_gap_s"], 4.9)
            self.assertEqual(report["max_allowed_sample_gap_s"], .25)
            # Boundary-covering gaps remain large even if little overlaps phase.
            self.assertEqual(_max_sample_gap([(0., 1.), (5., 1.), (5.1, 1.)], 4.9, 5.05), 5.)
            sample.interval = .1
            sample.samples = [(i * .4, 20.) for i in range(6)]
            report = sample.report(.1, 1.9, None)
            self.assertIsNotNone(report["power"])
            self.assertEqual(report["max_allowed_sample_gap_s"], .5)

        def test_sampler_failure_is_null_and_thread_closes(self):
            def fail():
                raise RuntimeError("unsupported")
            sample = _PowerWindow(fail, .01)
            sample.start()
            sample.stop()
            report = sample.report(1, 2, None)
            self.assertIsNone(report["power"])
            self.assertIn("unsupported", report["power_unavailable_reason"])
            self.assertIsNone(sample.thread)
            json.dumps(report, allow_nan=False)

        def test_cpu_rejection_never_calls_cuda(self):
            with patch.object(torch.cuda, "get_device_properties", side_effect=AssertionError("CUDA touched")):
                with self.assertRaisesRegex(ValueError, "already allocated CUDA"):
                    run_benchmark(torch.nn.Linear(2, 2), torch.arange(3000))

        def test_nvml_init_then_handle_failure_shuts_down(self):
            uid = "GPU-12345678-1234-1234-1234-123456789abc"
            module = SimpleNamespace(nvmlInit=Mock(), nvmlShutdown=Mock(),
                                     nvmlDeviceGetHandleByUUID=Mock(side_effect=RuntimeError("missing")))
            with patch.dict(sys.modules, {"pynvml": module}):
                session = _NvmlSession(uid, uid)
            module.nvmlShutdown.assert_called_once()
            self.assertIsNone(session.reader)

        def test_bare_uuid_normalized_and_handle_uuid_rechecked(self):
            uid = "GPU-12345678-1234-1234-1234-123456789abc"
            for request in (uid, uid[4:]):
                module = SimpleNamespace(nvmlInit=Mock(), nvmlShutdown=Mock(),
                    nvmlDeviceGetHandleByUUID=Mock(return_value="handle"),
                    nvmlDeviceGetUUID=Mock(return_value=uid.encode()),
                    nvmlDeviceGetPowerUsage=Mock(return_value=20000))
                with patch.dict(sys.modules, {"pynvml": module}):
                    session = _NvmlSession(uid[4:], request)
                    self.assertIsNone(session.reason)
                    self.assertEqual(session.uuid, uid)
                    self.assertEqual(session.reader(), 20000)
                    module.nvmlDeviceGetHandleByUUID.assert_called_once_with(uid.encode())
                    session.close()
                    module.nvmlShutdown.assert_called_once()
            module.nvmlDeviceGetUUID.return_value = "GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            with patch.dict(sys.modules, {"pynvml": module}):
                session = _NvmlSession(uid[4:], uid[4:])
            self.assertIsNone(session.reader)
            self.assertIn("handle UUID differs", session.reason)

        def test_numeric_and_mig_uuid_never_initialize_nvml(self):
            uid = "GPU-12345678-1234-1234-1234-123456789abc"
            module = SimpleNamespace(nvmlInit=Mock())
            with patch.dict(sys.modules, {"pynvml": module}):
                for request in ("0", 0, "MIG-"+uid, "bad", " "+uid):
                    self.assertIsNone(_NvmlSession(uid, request).reader)
            module.nvmlInit.assert_not_called()

        def test_measure_failure_stops_sampler(self):
            window = Mock()
            module = sys.modules[__name__]
            with patch.object(torch.cuda, "synchronize"), patch.object(torch.cuda, "Event"), \
                    patch.object(module, "_PowerWindow", return_value=window):
                with self.assertRaisesRegex(RuntimeError, "forward failed"):
                    _measure(Mock(side_effect=RuntimeError("forward failed")), None,
                             SimpleNamespace(reader=None), .02)
            window.stop.assert_called_once()

        def test_trial_failure_restores_controller(self):
            controller = SimpleNamespace(install=Mock(), close=Mock(), prefill=nullcontext)
            adapter = SimpleNamespace(SparQController=Mock(return_value=controller))
            fake = SimpleNamespace(model=Mock(side_effect=RuntimeError("forward failed")))
            with patch.dict(sys.modules, {"qwen3.sparq.adapter": adapter}), \
                    patch.object(sys.modules[__name__], "_snapshot", return_value=()):
                with self.assertRaisesRegex(RuntimeError, "forward failed"):
                    _trial(fake, torch.arange(10)[None], 3, 2, "sparq", None, None, None, .02, False)
            controller.close.assert_called_once()

        def test_pair_order_and_json_orchestration_without_gpu(self):
            # Mock timing/model execution only: this is NOT CUDA validation.
            fake = torch.nn.Linear(2, 2)
            fake.config = SimpleNamespace(vocab_size=32)
            def trial(*args):
                if not args[-1]:
                    return None
                def phase():
                    return dict(wall_seconds=2., cuda_event_seconds=1.5,
                                tokens_per_wall_second=3., power=None, max_sample_gap_s=None,
                                power_unavailable_reason="mock timing; no telemetry")
                return dict(prefill=phase(), decode=phase(), controller=None)
            module = sys.modules[__name__]
            with patch.object(module, "_check_model", return_value=torch.device("cpu")), \
                    patch.object(module, "_trial", side_effect=trial) as execute, \
                    patch.object(torch.cuda, "device", side_effect=lambda _: nullcontext()), \
                    patch.object(torch.cuda, "get_device_properties", return_value=SimpleNamespace(name="mock")):
                result = run_benchmark(fake, torch.arange(10), contexts=(3,), decode_lengths=(2,), repeats=2)
            self.assertEqual(execute.call_count, 9)
            self.assertEqual([r[-1] for r in result["execution_order"]],
                             ["native", "dense", "sparq", "dense", "sparq", "native"])
            self.assertEqual(len(result["summaries"]), 3)
            for summary in result["summaries"]:
                for phase in ("prefill", "decode"):
                    self.assertFalse(summary[phase]["phase_energy_attribution_validated"])
                    self.assertIn("1s average", summary[phase]["sensor_semantics"])
                    self.assertEqual(summary[phase]["max_allowed_sample_gap_s"], .25)
            json.dumps(result, allow_nan=False)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Helpers))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    _self_test()
