"""Native sources checked against original per-edge recurrence and protocol."""
import unittest

from architecture_tlm.cycle_v1.contracts import Clock, Operation, Resource
from architecture_tlm.cycle_v1.kernel import Kernel
from architecture_tlm.cycle_v1.rng_protocol import NativeRandomService, buffers, resources
from architecture_tlm.cycle_v1.ffn import FFNConfig, make_kernel, build_ffn
from architecture_tlm.random_service.model import Endpoint, RandomNetwork, SeedWords
from architecture_tlm.cycle_v1.audit.scalar_oracles import scalar_ffn


class IndependentNativeAudit(unittest.TestCase):
    def test_mixed_endpoint_hold_checkpoint_and_idle_match_original_each_edge(self):
        captured = []
        pairs = []
        for mode in ("cycle", "event"):
            clock = Clock("core", 10000)
            k = Kernel(resources()+[Resource("delay", clock, 1)], buffers("audit"))
            service = NativeRandomService(k, "audit", {"ffn":"lfsr32", "biased":"bivium"},
                                          seed=812, seed_interval=3, seed_startup=7,
                                          reseed_cycles=70, hold_cycles=3)
            responses = []
            callback = lambda response, done: responses.append(response)
            saved = service.command("save", "ffn", 1, ())
            first = service.frame("first", {"ffn":[128], "biased":[0, 256]+[128]*18}, (saved,), callback)
            k.add(Operation("gap", "delay", deps=(first,), earliest_ps=5000000))
            second = service.frame("second", {"ffn":[128]}, ("gap",), callback)
            restored = service.command("restore", "ffn", 2, (second,))
            replay = service.frame("replay", {"ffn":[128]}, (restored,), callback)
            service.command("release", "ffn", 3, (replay,))
            result = k.run(mode=mode)
            report = service.report()
            self.assertEqual(responses[0]["words"]["ffn"], responses[2]["words"]["ffn"])
            self.assertEqual(responses[0]["bits"]["biased"][:2], (False, True))
            slow = RandomNetwork({"ffn":Endpoint("lfsr32",70), "biased":Endpoint("bivium",70)},
                                 SeedWords("fixture",3,7,fixture_seed=812,
                                     provenance="explicit deterministic seed-bus fixture; not physical entropy"), clock_ns=10)
            accept_cycles = {response["valid_ps"]//10000:response for response in responses}
            command_cycles = {row["native_complete_ps"]//10000:row["command"]
                              for row in service.receipts if row["kind"] == "command"}
            seen = []
            for cycle in range(report["cycles"]):
                request = accept_cycles.get(cycle)
                requests = {}
                if request is not None:
                    requests = {name:([0,256]+[128]*18 if name=="biased" else [128]) for name in request["words"]}
                readies = {name:False for response in responses
                           if response["valid_ps"]//10000 <= cycle < response["native_complete_ps"]//10000
                           for name in response["words"]}
                commands = {"ffn":command_cycles[cycle]} if cycle in command_cycles else {}
                tick = slow.tick(requests, readies, commands)
                if request is not None:
                    self.assertTrue(all(tick[name]["accepted"] for name in requests))
                    seen.append({name:tick[name]["words"] for name in requests})
            self.assertEqual(seen, [response["words"] for response in responses])
            for name in slow.ports:
                self.assertEqual(slow.ports[name].report(), service.network.ports[name].report(), name)
                for field in ("state", "age", "epoch", "locked"):
                    self.assertEqual(getattr(slow.ports[name],field), getattr(service.network.ports[name],field))
            self.assertEqual(slow.report()["seed_events"], report["seed_events"])
            self.assertEqual(slow.report()["seed_word_transcript"], report["seed_word_transcript"])
            self.assertGreater(report["ports"]["ffn"]["counts"]["reseed_deferred_cycles"], 400)
            pairs.append((result.equivalence_payload(), responses, report))
        self.assertEqual(pairs[0], pairs[1])

    def test_native_ffn_eight_engine_broadcast_and_second_wave_replay(self):
        width = 257
        fixture = {"x":[1.0], "wg":{"codes":[[1]]*width,"scales":[[1.0]]*5},
                   "wu":{"codes":[[1]]*width,"scales":[[1.0]]*5},
                   "wd":{"codes":[[1]*width],"scales":[[1.0]*5]}}
        c = FFNConfig(samples=16, strata=16, output_bf16=False, seed_word_interval=2, seed_startup=0)
        k = make_kernel(c)
        state = build_ffn(k, fixture, c)
        result = k.run(mode="event")
        # x: ten tiles in two shared waves; z: five input groups, one wave each.
        counts = state["native_random"]["ports"]["ffn"]["counts"]
        self.assertEqual(counts["frames_generated"], 7*16)
        self.assertEqual(counts["responses_consumed"], 7*16)
        self.assertEqual(counts["restore_bits_loaded"], 32)
        self.assertEqual(counts["checkpoint_bits_written"], 6*32)
        self.assertEqual(result.actions["sc_sample_frames"], 15*16)
        frozen = dict(fixture, thresholds={"x":[state["thresholds"]["x",0]],
                                          "z":[state["thresholds"]["z",i] for i in range(5)]})
        oracle = scalar_ffn(frozen, samples=16, output_bf16=False)
        for field in ("gate", "up", "z", "projected", "output"):
            self.assertEqual(state[field], oracle[field], field)


if __name__ == "__main__":
    unittest.main()
