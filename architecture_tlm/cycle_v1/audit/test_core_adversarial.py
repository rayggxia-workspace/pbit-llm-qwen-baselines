"""Independent black-box invariants; expected times are derived, not replayed.

The core implementation does not import this module.  These tests intentionally
exercise resource scheduling beyond the application authors' smoke workloads.
"""
import itertools
import random
import unittest

from architecture_tlm.cycle_v1.contracts import Buffer, Clock, Operation, Resource
from architecture_tlm.cycle_v1.kernel import Kernel
from architecture_tlm.cycle_v1.memory import MemoryPort, MemoryRequest


class IndependentCoreAudit(unittest.TestCase):
    def _run_both(self, factory):
        cycle = factory().run(mode="cycle")
        event = factory().run(mode="event")
        for field in ("accepted_ps", "completion_ps", "actions", "memory_reads", "buffer_peak",
                      "buffer_final", "resource_peak", "resource_stats", "trace", "process_ticks"):
            self.assertEqual(getattr(cycle, field), getattr(event, field), field)
        return cycle

    def test_native_process_enqueue_and_delivery_each_cross_an_edge(self):
        observed = []
        def factory():
            clock = Clock("core", 10000)
            k = Kernel([Resource("pipe", clock, 1)])
            inbox = []
            ticks = []
            def process(kernel):
                ticks.append(kernel.now_ps)
                self.assertEqual(inbox, ["request"])
                inbox.pop()
                kernel.add(Operation("delivered", "pipe"))
                return False
            k.register_clock_process("native", clock, process)
            def submit(kernel, operation):
                inbox.append("request")
                kernel.wake_clock_process("native")
            k.add(Operation("submit", "pipe", on_complete=submit))
            observed.append(ticks)
            return k
        r = self._run_both(factory)
        self.assertEqual(r.completion_ps["submit"], 10000)
        self.assertEqual(observed, [[20000], [20000]])
        self.assertEqual(r.accepted_ps["delivered"], 30000)
        self.assertEqual(r.completion_ps["delivered"], 40000)
        self.assertEqual(r.process_ticks, {"native": 1})

    def test_active_native_process_edges_are_not_skipped(self):
        edges = []
        def factory():
            clock = Clock("native", 12500, 2500)
            k = Kernel([])
            seen = []
            def process(kernel):
                seen.append(kernel.now_ps)
                return len(seen) < 5
            k.register_clock_process("native", clock, process)
            k.wake_clock_process("native")
            edges.append(seen)
            return k
        r = self._run_both(factory)
        self.assertEqual(edges, [[2500, 15000, 27500, 40000, 52500]]*2)
        self.assertEqual(r.process_ticks["native"], 5)

    def test_latency_five_ii_two_is_not_five_or_two_for_both(self):
        def factory():
            k = Kernel([Resource("pipe", Clock("compute", 10000), 5, ii_cycles=2, capacity=8)])
            for i in range(4):
                k.add(Operation(f"job{i}", "pipe", actions={"complete_once": 1}))
            return k
        r = self._run_both(factory)
        origin = r.accepted_ps["job0"]
        self.assertEqual([r.accepted_ps[f"job{i}"] - origin for i in range(4)], [0, 20000, 40000, 60000])
        self.assertEqual([r.completion_ps[f"job{i}"] - origin for i in range(4)], [50000, 70000, 90000, 110000])
        self.assertEqual(r.actions["complete_once"], 4)

    def test_capacity_is_per_instance_and_release_is_next_edge(self):
        def factory():
            k = Kernel([Resource("pipe", Clock("compute", 10000), 3, capacity=1, instances=2)])
            for i in range(5):
                k.add(Operation(f"job{i}", "pipe"))
            return k
        r = self._run_both(factory)
        origin = r.accepted_ps["job0"]
        self.assertEqual([r.accepted_ps[f"job{i}"] - origin for i in range(5)], [0, 0, 40000, 40000, 80000])
        for i in range(5):
            self.assertEqual(r.completion_ps[f"job{i}"] - r.accepted_ps[f"job{i}"], 30000)

    def test_add_order_cannot_create_same_edge_dependency_bypass(self):
        observed = []
        for order in itertools.permutations("abc"):
            k = Kernel([Resource(name, Clock("compute", 10000), 1) for name in "abc"])
            ops = {"a": Operation("a", "a"), "b": Operation("b", "b", deps=("a",)),
                   "c": Operation("c", "c", deps=("b",))}
            for name in order:
                k.add(ops[name])
            r = k.run(mode="event")
            observed.append((r.accepted_ps, r.completion_ps))
            self.assertEqual(r.accepted_ps["b"], r.completion_ps["a"] + 10000)
            self.assertEqual(r.accepted_ps["c"], r.completion_ps["b"] + 10000)
        self.assertTrue(all(item == observed[0] for item in observed))

    def test_simultaneous_producers_cannot_overbook_one_output_slot(self):
        def factory():
            k = Kernel([Resource("prod", Clock("compute", 10000), 1, instances=2),
                        Resource("sink", Clock("compute", 10000), 1)], [Buffer("q", 1)])
            k.add(Operation("p0", "prod", outputs={"q": 1}))
            k.add(Operation("p1", "prod", outputs={"q": 1}))
            k.add(Operation("s0", "sink", inputs={"q": 1}, deps=("p0",)))
            k.add(Operation("s1", "sink", inputs={"q": 1}, deps=("s0", "p1")))
            return k
        r = self._run_both(factory)
        self.assertEqual(r.buffer_peak["q"], 1)
        self.assertGreater(r.completion_ps["p1"], r.accepted_ps["s0"])
        self.assertGreater(r.accepted_ps["s1"], r.completion_ps["p1"])

    def test_two_consumers_cannot_spend_one_token_twice(self):
        def factory():
            k = Kernel([Resource("cons", Clock("compute", 10000), 1, instances=2),
                        Resource("refill", Clock("compute", 10000), 4)], [Buffer("q", 1, initial=1)])
            k.add(Operation("a", "cons", inputs={"q": 1}))
            k.add(Operation("b", "cons", inputs={"q": 1}))
            k.add(Operation("r", "refill", outputs={"q": 1}))
            return k
        r = self._run_both(factory)
        self.assertEqual(r.accepted_ps["a"], 0)
        self.assertGreater(r.accepted_ps["b"], r.completion_ps["r"])
        self.assertEqual(r.buffer_peak["q"], 1)

    def test_memory_window_rejection_keeps_unique_request_and_value(self):
        def factory():
            mem = MemoryPort("mem", Clock("memory", 12500), banks=2, line_bytes=16, window=1,
                             latency_cycles=3, initial_data={0: b"abcd", 16: b"wxyz"}, strict_reads=True)
            k = Kernel([], memory_ports=[mem])
            k.add(Operation("a", "mem", memory=MemoryRequest(0, 4)))
            k.add(Operation("b", "mem", memory=MemoryRequest(16, 4)))
            return k
        r = self._run_both(factory)
        self.assertEqual(r.memory_reads, {"a": b"abcd", "b": b"wxyz"})
        self.assertGreater(r.accepted_ps["b"], r.completion_ps["a"])

    def test_out_of_order_memory_completion_retains_id_dependency(self):
        def factory():
            mem = MemoryPort("mem", Clock("compute", 10000), banks=2, line_bytes=16, window=2,
                             latency_cycles=1, latency_by_address={0: 7, 16: 1},
                             initial_data={0: b"slow", 16: b"fast"}, strict_reads=True)
            k = Kernel([Resource("sink", Clock("compute", 10000), 1, instances=2)], memory_ports=[mem])
            k.add(Operation("a", "mem", memory=MemoryRequest(0, 4)))
            k.add(Operation("b", "mem", memory=MemoryRequest(16, 4)))
            k.add(Operation("use_a", "sink", deps=("a",)))
            k.add(Operation("use_b", "sink", deps=("b",)))
            return k
        r = self._run_both(factory)
        self.assertLess(r.completion_ps["b"], r.completion_ps["a"])
        self.assertEqual(r.memory_reads, {"a": b"slow", "b": b"fast"})
        self.assertGreater(r.accepted_ps["use_a"], r.completion_ps["a"])
        self.assertLess(r.accepted_ps["use_b"], r.completion_ps["a"])

    def test_same_bank_serializes_and_different_banks_parallelize(self):
        def run(address):
            def factory():
                mem = MemoryPort("mem", Clock("memory", 12500), banks=2, line_bytes=16,
                                 window=4, latency_cycles=4, ii_cycles=2)
                k = Kernel([], memory_ports=[mem])
                k.add(Operation("a", "mem", memory=MemoryRequest(0, 4)))
                k.add(Operation("b", "mem", memory=MemoryRequest(address, 4)))
                return k
            return self._run_both(factory)
        same, other = run(32), run(16)
        self.assertEqual(same.accepted_ps["b"] - same.accepted_ps["a"], 25000)
        self.assertEqual(other.accepted_ps["b"], other.accepted_ps["a"])

    def test_write_then_read_waits_for_commit_even_with_reversed_ids(self):
        def factory():
            mem = MemoryPort("mem", Clock("memory", 12500), banks=2, line_bytes=16, window=4,
                             latency_cycles=3, initial_data={0: b"old!"}, strict_reads=True)
            k = Kernel([], memory_ports=[mem])
            k.add(Operation("z_write", "mem", memory=MemoryRequest(0, 4, write=True, data=b"new!")))
            k.add(Operation("a_read", "mem", memory=MemoryRequest(0, 4)))
            return k
        r = self._run_both(factory)
        self.assertEqual(r.memory_reads["a_read"], b"new!")
        self.assertGreater(r.accepted_ps["a_read"], r.completion_ps["z_write"])

    def test_dynamic_callback_cannot_inject_same_edge_work(self):
        def factory():
            k = Kernel([Resource("pipe", Clock("compute", 10000), 1, instances=2)])
            def add_child(kernel, operation):
                kernel.add(Operation("child", "pipe"))
            k.add(Operation("parent", "pipe", on_complete=add_child))
            return k
        r = self._run_both(factory)
        self.assertGreater(r.accepted_ps["child"], r.completion_ps["parent"])

    def test_cross_domain_100_and_80_mhz_use_exact_destination_edges(self):
        # The first synchronizer stage samples only an already committed source.
        for phase, latency, expected in ((0, 1, 25000), (5000, 1, 37500),
                                         (5000, 2, 50000), (0, 5, 75000)):
            def factory():
                k = Kernel([Resource("src", Clock("core", 10000, phase), latency),
                            Resource("dst", Clock("sram", 12500), 1)])
                k.add(Operation("source", "src"))
                k.add(Operation("dest", "dst", deps=("source",), cdc_cycles=2))
                return k
            r = self._run_both(factory)
            self.assertEqual(r.accepted_ps["dest"], expected, (phase, latency))

    def test_multiline_requests_pay_beat_ii_and_available_ports(self):
        for ports, expected_latency in ((1, 110000), (2, 50000)):
            def factory():
                mem = MemoryPort("mem", Clock("memory", 10000), banks=1, line_bytes=16,
                                 latency_cycles=2, ii_cycles=3, ports_per_bank=ports)
                k = Kernel([], memory_ports=[mem])
                k.add(Operation("burst", "mem", memory=MemoryRequest(0, 64)))
                return k
            r = self._run_both(factory)
            self.assertEqual(r.completion_ps["burst"] - r.accepted_ps["burst"], expected_latency)

    def test_single_pipeline_cannot_flush_three_results_on_one_edge(self):
        def factory():
            k = Kernel([Resource("prod", Clock("core", 10000), 1, capacity=4),
                        Resource("sink", Clock("core", 10000), 1)], [Buffer("q", 3, initial=3)])
            for i in range(3):
                k.add(Operation(f"p{i}", "prod", outputs={"q": 1}, earliest_ps=i*10000))
            k.add(Operation("release_space", "sink", inputs={"q": 3}, earliest_ps=50000))
            return k
        result = self._run_both(factory)
        completed = [result.completion_ps[f"p{i}"] for i in range(3)]
        self.assertEqual(len(set(completed)), 3, "one output port retired multiple held pipeline items on the same edge")

    def test_in_order_pipeline_does_not_overtake_long_previous_operation(self):
        def factory():
            k = Kernel([Resource("pipe", Clock("core", 10000), 1, capacity=2)])
            k.add(Operation("a_slow", "pipe", latency_cycles=5))
            k.add(Operation("b_fast", "pipe", latency_cycles=1))
            return k
        result = self._run_both(factory)
        self.assertEqual(result.accepted_ps["b_fast"], 10000)
        self.assertEqual(result.completion_ps["a_slow"], 50000)
        self.assertEqual(result.completion_ps["b_fast"], 60000)

    def test_cdc_visibility_expiry_is_an_event_even_when_memory_still_busy(self):
        def factory():
            mem = MemoryPort("mem", Clock("sram", 12500), banks=1, line_bytes=16,
                             latency_cycles=2, ii_cycles=1, window=4)
            k = Kernel([Resource("src", Clock("core", 10000), 1)], memory_ports=[mem])
            k.add(Operation("occupy", "mem", memory=MemoryRequest(0, 160)))
            k.add(Operation("source", "src"))
            k.add(Operation("wait", "mem", deps=("source",), cdc_cycles=3, memory=MemoryRequest(256, 4)))
            return k
        result = self._run_both(factory)
        changed = [row for row in result.trace if row["op"] == "wait" and row["kind"] == "stall" and row["reason"] == "memory_bank_port:0"]
        self.assertEqual(changed[0]["time_ps"], 37500)

    def test_first_conflicting_bank_change_is_an_event_before_request_acceptance(self):
        def factory():
            mem = MemoryPort("mem", Clock("memory", 10000), banks=2, line_bytes=16,
                             latency_cycles=4, ii_cycles=1, window=4)
            k = Kernel([], memory_ports=[mem])
            # Lines 1..5 reserve bank0 for 2 beats and bank1 for 3 beats.
            k.add(Operation("a_occupy", "mem", memory=MemoryRequest(16, 80)))
            k.add(Operation("b_wait", "mem", memory=MemoryRequest(128, 32)))
            return k
        result = self._run_both(factory)
        reasons = [(row["time_ps"], row["reason"]) for row in result.trace if row["op"] == "b_wait" and row["kind"] == "stall"]
        self.assertIn((0, "memory_bank_port:0"), reasons)
        self.assertIn((20000, "memory_bank_port:1"), reasons)

    def test_seeded_dags_preserve_every_dependency_and_all_observable_events(self):
        for seed in range(32):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                resources = [Resource("a", Clock("a", 10000), 3, capacity=2),
                             Resource("b", Clock("b", 12500, 2500), 2, ii_cycles=2, capacity=3),
                             Resource("c", Clock("c", 7000, 1000), 4, capacity=2, instances=2)]
                operations = []
                for i in range(15):
                    deps = tuple(f"op{j:02}" for j in rng.sample(range(i), min(i, rng.randrange(4))))
                    operations.append(Operation(f"op{i:02}", rng.choice("abc"), deps=deps,
                                                earliest_ps=rng.randrange(5)*11000, cdc_cycles=2))
                def factory():
                    k = Kernel(resources)
                    for op in reversed(operations):
                        k.add(op)
                    return k
                result = self._run_both(factory)
                for op in operations:
                    for dep in op.deps:
                        self.assertGreater(result.accepted_ps[op.id], result.completion_ps[dep])

    def test_seeded_overlapping_byte_memory_matches_program_order_oracle(self):
        for seed in range(32):
            with self.subTest(seed=seed):
                rng = random.Random(9000+seed)
                original = bytes(rng.randrange(256) for _ in range(512))
                oracle = bytearray(original)
                operations, expected = [], {}
                for i in range(20):
                    address, size = rng.randrange(384), rng.randrange(1, 129)
                    write = bool(rng.randrange(2))
                    payload = bytes(rng.randrange(256) for _ in range(size)) if write else None
                    # IDs deliberately reverse issue order; memory hazards must
                    # follow program order, not lexicographic arbitration order.
                    ident = f"op{99-i:02}"
                    operations.append(Operation(ident, "mem", memory=MemoryRequest(address, size, write, payload)))
                    if write:
                        oracle[address:address+size] = payload
                    else:
                        expected[ident] = bytes(oracle[address:address+size])
                def factory():
                    mem = MemoryPort("mem", Clock("memory", 12500), banks=1+seed%4, line_bytes=8+8*(seed%2),
                                     window=4, latency_cycles=2+seed%5, ii_cycles=1+seed%3, ports_per_bank=1+seed%2,
                                     initial_data={0: original}, strict_reads=True)
                    k = Kernel([], memory_ports=[mem])
                    for op in operations:
                        k.add(op)
                    return k
                result = self._run_both(factory)
                self.assertEqual(result.memory_reads, expected)


if __name__ == "__main__":
    unittest.main()
