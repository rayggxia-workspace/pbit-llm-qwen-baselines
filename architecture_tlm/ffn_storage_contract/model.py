"""Re-playable, integer-ps SRAM -> weight-consumer interface model.

This is NOT a cycle-accurate FFN, CDC implementation, physical SRAM integration,
or a measured throughput/PPA result. Two explicitly conditional contracts are
provided: complete local weight holding, or re-reading every weight for every
accepted sample while retaining that sample's bits/signs/bins. No random numbers
are generated here. The external source advances only at ``sample_begin``.

Each aligned word is one single-1RW-bank read. Issue-to-ready latency is an
integer number of SRAM cycles plus an explicitly assumed CDC delay. Fabric
occupancy is serial and rounded UP to integer ps. A response-buffer slot is
conservatively reserved from issue until destination commit, including time spent
in flight: there is no unpriced, unbounded queue at macro outputs. Local writes
and chunk consumption are explicit core-clock intervals. The resident candidate
requires a full-width local holding interface; its physical implementation is
unproven. Both schedules are conservative legal examples, not optima.
"""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from heapq import heapreplace
from typing import Iterable, Mapping, Sequence

PS_PER_SECOND = 10**12


class ContractError(ValueError):
    """The requested interface or replay trace violates a stated contract."""


def ceildiv(n: int, d: int) -> int:
    return (n + d - 1) // d


def edge_ps(cycle: int, hz: int) -> int:
    """Ceil of an absolute rational clock edge, without period-rounding drift."""
    return ceildiv(cycle * PS_PER_SECOND, hz)


def edge_at_or_after(t_ps: int, hz: int) -> int:
    """First cycle whose ceil-quantized edge is at or after integer t_ps."""
    return 0 if t_ps == 0 else ((t_ps - 1) * hz) // PS_PER_SECOND + 1


@dataclass(frozen=True)
class ContractConfig:
    mode: str = "resident"
    inputs: int = 64
    outputs: int = 64
    tiles: int = 8
    bins: int = 4
    samples: int = 32
    core_hz: int = 100_000_000
    sram_hz: int = 80_000_000
    # Default F/SS 4096x128 1RW library extraction, NOT interface STA.
    # ceil(1000*max(read_cycle_ns=10.9192, write_cycle_ns=11.0613)).
    sram_min_cycle_ps: int = 11_062
    sram_read_access_ps: int = 9_588
    banks: int = 16
    word_bytes: int = 16
    sram_capacity_bytes: int = 1_048_576
    fabric_bytes_per_second: int = 16_000_000_000
    read_latency_sram_cycles: int = 1
    cdc_delay_ps: int = 20_000
    response_buffer_bytes: int = 256
    local_weight_hold_bytes: int = 32_768
    local_hold_write_ports: int = 16
    local_hold_write_cycles: int = 1
    sample_hold_capacity_bits: int = 256
    accumulator_bits: int = 20
    counter_capacity_bits: int = 40_960
    sample_ii_core_cycles: int = 1
    resident_sample_core_cycles: int = 1
    chunk_compute_core_cycles: int = 1

    @property
    def wave_bytes(self) -> int:
        return self.inputs * self.outputs * self.tiles  # fixed signed W8

    @property
    def word_count(self) -> int:
        return self.wave_bytes // self.word_bytes

    @property
    def sample_state_bits(self) -> int:
        # Shared by all output tiles: sample bit, input sign, bin identifier.
        return self.inputs * (2 + (self.bins - 1).bit_length())

    @property
    def required_counter_bits(self) -> int:
        return self.tiles * self.outputs * self.bins * self.accumulator_bits


def candidate_config(mode: str = "resident", **overrides) -> ContractConfig:
    """Construct explicit budgets; overrides may deliberately make them invalid.

    The reread candidate reserves one 16B response by default. T64 is assigned
    signed21 because +64*128*64 is not representable in signed20. These are state
    budgets, not a counter implementation or an area/energy characterization.
    """
    cfg = replace(ContractConfig(), mode=mode, **overrides)
    budgets = {}
    if "local_weight_hold_bytes" not in overrides:
        budgets["local_weight_hold_bytes"] = cfg.wave_bytes if mode == "resident" else 0
    if "response_buffer_bytes" not in overrides:
        budgets["response_buffer_bytes"] = cfg.word_bytes * (cfg.banks if mode == "resident" else 1)
    if "sample_hold_capacity_bits" not in overrides:
        budgets["sample_hold_capacity_bits"] = cfg.sample_state_bits
    if "accumulator_bits" not in overrides:
        budgets["accumulator_bits"] = (128 * cfg.inputs * cfg.samples).bit_length() + 1
    cfg = replace(cfg, **budgets)
    if "counter_capacity_bits" not in overrides:
        cfg = replace(cfg, counter_capacity_bits=cfg.required_counter_bits)
    return cfg


