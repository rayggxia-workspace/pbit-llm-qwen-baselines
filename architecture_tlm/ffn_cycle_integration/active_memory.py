"""Equivalent live-request scoreboard and dependency cache for large FFN runs.

The Issue116 kernel retains completed operations for trace/provenance. A hazard
query need only inspect pending and in-flight requests. This subclass preserves
the first conflict in registration order, including the exact stall reason.
It changes host simulation cost, never modeled hardware timing or resources.

The original kernel still visits every pending operation on every scheduled
edge, in its original order. Dependency answers are cached until an actual
completion changes them. This preserves first stalls, partial-dependency
reason transitions, CDC visibility and old-state acceptance decisions.
"""
from architecture_tlm.cycle_v1.kernel import Kernel


class _CompletionTimes(dict):
    """Observe the original kernel's one append at each completion commit.

    Kernel._step makes *all* completion and acceptance decisions before it
    writes this mapping. Notifications therefore cannot create same-edge
    forwarding. Every callback sees all commits, as in the original kernel.
    This is internal scheduler state, not an externally mutable input.
    """
    def __init__(self, notify):
        super().__init__()
        self.notify=notify

    def __setitem__(self, ident, time_ps):
        super().__setitem__(ident,time_ps)
        self.notify(ident)


class ActiveMemoryKernel(Kernel):
    def __init__(self, resources, buffers=(), memory_ports=()):
        super().__init__(resources,buffers,memory_ports)
        self._dependency_cache={}
        self._missing_dependencies={}
        self._dependency_waiters={}
        self._live_memory={name:{} for name in self.memory_ports}
        self.completed=_CompletionTimes(self._dependency_completed)

    def add(self, op):
        op=super().add(op)
        if op.memory is not None:
            # Ordered dict insertion follows Kernel.add registration sequence,
            # including requests whose dependencies are still unresolved.
            self._live_memory[op.resource][op.id]=op
        missing={dep for dep in op.deps if dep not in self.completed}
        if missing:
            self._missing_dependencies[op.id]=missing
            self._dependency_cache[op.id]=(None,'dependency:'+','.join(sorted(missing)))
            # Future producer IDs are legal: register their watchers now,
            # even when the producer operation has not yet been inserted.
            for dep in missing:
                self._dependency_waiters.setdefault(dep,set()).add(op.id)
        else:
            self._dependency_cache[op.id]=super()._dependency_ready(op)
        return op

    def _dependency_completed(self, ident):
        self._dependency_cache.pop(ident,None)
        resource=self.operations[ident].resource
        if resource in self._live_memory:
            del self._live_memory[resource][ident]
        for consumer in self._dependency_waiters.pop(ident,()):
            missing=self._missing_dependencies[consumer]
            missing.remove(ident)
            if missing:
                self._dependency_cache[consumer]=(None,'dependency:'+','.join(sorted(missing)))
            else:
                del self._missing_dependencies[consumer]
                self._dependency_cache[consumer]=super()._dependency_ready(self.operations[consumer])

    def _dependency_ready(self, op):
        try:
            return self._dependency_cache[op.id]
        except KeyError:
            # Normal scheduling only queries pending operations. Retain the
            # original answer for a diagnostic caller querying a completed op.
            return super()._dependency_ready(op)

    def _memory_hazard(self, op):
        if op.memory is None:
            return None
        limit = self._sequence[op.id]
        for other in self._live_memory[op.resource].values():
            sequence = self._sequence[other.id]
            if sequence >= limit:
                break
            if (op.memory.write or other.memory.write) and op.memory.overlaps(other.memory):
                return 'memory_order:' + other.id
        return None

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
            # A previously reported, unchanged missing-dependency reason
            # contributes no future time in the original algorithm. Keep the
            # full pending dictionary intact: memory hazards still need it.
            # First evaluation and any partial dependency change take the
            # original path below, preserving their next local-edge stalls.
            cached = self._dependency_cache[op.id]
            if cached[1] is not None and self._last_stall.get((op.id, "accept")) == cached[1]:
                continue
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

