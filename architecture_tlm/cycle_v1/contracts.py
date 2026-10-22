"""Explicit, integer-time contracts for the cycle_v1 execution backend.

These are timing-model contracts, not RTL/STA or physical PPA evidence.  All
latencies and initiation intervals are expressed in the owning clock's cycles.
There is no implicit same-edge forwarding, including resource/buffer release.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from .kernel import Kernel
    from .memory import MemoryRequest


def positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")


def nonnegative_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer, got {value!r}")


@dataclass(frozen=True)
class Clock:
    name: str
    period_ps: int
    phase_ps: int = 0

    def __post_init__(self) -> None:
        positive_int(self.period_ps, "period_ps")
        nonnegative_int(self.phase_ps, "phase_ps")
        if self.phase_ps >= self.period_ps:
            raise ValueError("phase_ps must be smaller than period_ps")

    def is_edge(self, time_ps: int) -> bool:
        return time_ps >= self.phase_ps and (time_ps - self.phase_ps) % self.period_ps == 0

    def next_edge(self, time_ps: int, *, strict: bool = False) -> int:
        """First edge >= time_ps (or > time_ps when strict)."""
        target = time_ps + int(strict)
        if target <= self.phase_ps:
            return self.phase_ps
        return self.phase_ps + ((target - self.phase_ps + self.period_ps - 1) // self.period_ps) * self.period_ps


@dataclass(frozen=True)
class Resource:
    name: str
    clock: Clock
    latency_cycles: int
    ii_cycles: int = 1
    capacity: int = 1
    instances: int = 1
    provenance: str = "assumption; not STA calibrated"
    completion_ports: int = 1
    output_ii_cycles: int = 1

    def __post_init__(self) -> None:
        for key in ("latency_cycles", "ii_cycles", "capacity", "instances", "completion_ports", "output_ii_cycles"):
            positive_int(getattr(self, key), key)
        if not self.name:
            raise ValueError("resource name must be nonempty")


@dataclass(frozen=True)
class Buffer:
    """A finite FIFO occupancy or credit count; the caller declares its unit.

    inputs are removed at acceptance, outputs are inserted at completion.  For
    storage held across an operation chain, use credits: allocate on the first
    operation and return on a release operation dependent on the last use.
    """
    name: str
    capacity: int
    initial: int = 0
    unit: str = "token"

    def __post_init__(self) -> None:
        positive_int(self.capacity, "capacity")
        nonnegative_int(self.initial, "initial")
        if self.initial > self.capacity:
            raise ValueError("buffer initial occupancy exceeds capacity")


@dataclass(frozen=True)
class Operation:
    id: str
    resource: str
    deps: tuple[str, ...] = ()
    inputs: Mapping[str, int] = field(default_factory=dict)
    outputs: Mapping[str, int] = field(default_factory=dict)
    latency_cycles: int | None = None
    ii_cycles: int | None = None
    actions: Mapping[str, int] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    on_complete: Callable[["Kernel", "Operation"], Any] | None = field(default=None, repr=False, compare=False)
    memory: "MemoryRequest | None" = None
    earliest_ps: int = 0
    cdc_cycles: int = 0

    def __post_init__(self) -> None:
        if not self.id or not self.resource:
            raise ValueError("operation id and resource must be nonempty")
        if self.id in self.deps:
            raise ValueError("operation cannot depend on itself")
        if len(set(self.deps)) != len(self.deps):
            raise ValueError("duplicate dependency")
        for key in ("latency_cycles", "ii_cycles"):
            if getattr(self, key) is not None:
                positive_int(getattr(self, key), key)
        for mapping in (self.inputs, self.outputs):
            for name, amount in mapping.items():
                positive_int(amount, f"buffer amount {name}")
        for name, amount in self.actions.items():
            nonnegative_int(amount, f"action amount {name}")
        nonnegative_int(self.earliest_ps, "earliest_ps")
        nonnegative_int(self.cdc_cycles, "cdc_cycles")


@dataclass
class RunResult:
    finish_ps: int
    accepted_ps: dict[str, int]
    completion_ps: dict[str, int]
    actions: dict[str, int]
    trace: list[dict[str, Any]]
    memory_reads: dict[str, bytes]
    buffer_peak: dict[str, int]
    buffer_final: dict[str, int]
    resource_peak: dict[str, int]
    resource_stats: dict[str, dict[str, int]]
    steps: int
    mode: str

    def equivalence_payload(self) -> dict[str, Any]:
        """Everything that must agree between cycle and event execution.

        Only the number of visited time points and mode label are excluded.
        """
        return {name: getattr(self, name) for name in (
            "finish_ps", "accepted_ps", "completion_ps", "actions", "trace",
            "memory_reads", "buffer_peak", "buffer_final", "resource_peak", "resource_stats",
        )}
