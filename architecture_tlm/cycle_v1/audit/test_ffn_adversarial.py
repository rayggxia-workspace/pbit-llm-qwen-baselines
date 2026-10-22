"""Independent exact fixtures for the complete small FFN dependency chain."""
import copy
import random
import struct
import unittest

from architecture_tlm.cycle_v1.ffn import FFNConfig, build_ffn, encode_group, make_kernel, restore_bin_value
from architecture_tlm.cycle_v1.contracts import Operation
from architecture_tlm.cycle_v1.audit.scalar_oracles import f32, frozen_thresholds, scalar_ffn, scalar_restore


def quantized(rows, scales):
    return {"codes": rows, "scales": scales}


def endpoint_fixture():
    # Negative input times W=-128 gives the positive signed-count endpoint.
    return {"x": [-1.0] * 64,
            "wg": quantized([[-128] * 64], [[1.0]]),
            "wu": quantized([[-128] * 64], [[1.0]]),
            "wd": quantized([[1]], [[1.0]]),
            "thresholds": {"x": [[8*i for i in range(32)]], "z": [[8*i for i in range(32)]]}}


class IndependentFFNAudit(unittest.TestCase):
    def test_restore_profiles_match_exact_rational_rounding_and_known_subnormal_bits(self):
        rng = random.Random(0x310023)
        terms = [(3, 2**-145, 1.5, 32), (-3, 2**-145, 1.5, 32),
                 (1, 2**-149, 16.0, 32), (-1, 2**-149, 16.0, 32)]
        for _ in range(256):
            terms.append((rng.randrange(-262144, 262145), 2.0**rng.randrange(-149, 65),
                          f32(rng.uniform(.5, 2)*2.0**rng.randrange(-25, 26)), 2**rng.randrange(0, 7)))
        for integer, scale, weight, samples in terms:
            for profile in ("host_order", "rtl_fused0_order"):
                actual = restore_bin_value(integer, scale, weight, samples, profile)
                expected = scalar_restore(integer, scale, weight, samples, profile)
                self.assertEqual(struct.pack("!f", actual), struct.pack("!f", expected),
                                 (integer, scale, weight, samples, profile))
        self.assertEqual(struct.pack("<f", restore_bin_value(3, 2**-145, 1.5, 32, "host_order")), bytes.fromhex("02000000"))
        self.assertEqual(struct.pack("<f", restore_bin_value(3, 2**-145, 1.5, 32, "rtl_fused0_order")), bytes.fromhex("03000000"))
        with self.assertRaisesRegex(ValueError, "power-of-two"):
            FFNConfig(samples=48, strata=16, restore_rounding="rtl_fused0_order").validate()

    def test_both_restore_profiles_preserve_ordered_bins_and_cross_tile_scalar_contract(self):
        rng = random.Random(0x2345)
        width, hidden, output = 70, 5, 3
        def matrix(rows, cols):
            return quantized([[rng.randrange(-128, 128) for _ in range(cols)] for _ in range(rows)],
                             [[f32(.00137+rng.random()*.017) for _ in range((cols+63)//64)] for _ in range((rows+63)//64)])
        fixture = {"x": [(-1)**i*2.0**(-(i % 8)) for i in range(width)],
                   "wg": matrix(hidden, width), "wu": matrix(hidden, width), "wd": matrix(output, hidden),
                   "thresholds": frozen_thresholds(width, hidden, seed=919)}
        for tiny in (False, True):
            data = copy.deepcopy(fixture)
            if tiny:
                data["x"] = [f32(value*2**-126) for value in data["x"]]
            for profile in ("host_order", "rtl_fused0_order"):
                config = FFNConfig(random_backend="replay", output_bf16=False, restore_rounding=profile)
                expected = scalar_ffn(data, output_bf16=False, restore_rounding=profile)
                pairs = []
                for mode in ("cycle", "event"):
                    k = make_kernel(config)
                    state = build_ffn(k, data, config)
                    result = k.run(mode=mode)
                    for field in ("gate", "up", "z", "projected", "output"):
                        self.assertEqual(state[field], expected[field], (tiny, profile, field))
                    pairs.append(result.equivalence_payload())
                self.assertEqual(*pairs)

    def test_positive_signed_endpoint_and_true_one(self):
        config = FFNConfig(output_bf16=False, random_backend="replay")
        for mode in ("cycle", "event"):
            k = make_kernel(config)
            state = build_ffn(k, endpoint_fixture(), config)
            result = k.run(mode=mode)
            self.assertEqual(state["gate"], [8192.0])
            self.assertEqual(state["up"], [8192.0])
            self.assertEqual(state["z"], [67108864.0])
            self.assertEqual(state["output"], [67108864.0])
            peaks = [row["counter_peak"] for row in state["tile_receipts"]]
            self.assertIn(2048, peaks)
            equivalent = [row["integer_equivalent_peak"] for row in state["tile_receipts"]]
            self.assertIn(262144, equivalent)
            self.assertEqual(result.actions["sc_sample_frames"], 96)

    def test_19_bit_counter_rejects_positive_262144_endpoint(self):
        with self.assertRaises(ValueError):
            FFNConfig(count_bits=19, counter_layout="signed_bin").validate()
        with self.assertRaises(ValueError):
            FFNConfig(count_bits=11, counter_layout="bitplane").validate()

    def test_raw_bitplanes_match_legacy_input_sign_and_twos_complement(self):
        fixture = endpoint_fixture()
        fixture["wg"]["codes"] = [[-1]*64]
        config = FFNConfig(output_bf16=False, random_backend="replay", restore_latency=8)
        k = make_kernel(config)
        state = build_ffn(k, fixture, config)
        observed = []
        def inspect_counter(kernel, operation):
            observed.append(copy.deepcopy(state["counters"]["wg", 0, 0][0][0]))
        k.add(Operation("audit.observe", "control", deps=("ffn.wg.r0.k0.sample31",), on_complete=inspect_counter))
        k.run(mode="event")
        self.assertEqual(observed, [[[0]*8, [2048]*8]])
        self.assertEqual(state["gate"], [64.0])

    def test_encoder_tiny_values_and_explicit_largest_scale_domain(self):
        tiny = encode_group([1e-38, -1e-39, 0.0])
        self.assertEqual([item["q"] for item in tiny], [218, 22, 0])
        self.assertEqual([item["sign"] for item in tiny], [1, -1, 0])
        self.assertTrue(all(item["scale"] == 2**-126 for item in tiny))
        subnormal = encode_group([2**-149, -(2**-149)])
        self.assertEqual([item["q"] for item in subnormal], [0, 0])
        maximum_scale = encode_group([2**127])[0]
        self.assertEqual(maximum_scale["scale"], 2**127)
        self.assertTrue(maximum_scale["full_one"])
        with self.assertRaisesRegex(ValueError, "2\\*\\*127"):
            encode_group([struct.unpack("<f", bytes.fromhex("ffff7f7f"))[0]])

    def test_raw_input_residency_and_restore_scratch_are_finite(self):
        for config in (FFNConfig(encoded_capacity_bytes=196, random_backend="replay"),
                       FFNConfig(restore_capacity_bytes=11, random_backend="replay")):
            with self.subTest(config=config):
                k = make_kernel(config)
                with self.assertRaisesRegex(ValueError, "capacity"):
                    state = build_ffn(k, endpoint_fixture(), config)
                    k.run(mode="event")

    def test_restoration_scales_with_lanes_and_keeps_counter_credits_until_done(self):
        outputs = []
        durations = []
        for lanes in (16, 1):
            c = FFNConfig(vector_lanes=lanes, random_backend="replay", output_bf16=False)
            k = make_kernel(c)
            state = build_ffn(k, endpoint_fixture(), c)
            r = k.run(mode="event")
            prefix = "ffn.wg.r0.k0."
            rail = prefix+"restore_rails"
            # One row x four bins x eight bit positions: 32 lane operations.
            self.assertEqual(r.completion_ps[rail]-r.accepted_ps[rail], (4+32//lanes-1)*10000)
            restore = k.operations[prefix+"restore"]
            self.assertIn("ffn.counters", restore.outputs)
            self.assertIn("ffn.restore", restore.outputs)
            for name in ("restore_rails", "restore_plane_tree0", "restore_plane_tree1", "restore_plane_tree2", "restore_bin0", "restore_bin1", "restore_bin2", "restore_bin3"):
                self.assertNotIn("ffn.counters", k.operations[prefix+name].outputs)
            self.assertEqual(r.buffer_final["ffn.restore"], c.restore_capacity_bytes)
            self.assertEqual(state["restore_intermediates"], {})
            outputs.append(state["output"])
            durations.append(r.finish_ps)
        self.assertEqual(outputs[0], outputs[1])
        self.assertGreater(durations[1], durations[0])

    def test_cross_input_tiles_reduce_before_swiglu(self):
        fixture = {"x": [1.0]*128,
                   "wg": quantized([[1]*64 + [-1]*64], [[1.0, 1.0]]),
                   "wu": quantized([[1]*128], [[1.0, 1.0]]),
                   "wd": quantized([[1]], [[1.0]])}
        config = FFNConfig(output_bf16=False)
        for mode in ("cycle", "event"):
            k = make_kernel(config)
            state = build_ffn(k, fixture, config)
            result = k.run(mode=mode)
            self.assertEqual(state["gate"], [0.0])
            self.assertEqual(state["up"], [128.0])
            self.assertEqual(state["output"], [0.0])
            for matrix in ("wg", "wu"):
                last = f"ffn.{matrix}.r0.k1.partial_write"
                self.assertGreater(result.accepted_ps["ffn.swiglu"], result.completion_ps[last])

    def test_four_bin_boundaries_q255_and_true_one_are_distinct(self):
        values = [1.0, 255/256, 1/4, -1/16, 1/64, 0.0]
        encoded = encode_group(values, bins=4)
        self.assertEqual([item["bin"] for item in encoded], [0, 0, 1, 2, 3, 3])
        self.assertEqual([item["sign"] for item in encoded], [1, 1, 1, -1, 1, 0])
        self.assertEqual([item["full_one"] for item in encoded], [True, False, True, True, True, False])
        self.assertEqual(encoded[1]["q"], 255)
        self.assertEqual(encoded[5]["q"], 0)

    def test_tail_input_and_output_dimensions_are_not_silently_truncated(self):
        fixture = {"x": [0.0]*64 + [1.0],
                   "wg": quantized([[0]*64+[1], [0]*64+[2], [0]*64+[-1]], [[1.0, 1.0]]),
                   "wu": quantized([[0]*64+[1]]*3, [[1.0, 1.0]]),
                   "wd": quantized([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [[1.0]])}
        config = FFNConfig(output_bf16=False)
        k = make_kernel(config)
        state = build_ffn(k, fixture, config)
        k.run(mode="event")
        self.assertEqual(state["gate"], [1.0, 2.0, -1.0])
        self.assertEqual(state["up"], [1.0, 1.0, 1.0])
        self.assertEqual(len(state["output"]), 3)
        self.assertGreater(state["output"][0], 0)
        self.assertGreater(state["output"][1], state["output"][0])
        self.assertLess(state["output"][2], 0)

    def test_data_corruption_cannot_be_invisible_to_arithmetic(self):
        config = FFNConfig(output_bf16=False, random_backend="replay")
        k = make_kernel(config)
        state = build_ffn(k, endpoint_fixture(), config)
        # Replace the gate W8 payload in backing memory, leaving its valid scale.
        # A data-carrying execution must observe zeros or explicitly reject a
        # frozen-payload integrity failure; the original gate is never valid.
        k.load_memory("dram", 0x10000000, bytes(64))
        try:
            k.run(mode="event")
        except (ValueError, AssertionError) as error:
            self.assertRegex(str(error).lower(), "weight|payload|frozen")
            return
        self.assertNotEqual(state["gate"], [8192.0], "arithmetic ignored DMA payload corruption")

    def test_independent_scalar_oracle_matches_every_fp32_boundary(self):
        for seed, samples, bins in ((0, 16, 4), (1, 32, 4), (2, 64, 4), (3, 32, 2)):
            with self.subTest(seed=seed, samples=samples, bins=bins):
                rng = random.Random(seed+991)
                width, hidden, output = 70, 5, 3
                def matrix(rows, cols):
                    return quantized([[rng.randrange(-128, 128) for _ in range(cols)] for _ in range(rows)],
                                     [[0.00137+rng.random()*0.017 for _ in range((cols+63)//64)] for _ in range((rows+63)//64)])
                fixture = {"x": [rng.uniform(-2, 2)*2**rng.randrange(-5, 3) for _ in range(width)],
                           "wg": matrix(hidden, width), "wu": matrix(hidden, width),
                           "wd": matrix(output, hidden), "residual": [rng.uniform(-2, 2) for _ in range(output)],
                           "thresholds": frozen_thresholds(width, hidden, samples=samples, strata=samples, seed=seed+77)}
                config = FFNConfig(samples=samples, strata=samples, bins=bins, output_bf16=bool(seed % 2), random_backend="replay")
                expected = scalar_ffn(fixture, samples=samples, bins=bins, output_bf16=config.output_bf16)
                kernel = make_kernel(config)
                state = build_ffn(kernel, fixture, config)
                kernel.run(mode="event")
                for field in ("gate", "up", "z", "projected", "output"):
                    self.assertEqual(state[field], expected[field], field)


if __name__ == "__main__":
    unittest.main()
