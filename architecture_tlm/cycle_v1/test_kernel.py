"""Directed semantic tests; arithmetic expectations do not call the scheduler."""
import random
import unittest

from architecture_tlm.cycle_v1.contracts import Buffer, Clock, Operation, Resource
from architecture_tlm.cycle_v1.kernel import DeadlockError, Kernel


C = Clock("core", 10_000)


class KernelTests(unittest.TestCase):
    def both(self, build):
        cycle = build().run("cycle")
        event = build().run("event")
        self.assertEqual(cycle.equivalence_payload(), event.equivalence_payload())
        return event

    def test_latency_and_initiation_interval_are_distinct(self):
        def build():
            k = Kernel([Resource("pipe", C, 3, ii_cycles=1, capacity=4)])
            for i in range(4):
                k.add(Operation(str(i), "pipe", actions={"multiply": 8}))
            return k
        r = self.both(build)
        self.assertEqual(list(r.accepted_ps.values()), [0, 10_000, 20_000, 30_000])
        self.assertEqual(list(r.completion_ps.values()), [30_000, 40_000, 50_000, 60_000])
        self.assertEqual(r.actions, {"multiply": 32})

    def test_completed_data_not_visible_on_same_edge(self):
        def build():
            k = Kernel([Resource("a", C, 3), Resource("b", C, 1)])
            k.add(Operation("producer", "a"))
            k.add(Operation("consumer", "b", deps=("producer",)))
            return k
        r = self.both(build)
        self.assertEqual(r.completion_ps["producer"], 30_000)
        self.assertEqual(r.accepted_ps["consumer"], 40_000)

    def test_same_edge_resource_release_has_no_bypass(self):
        def build():
            k = Kernel([Resource("a", C, 1, capacity=1)])
            k.add(Operation("a", "a"))
            k.add(Operation("b", "a"))
            return k
        r = self.both(build)
        self.assertEqual(r.accepted_ps, {"a": 0, "b": 20_000})

    def test_instances_are_independent_and_capacity_is_per_instance(self):
        def build():
            k = Kernel([Resource("pipe", C, 3, instances=2)])
            for name in "dcba":
                k.add(Operation(name, "pipe"))
            return k
        r = self.both(build)
        self.assertEqual(r.accepted_ps, {"a": 0, "b": 0, "c": 40_000, "d": 40_000})
        self.assertEqual(r.resource_peak["pipe"], 2)

    def test_output_backpressure_retains_inflight_slot(self):
        def build():
            k = Kernel([Resource("producer", C, 1, capacity=2), Resource("sink", C, 1, capacity=2)],
                       [Buffer("fifo", 1)])
            k.add(Operation("p0", "producer", outputs={"fifo": 1}))
            k.add(Operation("p1", "producer", outputs={"fifo": 1}))
            k.add(Operation("p2", "producer", outputs={"fifo": 1}))
            for i, t in enumerate((50_000, 80_000, 110_000)):
                k.add(Operation(f"c{i}", "sink", inputs={"fifo": 1}, earliest_ps=t))
            return k
        r = self.both(build)
        self.assertEqual(r.completion_ps["p0"], 10_000)
        self.assertEqual(r.completion_ps["p1"], 60_000)
        self.assertEqual(r.completion_ps["p2"], 90_000)
        self.assertEqual(r.buffer_peak["fifo"], 1)
        self.assertEqual(r.buffer_final["fifo"], 0)
        self.assertGreater(r.resource_stats["producer"]["output_blocked_ps"], 0)

    def test_credit_storage_not_released_before_last_use(self):
        def build():
            k = Kernel([Resource("load", C, 1), Resource("sc", C, 5), Resource("release", C, 1)],
                       [Buffer("free_weight_bytes", 64, 64, unit="byte")])
            k.add(Operation("load0", "load", inputs={"free_weight_bytes": 64}))
            k.add(Operation("sc0", "sc", deps=("load0",)))
            k.add(Operation("release0", "release", deps=("sc0",), outputs={"free_weight_bytes": 64}))
            k.add(Operation("load1", "load", inputs={"free_weight_bytes": 64}))
            return k
        r = self.both(build)
        self.assertGreater(r.accepted_ps["load1"], r.completion_ps["release0"])
        self.assertEqual(r.buffer_final["free_weight_bytes"], 0)

    def test_backlog_cannot_flush_past_completion_port_bandwidth(self):
        def build():
            k = Kernel([Resource("producer", C, 1, capacity=4), Resource("sink", C, 1)],
                       [Buffer("fifo", 3, 3)])
            for i in range(3):
                k.add(Operation(f"p{i}", "producer", outputs={"fifo": 1}))
            k.add(Operation("sink", "sink", inputs={"fifo": 3}, earliest_ps=50_000))
            return k
        r = self.both(build)
        self.assertEqual([r.completion_ps[f"p{i}"] for i in range(3)], [60_000, 70_000, 80_000])

    def test_explicit_output_ii_and_ports(self):
        def build():
            k = Kernel([Resource("producer", C, 1, capacity=4, completion_ports=2, output_ii_cycles=3),
                        Resource("sink", C, 1)], [Buffer("fifo", 3, 3)])
            for i in range(3):
                k.add(Operation(f"p{i}", "producer", outputs={"fifo": 1}))
            k.add(Operation("sink", "sink", inputs={"fifo": 3}, earliest_ps=50_000))
            return k
        r = self.both(build)
        self.assertEqual([r.completion_ps[f"p{i}"] for i in range(3)], [60_000, 60_000, 90_000])

    def test_cross_domain_two_destination_edges(self):
        def build():
            sram = Clock("sram", 12_500)
            k = Kernel([Resource("read", sram, 3), Resource("compute", C, 1)])
            k.add(Operation("read", "read"))
            k.add(Operation("compute", "compute", deps=("read",), cdc_cycles=2))
            return k
        r = self.both(build)
        self.assertEqual(r.completion_ps["read"], 37_500)
        self.assertEqual(r.accepted_ps["compute"], 50_000)

    def test_cdc_depth_not_recharged_inside_one_clock(self):
        def build():
            k = Kernel([Resource("p", C, 1), Resource("q", C, 1)])
            k.add(Operation("p", "p"))
            k.add(Operation("q", "q", deps=("p",), cdc_cycles=2))
            return k
        self.assertEqual(self.both(build).accepted_ps["q"], 20_000)

    def test_integer_phases_and_noncommensurate_clocks(self):
        def build():
            a, b = Clock("a", 7, 2), Clock("b", 11, 4)
            k = Kernel([Resource("a", a, 3), Resource("b", b, 2)])
            k.add(Operation("a", "a"))
            k.add(Operation("b", "b", deps=("a",), cdc_cycles=2))
            return k
        r = self.both(build)
        self.assertEqual(r.accepted_ps, {"a": 2, "b": 37})
        self.assertEqual(r.completion_ps, {"a": 23, "b": 59})

    def test_dynamic_graph_is_next_edge_visible(self):
        def build():
            k = Kernel([Resource("r", C, 1, capacity=2)])
            def next_sample(kernel, op):
                i = int(op.id)
                if i < 4:
                    kernel.add(Operation(str(i + 1), "r", deps=(op.id,), on_complete=next_sample,
                                         actions={"proposal": 1}))
            k.add(Operation("0", "r", on_complete=next_sample, actions={"proposal": 1}))
            return k
        r = self.both(build)
        self.assertEqual(list(r.accepted_ps.values()), [0, 20_000, 40_000, 60_000, 80_000])
        self.assertEqual(r.actions["proposal"], 5)

    def test_registration_order_does_not_change_arbitration(self):
        ops = [Operation("a", "r"), Operation("b", "r"), Operation("c", "r", deps=("a", "b"))]
        def run(order):
            k = Kernel([Resource("r", C, 2, capacity=2)])
            for i in order:
                k.add(ops[i])
            return k.run().equivalence_payload()
        self.assertEqual(run([0, 1, 2]), run([2, 1, 0]))

    def test_event_skips_long_idle_interval(self):
        def build():
            k = Kernel([Resource("r", C, 1000)])
            k.add(Operation("a", "r"))
            return k
        cycle, event = build().run("cycle"), build().run("event")
        self.assertEqual(cycle.equivalence_payload(), event.equivalence_payload())
        self.assertEqual(cycle.steps, 1001)
        self.assertEqual(event.steps, 2)

    def test_partial_dependency_stall_transitions_match(self):
        def build():
            k = Kernel([Resource("a", C, 2), Resource("b", C, 9), Resource("c", C, 1)])
            k.add(Operation("a", "a"))
            k.add(Operation("b", "b"))
            k.add(Operation("c", "c", deps=("a", "b")))
            return k
        r = self.both(build)
        self.assertIn((30_000, "dependency:b"), [(x["time_ps"], x.get("reason")) for x in r.trace])

    def test_seeded_dags_cycle_event_equivalence(self):
        for seed in range(30):
            def build(seed=seed):
                rng = random.Random(seed)
                clocks = [Clock("a", 10), Clock("b", 13, 2)]
                k = Kernel([Resource("a", clocks[0], rng.randrange(1, 8), capacity=3, instances=2),
                            Resource("b", clocks[1], rng.randrange(1, 8), ii_cycles=2, capacity=3)])
                for i in range(20):
                    deps = tuple(str(j) for j in range(i) if rng.random() < .12)
                    k.add(Operation(str(i), rng.choice(("a", "b")), deps=deps,
                                    earliest_ps=rng.randrange(0, 100), cdc_cycles=2,
                                    actions={"op": 1}))
                return k
            with self.subTest(seed=seed):
                self.both(build)

    def test_deadlock_is_reported_with_buffer_reason(self):
        k = Kernel([Resource("r", C, 1)], [Buffer("empty", 1)])
        k.add(Operation("a", "r", inputs={"empty": 1}))
        with self.assertRaisesRegex(DeadlockError, "input_empty:empty"):
            k.run()

    def test_bad_contracts_fail_early(self):
        for period in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                Clock("bad", period)
        with self.assertRaises(ValueError):
            Resource("r", C, 0)
        k = Kernel([Resource("r", C, 1)], [Buffer("b", 1)])
        with self.assertRaises(ValueError):
            k.add(Operation("a", "r", outputs={"b": 2}))


if __name__ == "__main__":
    unittest.main()
