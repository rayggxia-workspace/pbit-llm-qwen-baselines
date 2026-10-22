"""Reduced decoder closure checked through closed-form and independent oracles."""
import copy
import math
import struct
import unittest

from architecture_tlm.cycle_v1.ffn import FFNConfig
from architecture_tlm.cycle_v1.attention import AttentionConfig
from architecture_tlm.cycle_v1.layer import make_layer
from architecture_tlm.cycle_v1.audit.scalar_oracles import f32, scalar_ffn


def two_lane_fixture():
    identity = [[1.0, 0.0], [0.0, 1.0]]
    quantized_identity = [[127.0, 0.0], [0.0, 127.0]]
    return dict(x=[1.0, -0.5], norm1=[1.0, 1.0], norm2=[1.0, 1.0],
                wq=copy.deepcopy(identity), wk=copy.deepcopy(identity),
                wv=copy.deepcopy(identity), wo=copy.deepcopy(identity),
                past_k=[], past_v=[], wg=copy.deepcopy(quantized_identity),
                wu=copy.deepcopy(quantized_identity), wd=copy.deepcopy(quantized_identity))


class IndependentLayerAudit(unittest.TestCase):
    def run_layer(self, mode="event", latency=4):
        return make_layer(two_lane_fixture(), ffn_config=FFNConfig(samples=16, strata=16),
                          attention_config=AttentionConfig(mode="exact"), memory_latency=latency)

    def test_two_lane_closed_form_frontend_and_independent_ffn_output(self):
        states, results = [], []
        for mode in ("cycle", "event"):
            k, state = self.run_layer()
            result = k.run(mode=mode)
            states.append(state)
            results.append(result)
            # Identity QKVO, one current token, position 0: RoPE is identity,
            # softmax is exactly one, and attention must return RMSNorm(x).
            x = [1.0, -0.5]
            scale1 = f32(1/math.sqrt((1.0+0.25)/2+1e-6))
            normalized = [f32(value*scale1) for value in x]
            for field in ("norm1", "q", "k", "v", "qrope", "krope", "wo"):
                self.assertEqual(state["vectors"][field], normalized, field)
            self.assertEqual(state["attention"]["output"], normalized)
            residual = [f32(x[i]+normalized[i]) for i in range(2)]
            self.assertEqual(state["vectors"]["residual"], residual)
            scale2 = f32(1/math.sqrt((residual[0]**2+residual[1]**2)/2+1e-6))
            norm2 = [f32(value*scale2) for value in residual]
            self.assertEqual(state["vectors"]["norm2"], norm2)
            oracle_fixture = {name:{"codes":[[127, 0], [0, 127]], "scales":[[1.0]]}
                              for name in ("wg", "wu", "wd")}
            oracle_fixture.update(x=norm2, residual=residual,
                thresholds={phase:[state["ffn"]["thresholds"][phase, 0]] for phase in ("x", "z")})
            oracle = scalar_ffn(oracle_fixture, samples=16)
            for field in ("gate", "up", "z", "projected", "output"):
                self.assertEqual(state["ffn"][field], oracle[field], field)
            self.assertEqual(state["output"], oracle["output"])
            self.assertEqual(k.read_memory("sram", state["ffn"]["output_address"], 4), state["output_bytes"])
            self.assertTrue(all(result.buffer_final[name] == spec.initial for name, spec in k.buffer_specs.items()))
            self.assertEqual(result.actions["digital_mac"], 16)
            self.assertEqual(result.actions["rmsnorm_values"], 4)
        self.assertEqual(states[0], states[1])
        self.assertEqual(results[0].equivalence_payload(), results[1].equivalence_payload())

    def test_live_input_bytes_override_the_retained_fixture(self):
        k, state = self.run_layer()
        # The retained fixture still contains nonzero x. Only the actual SRAM
        # input is overwritten; a callback using the fixture silently would fail.
        k.load_memory("sram", 0x90000000, struct.pack("<ff", 0.0, 0.0))
        k.run(mode="event")
        for name, vector in state["vectors"].items():
            self.assertEqual(vector, [0.0, 0.0], name)
        self.assertEqual(state["output"], [0.0, 0.0])

    def test_slower_memory_changes_latency_not_the_connected_result(self):
        outputs, finishes = [], []
        for latency in (1, 13):
            k, state = self.run_layer(latency=latency)
            result = k.run(mode="event")
            outputs.append(state["output"])
            finishes.append(result.finish_ps)
        self.assertEqual(outputs[0], outputs[1])
        self.assertGreater(finishes[1], finishes[0])

    def test_dynamic_initialization_obeys_producer_cdc(self):
        k, state = self.run_layer()
        result = k.run(mode="event")
        writes = [op for op in k.operations.values() if ".initialize." in op.id]
        self.assertGreater(len(writes), 0)
        for op in writes:
            producer = "layer.attention_start" if op.id.startswith("layer.attention.") else "layer.ffn_start"
            self.assertIn(producer, op.deps, op.id)
            destination = k.clock_for(op.resource)
            earliest = destination.next_edge(result.completion_ps[producer], strict=True)+2*destination.period_ps
            self.assertGreaterEqual(result.accepted_ps[op.id], earliest, op.id)

    def test_one_bank_one_window_preserves_end_to_end_values(self):
        pairs = []
        for banks, window in ((4, 4), (1, 1)):
            k, state = make_layer(two_lane_fixture(), ffn_config=FFNConfig(samples=16, strata=16),
                                  memory_banks=banks, memory_window=window)
            result = k.run(mode="event")
            pairs.append((state["output"], result.finish_ps))
            for resource in ("dram", "sram"):
                self.assertLessEqual(result.resource_peak[resource], window)
            self.assertTrue(all(result.buffer_final[name] == spec.initial for name, spec in k.buffer_specs.items()))
        self.assertEqual(pairs[0][0], pairs[1][0])
        self.assertGreater(pairs[1][1], pairs[0][1])


if __name__ == "__main__":
    unittest.main()
