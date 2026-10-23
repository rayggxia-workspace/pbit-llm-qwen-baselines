"""One decode token / one layer, paper-v6 GQA SparQ resource ledger.

Counts describe an explicit reference implementation, not PyTorch's kernel
instruction counts. Memory transactions are exact for supplied selected indices
under the declared burst/no-cross-stage-cache policy. No power/area coefficients
are inferred from counts. Standard-library only; no model or GPU is loaded.
"""

from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json


def _positive(name, value, *, zero=False):
    if type(value) is not int or value < (0 if zero else 1):
        raise ValueError(f"{name} must be a {'nonnegative' if zero else 'positive'} integer")


def _ceil(a, b):
    return (a + b - 1) // b


@dataclass(frozen=True)
class Config:
    n_tokens: int
    query_heads: int = 32
    kv_heads: int = 8
    head_dim: int = 128
    channels: int = 32
    selected_tokens: int = 128
    local_tokens: int = 32
    layout: str = "dual_k"
    burst_bytes: int = 64
    capacity_tokens: int | None = None
    reallocation: bool = False
    storage_dtype: str = "bf16"
    compute_dtype: str = "fp32"

    def validate(self):
        for name in ("n_tokens", "query_heads", "kv_heads", "head_dim", "channels",
                     "selected_tokens", "burst_bytes"):
            _positive(name, getattr(self, name))
        _positive("local_tokens", self.local_tokens, zero=True)
        if self.query_heads % self.kv_heads:
            raise ValueError("query_heads must be divisible by kv_heads")
        if self.channels > self.head_dim:
            raise ValueError("channels exceeds head_dim")
        if self.local_tokens > self.selected_tokens:
            raise ValueError("local_tokens exceeds total selected_tokens")
        if self.capacity_tokens is not None:
            _positive("capacity_tokens", self.capacity_tokens)
            if self.capacity_tokens < self.n_tokens:
                raise ValueError("cache capacity smaller than visible tokens")
        if self.layout not in ("dual_k", "token_major"):
            raise ValueError("layout must be dual_k or token_major")
        if self.burst_bytes % 2:
            raise ValueError("burst size must be a multiple of the BF16 element size")
        if type(self.reallocation) is not bool or self.reallocation:
            raise ValueError("this ledger supports reallocation=False only; meanV/alpha need a separate profile")
        if (self.storage_dtype, self.compute_dtype) != ("bf16", "fp32"):
            raise ValueError("only BF16 cache / FP32 compute is defined")


@dataclass(frozen=True)
class Rates:
    """Hypothetical aggregate resources for the ENTIRE layer, never per head."""

    clock_hz: int = 100_000_000
    macs_per_cycle: int = 64
    vector_ops_per_cycle: int = 16
    compare_exchanges_per_cycle: int = 16
    exps_per_cycle: int = 4
    reciprocals_per_cycle: int = 1
    sqrts_per_cycle: int = 1
    conversions_per_cycle: int = 16
    dram_bytes_per_cycle: int = 16

    def validate(self):
        for key, value in asdict(self).items():
            _positive(key, value)


def bitonic_comparisons(length):
    """Full padded bitonic SORT cost; a declared conservative top-k baseline."""
    _positive("length", length)
    levels = (length - 1).bit_length()
    return (1 << levels) * levels * (levels + 1) // 4


