"""Isolated host experiment: omit only already-reported stable dependency stalls.

Never replaces or filters the full _pending mapping. The candidate mapping
contains every newly registered operation, every changed dependency waiter,
and all operations with resolved dependencies. Resource/input/memory blocked
operations remain candidates. The original _step arbitration and commit code
below differs only in its input iteration and a candidate bookkeeping pop.
Not part of the currently running source snapshot or a hardware optimization.
"""
from architecture_tlm.cycle_v1.kernel import Kernel, _Flight
from architecture_tlm.cycle_v1.contracts import Operation
from architecture_tlm.ffn_cycle_integration.active_memory import ActiveMemoryKernel


class PendingCandidateKernel(ActiveMemoryKernel):
    def __init__(self,resources,buffers=(),memory_ports=()):
        self._accept_candidates={}
        super().__init__(resources,buffers,memory_ports)

    def add(self,op):
        op=super().add(op)
        self._accept_candidates[op.id]=op
        return op

    def _stall(self,op,phase,reason):
        super()._stall(op,phase,reason)
        if phase=='accept' and self._dependency_cache.get(op.id,(None,None))[1]==reason:
            # This dependency stall was just emitted (or already had the exact
            # same reason). Only a dependency completion can change it next.
            self._accept_candidates.pop(op.id,None)

    def _dependency_completed(self,ident):
        consumers=tuple(self._dependency_waiters.get(ident,()))
        super()._dependency_completed(ident)
        for consumer in consumers:
            if consumer in self._pending:
                self._accept_candidates[consumer]=self._pending[consumer]

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
        for op in sorted(self._accept_candidates.values(), key=lambda op: op.id):
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
            self._accept_candidates.pop(op.id,None)
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
        for op in self._accept_candidates.values():
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
