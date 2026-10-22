import unittest

from architecture_tlm.cycle_v1.contracts import Buffer, Clock, Operation, Resource
from architecture_tlm.cycle_v1.kernel import Kernel
from architecture_tlm.cycle_v1.memory import MemoryPort, MemoryRequest


C = Clock("memory", 10)


class MemoryTests(unittest.TestCase):
    def both(self, build):
        cycle = build().run("cycle")
        event = build().run("event")
        self.assertEqual(cycle.equivalence_payload(), event.equivalence_payload())
        return event

    def test_same_bank_conflict_different_bank_parallel(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=2, line_bytes=64, ii_cycles=2)])
            for name, addr in (("a", 0), ("b", 64), ("c", 128)):
                k.add(Operation(name, "m", memory=MemoryRequest(addr, 64)))
            return k
        r = self.both(build)
        self.assertEqual(r.accepted_ps, {"a": 0, "b": 0, "c": 20})

    def test_out_of_order_return_keeps_request_identity(self):
        def build():
            m = MemoryPort("m", C, banks=2, latency_by_address={0: 9, 64: 2},
                           initial_data={0: b"slow", 64: b"fast"}, strict_reads=True)
            k = Kernel([], memory_ports=[m])
            k.add(Operation("a_slow", "m", memory=MemoryRequest(0, 4)))
            k.add(Operation("b_fast", "m", memory=MemoryRequest(64, 4)))
            return k
        r = self.both(build)
        self.assertEqual(list(r.completion_ps), ["b_fast", "a_slow"])
        self.assertEqual(r.memory_reads, {"b_fast": b"fast", "a_slow": b"slow"})

    def test_finite_window_retries_without_duplicate_charge(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=4, window=1, latency_cycles=2)])
            for i in range(3):
                k.add(Operation(str(i), "m", memory=MemoryRequest(i * 64, 64)))
            return k
        r = self.both(build)
        self.assertEqual(r.accepted_ps, {"0": 0, "1": 30, "2": 60})
        self.assertEqual(r.actions["memory.m.read_requests"], 3)
        self.assertEqual(r.actions["memory.m.read_bytes"], 192)
        self.assertEqual(r.resource_peak["m"], 1)

    def test_cross_line_beats_pay_ii_and_actual_address(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=2, line_bytes=16, latency_cycles=3, ii_cycles=2)])
            # [8, 72) touches lines 0..4: bank0 three beats, bank1 two.
            k.add(Operation("wide", "m", memory=MemoryRequest(8, 64)))
            return k
        r = self.both(build)
        self.assertEqual(r.finish_ps, (3 + (3 - 1) * 2) * 10)
        a = next(x for x in r.trace if x["kind"] == "accept")
        self.assertEqual(a["bank_beats"], {0: 3, 1: 2})
        self.assertEqual(r.actions["memory.m.read_beats"], 5)

    def test_two_ports_split_beat_train(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=1, line_bytes=16,
                       ports_per_bank=2, latency_cycles=3, ii_cycles=2)])
            k.add(Operation("wide", "m", memory=MemoryRequest(0, 64)))
            return k
        self.assertEqual(self.both(build).finish_ps, 50)

    def test_response_ports_bound_descriptor_completions(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=4, latency_cycles=2,
                                                  response_ports=1, response_ii_cycles=2)])
            for i in range(3):
                k.add(Operation(str(i), "m", memory=MemoryRequest(i * 64, 4)))
            return k
        r = self.both(build)
        self.assertEqual(list(r.completion_ps.values()), [20, 40, 60])

    def test_raw_write_completion_controls_data_visibility(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=1, latency_cycles=2, strict_reads=True)])
            k.add(Operation("z_write", "m", memory=MemoryRequest(0, 4, write=True, data=b"DATA")))
            # No explicit dep: the address scoreboard establishes RAW ordering.
            k.add(Operation("a_read", "m", memory=MemoryRequest(0, 4)))
            return k
        r = self.both(build)
        self.assertEqual(r.completion_ps["z_write"], 20)
        self.assertEqual(r.accepted_ps["a_read"], 30)
        self.assertEqual(r.memory_reads["a_read"], b"DATA")

    def test_war_preserves_original_read_data(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=1, latency_cycles=2,
                       initial_data={0: b"OLD!"}, strict_reads=True)])
            k.add(Operation("z_read", "m", memory=MemoryRequest(0, 4)))
            k.add(Operation("a_write", "m", memory=MemoryRequest(0, 4, write=True, data=b"NEW!")))
            k.add(Operation("b_read", "m", memory=MemoryRequest(0, 4)))
            return k
        r = self.both(build)
        self.assertEqual(r.memory_reads, {"z_read": b"OLD!", "b_read": b"NEW!"})
        self.assertGreater(r.accepted_ps["a_write"], r.completion_ps["z_read"])

    def test_waw_and_partial_overlap(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=2, latency_cycles=2, strict_reads=True)])
            k.add(Operation("z_first", "m", memory=MemoryRequest(0, 4, write=True, data=b"AAAA")))
            k.add(Operation("a_second", "m", memory=MemoryRequest(2, 4, write=True, data=b"BBBB")))
            k.add(Operation("read", "m", memory=MemoryRequest(0, 6)))
            return k
        self.assertEqual(self.both(build).memory_reads["read"], b"AABBBB")

    def test_nonoverlapping_write_does_not_create_false_hazard(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=2, latency_cycles=2)])
            k.add(Operation("a", "m", memory=MemoryRequest(0, 4, write=True, data=b"AAAA")))
            k.add(Operation("b", "m", memory=MemoryRequest(64, 4, write=True, data=b"BBBB")))
            return k
        self.assertEqual(self.both(build).accepted_ps, {"a": 0, "b": 0})

    def test_backpressured_read_holds_memory_window(self):
        def build():
            k = Kernel([Resource("sink", C, 1)], [Buffer("f", 1, 1)],
                       [MemoryPort("m", C, window=1, latency_cycles=2)])
            k.add(Operation("a", "m", memory=MemoryRequest(0, 4), outputs={"f": 1}))
            k.add(Operation("b", "m", memory=MemoryRequest(64, 4)))
            k.add(Operation("c", "sink", inputs={"f": 1}, earliest_ps=60))
            return k
        r = self.both(build)
        self.assertEqual(r.completion_ps["a"], 70)
        self.assertEqual(r.accepted_ps["b"], 80)

    def test_dynamic_dma_write_read_loop(self):
        def build():
            k = Kernel([Resource("compute", C, 1)], memory_ports=[MemoryPort("m", C, strict_reads=True)])
            def produce(kernel, op):
                kernel.add(Operation("write", "m", deps=(op.id,),
                                     memory=MemoryRequest(0, 4, True, b"TEST")))
                kernel.add(Operation("read", "m", deps=("write",), memory=MemoryRequest(0, 4)))
            k.add(Operation("compute", "compute", on_complete=produce))
            return k
        r = self.both(build)
        self.assertEqual(r.memory_reads["read"], b"TEST")
        self.assertGreater(r.accepted_ps["read"], r.completion_ps["write"])

    def test_cdc_visibility_expiry_exposes_bank_stall_before_ready(self):
        def build():
            core, mem = Clock("core", 10_000), Clock("mem", 12_500)
            k = Kernel([Resource("source", core, 1)], memory_ports=[
                MemoryPort("m", mem, banks=1, line_bytes=16, latency_cycles=2)])
            k.add(Operation("occupy", "m", memory=MemoryRequest(0, 160)))
            k.add(Operation("source", "source"))
            k.add(Operation("wait", "m", deps=("source",), cdc_cycles=3,
                            memory=MemoryRequest(256, 16)))
            return k
        r = self.both(build)
        self.assertIn((37_500, "memory_bank_port:0"),
                      [(x["time_ps"], x.get("reason")) for x in r.trace if x["op"] == "wait"])

    def test_multiple_bank_unblock_transitions_are_not_skipped(self):
        def build():
            k = Kernel([], memory_ports=[MemoryPort("m", C, banks=2, line_bytes=16,
                       ii_cycles=3, latency_cycles=2)])
            k.add(Operation("a", "m", memory=MemoryRequest(0, 16)))
            k.add(Operation("b", "m", memory=MemoryRequest(16, 16), earliest_ps=10))
            k.add(Operation("c", "m", memory=MemoryRequest(0, 32), earliest_ps=20))
            return k
        self.both(build)

    def test_invalid_requests_and_strict_uninitialized_reads(self):
        for request_args in ((0, 0), (-1, 4), (0, -2)):
            with self.assertRaises(ValueError):
                MemoryRequest(*request_args)
        with self.assertRaises(ValueError):
            MemoryRequest(0, 4, True, b"bad")
        k = Kernel([], memory_ports=[MemoryPort("m", C, strict_reads=True)])
        k.add(Operation("bad", "m", memory=MemoryRequest(128, 4)))
        with self.assertRaisesRegex(ValueError, "uninitialized"):
            k.run()


if __name__ == "__main__":
    unittest.main()
