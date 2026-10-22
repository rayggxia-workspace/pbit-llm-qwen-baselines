"""Synchronous two-phase execution and an event-skipping implementation.

At each timestamp, completion and acceptance decisions read the PRE-edge
state. They reserve against separate shadows and commit together. Thus a
producer's output, freed buffer space, and freed pipeline slot cannot be used
by another operation on the same edge. No implicit combinational bypass exists.

Callbacks run only after the entire edge commits. They may add operations;
added operations cannot start at that timestamp. Numeric callbacks must use
declared dependencies for shared state, rather than relying on callback order.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable

from .contracts import Buffer, Clock, Operation, Resource, RunResult, nonnegative_int, positive_int
from .memory import MemoryPort, MemoryReservation, MemoryRuntime


class DeadlockError(RuntimeError):
    """No future accepted/completed operation can change the stalled graph."""


@dataclass
class _Flight:
    op: Operation
    accepted_ps: int
    due_ps: int
    instance: int | None
    reservation: MemoryReservation | None = None


@dataclass
class _ClockProcess:
    clock: Clock
    callback: Callable[["Kernel"], bool]
    active: bool = False
    not_before_ps: int = 0
    started: bool = False
    ticks: int = 0


class Kernel:
    def __init__(self, resources: Iterable[Resource], buffers: Iterable[Buffer] = (),
                 memory_ports: Iterable[MemoryPort] = ()):
        resources, buffers, memory_ports = list(resources), list(buffers), list(memory_ports)
        self.resources = {r.name: r for r in resources}
        self.buffer_specs = {b.name: b for b in buffers}
        self.memory_ports = {m.name: m for m in memory_ports}
        if len(self.resources) != len(resources) or len(self.buffer_specs) != len(buffers) or len(self.memory_ports) != len(memory_ports):
            raise ValueError("duplicate resource, buffer, or memory port name")
        if self.resources.keys() & self.memory_ports.keys():
            raise ValueError("memory port and compute resource names must be distinct")
        self._clocks: dict[str, Clock] = {}
        for spec in [*resources, *memory_ports]:
            clock = spec.clock
            if clock.name in self._clocks and self._clocks[clock.name] != clock:
                raise ValueError("a clock name cannot describe different clocks")
            self._clocks[clock.name] = clock
        self._memory = {m.name: MemoryRuntime(m) for m in memory_ports}
        self.buffers = {b.name: b.initial for b in buffers}
        self.buffer_peak = dict(self.buffers)
        self.resource_peak = {name: 0 for name in [*self.resources, *self.memory_ports]}
        self._next_issue = {r.name: [0] * r.instances for r in resources}
        self._occupancy = {r.name: [0] * r.instances for r in resources}
        self._next_complete = {r.name: [[0] * r.completion_ports for _ in range(r.instances)] for r in resources}
        self.operations: dict[str, Operation] = {}
        self._sequence: dict[str, int] = {}
        self._born_ps: dict[str, int] = {}
        self._pending: dict[str, Operation] = {}
        self._flights: dict[str, _Flight] = {}
        self.accepted: dict[str, int] = {}
        self.completed: dict[str, int] = {}
        self.memory_reads: dict[str, bytes] = {}
        self.actions: Counter[str] = Counter()
        self.trace: list[dict[str, Any]] = []
        self._last_stall: dict[tuple[str, str], str | None] = {}
        self._ever_evaluated: set[tuple[str, str]] = set()
        self._stats = {name: {"accepted": 0, "completed": 0, "execution_ps": 0, "held_ps": 0, "output_blocked_ps": 0}
                       for name in self.resource_peak}
        self.now_ps = 0
        self._running = False
        self._ran = False
        self._processes: dict[str, _ClockProcess] = {}

    def register_clock_process(self, name: str, clock: Clock, callback: Callable[["Kernel"], bool]) -> None:
        """Register an initially sleeping native state machine.

        callback(kernel) executes once per active local edge and returns whether
        to remain active. It runs AFTER all kernel commits but BEFORE operation
        completion callbacks; newly enqueued requests therefore cannot be used
        by a process on their enqueue edge. Active processes prevent event mode
        from skipping their clock edges. Their native action accounting stays
        with the adapter; a process tick is not automatically a random draw.
        """
        if self._ran and not self._running:
            raise RuntimeError("a finished Kernel is single-use")
        if not name or name in self._processes or not callable(callback):
            raise ValueError("clock process needs a unique name and callable")
        if clock.name in self._clocks and self._clocks[clock.name] != clock:
            raise ValueError("a clock name cannot describe different clocks")
        self._clocks[clock.name] = clock
        self._processes[name] = _ClockProcess(clock, callback)

    def wake_clock_process(self, name: str) -> None:
        process = self._processes[name]
        if not process.active:
            process.active = True
            process.not_before_ps = self.now_ps + 1 if self._running else 0

    def clock_for(self, resource: str) -> Clock:
        if resource in self.resources:
            return self.resources[resource].clock
        return self.memory_ports[resource].clock

    def add(self, op: Operation) -> Operation:
        if self._ran and not self._running:
            raise RuntimeError("a finished Kernel is single-use; construct a fresh Kernel")
        if op.id in self.operations:
            raise ValueError(f"duplicate operation id: {op.id}")
        if op.resource not in self.resources and op.resource not in self.memory_ports:
            raise ValueError(f"unknown resource {op.resource!r}")
        if (op.memory is not None) != (op.resource in self.memory_ports):
            raise ValueError("memory-port operations require MemoryRequest; compute operations cannot carry one")
        if op.memory is not None and (op.latency_cycles is not None or op.ii_cycles is not None):
            raise ValueError("memory timing belongs to MemoryPort, not an Operation override")
        for name, amount in [*op.inputs.items(), *op.outputs.items()]:
            if name not in self.buffer_specs:
                raise ValueError(f"unknown buffer {name!r}")
            if amount > self.buffer_specs[name].capacity:
                raise ValueError(f"operation {op.id} exceeds buffer {name} capacity")
        # A caller retaining its configuration dictionaries must not mutate the
        # graph after acceptance. Snapshot mappings at insertion.
        op = replace(op, deps=tuple(op.deps), inputs=dict(op.inputs), outputs=dict(op.outputs),
                     actions=dict(op.actions), metadata=dict(op.metadata))
        self._sequence[op.id] = len(self.operations)
        self._born_ps[op.id] = self.now_ps if self._running else -1
        self.operations[op.id] = op
        self._pending[op.id] = op
        return op

    def load_memory(self, port: str, address: int, data: bytes) -> None:
        if self._running or self._ran:
            raise RuntimeError("load_memory is for initial state only; use a write request during execution")
        nonnegative_int(address, "address")
        if not isinstance(data, bytes):
            raise ValueError("initial memory data must be bytes")
        self._memory[port].write(address, data)

    def read_memory(self, port: str, address: int, size_bytes: int) -> bytes:
        nonnegative_int(address, "address")
        positive_int(size_bytes, "size_bytes")
        return self._memory[port].read(address, size_bytes)

    def _dependency_ready(self, op: Operation) -> tuple[int | None, str | None]:
        missing = [dep for dep in op.deps if dep not in self.completed]
        if missing:
            return None, "dependency:" + ",".join(sorted(missing))
        clock = self.clock_for(op.resource)
        ready = max(op.earliest_ps, self._born_ps[op.id] + 1)
        for dep in op.deps:
            dep_time = self.completed[dep]
            dep_clock = self.clock_for(self.operations[dep].resource)
            if dep_clock != clock and op.cdc_cycles:
                ready = max(ready, clock.next_edge(dep_time, strict=True) + (op.cdc_cycles - 1) * clock.period_ps)
            else:
                ready = max(ready, dep_time + 1)
        return ready, None

    def _memory_hazard(self, op: Operation) -> str | None:
        if op.memory is None:
            return None
        for other in self.operations.values():
            if (self._sequence[other.id] >= self._sequence[op.id] or other.id in self.completed
                    or other.resource != op.resource or other.memory is None):
                continue
            if (op.memory.write or other.memory.write) and op.memory.overlaps(other.memory):
                return "memory_order:" + other.id
        return None

    def _stall(self, op: Operation, phase: str, reason: str) -> None:
        key = (op.id, phase)
        self._ever_evaluated.add(key)
        if self._last_stall.get(key) != reason:
            self.trace.append({"time_ps": self.now_ps, "kind": "stall", "phase": phase,
                               "op": op.id, "resource": op.resource, "reason": reason})
            self._last_stall[key] = reason

    def _resolve_stall(self, op: Operation, phase: str) -> None:
        key = (op.id, phase)
        self._ever_evaluated.add(key)
        if self._last_stall.get(key) is not None:
            self.trace.append({"time_ps": self.now_ps, "kind": "stall_end", "phase": phase,
                               "op": op.id, "resource": op.resource, "reason": self._last_stall[key]})
            self._last_stall[key] = None

    def _base_reason(self, op: Operation, time_ps: int, inputs: dict[str, int]) -> str | None:
        ready, reason = self._dependency_ready(op)
        if reason is not None:
            return reason
        if time_ps < ready:
            return "not_visible_yet"
        for name, amount in sorted(op.inputs.items()):
            if inputs[name] < amount:
                return "input_empty:" + name
        return self._memory_hazard(op)

    def _current_reason(self, op: Operation, time_ps: int) -> str | None:
        """Read-only reason, before any peers arbitrate on that future edge."""
        reason = self._base_reason(op, time_ps, self.buffers)
        if reason is not None:
            return reason
        if op.memory is not None:
            return self._memory[op.resource].plan(op.memory, time_ps)[1]
        spec = self.resources[op.resource]
        if all(n >= spec.capacity for n in self._occupancy[op.resource]):
            return "resource_capacity"
        if not any(n < spec.capacity and self._next_issue[op.resource][i] <= time_ps
                   for i, n in enumerate(self._occupancy[op.resource])):
            return "resource_ii"
        return None

    def _older_inflight(self, flight: _Flight, selected: set[str] | None = None) -> str | None:
        if flight.reservation is not None or not self.resources[flight.op.resource].in_order_completion:
            return None
        selected = selected or set()
        earlier = [other for other in self._flights.values()
                   if other.op.resource == flight.op.resource and other.instance == flight.instance
                   and (other.accepted_ps, other.op.id) < (flight.accepted_ps, flight.op.id)
                   and other.op.id not in selected]
        if not earlier:
            return None
        return min(earlier, key=lambda item: (item.accepted_ps, item.op.id)).op.id

    def _completion_sort_key(self, flight: _Flight) -> tuple:
        if flight.reservation is None and self.resources[flight.op.resource].in_order_completion:
            return flight.op.resource, flight.instance, flight.accepted_ps, flight.op.id
        return flight.op.resource, -1, flight.due_ps, flight.op.id

    def _completion_reason(self, flight: _Flight, time_ps: int) -> str | None:
        op = flight.op
        earlier = self._older_inflight(flight)
        if earlier is not None:
            return "completion_order:" + earlier
        for name, amount in sorted(op.outputs.items()):
            if self.buffers[name] + amount > self.buffer_specs[name].capacity:
                return "output_full:" + name
        if flight.reservation is not None:
            if min(self._memory[op.resource].next_response) > time_ps:
                return "memory_response_port"
        elif min(self._next_complete[op.resource][flight.instance]) > time_ps:
            return "completion_port"
        return None

    def _step(self, time_ps: int) -> None:
        self.now_ps = time_ps
        active_processes = [(name, process) for name, process in sorted(self._processes.items())
                            if process.active and process.not_before_ps <= time_ps and process.clock.is_edge(time_ps)]
        # COMPLETE decisions use old buffer occupancies. Independently accepted
        # consumers do not provide same-edge room for these outputs.
        output_shadow = dict(self.buffers)
        finishing: list[_Flight] = []
        read_results: dict[str, bytes] = {}
        complete_issue = {name: [ports.copy() for ports in instances]
                          for name, instances in self._next_complete.items()}
        response_issue = {name: runtime.next_response.copy() for name, runtime in self._memory.items()}
        selected_completion_ports: dict[str, int] = {}
        for flight in sorted(self._flights.values(), key=self._completion_sort_key):
            op = flight.op
            if flight.due_ps > time_ps or not self.clock_for(op.resource).is_edge(time_ps):
                continue
            earlier = self._older_inflight(flight, {f.op.id for f in finishing})
            if earlier is not None:
                self._stall(op, "complete", "completion_order:" + earlier)
                continue
            full = next((name for name, amount in sorted(op.outputs.items())
                         if output_shadow[name] + amount > self.buffer_specs[name].capacity), None)
            if full is not None:
                self._stall(op, "complete", "output_full:" + full)
                continue
            available = (response_issue[op.resource] if flight.reservation is not None
                         else complete_issue[op.resource][flight.instance])
            port = next((i for i, ready in enumerate(available) if ready <= time_ps), None)
            if port is None:
                self._stall(op, "complete", "memory_response_port" if flight.reservation is not None else "completion_port")
                continue
            selected_completion_ports[op.id] = port
            complete_ii = (self.memory_ports[op.resource].response_ii_cycles if flight.reservation is not None
                           else self.resources[op.resource].output_ii_cycles)
            available[port] = time_ps + complete_ii * self.clock_for(op.resource).period_ps
            self._resolve_stall(op, "complete")
            for name, amount in op.outputs.items():
                output_shadow[name] += amount
            finishing.append(flight)
            # Read bytes before ANY completion write is committed. Overlapping
            # read/write requests cannot be co-inflight because of the scoreboard.
            if op.memory is not None and not op.memory.write:
                read_results[op.id] = self._memory[op.resource].read(op.memory.address, op.memory.size_bytes)

        # ACCEPT decisions also use PRE-edge state, including occupied slots of
        # operations selected above for completion.
        input_shadow = dict(self.buffers)
        occupancy = {name: values.copy() for name, values in self._occupancy.items()}
        issue = {name: values.copy() for name, values in self._next_issue.items()}
        mem_shadow = {name: [runtime.inflight, runtime.bank_inflight.copy(), [x.copy() for x in runtime.next_issue]]
                      for name, runtime in self._memory.items()}
        starting: list[_Flight] = []
        for op in sorted(self._pending.values(), key=lambda op: op.id):
            clock = self.clock_for(op.resource)
            if not clock.is_edge(time_ps):
                continue
            reason = self._base_reason(op, time_ps, input_shadow)
            instance = None
            reservation = None
            if reason is None and op.memory is not None:
                runtime = self._memory[op.resource]
                ms = mem_shadow[op.resource]
                reservation, reason = runtime.plan(op.memory, time_ps, inflight=ms[0], bank_inflight=ms[1], next_issue=ms[2])
                if reservation is not None:
                    due_ps = reservation.due_ps
            elif reason is None:
                spec = self.resources[op.resource]
                candidates = [i for i in range(spec.instances)
                              if occupancy[op.resource][i] < spec.capacity and issue[op.resource][i] <= time_ps]
                if not candidates:
                    reason = ("resource_capacity" if all(n >= spec.capacity for n in occupancy[op.resource])
                              else "resource_ii")
                else:
                    instance = candidates[0]
                    latency = op.latency_cycles or spec.latency_cycles
                    due_ps = time_ps + latency * clock.period_ps
            if reason is not None:
                self._stall(op, "accept", reason)
                continue
            self._resolve_stall(op, "accept")
            for name, amount in op.inputs.items():
                input_shadow[name] -= amount
            if reservation is not None:
                ms = mem_shadow[op.resource]
                ms[0] += 1
                for bank in reservation.bank_beats:
                    ms[1][bank] += 1
                for bank, port, beats in reservation.assignments:
                    ms[2][bank][port] = time_ps + beats * self.memory_ports[op.resource].ii_cycles * clock.period_ps
            else:
                spec = self.resources[op.resource]
                occupancy[op.resource][instance] += 1
                issue[op.resource][instance] = time_ps + (op.ii_cycles or spec.ii_cycles) * clock.period_ps
            starting.append(_Flight(op, time_ps, due_ps, instance, reservation))

        # COMMIT: all decisions above are fixed. Completion and acceptance trace
        # events have a fixed canonical order, independent of registration order.
        for flight in finishing:
            op = flight.op
            self.completed[op.id] = time_ps
            del self._flights[op.id]
            if flight.reservation is not None:
                runtime = self._memory[op.resource]
                runtime.complete(flight.reservation)
                runtime.next_response[selected_completion_ports[op.id]] = time_ps + runtime.spec.response_ii_cycles * runtime.spec.clock.period_ps
                if op.memory.write and op.memory.data is not None:
                    runtime.write(op.memory.address, op.memory.data)
            else:
                self._occupancy[op.resource][flight.instance] -= 1
                spec = self.resources[op.resource]
                self._next_complete[op.resource][flight.instance][selected_completion_ports[op.id]] = time_ps + spec.output_ii_cycles * spec.clock.period_ps
            for name, amount in op.outputs.items():
                self.buffers[name] += amount
            stats = self._stats[op.resource]
            stats["completed"] += 1
            stats["execution_ps"] += flight.due_ps - flight.accepted_ps
            stats["held_ps"] += time_ps - flight.accepted_ps
            stats["output_blocked_ps"] += time_ps - flight.due_ps
            self.trace.append({"time_ps": time_ps, "kind": "complete", "op": op.id,
                               "resource": op.resource, "instance": flight.instance,
                               "completion_port": selected_completion_ports[op.id],
                               "accepted_ps": flight.accepted_ps, "due_ps": flight.due_ps,
                               "outputs": dict(op.outputs), "metadata": dict(op.metadata)})
        self.memory_reads.update(read_results)
        for flight in starting:
            op = flight.op
            del self._pending[op.id]
            self._flights[op.id] = flight
            self.accepted[op.id] = time_ps
            for name, amount in op.inputs.items():
                self.buffers[name] -= amount
            if flight.reservation is not None:
                runtime = self._memory[op.resource]
                runtime.accept(flight.reservation, time_ps)
                direction = "write" if op.memory.write else "read"
                self.actions[f"memory.{op.resource}.{direction}_bytes"] += op.memory.size_bytes
                self.actions[f"memory.{op.resource}.{direction}_requests"] += 1
                self.actions[f"memory.{op.resource}.{direction}_beats"] += sum(flight.reservation.bank_beats.values())
            else:
                spec = self.resources[op.resource]
                self._occupancy[op.resource][flight.instance] += 1
                self._next_issue[op.resource][flight.instance] = time_ps + (op.ii_cycles or spec.ii_cycles) * spec.clock.period_ps
            self.actions.update(op.actions)
            self._stats[op.resource]["accepted"] += 1
            entry = {"time_ps": time_ps, "kind": "accept", "op": op.id,
                     "resource": op.resource, "instance": flight.instance, "due_ps": flight.due_ps,
                     "inputs": dict(op.inputs), "actions": dict(op.actions), "metadata": dict(op.metadata)}
            if op.memory is not None:
                entry.update(address=op.memory.address, size_bytes=op.memory.size_bytes, write=op.memory.write,
                             bank_beats=flight.reservation.bank_beats,
                             bank_ports=[list(x) for x in flight.reservation.assignments])
            self.trace.append(entry)
        for name, value in self.buffers.items():
            if not 0 <= value <= self.buffer_specs[name].capacity:
                raise AssertionError(f"buffer conservation failed: {name}={value}")
            self.buffer_peak[name] = max(self.buffer_peak[name], value)
        for name in self.resource_peak:
            used = self._memory[name].inflight if name in self._memory else sum(self._occupancy[name])
            self.resource_peak[name] = max(self.resource_peak[name], used)
        for name, process in active_processes:
            if not process.started:
                self.trace.append({"time_ps": time_ps, "kind": "process_start", "process": name,
                                   "clock": process.clock.name})
                process.started = True
            process.ticks += 1
            keep_active = process.callback(self)
            if not isinstance(keep_active, bool):
                raise ValueError("clock process callback must return bool")
            process.active = keep_active
            if not keep_active:
                self.trace.append({"time_ps": time_ps, "kind": "process_stop", "process": name,
                                   "clock": process.clock.name})
                process.started = False
        for flight in finishing:
            if flight.op.on_complete is not None:
                flight.op.on_complete(self, flight.op)

    def _next_event_time(self, after_ps: int) -> int | None:
        times: list[int] = []
        for process in self._processes.values():
            if process.active:
                times.append(process.clock.next_edge(max(after_ps + 1, process.not_before_ps)))
        for flight in self._flights.values():
            clock = self.clock_for(flight.op.resource)
            if flight.due_ps > after_ps:
                times.append(flight.due_ps)
            else:
                reason = self._completion_reason(flight, clock.next_edge(after_ps, strict=True))
                if reason is None or reason != self._last_stall.get((flight.op.id, "complete")):
                    times.append(clock.next_edge(after_ps, strict=True))
                if reason in ("completion_port", "memory_response_port"):
                    next_port = (min(self._memory[flight.op.resource].next_response) if flight.reservation is not None
                                 else min(self._next_complete[flight.op.resource][flight.instance]))
                    times.append(clock.next_edge(max(after_ps + 1, next_port)))
        for op in self._pending.values():
            clock = self.clock_for(op.resource)
            # Record the initial stall at its first local edge, even if it will
            # wait for a long dependency. Later unchanged stalls are compressed.
            if (op.id, "accept") not in self._ever_evaluated:
                times.append(clock.next_edge(max(after_ps + 1, self._born_ps[op.id] + 1)))
                continue
            next_edge = clock.next_edge(after_ps, strict=True)
            # A partial dependency completion or a newly freed slot can change
            # the explanatory stall before the operation becomes executable.
            # Preserve that transition exactly, not just the final timings.
            if self._current_reason(op, next_edge) != self._last_stall.get((op.id, "accept")):
                times.append(next_edge)
            ready, reason = self._dependency_ready(op)
            if reason is not None:
                continue
            # Visibility expiration is itself an explanatory state transition:
            # a later resource availability must not hide the newly exposed
            # input/bank/port stall from the event trace.
            if ready > after_ps:
                times.append(clock.next_edge(ready))
            if any(self.buffers[name] < amount for name, amount in op.inputs.items()):
                continue
            if self._memory_hazard(op) is not None:
                continue
            earliest = max(after_ps + 1, ready)
            if op.memory is not None:
                runtime = self._memory[op.resource]
                possible = runtime.future_ready(op.memory, earliest)
                if possible is not None:
                    times.append(clock.next_edge(possible))
                # Several banks may unblock on different edges. Preserve the
                # reason change at each earlier bank rather than jumping to
                # the last bank that makes the whole descriptor acceptable.
                for bank in runtime.spec.bank_beats(op.memory):
                    bank_ready = min(runtime.next_issue[bank])
                    if bank_ready > after_ps:
                        times.append(clock.next_edge(max(earliest, bank_ready)))
            else:
                spec = self.resources[op.resource]
                candidates = [max(earliest, self._next_issue[op.resource][i]) for i in range(spec.instances)
                              if self._occupancy[op.resource][i] < spec.capacity]
                if candidates:
                    times.append(clock.next_edge(min(candidates)))
        return min(times) if times else None

    def _diagnostic(self) -> str:
        reasons = {op.id: self._base_reason(op, self.now_ps, self.buffers) or self._last_stall.get((op.id, "accept"))
                   for op in self._pending.values()}
        reasons.update({op_id: self._last_stall.get((op_id, "complete"), "inflight") for op_id in self._flights})
        return f"time_ps={self.now_ps}; pending/held={reasons}; buffers={self.buffers}"

    def run(self, mode: str = "event", *, max_time_ps: int = 10**12, max_steps: int = 10**7) -> RunResult:
        if mode not in ("cycle", "event"):
            raise ValueError("mode must be 'cycle' or 'event'")
        if self._ran or self._running:
            raise RuntimeError("Kernel.run is single-use")
        nonnegative_int(max_time_ps, "max_time_ps")
        positive_int(max_steps, "max_steps")
        self._running = True
        self._ran = True
        steps = 0
        now = min((c.phase_ps for c in self._clocks.values()), default=0)
        try:
            while self._pending or self._flights or any(p.active for p in self._processes.values()):
                if now > max_time_ps or steps >= max_steps:
                    raise RuntimeError("execution limit: " + self._diagnostic())
                self._step(now)
                steps += 1
                if not self._pending and not self._flights and not any(p.active for p in self._processes.values()):
                    break
                event_time = self._next_event_time(now)
                if event_time is None:
                    raise DeadlockError("no future progress: " + self._diagnostic())
                now = (event_time if mode == "event" else
                       min(c.next_edge(now, strict=True) for c in self._clocks.values()))
        finally:
            self._running = False
        return RunResult(
            finish_ps=max([*self.completed.values(), self.now_ps if steps else 0]), accepted_ps=dict(self.accepted),
            completion_ps=dict(self.completed), actions=dict(sorted(self.actions.items())), trace=self.trace.copy(),
            memory_reads=dict(self.memory_reads), buffer_peak=dict(self.buffer_peak), buffer_final=dict(self.buffers),
            resource_peak=dict(self.resource_peak), resource_stats={k: dict(v) for k, v in self._stats.items()},
            steps=steps, mode=mode,
            process_ticks={name: p.ticks for name, p in self._processes.items()},
        )
