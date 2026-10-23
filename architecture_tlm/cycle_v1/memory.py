"""Online, finite-window address/bank memory model.

The built-in backend is a configurable banked timing model, NOT DRAMSys,
Ramulator, or a DRAM command/energy model. Requests are accepted online, after
their producers complete. A request spanning lines reserves actual per-bank
beats; replies may complete out of order. Overlapping accesses with a writer
are ordered by Kernel.add program order; nonoverlapping requests can overlap.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping

from .contracts import Clock, positive_int, nonnegative_int


@dataclass(frozen=True)
class MemoryRequest:
    address: int
    size_bytes: int
    write: bool = False
    data: bytes | None = None

    def __post_init__(self) -> None:
        nonnegative_int(self.address, "address")
        positive_int(self.size_bytes, "size_bytes")
        if self.data is not None:
            if not self.write:
                raise ValueError("read requests cannot supply write data")
            if not isinstance(self.data, bytes) or len(self.data) != self.size_bytes:
                raise ValueError("write data must be bytes of exactly size_bytes")

    def overlaps(self, other: "MemoryRequest") -> bool:
        return self.address < other.address + other.size_bytes and other.address < self.address + self.size_bytes


@dataclass(frozen=True)
class MemoryPort:
    name: str
    clock: Clock
    banks: int = 4
    line_bytes: int = 64
    window: int = 8
    latency_cycles: int = 4
    ii_cycles: int = 1
    ports_per_bank: int = 1
    bank_capacity: int = 8
    latency_by_address: Mapping[int, int] | None = None
    initial_data: Mapping[int, bytes] = field(default_factory=dict)
    strict_reads: bool = False
    provenance: str = "banked timing assumption; not a DRAM command model"
    response_ports: int = 1
    response_ii_cycles: int = 1

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("memory port name must be nonempty")
        for key in ("banks", "line_bytes", "window", "latency_cycles", "ii_cycles", "ports_per_bank", "bank_capacity", "response_ports", "response_ii_cycles"):
            positive_int(getattr(self, key), key)
        for address, latency in (self.latency_by_address or {}).items():
            nonnegative_int(address, "latency address")
            positive_int(latency, "latency override")
        for address, data in self.initial_data.items():
            nonnegative_int(address, "initial address")
            if not isinstance(data, bytes):
                raise ValueError("initial_data values must be bytes")

    def bank_beats(self, request: MemoryRequest) -> dict[int, int]:
        first = request.address // self.line_bytes
        last = (request.address + request.size_bytes - 1) // self.line_bytes
        return dict(sorted(Counter(line % self.banks for line in range(first, last + 1)).items()))


@dataclass(frozen=True)
class MemoryReservation:
    due_ps: int
    bank_beats: dict[int, int]
    # bank, physical port, beat count. All beats have reserved issue slots.
    assignments: tuple[tuple[int, int, int], ...]


class MemoryRuntime:
    def __init__(self, spec: MemoryPort):
        self.spec = spec
        self.next_issue = [[0] * spec.ports_per_bank for _ in range(spec.banks)]
        self.inflight = 0
        self.bank_inflight = [0] * spec.banks
        self.next_response = [0] * spec.response_ports
        self.data: dict[int, int] = {}
        for address, blob in spec.initial_data.items():
            self.write(address, blob)

    def write(self, address: int, data: bytes) -> None:
        self.data.update((address + offset, value) for offset, value in enumerate(data))

    def read(self, address: int, size_bytes: int) -> bytes:
        if self.spec.strict_reads:
            missing = next((a for a in range(address, address + size_bytes) if a not in self.data), None)
            if missing is not None:
                raise ValueError(f"uninitialized read on {self.spec.name} at address {missing}")
        return bytes(self.data.get(a, 0) for a in range(address, address + size_bytes))

    def plan(self, request: MemoryRequest, now_ps: int, *,
             inflight: int | None = None, bank_inflight: list[int] | None = None,
             next_issue: list[list[int]] | None = None) -> tuple[MemoryReservation | None, str | None]:
        count = self.inflight if inflight is None else inflight
        bank_count = self.bank_inflight if bank_inflight is None else bank_inflight
        issues = self.next_issue if next_issue is None else next_issue
        if count >= self.spec.window:
            return None, "memory_window_full"
        beats = self.spec.bank_beats(request)
        assignments: list[tuple[int, int, int]] = []
        last_beat_cycles = 0
        for bank, nbeats in beats.items():
            if bank_count[bank] >= self.spec.bank_capacity:
                return None, f"memory_bank_capacity:{bank}"
            available = [port for port, ready in enumerate(issues[bank]) if ready <= now_ps]
            if not available:
                return None, f"memory_bank_port:{bank}"
            # Balanced, deterministic allocation over ports available this edge.
            for index, port in enumerate(available):
                per_port = nbeats // len(available) + int(index < nbeats % len(available))
                if per_port:
                    assignments.append((bank, port, per_port))
                    last_beat_cycles = max(last_beat_cycles, (per_port - 1) * self.spec.ii_cycles)
        latency = (self.spec.latency_by_address or {}).get(request.address, self.spec.latency_cycles)
        due = now_ps + (latency + last_beat_cycles) * self.spec.clock.period_ps
        return MemoryReservation(due, beats, tuple(assignments)), None

    def future_ready(self, request: MemoryRequest, after_ps: int) -> int | None:
        """Earliest possible acceptance without assuming any future release."""
        if self.inflight >= self.spec.window:
            return None
        beats = self.spec.bank_beats(request)
        if any(self.bank_inflight[bank] >= self.spec.bank_capacity for bank in beats):
            return None
        return max(after_ps, *(min(self.next_issue[bank]) for bank in beats))

    def accept(self, reservation: MemoryReservation, now_ps: int) -> None:
        self.inflight += 1
        for bank in reservation.bank_beats:
            self.bank_inflight[bank] += 1
        for bank, port, beats in reservation.assignments:
            self.next_issue[bank][port] = now_ps + beats * self.spec.ii_cycles * self.spec.clock.period_ps

    def complete(self, reservation: MemoryReservation) -> None:
        self.inflight -= 1
        for bank in reservation.bank_beats:
            self.bank_inflight[bank] -= 1