def _check_config(cfg: ContractConfig) -> None:
    if cfg.mode not in ("resident", "reread"):
        raise ContractError("unsupported no-hold/direct-feed interface; choose explicit resident or reread")
    for name, value in asdict(cfg).items():
        if name == "mode":
            continue
        if type(value) is not int or value < 0:
            raise ContractError(name + " must be a nonnegative integer")
        if name not in ("cdc_delay_ps", "local_weight_hold_bytes") and value == 0:
            raise ContractError(name + " must be positive")
    if cfg.core_hz > PS_PER_SECOND or cfg.sram_hz > PS_PER_SECOND:
        raise ContractError("integer-ps model requires clocks <= 1 THz")
    if PS_PER_SECOND // cfg.sram_hz < cfg.sram_min_cycle_ps:
        raise ContractError("SRAM shortest clock interval violates declared macro minimum cycle")
    if (cfg.read_latency_sram_cycles * PS_PER_SECOND) // cfg.sram_hz < cfg.sram_read_access_ps:
        raise ContractError("read return latency is shorter than declared SRAM access")
    if cfg.wave_bytes % cfg.word_bytes:
        raise ContractError("wave must consist of complete aligned words; padding is not implicit")
    if cfg.response_buffer_bytes % cfg.word_bytes or cfg.response_buffer_bytes < cfg.word_bytes:
        raise ContractError("finite response capacity must contain whole words")
    if cfg.sram_capacity_bytes < cfg.wave_bytes:
        raise ContractError("SRAM cannot contain the weight wave")
    if cfg.mode == "resident" and cfg.local_weight_hold_bytes < cfg.wave_bytes:
        raise ContractError("full-wave consumption needs explicit complete local weight holding")
    if cfg.mode == "reread" and cfg.local_weight_hold_bytes != 0:
        raise ContractError("reread candidate declares zero persistent weight holding")
    if cfg.sample_hold_capacity_bits < cfg.sample_state_bits:
        raise ContractError("sample bits/signs/bins must be retained while weights are consumed")
    # Positive 8192 for W=-128 and negative input sign is a necessary boundary.
    if 128 * cfg.inputs * cfg.samples > (1 << (cfg.accumulator_bits - 1)) - 1:
        raise ContractError("signed accumulator cannot represent positive input-sign/W8 boundary")
    if cfg.counter_capacity_bits < cfg.required_counter_bits:
        raise ContractError("all tile/output/bin accumulator state must be allocated")


def _addresses(cfg: ContractConfig, addresses: Sequence[int] | None) -> list[int]:
    words = list(range(0, cfg.wave_bytes, cfg.word_bytes)) if addresses is None else list(addresses)
    if len(words) != cfg.word_count:
        raise ContractError("address map must cover every logical weight word exactly once")
    if any(type(a) is not int or a < 0 or a % cfg.word_bytes or
           a + cfg.word_bytes > cfg.sram_capacity_bytes for a in words):
        raise ContractError("address map contains unaligned or out-of-range words")
    if len(set(words)) != len(words):
        raise ContractError("distinct logical words cannot alias one physical SRAM word")
    return words


_RANK = {"read_ready": 0, "read_complete": 1, "hold_write": 2,
         "consume_chunk": 2, "consume_resident": 2, "sample_end": 3,
         "sample_begin": 4, "read_issue": 5, "fabric_start": 6}


