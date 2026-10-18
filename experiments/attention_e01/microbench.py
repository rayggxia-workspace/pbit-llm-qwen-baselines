"""E1 attention *numerical* microbenchmarks; CPU time is not ASIC latency.

The three contracts are full probabilities, category indices/counts, and final
V output. Ising is the repository's exact event-compressed DISCRETE serial
heat-bath reference, not an IID or physical-device model. Skipping null updates
saves Python work only: every attempted hardware update is still reported.

Trace NPZ (allow_pickle=False): logits [R,M], values [R,M,D], optional lengths
[R], row_metadata either a JSON list scalar or [R] JSON strings. Logits must be
post-scale, post-mask, finite scores for eligible causal keys; V uses exactly
the same key order. Every first-M experiment is explicitly a renormalized
subcandidate distribution, not the original full-context distribution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from architecture_tlm.attention_reference_v3 import ising_random_scan


SCHEMA = "attention_e01_microbench_v1"
NUMERICAL = ("stable_fp32", "bf16_probability_cast_fp32_sum", "exp2_pwl_fp32", "online_tiled_fp32_pv")
SAMPLERS = ("digital_iid_inverse_cdf", "digital_systematic_single_phase", "serial_random_scan_ising")
DEFAULTS = {
    "candidate_counts": [64, 512, 2048], "sample_counts": [32, 128, 512],
    "seeds": [0, 1, 2], "real_row_indices": [0, 2, 4],
    "pwl_segments": 32, "online_tile": 64, "ising_burn_sweeps": 16,
    "ising_spacing_sweeps": 4, "case_timeout_seconds": 120,
    "ess_min_samples": 1024,
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")


def stable_probability(logits, dtype=np.float64):
    x = np.asarray(logits, dtype=dtype)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError("logits must be a finite nonempty vector")
    weights = np.exp(x - np.max(x))
    return weights / np.sum(weights, dtype=dtype)


def bf16_rne(values):
    """Round FP32 to BF16 nearest-even, represented as FP32; retain NaN/Inf."""
    x = np.asarray(values, dtype=np.float32)
    bits = x.view(np.uint32)
    rounded = bits + np.uint32(0x7FFF) + ((bits >> 16) & np.uint32(1))
    rounded = rounded & np.uint32(0xFFFF0000)
    special = (bits & np.uint32(0x7F800000)) == np.uint32(0x7F800000)
    return np.where(special, bits, rounded).astype(np.uint32).view(np.float32)


def exp2_pwl_probability(logits, segments=32):
    """Software FP32 PWL model of exp(x), NOT a fixed-point RTL implementation.

    exp(x-max) = 2**((x-max)*log2(e)). Fractional 2**f is linearly interpolated
    on [0,1]; exponent range reduction uses floor and ldexp. No e->2 temperature
    change is hidden in the approximation. Values below FP32 subnormal range
    underflow to zero. LUT, reciprocal and multiplier costs are not synthesized.
    """
    if not isinstance(segments, int) or not 2 <= segments <= 4096:
        raise ValueError("pwl_segments must be an integer in [2,4096]")
    x = np.asarray(logits, dtype=np.float32)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError("invalid logits")
    with np.errstate(over="ignore"):
        scaled = (x - np.max(x)) * np.float32(math.log2(math.e))
    clipped = np.maximum(scaled, np.float32(-150))
    exponent = np.floor(clipped).astype(np.int32)
    position = (clipped - exponent.astype(np.float32)) * np.float32(segments)
    slot = np.minimum(position.astype(np.int32), segments - 1)
    fraction = position - slot.astype(np.float32)
    table = np.exp2(np.arange(segments + 1, dtype=np.float32) / np.float32(segments))
    mantissa = table[slot] + fraction * (table[slot + 1] - table[slot])
    weights = np.ldexp(mantissa, exponent).astype(np.float32)
    weights[scaled < -150] = 0
    return weights / np.sum(weights, dtype=np.float32)


def online_tiled_pv(logits, values, tile=64):
    """Online FP32 max/sum/PV; includes rescaling when a later max increases."""
    x = np.asarray(logits, dtype=np.float32)
    v = np.asarray(values, dtype=np.float32)
    if tile < 1 or x.ndim != 1 or v.ndim != 2 or len(x) != len(v):
        raise ValueError("invalid online PV shapes/tile")
    if not len(x) or not np.isfinite(x).all() or not np.isfinite(v).all():
        raise ValueError("online PV requires finite nonempty inputs")
    maximum = np.float32(-np.inf)
    denominator = np.float32(0)
    numerator = np.zeros(v.shape[1], dtype=np.float32)
    for start in range(0, len(x), tile):
        chunk = x[start:start + tile]
        new_maximum = np.maximum(maximum, np.max(chunk))
        scale = np.float32(0) if np.isneginf(maximum) else np.exp(maximum - new_maximum)
        weights = np.exp(chunk - new_maximum)
        denominator = denominator * scale + np.sum(weights, dtype=np.float32)
        numerator = numerator * scale + weights @ v[start:start + tile]
        maximum = new_maximum
    return numerator / denominator


def sample_indices(probabilities, samples, seed, backend, logits=None, burn=16, spacing=4):
    if samples < 1:
        raise ValueError("samples must be positive")
    p = np.asarray(probabilities, dtype=np.float64)
    if p.ndim != 1 or not len(p) or not np.isfinite(p).all() or np.any(p < 0) or p.sum() <= 0:
        raise ValueError("invalid probabilities")
    if backend == "serial_random_scan_ising":
        if logits is None or len(logits) != len(p):
            raise ValueError("Ising requires matching logits")
        indices, counters = ising_random_scan(list(map(float, logits)), samples, burn, spacing, random.Random(seed))
        return np.asarray(indices, dtype=np.int64), {
            "iid": False, "algorithm": "exact_event_compressed_discrete_serial_heat_bath",
            "attempted_updates": counters["attempts"], "state_flips": counters["flips"],
            "sites": counters["sites"], "burn_sweeps": burn, "spacing_sweeps": spacing,
            "physical_device_model": False, "null_updates_skipped_in_software_only": True,
        }
    cumulative = np.cumsum(p / p.sum(), dtype=np.float64)
    cumulative[-1] = 1.0
    rng = np.random.default_rng(seed)
    if backend == "digital_iid_inverse_cdf":
        thresholds = rng.random(samples)
        description = {"iid": True, "random_uniform_words": samples}
    elif backend == "digital_systematic_single_phase":
        thresholds = (np.arange(samples, dtype=np.float64) + rng.random()) / samples
        description = {"iid": False, "random_uniform_words": 1, "ordered_thresholds": True}
    else:
        raise ValueError("unknown sampler " + backend)
    indices = np.searchsorted(cumulative, thresholds, side="right")
    return indices.astype(np.int64), description


def indices_to_pv(indices, values):
    """Histogram, unique V gather, and FP32 count-weighted accumulation."""
    idx = np.asarray(indices)
    v = np.asarray(values, dtype=np.float32)
    if idx.ndim != 1 or not idx.size or not np.issubdtype(idx.dtype, np.integer):
        raise ValueError("indices must be a nonempty integer vector")
    if v.ndim != 2 or np.any(idx < 0) or np.any(idx >= len(v)):
        raise ValueError("index/value mismatch")
    counts = np.bincount(idx, minlength=len(v))
    used = np.flatnonzero(counts)
    result = counts[used].astype(np.float32) @ v[used] / np.float32(len(idx))
    return counts, result


def probability_metrics(actual, reference):
    p, q = np.asarray(actual, dtype=np.float64), np.asarray(reference, dtype=np.float64)
    if p.shape != q.shape or p.ndim != 1 or not np.isfinite(p).all():
        raise ValueError("invalid probability metric inputs")
    return {"shape": list(p.shape), "tv": float(np.abs(p - q).sum() / 2),
            "tv_definition": "half_L1_before_any_renormalization_report_row_sum_separately",
            "max_abs_error": float(np.abs(p - q).max()), "row_sum": float(p.sum()),
            "abs_row_sum_minus_one": float(abs(p.sum() - 1)),
            "minimum_probability": float(p.min())}


def vector_metrics(actual, reference):
    y, target = np.asarray(actual, dtype=np.float64), np.asarray(reference, dtype=np.float64)
    if y.shape != target.shape or y.ndim != 1 or not np.isfinite(y).all():
        raise ValueError("invalid V metric inputs")
    square_error = float(np.dot(y - target, y - target))
    reference_energy = float(np.dot(target, target))
    floor = 1e-30
    return {"shape": list(y.shape), "nmse": square_error / max(reference_energy, floor),
            "relative_l2_error": math.sqrt(square_error / max(reference_energy, floor)),
            "absolute_l2_error": math.sqrt(square_error), "reference_energy": reference_energy,
            "relative_denominator_floor": floor}


def effective_sample_size(observations, minimum=1024):
    """FFT autocovariance, initial positive paired sums; diagnostic, not proof."""
    x = np.asarray(observations, dtype=np.float64)
    if len(x) < minimum:
        return {"status": "insufficient_samples", "samples": len(x), "minimum": minimum}
    centered = x - np.mean(x)
    variance = float(np.dot(centered, centered) / len(x))
    if variance < 1e-30:
        return {"status": "unresolved_constant_observable", "samples": len(x)}
    size = 1 << (2 * len(x) - 1).bit_length()
    spectrum = np.fft.rfft(centered, n=size)
    covariance = np.fft.irfft(spectrum * spectrum.conjugate(), n=size)[:len(x)]
    covariance /= np.arange(len(x), 0, -1)
    rho = covariance / covariance[0]
    positive_sum = 0.0
    for lag in range(1, len(x) - 1, 2):
        pair = float(rho[lag] + rho[lag + 1])
        if pair <= 0:
            break
        positive_sum += pair
    tau = max(1.0, 1.0 + 2.0 * positive_sum)
    return {"status": "diagnostic_only_no_stationarity_proof", "samples": len(x),
            "ess": min(float(len(x)), len(x) / tau), "integrated_autocorrelation_time": tau,
            "method": "initial_positive_paired_autocorrelation_sums"}


def _metadata_strings(array, count):
    def parse(value):
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(str(value))
    a = np.asarray(array)
    result = parse(a.item()) if a.ndim == 0 else [parse(value) for value in a]
    if isinstance(result, dict):
        result = result.get("rows", [])
    if not isinstance(result, list) or len(result) != count:
        raise ValueError("row_metadata must describe every trace row")
    return result


def load_trace(path, synthetic_only=False):
    if synthetic_only:
        if path:
            raise ValueError("--synthetic-only must not be combined with --trace")
        rng = np.random.default_rng(20261019)
        logits = rng.normal(size=(5, 2048)).astype(np.float32)
        values = rng.normal(size=(5, 2048, 64)).astype(np.float32)
        return {"logits": logits, "values": values, "lengths": np.full(5, 2048),
                "metadata": [{"kind": "synthetic_fixture", "row": i} for i in range(5)],
                "provenance": {"kind": "EXPLICIT_SYNTHETIC_ONLY", "model_quality_validated": False}}
    if not path:
        raise ValueError("--trace is required unless --synthetic-only is explicit")
    with np.load(path, allow_pickle=False) as data:
        logits = np.asarray(data["logits"], dtype=np.float32)
        values = np.asarray(data["values"], dtype=np.float32)
        if logits.ndim != 2 or values.ndim != 3 or values.shape[:2] != logits.shape or min(*logits.shape, values.shape[-1]) < 1:
            raise ValueError("trace requires logits [R,M] and matching values [R,M,D]")
        lengths = np.asarray(data["lengths"], dtype=np.int64) if "lengths" in data else np.full(len(logits), logits.shape[1])
        metadata = _metadata_strings(data["row_metadata"], len(logits)) if "row_metadata" in data else [{"row": i, "metadata": "not_supplied"} for i in range(len(logits))]
    if lengths.shape != (len(logits),) or np.any(lengths < 1) or np.any(lengths > logits.shape[1]):
        raise ValueError("invalid trace lengths")
    for row, length in enumerate(lengths):
        if not np.isfinite(logits[row, :length]).all() or not np.isfinite(values[row, :length]).all():
            raise ValueError("nonfinite eligible logits or V in trace")
    return {"logits": logits, "values": values, "lengths": lengths, "metadata": metadata,
            "provenance": {"kind": "SOURCED_LOGIT_AND_VALUE_TRACE", "path": str(Path(path).resolve()),
                           "sha256": sha256(path), "model_quality_validated": False}}


def normalize_config(config):
    unknown = set(config) - set(DEFAULTS)
    if unknown:
        raise ValueError("unknown E1 config keys: " + ", ".join(sorted(unknown)))
    result = {**DEFAULTS, **config}
    for field in ("candidate_counts", "sample_counts", "seeds", "real_row_indices"):
        values = result[field]
        if not isinstance(values, list) or not 1 <= len(values) <= 3 or any(type(v) is not int for v in values) or len(set(values)) != len(values):
            raise ValueError(field + " must contain one to three unique integers")
    if any(m < 1 or m > 2048 for m in result["candidate_counts"]) or any(s < 1 or s > 512 for s in result["sample_counts"]):
        raise ValueError("finite E1 workload requires 1<=M<=2048 and 1<=S<=512")
    if any(i < 0 for i in result["real_row_indices"]) or len(result["real_row_indices"]) > 3:
        raise ValueError("select one to three nonnegative real_row_indices")
    if any(seed < 0 or seed >= 2 ** 64 for seed in result["seeds"]):
        raise ValueError("seeds must be nonnegative integers below 2**64")
    for field, lower, upper in (("pwl_segments", 2, 4096), ("online_tile", 1, 2048),
                                ("ising_burn_sweeps", 0, 256), ("ising_spacing_sweeps", 1, 64),
                                ("ess_min_samples", 128, 1048576)):
        if type(result[field]) is not int or not lower <= result[field] <= upper:
            raise ValueError("invalid bounded config field " + field)
    if not 1 <= result["case_timeout_seconds"] <= 1800:
        raise ValueError("case_timeout_seconds must be in [1,1800]")
    return result


def profile_inputs(trace, profile, candidates, real_rows):
    source_row = int(profile.split(":")[1]) if profile.startswith("real:") else real_rows[0]
    if source_row >= len(trace["logits"]) or candidates > trace["lengths"][source_row]:
        raise ValueError("requested row/M exceeds trace eligibility")
    logits = trace["logits"][source_row, :candidates].copy()
    values = trace["values"][source_row, :candidates].copy()
    if profile == "uniform":
        logits.fill(0)
    elif profile == "peaked":
        logits.fill(0)
        logits[0] = np.float32(math.log(max(1, candidates - 1)) + math.log(9))
    metadata = {"profile": profile, "source_row": source_row, "source_row_metadata": trace["metadata"][source_row],
                "candidate_selection": "first_M_logits_and_matching_V_prefix",
                "distribution_scope": "renormalized_subcandidate_distribution",
                "values_kind": "source_row_prefix", "representative_of_full_model": False}
    if profile in ("uniform", "peaked"):
        metadata["logits_kind"] = "synthetic_" + profile
    else:
        metadata["logits_kind"] = "sourced_real" if trace["provenance"]["kind"] != "EXPLICIT_SYNTHETIC_ONLY" else "explicit_synthetic_fixture"
    return logits, values, metadata


def build_cases(config, phase):
    real_profiles = ["real:" + str(index) for index in config["real_row_indices"]]
    profiles = ["uniform", "peaked"] + real_profiles
    if phase == "pilot":
        low, middle, high = min(config["candidate_counts"]), config["candidate_counts"][len(config["candidate_counts"]) // 2], max(config["candidate_counts"])
        small_s, big_s = min(config["sample_counts"]), max(config["sample_counts"])
        # Twelve finite pilots cover all kernels, three M, sourced V and the
        # largest Ising horizon. They are gates, not scientific repetitions.
        cases = [{"profile": "uniform", "M": low, "backend": backend} for backend in NUMERICAL]
        cases += [{"profile": "peaked", "M": middle, "S": small_s, "seed": config["seeds"][0], "backend": backend} for backend in SAMPLERS]
        cases += [{"profile": real_profiles[0], "M": high, "backend": backend} for backend in ("stable_fp32", "exp2_pwl_fp32", "online_tiled_fp32_pv")]
        cases += [{"profile": real_profiles[0], "M": high, "S": big_s, "seed": config["seeds"][0], "backend": backend} for backend in ("serial_random_scan_ising", "digital_systematic_single_phase")]
    elif phase == "full":
        cases = [{"profile": profile, "M": m, "backend": backend} for profile in profiles for m in config["candidate_counts"] for backend in NUMERICAL]
        cases += [{"profile": profile, "M": m, "S": s, "seed": seed, "backend": backend}
                  for profile in profiles for m in config["candidate_counts"] for s in config["sample_counts"]
                  for seed in config["seeds"] for backend in SAMPLERS]
    else:
        raise ValueError("unknown phase")
    for index, case in enumerate(cases):
        case["case_id"] = f"{phase}_{index:05d}"
    return cases


_WORKER_TRACE = None
_WORKER_CONFIG = None


def _init_worker(path, synthetic_only, config):
    global _WORKER_TRACE, _WORKER_CONFIG
    _WORKER_TRACE = load_trace(path, synthetic_only)
    _WORKER_CONFIG = config


def evaluate_case(case, trace, config):
    logits, values, metadata = profile_inputs(trace, case["profile"], case["M"], config["real_row_indices"])
    reference = stable_probability(logits, np.float64)
    reference_v = reference @ values.astype(np.float64)
    backend = case["backend"]
    start = time.perf_counter()
    arrays = {"reference_probability": reference, "reference_v": reference_v}
    record = {**case, "status": "ok", "input": metadata, "reference": "stable_fp64_on_same_subcandidate_logits_and_V",
              "timing_scope": "CPU_software_numerical_simulation_NOT_hardware_latency_or_energy",
              "native_hardware_advantage_validated": False, "stationarity_proven": False}
    if backend in NUMERICAL:
        if backend == "online_tiled_fp32_pv":
            output = online_tiled_pv(logits, values, config["online_tile"])
            contracts = {"final_v": {**vector_metrics(output, reference_v), "accumulation": "FP32_online_max_sum_PV"},
                         "full_probability": {"status": "not_materialized_by_this_contract"},
                         "category_indices": {"status": "not_requested"}}
        else:
            if backend == "stable_fp32":
                probability = stable_probability(logits, np.float32)
            elif backend == "bf16_probability_cast_fp32_sum":
                probability = bf16_rne(stable_probability(logits, np.float32))
                record["precision_note"] = "FP32 exp_and_sum_then_BF16_probability_RNE_cast_without_renormalization"
            else:
                probability = exp2_pwl_probability(logits, config["pwl_segments"])
                record["precision_note"] = "FP32_numerical_PWL_exp2_with_log2e_NOT_fixed_point_RTL"
            output = probability.astype(np.float32) @ values
            arrays["probability"] = probability
            contracts = {"full_probability": probability_metrics(probability, reference),
                         "category_indices": {"status": "not_requested"},
                         "final_v": {**vector_metrics(output, reference_v), "accumulation": "FP32_dense_PV"}}
    else:
        # Digital branches include FP32 softmax preparation; Ising receives
        # logits directly. Baseline FP64 is only the numerical error reference.
        preparation_start = time.perf_counter()
        probability = stable_probability(logits, np.float32) if backend != "serial_random_scan_ising" else reference
        preparation_seconds = time.perf_counter() - preparation_start
        sampling_start = time.perf_counter()
        indices, counters = sample_indices(probability, case["S"], case["seed"], backend, logits,
                                           config["ising_burn_sweeps"], config["ising_spacing_sweeps"])
        record["sampling_cpu_software_seconds"] = time.perf_counter() - sampling_start
        record["probability_preparation_cpu_software_seconds"] = preparation_seconds
        counts, output = indices_to_pv(indices, values)
        empirical = counts.astype(np.float64) / case["S"]
        histogram = probability_metrics(empirical, reference)
        histogram.update({"kind": "finite_sample_empirical_histogram_NOT_exact_probability_vector",
                          "uniform_support_tv_lower_bound": max(0., 1 - case["S"] / case["M"]) if case["profile"] == "uniform" else None})
        contracts = {"full_probability": histogram,
                     "category_indices": {"shape": list(indices.shape), "dtype": "int64", "count_sum": int(counts.sum()),
                                          "unique_V_rows": int(np.count_nonzero(counts)), "within_candidate_range": True},
                     "final_v": {**vector_metrics(output, reference_v), "accumulation": "FP32_unique_V_count_weighted_sum_divided_by_S"}}
        record["sampler"] = counters
        if backend == "digital_systematic_single_phase":
            record["ess"] = {"status": "not_applicable_ordered_systematic_thresholds_are_not_a_stationary_chain"}
        else:
            top = int(np.argmax(reference))
            record["ess"] = {
                "category_indicator": {"category": top, **effective_sample_size(indices == top, config["ess_min_samples"])},
                "V_coordinate_0": effective_sample_size(values[indices, 0], config["ess_min_samples"]),
                "warning": "short_sample_error_does_not_prove_stationarity_or_independent_physical_events",
            }
        arrays.update({"indices": indices, "counts": counts, "empirical_probability": empirical})
    arrays["v_output"] = output
    record["contracts"] = contracts
    record["backend_cpu_software_seconds"] = time.perf_counter() - start
    # Pilot checks correctness invariants and reference-level precision only.
    # Finite Ising quality is measured, never silently made a stationarity gate.
    numeric_p = contracts["full_probability"]
    invariant_ok = bool(np.isfinite(output).all())
    if backend in ("stable_fp32", "exp2_pwl_fp32"):
        invariant_ok &= numeric_p["tv"] <= 1e-3 and numeric_p["abs_row_sum_minus_one"] <= 1e-5
    if backend == "online_tiled_fp32_pv":
        invariant_ok &= contracts["final_v"]["relative_l2_error"] <= 1e-4
    record["correctness_invariants_passed"] = bool(invariant_ok)
    return record, arrays


def _execute_case(case):
    return evaluate_case(case, _WORKER_TRACE, _WORKER_CONFIG)


def execution_source_identity(source_manifest_sha256=None):
    """Bind pilot gates to actual sources, including standalone execution.

    A driver manifest is extra provenance, not a substitute for checking the
    bytes loaded here. A passing pilot must be rerun after either engine or
    reused serial-sampler code changes.
    """
    if source_manifest_sha256 is not None:
        source_manifest_sha256 = source_manifest_sha256.lower()
        if len(source_manifest_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_manifest_sha256):
            raise ValueError("source_manifest_sha256 must be a 64-character hexadecimal digest")
    return {
        "microbench.py": sha256(Path(__file__).resolve()),
        "architecture_tlm/attention_reference_v3.py": sha256(REPO_ROOT / "architecture_tlm/attention_reference_v3.py"),
        "source_manifest_sha256": source_manifest_sha256,
    }


def run(trace_path, output, phase, config, synthetic_only=False, source_manifest_sha256=None):
    trace = load_trace(trace_path, synthetic_only)
    for index in config["real_row_indices"]:
        if index >= len(trace["logits"]):
            raise ValueError("real_row_indices exceeds number of trace rows")
        if max(config["candidate_counts"]) > trace["lengths"][index]:
            raise ValueError("selected trace row too short for requested M")
    context = {"schema": SCHEMA, "config": config, "trace": trace["provenance"],
               "execution_sources": execution_source_identity(source_manifest_sha256),
               "synthetic_only": synthetic_only, "numpy": np.__version__, "python": platform.python_version()}
    fingerprint = hashlib.sha256(_json_bytes(context)).hexdigest()
    phase_dir = Path(output) / phase
    if phase_dir.exists() and any(phase_dir.iterdir()):
        raise ValueError("refusing to overwrite an existing phase output; choose a new output root")
    if phase == "full":
        gate_path = Path(output) / "pilot" / "summary.json"
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        if not gate.get("gate_passed") or gate.get("context_sha256") != fingerprint or gate.get("completed_cases") != 12:
            raise ValueError("full requires a passing 12-case pilot with identical trace/config/environment")
    phase_dir.mkdir(parents=True, exist_ok=True)
    output_arrays = phase_dir / "case_outputs"
    output_arrays.mkdir()
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
    context.update({"context_sha256": fingerprint, "phase": phase, "command": sys.argv,
                    "git_commit": commit, "host": platform.node(),
                    "thread_environment": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
                    "scope": "numerical_microbench_only_NO_PPL_NO_RTL_NO_PPA"})
    (phase_dir / "run_context.json").write_bytes(_json_bytes(context) + b"\n")
    cases = build_cases(config, phase)
    records = []
    pool = None
    spawn = mp.get_context("spawn")
    try:
        with (phase_dir / "cases.jsonl").open("x", encoding="utf-8", newline="\n") as journal:
            for case in cases:
                if pool is None:
                    pool = spawn.Pool(1, initializer=_init_worker, initargs=(trace_path, synthetic_only, config))
                try:
                    record, arrays = pool.apply_async(_execute_case, (case,)).get(timeout=config["case_timeout_seconds"])
                    artifact = output_arrays / (case["case_id"] + ".npz")
                    np.savez_compressed(artifact, **arrays)
                    record["artifact"] = {"path": str(artifact.relative_to(phase_dir)), "sha256": sha256(artifact)}
                except mp.TimeoutError:
                    pool.terminate()
                    pool.join()
                    pool = None
                    record = {**case, "status": "timed_out", "case_timeout_seconds": config["case_timeout_seconds"],
                              "correctness_invariants_passed": False, "partial_output_not_a_result": True}
                except Exception as error:
                    record = {**case, "status": "error", "error": repr(error), "correctness_invariants_passed": False}
                records.append(record)
                journal.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
                print(f"{case['case_id']} {case['backend']} {record['status']}", flush=True)
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    completed = sum(record["status"] == "ok" for record in records)
    passed = all(record.get("correctness_invariants_passed", False) for record in records)
    summary = {"schema": SCHEMA, "phase": phase, "context_sha256": fingerprint,
               "planned_cases": len(cases), "recorded_cases": len(records), "completed_cases": completed,
               "timed_out_cases": sum(record["status"] == "timed_out" for record in records),
               "error_cases": sum(record["status"] == "error" for record in records),
               "gate_passed": passed and completed == len(cases), "synthetic_only": synthetic_only,
               "gate_scope": "finite_execution_and_numerical_invariants_NOT_physical_quality_or_stationarity",
               "actual_case_count_is_this_matrix_not_the_previous_planning_CSV": True,
               "category_backends": list(SAMPLERS), "no_native_event_oracle_substituted_for_physical_model": True,
               "scientific_scope": "numerical_errors_and_finite_serial_sampling_NO_hardware_advantage_claim",
               "journal_sha256": sha256(phase_dir / "cases.jsonl")}
    (phase_dir / "summary.json").write_bytes(_json_bytes(summary) + b"\n")
    print(json.dumps(summary, sort_keys=True), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", help="NPZ logits/values in matching candidate order")
    parser.add_argument("--output", required=True, help="new output root; creates pilot/ and full/ subdirectories")
    parser.add_argument("--phase", required=True, choices=("pilot", "full"))
    parser.add_argument("--config", help="flat JSON overrides of bounded E1 settings")
    parser.add_argument("--source-manifest-sha256", help="optional driver source-manifest digest, also bound into the pilot gate")
    parser.add_argument("--synthetic-only", action="store_true", help="explicit fixture-only run, no sourced model results")
    args = parser.parse_args()
    config = normalize_config(json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {})
    summary = run(args.trace, args.output, args.phase, config, args.synthetic_only, args.source_manifest_sha256)
    return 0 if summary["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