def burst_traffic(ranges, burst_bytes):
    """Union touched bursts within one stage/address space, including overfetch.

    Each range is (byte_address, byte_length). Adjacent/overlapping touched
    bursts are merged. This is a cold transaction count, not a DRAM command or
    bank schedule; no reuse is assumed between calls/stages.
    """
    _positive("burst_bytes", burst_bytes)
    intervals = []
    for address, length in ranges:
        _positive("address", address, zero=True)
        _positive("length", length, zero=True)
        if length:
            intervals.append((address // burst_bytes, (address + length - 1) // burst_bytes + 1))
    end = -1
    count = 0
    for start, stop in sorted(intervals):
        count += max(0, stop - max(start, end))
        end = max(end, stop)
    return {"burst_transactions": count, "physical_bytes": count * burst_bytes}


def _runs(indices):
    result = []
    for index in sorted(indices):
        if result and result[-1][0] + result[-1][1] == index:
            result[-1] = (result[-1][0], result[-1][1] + 1)
        else:
            result.append((index, 1))
    return result


def _indices(name, value, groups, count, limit):
    if not isinstance(value, (list, tuple)) or len(value) != groups:
        raise ValueError(f"{name} requires one index list per KV head")
    result = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != count:
            raise ValueError(f"{name} requires exactly {count} entries per KV head")
        if any(type(i) is not int or not 0 <= i < limit for i in row) or len(set(row)) != count:
            raise ValueError(f"{name} contains invalid or duplicate indices")
        result.append(sorted(row))
    return result


def synthetic_indices(config, pattern="contiguous"):
    """Layout fixtures only: these are NOT selections observed from a model."""
    config.validate()
    if pattern not in ("contiguous", "spread"):
        raise ValueError("unknown synthetic channel pattern")
    c = config
    channel = (list(range(c.channels)) if pattern == "contiguous" else
               [i * c.head_dim // c.channels for i in range(c.channels)])
    k, local = min(c.selected_tokens, c.n_tokens), min(c.local_tokens, c.n_tokens)
    token = list(range(k - local)) + list(range(c.n_tokens - local, c.n_tokens))
    return {"channel_ids": [channel[:] for _ in range(c.kv_heads)],
            "token_ids": [token[:] for _ in range(c.kv_heads)],
            "provenance": {"kind": "synthetic_layout_fixture", "channel_pattern": pattern,
                           "tokens": "prefix plus required recent window; no Q/K-based selection"}}


def _add(dst, src):
    for key, value in src.items():
        dst[key] = dst.get(key, 0) + value


def _softmax(rows, width):
    return {"max_compare": rows * (width - 1), "subtract": rows * width,
            "exp": rows * width, "sum_add": rows * (width - 1),
            "reciprocal": rows, "normalize_multiply": rows * width}


def _physical(c, channels, tokens, sparse_groups):
    n, d, b, cap = c.n_tokens, c.head_dim, 2, c.capacity_tokens or c.n_tokens
    burst = c.burst_bytes
    # Every head/tensor starts on a burst boundary; padding is reported in storage.
    stride = _ceil(cap * d * b, burst) * burst
    totals = {}
    for group in range(c.kv_heads):
        base = group * stride
        selected = tokens[group]
        dense_rows = [(base, n * d * b)]
        full_rows = [(base + start * d * b, count * d * b) for start, count in _runs(selected)]
        stage2 = burst_traffic(full_rows, burst)
        dense = burst_traffic(dense_rows, burst)
        stage1 = {"burst_transactions": 0, "physical_bytes": 0}
        if group in sparse_groups:
            if c.layout == "dual_k":
                stage1 = burst_traffic(((base + channel * cap * b, n * b) for channel in channels[group]), burst)
            elif d * b % burst == 0:
                # An aligned row repeats exactly the same burst pattern N times.
                one = burst_traffic(((i * b, length * b) for i, length in _runs(channels[group])), burst)
                stage1 = {key: value * n for key, value in one.items()}
            else:
                stage1 = burst_traffic(((base + token * d * b + i * b, length * b)
                                       for token in range(n) for i, length in _runs(channels[group])), burst)
        append_row = burst_traffic([(base + (n - 1) * d * b, d * b)], burst)
        append_transpose = (burst_traffic(((base + channel * cap * b + (n - 1) * b, b)
                                          for channel in range(d)), burst)
                            if c.layout == "dual_k" else {"burst_transactions": 0, "physical_bytes": 0})
        transpose_build = (burst_traffic(((base + channel * cap * b, n * b) for channel in range(d)), burst)
                           if c.layout == "dual_k" else {"burst_transactions": 0, "physical_bytes": 0})
        for label, entry in (("approx_K_read", stage1), ("selected_K_read", stage2),
                             ("selected_V_read", stage2), ("dense_K_read", dense), ("dense_V_read", dense),
                             ("append_K_write", append_row), ("append_V_write", append_row),
                             ("append_transposed_K_write", append_transpose),
                             ("build_transposed_K_write", transpose_build)):
            _add(totals.setdefault(label, {}), entry)
        if c.layout == "dual_k":
            _add(totals.setdefault("build_transposed_K_read", {}), dense)
    totals.setdefault("build_transposed_K_read", {"physical_bytes": 0, "burst_transactions": 0})
    return totals


def _resource_work(operations, memory_bytes, rates):
    """Capacity bounds and serial work estimate, NOT cycle-accurate latency."""
    rates.validate()
    work = {"mac": 0, "vector": 0, "compare_exchange": 0, "exp": 0,
            "reciprocal": 0, "sqrt": 0, "conversion": 0, "dram_bytes": memory_bytes}
    for stage in operations.values():
        for name, count in stage.items():
            resource = ("mac" if name.endswith("mac") else "compare_exchange" if name in
                        ("compare_exchange", "max_compare") else "exp" if name == "exp" else
                        "reciprocal" if name == "reciprocal" else "sqrt" if name == "sqrt" else
                        "conversion" if name.startswith("convert_") else "vector")
            work[resource] += count
    capacities = dict(mac=rates.macs_per_cycle, vector=rates.vector_ops_per_cycle,
                      compare_exchange=rates.compare_exchanges_per_cycle, exp=rates.exps_per_cycle,
                      reciprocal=rates.reciprocals_per_cycle, sqrt=rates.sqrts_per_cycle,
                      conversion=rates.conversions_per_cycle, dram_bytes=rates.dram_bytes_per_cycle)
    cycles = {key: _ceil(value, capacities[key]) for key, value in work.items()}
    lower, serial = max(cycles.values()), sum(cycles.values())
    return {"status": "conditional_resource_work_only", "rates": asdict(rates),
            "work": work, "cycles_by_resource": cycles,
            "capacity_lower_bound_cycles": lower, "no_overlap_service_work_cycles": serial,
            "capacity_lower_bound_ns": float(Fraction(lower * 10**9, rates.clock_hz)),
            "no_overlap_service_work_ns": float(Fraction(serial * 10**9, rates.clock_hz)),
            "latency_ns": None,
            "limitations": ["Neither cycle figure is a realized schedule or a latency upper bound",
                            "No reduction/sort dependency latency, pipeline fill, bank conflicts, CDC, command or host overhead",
                            "Aggregate resources are shared by all heads; no implicit replication",
                            "No mapped RTL, STA, clock or throughput qualification"]}


def build_ledger(config, channel_ids, token_ids, rates=None, *, provenance=None,
                 dense_fallback_kv_heads=()):
    """Return deterministic counts for explicit per-KV selected indices.

    The caller supplies selection evidence. This function validates size/range/
    mandatory local membership; it cannot prove the indices are Q/K top-k.
    For N<=k it charges dense fallback and requires every token exactly once.
    dense_fallback_kv_heads identifies additional zero-selected-L1 fallback
    groups from the numeric core. Their token lists must contain ALL tokens;
    their unused channel lists may be empty when the core masks indices away.
    """
    config.validate()
    c = config
    n, d, h, v, r = c.n_tokens, c.head_dim, c.query_heads, c.kv_heads, c.channels
    k, local, routed = min(n, c.selected_tokens), min(n, c.local_tokens), n > c.selected_tokens
    if not isinstance(dense_fallback_kv_heads,(list,tuple)) or any(type(i) is not int or not 0<=i<v for i in dense_fallback_kv_heads):
        raise ValueError("dense_fallback_kv_heads must contain valid KV-head indices")
    if len(set(dense_fallback_kv_heads)) != len(dense_fallback_kv_heads):
        raise ValueError("duplicate dense fallback KV head")
    fallback = set(dense_fallback_kv_heads) if routed else set(range(v))
    sparse_groups = set(range(v)) - fallback
    if not isinstance(channel_ids, (list, tuple)) or len(channel_ids) != v:
        raise ValueError("channel_ids requires one index list per KV head")
    channels = [([] if g in fallback and isinstance(row, (list, tuple)) and not row else
                 _indices("channel_ids", [row], 1, r, d)[0])
                for g, row in enumerate(channel_ids)]
    if not isinstance(token_ids,(list,tuple)) or len(token_ids)!=v:
        raise ValueError("token_ids requires one index list per KV head")
    tokens = [_indices("token_ids",[row],1,n if g in fallback else k,n)[0] for g,row in enumerate(token_ids)]
    mandatory = set(range(n - local, n))
    if any(not mandatory.issubset(row) for row in tokens):
        raise ValueError("selected tokens omit a mandatory recent token (current token included)")
    b = 2
    cap = c.capacity_tokens or n
    phy = _physical(c, channels, tokens, sparse_groups)
    operations = {}
    sv = len(sparse_groups)
    sh = sv*(h//v)
    selected_rows = sum(map(len,tokens))
    head_rows = selected_rows*(h//v)
    if routed:
        operations["channel_selection"] = dict(abs=h*d, head_sum_add=(h-v)*d,
            compare_exchange=v*(bitonic_comparisons(d) if r < d else 0))
        # Tau: sqrt(d * sum_selected(abs(q)) / sum_all(abs(q))).
        operations["tau"] = dict(sum_add=h*(d+r-2), zero_selected_l1_test=h,
                                 multiply=2*sh, reciprocal=sh, sqrt=sh,
                                 convert_bf16_to_fp32=h*d)
    if sv:
        # Match the numeric core's query prescaling; do not scale every logit.
        operations["approx_qk"] = dict(approx_qk_mac=sh*n*r, scale_multiply=sh*r,
                                       reciprocal=sh, convert_bf16_to_fp32=sv*n*r)
        operations["approx_softmax"] = _softmax(sh, n)
        operations["group_probability_sum"] = dict(head_sum_add=(sh-sv)*n)
        operations["token_selection"] = dict(compare_exchange=sv*(bitonic_comparisons(n-local)
            if k > local and k < n else 0), local_membership_test=sv*n,
            selected_index_write=sv*k)
    operations["exact_qk"] = dict(exact_qk_mac=head_rows*d, scale_multiply=h*d,
                                   convert_bf16_to_fp32=selected_rows*d+(0 if routed else h*d))
    operations["exact_softmax"] = _softmax(sh,k)
    _add(operations["exact_softmax"], _softmax(h-sh,n))
    operations["exact_pv"] = dict(exact_pv_mac=head_rows*d, convert_bf16_to_fp32=selected_rows*d,
                                  convert_fp32_to_bf16=h*d)
    dense_ops = {"exact_qk": dict(exact_qk_mac=h*n*d, scale_multiply=h*d,
                                  convert_bf16_to_fp32=h*d+v*n*d),
                 "exact_softmax": _softmax(h,n),
                 "exact_pv": dict(exact_pv_mac=h*n*d, convert_bf16_to_fp32=v*n*d,
                                  convert_fp32_to_bf16=h*d)}
    reads = sum(phy[label]["physical_bytes"] for label in ("approx_K_read","selected_K_read","selected_V_read"))
    dense_reads = phy["dense_K_read"]["physical_bytes"]+phy["dense_V_read"]["physical_bytes"]
    writes = sum(phy[label]["physical_bytes"] for label in ("append_K_write","append_V_write","append_transposed_K_write"))
    dense_writes = phy["append_K_write"]["physical_bytes"]+phy["append_V_write"]["physical_bytes"]
    logical_reads = b*(sv*n*r+2*selected_rows*d)
    aligned_tensor = v*_ceil(cap*d*b,c.burst_bytes)*c.burst_bytes
    scratch = dict(query_fp32=h*d*4, output_accumulator_fp32=h*d*4,
                   approx_logits_fp32=sh*n*4,
                   approx_probabilities_fp32=sh*n*4,
                   group_probability_fp32=sv*n*4,
                   exact_logits_fp32=head_rows*4, exact_probabilities_fp32=head_rows*4,
                   channel_indices_u32=v*r*4 if routed else 0, token_indices_u32=selected_rows*4)
    index_payload = {"channel_ids": channels, "token_ids": tokens}
    result = {"schema_version":1, "scope":"one layer / one decode token / attention core only",
        "algorithm":"paper-v6-gqa-probability-sum", "config":asdict(c),
        "effective":{"group_size":h//v,"selected_tokens":k,"local_tokens":local,
                     "dense_fallback":not sv,"dense_fallback_kv_heads":sorted(fallback),
                     "sparse_kv_heads":sorted(sparse_groups),"selected_tokens_by_kv_head":list(map(len,tokens)),
                     "capacity_tokens":cap},
        "input_provenance":provenance or {"kind":"caller_supplied_indices_not_independently_verified"},
        "indices_sha256":hashlib.sha256(json.dumps(index_payload,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        "operations":operations, "dense_baseline_operations":dense_ops,
        "selection_reference":{"algorithm":"full power-of-two-padded bitonic sorting network",
            "token_sort_input_count":n-local if sv and k>local else 0,
            "note":"Deterministic comparison baseline, not torch.topk instruction count or optimal top-k; no RTL claimed"},
        "traffic":{"policy":"burst-aligned per-KV arrays; cold stage transactions; no cross-stage reuse; masked full-burst append writes",
            "by_stage":phy,"core_logical_read_bytes":logical_reads,"core_physical_read_bytes":reads,
            "dense_core_logical_read_bytes":v*2*n*d*b,"dense_core_physical_read_bytes":dense_reads,
            "core_read_ratio":reads/dense_reads,"append_logical_write_bytes":v*d*b*(3 if c.layout=='dual_k' else 2),
            "append_physical_write_bytes":writes,"dense_append_physical_write_bytes":dense_writes,
            "core_plus_append_physical_bytes":reads+writes,"dense_core_plus_append_physical_bytes":dense_reads+dense_writes,
            "construction_extra_read_bytes":phy['build_transposed_K_read']['physical_bytes'],
            "construction_extra_write_bytes":phy['build_transposed_K_write']['physical_bytes']},
        "storage":{"K_token_major_allocated_bytes":aligned_tensor,"V_token_major_allocated_bytes":aligned_tensor,
            "K_channel_major_allocated_bytes":aligned_tensor if c.layout=='dual_k' else 0,
            "total_cache_allocated_bytes":aligned_tensor*(3 if c.layout=='dual_k' else 2),
            "dense_cache_allocated_bytes":2*aligned_tensor,"cache_capacity_ratio":1.5 if c.layout=='dual_k' else 1.0,
            "materialized_reference_scratch_bytes":scratch,"materialized_reference_scratch_sum_bytes":sum(scratch.values()),
            "scratch_note":"Named tensors only, not SRAM minimum/peak. Sort workspace, response FIFOs, transpose/write-combine storage, bank padding and physical state uncharacterized"},
        "disabled":{"max4_summary":True,"learned_small_network":True,"bernoulli_selector_rng":True,
                    "fixed_eight_block_repair":True,"meanV_alpha_reallocation":True},
        "hardware":{"area_um2":None,"power_W":None,"energy_J":None,"sta_status":"not_run",
                    "evidence":"analytic_operation_and_burst_accounting"},
        "reference_implementation_extra":{"finite_validation_if_enabled":{
            "kv_elements_checked":2*v*n*d,"logical_read_bytes":2*v*n*d*b,
            "cold_burst_read_bytes":dense_reads,
            "included_in_core_totals":False},
            "full_tensor_fp32_conversion_and_mixed_group_where_cost":"not modeled; measure actual GPU reference",
            "note":"Core logical counts are not the PyTorch reference's actual kernel work or memory transactions"},
        "limitations":["No quality, GPU speed or ASIC PPA result is produced",
            "FP32 compute is an accounting format, not a bit-true arithmetic implementation",
            "Selected-channel and selected-row reads are separate physical passes even where payload overlaps",
            "Cold bursts are transactions, not DRAM row/command energy; cache reuse/write combining need explicit state",
            "Append writes assume masked bursts; devices requiring read-modify-write need additional read cost",
            "Prefill initialization/transpose is reported separately and never silently amortized over one token",
            "No QKV projection, QK-Norm, RoPE, Wo, residual, FFN, host or complete-model cost",
            "Probabilities, selector scratch and response/storage movement are not included in DRAM payload counts",
            "Per-head probability softmax and sum are retained; official raw-score-sum/k+1 code is a different variant"]}
    result["conditional_cycles"] = (_resource_work(operations, reads+writes, rates) if rates else None)
    result["dense_conditional_cycles"] = (_resource_work(dense_ops, dense_reads+dense_writes, rates) if rates else None)
    return result