def simulate(cfg: ContractConfig, addresses: Sequence[int] | None = None,
             sample_tokens: Sequence[str] | None = None) -> dict:
    """Return JSON-compatible config, address map, complete events and summary.

    ``sample_tokens`` identify external bit/sign/bin frames; the model does not
    fabricate or re-encode them between chunks. One accepted token is one source
    advancement. Counter *numerical* equivalence is intentionally a separate gate.
    """
    _check_config(cfg)
    words = _addresses(cfg, addresses)
    tokens = list(sample_tokens) if sample_tokens is not None else [f"external_frame_{i}" for i in range(cfg.samples)]
    if len(tokens) != cfg.samples or any(type(t) is not str or not t for t in tokens):
        raise ContractError("exactly one nonempty identity per external sample is required")
    events = []
    bank_next_cycle = [0] * cfg.banks
    response_free = [0] * (cfg.response_buffer_bytes // cfg.word_bytes)
    write_free_cycle = [0] * cfg.local_hold_write_ports
    fabric_free = 0
    issue_floor = 0
    compute_free_cycle = 0
    next_read_id = 0
    word_service_ps = ceildiv(cfg.word_bytes * PS_PER_SECOND, cfg.fabric_bytes_per_second)

    def emit(kind, t_ps, **fields):
        events.append(dict(kind=kind, t_ps=t_ps, **fields))

    def transfer_wave(earliest_ps, sample, token):
        nonlocal fabric_free, issue_floor, compute_free_cycle, next_read_id
        done = earliest_ps
        for index, address in enumerate(words):
            read_id = next_read_id
            next_read_id += 1
            bank = (address // cfg.word_bytes) % cfg.banks
            cycle = max(bank_next_cycle[bank], edge_at_or_after(
                max(earliest_ps, issue_floor, response_free[0]), cfg.sram_hz))
            issue = edge_ps(cycle, cfg.sram_hz)
            bank_next_cycle[bank] = cycle + 1
            issue_floor = issue
            identity = dict(read_id=read_id, word_index=index, address=address,
                            bank=bank, nbytes=cfg.word_bytes, sample=sample, token=token)
            emit("read_issue", issue, sram_cycle=cycle, **identity)
            ready = edge_ps(cycle + cfg.read_latency_sram_cycles, cfg.sram_hz) + cfg.cdc_delay_ps
            emit("read_ready", ready, **identity)
            fabric_start = max(ready, fabric_free)
            fabric_free = fabric_start + word_service_ps
            emit("fabric_start", fabric_start, end_ps=fabric_free, **identity)
            emit("read_complete", fabric_free, **identity)
            if cfg.mode == "resident":
                start_cycle = max(edge_at_or_after(fabric_free, cfg.core_hz), write_free_cycle[0])
                end_cycle = start_cycle + cfg.local_hold_write_cycles
                heapreplace(write_free_cycle, end_cycle)
                destination = "hold_write"
            else:
                start_cycle = max(edge_at_or_after(fabric_free, cfg.core_hz), compute_free_cycle)
                end_cycle = start_cycle + cfg.chunk_compute_core_cycles
                compute_free_cycle = end_cycle
                destination = "consume_chunk"
            commit = edge_ps(end_cycle, cfg.core_hz)
            emit(destination, commit, start_ps=edge_ps(start_cycle, cfg.core_hz),
                 start_core_cycle=start_cycle, end_core_cycle=end_cycle, **identity)
            heapreplace(response_free, commit)
            done = max(done, commit)
        return done

    ready = transfer_wave(0, -1, "preload") if cfg.mode == "resident" else 0
    previous_start_cycle = -cfg.sample_ii_core_cycles
    for sample, token in enumerate(tokens):
        start_cycle = max(edge_at_or_after(ready, cfg.core_hz),
                          previous_start_cycle + cfg.sample_ii_core_cycles)
        begin = edge_ps(start_cycle, cfg.core_hz)
        emit("sample_begin", begin, sample=sample, token=token,
             core_cycle=start_cycle, sequence_index=sample,
             held_sample_bits=cfg.sample_state_bits)
        if cfg.mode == "resident":
            end_cycle = start_cycle + cfg.resident_sample_core_cycles
            ready = edge_ps(end_cycle, cfg.core_hz)
            emit("consume_resident", ready, sample=sample, token=token,
                 start_ps=begin, start_core_cycle=start_cycle,
                 end_core_cycle=end_cycle, nbytes=cfg.wave_bytes)
        else:
            ready = transfer_wave(begin, sample, token)
        emit("sample_end", ready, sample=sample, token=token,
             consumed_bytes=cfg.wave_bytes)
        previous_start_cycle = start_cycle
    events.sort(key=lambda e: (e["t_ps"], _RANK[e["kind"]], e.get("read_id", -1)))
    summary = validate(cfg, events, words, tokens)
    return dict(config=asdict(cfg), addresses=words, sample_tokens=tokens,
                events=events, summary=summary)


def _require(test, message):
    if not test:
        raise ContractError(message)


def validate(cfg: ContractConfig, events: Iterable[Mapping],
             addresses: Sequence[int] | None = None,
             sample_tokens: Sequence[str] | None = None) -> dict:
    """Independent replay: resource, identity, capacity, causality and coverage.

    Does not invoke or compare against the scheduler. Delayed legal schedules are
    accepted. Address mapping and optional expected external identities are caller
    inputs, so changing the recorded addresses cannot silently change the contract.
    """
    _check_config(cfg)
    words = _addresses(cfg, addresses)
    tokens = None if sample_tokens is None else list(sample_tokens)
    if tokens is not None:
        _require(len(tokens) == cfg.samples, "expected sample identity count mismatch")
    reads = {}
    issued_logical_words = set()
    occupied_bank_edges = set()
    response_reserved = 0
    peak_response = 0
    local_words = set()
    local_write_intervals = []
    chunk_intervals = []
    fabric_intervals = []
    accepted = []
    completed = []
    sample_word_sets = {}
    resident_consumed = set()
    active = None
    last_time = -1
    last_rank = -1
    word_service = ceildiv(cfg.word_bytes * PS_PER_SECOND, cfg.fabric_bytes_per_second)

    def core_interval(e, duration):
        sc, ec = e.get("start_core_cycle"), e.get("end_core_cycle")
        _require(type(sc) is int and type(ec) is int and sc >= 0 and ec - sc == duration,
                 "wrong core interval length")
        _require(e.get("start_ps") == edge_ps(sc, cfg.core_hz) and e["t_ps"] == edge_ps(ec, cfg.core_hz),
                 "core interval is not on exact rational-clock edges")
        return e["start_ps"], e["t_ps"]

    for raw in events:
        e = dict(raw)
        kind, t = e.get("kind"), e.get("t_ps")
        _require(kind in _RANK, "unknown event")
        _require(type(t) is int and t >= 0, "event time must be nonnegative integer ps")
        rank = _RANK[kind]
        _require(t > last_time or (t == last_time and rank >= last_rank), "events are not in replay order")
        last_time, last_rank = t, rank
        if kind == "sample_begin":
            s, token, cycle = e.get("sample"), e.get("token"), e.get("core_cycle")
            _require(active is None, "random source advanced while an earlier sample was incomplete")
            _require(type(s) is int and s == len(accepted) and s < cfg.samples and e.get("sequence_index") == s,
                     "sample source advancement is missing, repeated or out of sequence")
            _require(type(token) is str and bool(token), "sample needs an external frame identity")
            _require(tokens is None or token == tokens[s], "external frame identity changed")
            _require(type(cycle) is int and cycle >= 0 and t == edge_ps(cycle, cfg.core_hz),
                     "sample acceptance must be a core edge")
            if accepted:
                _require(cycle - accepted[-1]["core_cycle"] >= cfg.sample_ii_core_cycles,
                         "source advanced faster than declared sample II")
            _require(e.get("held_sample_bits") == cfg.sample_state_bits, "sample/sign/bin holding is incomplete")
            if cfg.mode == "resident":
                _require(len(local_words) == cfg.word_count, "sample accepted before complete local weight commit")
            active = dict(sample=s, token=token, begin=t)
            accepted.append(e)
            sample_word_sets[s] = set()
            continue
        if kind in ("consume_resident", "sample_end"):
            _require(active is not None and e.get("sample") == active["sample"] and e.get("token") == active["token"],
                     "sample identity not held through consumption")
            s = active["sample"]
            if kind == "consume_resident":
                _require(cfg.mode == "resident" and s not in resident_consumed, "invalid/repeated resident consume")
                start, _ = core_interval(e, cfg.resident_sample_core_cycles)
                _require(start >= active["begin"] and len(local_words) == cfg.word_count,
                         "resident consume before input or weight commit")
                _require(e.get("nbytes") == cfg.wave_bytes, "resident consume must cover the complete wave")
                resident_consumed.add(s)
                active["last_consume"] = t
            else:
                _require((s in resident_consumed) if cfg.mode == "resident" else
                         (sample_word_sets[s] == set(range(cfg.word_count))),
                         "sample completed with missing weight words")
                _require(t >= active.get("last_consume", t + 1), "sample completed before last consume")
                _require(e.get("consumed_bytes") == cfg.wave_bytes, "sample byte total mismatch")
                completed.append(e)
                active = None
            continue

        rid = e.get("read_id")
        _require(type(rid) is int and rid >= 0, "read identity must be a nonnegative integer")
        if kind == "read_issue":
            _require(rid not in reads, "duplicate read identity")
            index, addr, bank = e.get("word_index"), e.get("address"), e.get("bank")
            _require(type(index) is int and 0 <= index < cfg.word_count and addr == words[index],
                     "read does not address the declared logical word")
            _require(bank == (addr // cfg.word_bytes) % cfg.banks and e.get("nbytes") == cfg.word_bytes,
                     "read bank or width mismatch")
            cycle = e.get("sram_cycle")
            _require(type(cycle) is int and cycle >= 0 and t == edge_ps(cycle, cfg.sram_hz),
                     "read issue is not on an exact SRAM edge")
            _require((bank, cycle) not in occupied_bank_edges, "single-1RW bank conflict on same clock edge")
            occupied_bank_edges.add((bank, cycle))
            if cfg.mode == "resident":
                _require(e.get("sample") == -1 and e.get("token") == "preload" and not accepted,
                         "resident reads must be preload transactions")
                _require((-1, index) not in issued_logical_words, "duplicate resident word load")
            else:
                _require(active is not None and e.get("sample") == active["sample"] and e.get("token") == active["token"],
                         "reread must belong to the currently frozen sample")
                _require((e["sample"], index) not in issued_logical_words, "duplicate word read within sample")
            issued_logical_words.add((e["sample"], index))
            reads[rid] = dict(e, stage="issued")
            response_reserved += cfg.word_bytes
            peak_response = max(peak_response, response_reserved)
            _require(response_reserved <= cfg.response_buffer_bytes,
                     "finite response/in-flight reservation capacity exceeded")
            continue
        _require(rid in reads, "transaction used before read issue")
        r = reads[rid]
        _require(all(e.get(k) == r[k] for k in ("word_index", "address", "bank", "nbytes", "sample", "token")),
                 "read transaction identity changed")
        if kind == "read_ready":
            expected = edge_ps(r["sram_cycle"] + cfg.read_latency_sram_cycles, cfg.sram_hz) + cfg.cdc_delay_ps
            _require(r["stage"] == "issued" and t == expected, "read return latency changed or duplicate ready")
            r.update(stage="ready", ready=t)
        elif kind == "fabric_start":
            _require(r["stage"] == "ready" and t >= r["ready"], "fabric used before read return")
            _require(type(e.get("end_ps")) is int and e["end_ps"] - t == word_service,
                     "fabric service rate or integer-ps rounding violated")
            fabric_intervals.append((t, e["end_ps"]))
            r.update(stage="fabric", fabric_end=e["end_ps"])
        elif kind == "read_complete":
            _require(r["stage"] == "fabric" and t == r["fabric_end"], "read complete before fabric service ends")
            r.update(stage="complete", complete=t)
        elif kind in ("hold_write", "consume_chunk"):
            _require(r["stage"] == "complete", "weight used before valid read completion or used twice")
            duration = cfg.local_hold_write_cycles if kind == "hold_write" else cfg.chunk_compute_core_cycles
            start, end = core_interval(e, duration)
            _require(start >= r["complete"], "destination starts before valid read completion")
            if kind == "hold_write":
                _require(cfg.mode == "resident" and not accepted, "unexpected weight hold write")
                local_write_intervals.append((start, end))
                _require(r["word_index"] not in local_words, "local word overwritten")
                local_words.add(r["word_index"])
                _require(len(local_words) * cfg.word_bytes <= cfg.local_weight_hold_bytes,
                         "persistent local weight hold capacity exceeded")
            else:
                _require(cfg.mode == "reread" and active is not None and
                         r["sample"] == active["sample"] and r["token"] == active["token"],
                         "chunk consumed using a different or completed sample")
                _require(start >= active["begin"], "chunk used before sample acceptance")
                chunk_intervals.append((start, end))
                _require(r["word_index"] not in sample_word_sets[r["sample"]], "weight chunk consumed twice")
                sample_word_sets[r["sample"]].add(r["word_index"])
                active["last_consume"] = t
            response_reserved -= cfg.word_bytes
            r["stage"] = "used"
        else:
            raise ContractError("invalid event for a read transaction")

    def check_intervals(intervals, ports, label):
        changes = sorted([(a, 1) for a, b in intervals] + [(b, -1) for a, b in intervals])
        current = 0
        for _, change in changes:  # end before start on the same boundary
            current += change
            _require(0 <= current <= ports, label + " occupancy exceeds declared ports")

    check_intervals(fabric_intervals, 1, "fabric")
    check_intervals(local_write_intervals, cfg.local_hold_write_ports, "local hold write")
    check_intervals(chunk_intervals, 1, "chunk compute")
    _require(active is None and len(completed) == cfg.samples, "incomplete sample stream")
    expected_reads = cfg.word_count * (1 if cfg.mode == "resident" else cfg.samples)
    _require(len(reads) == expected_reads and all(r["stage"] == "used" for r in reads.values()),
             "missing, extra or unconsumed read transactions")
    _require(response_reserved == 0, "unreleased response reservation")
    bank_counts = Counter((a // cfg.word_bytes) % cfg.banks for a in words)
    # Separate necessary resource-only lower bounds from our actual schedule.
    first_ready = edge_ps(cfg.read_latency_sram_cycles, cfg.sram_hz) + cfg.cdc_delay_ps
    bank_ready = edge_ps(max(bank_counts.values()) - 1 + cfg.read_latency_sram_cycles,
                         cfg.sram_hz) + cfg.cdc_delay_ps
    lower_bound = max(bank_ready + word_service, first_ready + cfg.word_count * word_service)
    start_times = [e["t_ps"] for e in accepted]
    start_cycles = [e["core_cycle"] for e in accepted]
    return dict(
        scope="standalone conditional SRAM-to-weight-consumer contract; not full FFN or physical PPA",
        mode=cfg.mode, wave_bytes=cfg.wave_bytes, samples_completed=len(completed),
        source_advancements=len(accepted), external_sample_source="accepted identities only; RNG not simulated",
        read_transactions=len(reads), sram_read_bytes=len(reads) * cfg.word_bytes,
        weight_bytes_consumed=cfg.wave_bytes * cfg.samples,
        reads_per_sample=(cfg.word_count if cfg.mode == "reread" else 0),
        preload_read_transactions=(cfg.word_count if cfg.mode == "resident" else 0),
        accepted_sample_times_ps=start_times,
        accepted_sample_interval_core_cycles=[b - a for a, b in zip(start_cycles, start_cycles[1:])],
        first_sample_ps=start_times[0], end_ps=completed[-1]["t_ps"],
        actual_schedule="conservative finite-buffer schedule, not optimal throughput",
        weight_transfer_resource_lower_bound_ps_per_wave=lower_bound,
        lower_bound_scope="necessary SRAM/fabric bounds only; excludes local commit, consumer and queue constraints",
        fabric_word_service_ps=word_service, fabric_busy_ps=len(reads) * word_service,
        bank_count=cfg.banks, bank_port_contract="one read OR write per bank edge; this trace is read-only",
        read_return_latency=dict(sram_cycles=cfg.read_latency_sram_cycles, cdc_assumption_ps=cfg.cdc_delay_ps),
        sram_timing_screen=dict(minimum_cycle_ps=cfg.sram_min_cycle_ps,
                                read_access_ps=cfg.sram_read_access_ps,
                                shortest_clock_interval_ps=PS_PER_SECOND // cfg.sram_hz,
                                evidence="default parameters from F/SS 4096x128 1RW vendor-library extraction; not new STA",
                                source="architecture_tlm/llama7b/runtime/results/sram_calibration_v1_20261016/calibration.json",
                                generic_overrides="changed geometry or timing parameters require independent binding; not vendor-certified"),
        state_bits=dict(local_weights_allocated=cfg.local_weight_hold_bytes * 8,
                        local_weights_peak=len(local_words) * cfg.word_bytes * 8,
                        response_and_inflight_reserved=cfg.response_buffer_bytes * 8,
                        response_and_inflight_peak=peak_response * 8,
                        sample_bit_sign_bin_required=cfg.sample_state_bits,
                        sample_bit_sign_bin_allocated=cfg.sample_hold_capacity_bits,
                        signed_bin_accumulators_required=cfg.required_counter_bits,
                        signed_bin_accumulators_allocated=cfg.counter_capacity_bits),
        counter_contract=dict(representation="signed per-tile/output/bin integer sums",
                              accumulator_bits=cfg.accumulator_bits,
                              absolute_bound=128 * cfg.inputs * cfg.samples,
                              weight_contribution_visits=cfg.wave_bytes * cfg.samples,
                              numerical_value_check="separate counter equivalence gate required"),
        physical_conditions=["resident full-width weight holding requires registers or a custom macro implementation",
                             "macro clock check is period screening only, not interface timing or Q-hold validation",
                             "CDC delay is an interface assumption, not CDC safety verification",
                             "consumer latency/II and local hold write ports are explicit uncharacterized parameters",
                             "response reservation includes all in-flight word storage; control metadata is not priced",
                             "SRAM contents are assumed loaded and immutable; upstream DMA/write arbitration excluded"],
        area_um2=None, energy_pJ=None)
