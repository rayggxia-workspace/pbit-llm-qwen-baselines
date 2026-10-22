"""Externally specified finite trajectories for sampler and sparse addresses."""
import unittest
from dataclasses import replace

from architecture_tlm.cycle_v1.attention import (
    AttentionConfig, SamplerCapError, _Source, build_attention, make_kernel,
)
from architecture_tlm.random_service.service import SigmoidTable


def fixture_three():
    keys = [[0.0] for _ in range(8)]
    keys[5], keys[1], keys[7] = [3.0], [2.0], [1.0]
    return {"q": [1.0], "k": keys, "v": [[i+0.25] for i in range(8)],
            "candidate_ids": [5, 1, 7]}


class IndependentAttentionAudit(unittest.TestCase):
    def run_pair(self, fixture, config):
        if fixture.get("random_replay"):
            config = replace(config, random_backend="replay")
        pairs = []
        for mode in ("cycle", "event"):
            kernel = make_kernel(config)
            state = build_attention(kernel, fixture, config)
            result = kernel.run(mode=mode)
            pairs.append((state, result))
        self.assertEqual(pairs[0][0], pairs[1][0])
        self.assertEqual(pairs[0][1].equivalence_payload(), pairs[1][1].equivalence_payload())
        return pairs[0]

    def test_winner_holds_preserve_multiplicity_and_read_only_actual_sparse_v(self):
        fixture = fixture_three()
        fixture["random_replay"] = {"frames": [[False, False, False], [False, True, True],
                                                [True, False, True], [True, True, False]],
                                    "fair": [1, 0]}
        config = AttentionConfig(mode="winner", samples=4, source_lanes=2,
                                 output_capacity=1, histogram_delay_cycles=7)
        state, result = self.run_pair(fixture, config)
        self.assertEqual(state["local_indices"], [0, 2, 2, 0])
        self.assertEqual(state["physical_indices"], [5, 7, 7, 5])
        self.assertEqual(state["histogram"], {5: 2, 7: 2})
        self.assertEqual(state["output"], [6.25])
        self.assertEqual(state["source_waves"], 8)
        self.assertEqual(state["fair_draws"], 2)
        self.assertEqual(state["winner_holds"], 2)
        self.assertEqual(state["winner_switches"], 2)
        self.assertFalse(state["provenance"]["independent_samples"])
        reads = [row for row in result.trace if row["kind"] == "accept" and row.get("op", "").startswith("attention.V.") and "address" in row]
        self.assertEqual({row["address"] for row in reads}, {0x72000000+5*4, 0x72000000+7*4})
        self.assertEqual(result.actions["V_read_bytes"], 8)
        self.assertEqual(result.actions["K_read_bytes"], 12)
        self.assertEqual(result.actions["sample_output"], 4)

    def test_rejection_adapts_shift_and_counts_both_failed_attempt_types(self):
        fixture = fixture_three()
        fixture["random_replay"] = {"frames": [[True, True], [False, False], [False, True], [False, False]], "fair": [1]}
        config = AttentionConfig(mode="rejection", samples=2, source_lanes=1)
        state, result = self.run_pair(fixture, config)
        self.assertEqual(state["local_indices"], [2, 0])
        self.assertEqual(state["physical_indices"], [7, 5])
        self.assertEqual(state["proposals"], 4)
        self.assertEqual(state["rejected_multi"], 1)
        self.assertEqual(state["rejected_empty"], 1)
        self.assertEqual(state["source_frames"], 4)
        self.assertEqual(state["source_waves"], 8)
        self.assertEqual(state["fair_draws"], 1)
        self.assertEqual([(r["shift"], r["next_shift"]) for r in state["frames"]], [(0, 1), (1, 0), (0, 0), (0, 0)])
        self.assertEqual(state["output"], [6.25])
        self.assertEqual(result.actions["offset_changes"], 2)

    def test_uniform_rank_overflow_retries_instead_of_modulo_bias(self):
        fixture = {"q": [1.0], "k": [[4.0], [3.0], [2.0], [1.0]],
                   "v": [[10.0], [20.0], [30.0], [40.0]], "candidate_ids": [0, 1, 2, 3],
                   "random_replay": {"frames": [[False, True, True, True]], "fair": [3, 2]}}
        state, result = self.run_pair(fixture, AttentionConfig(mode="winner", samples=1))
        self.assertEqual(state["local_indices"], [3])
        self.assertEqual(state["output"], [40.0])
        self.assertEqual(state["rank_retries"], 1)
        self.assertEqual(state["fair_draws"], 2)
        self.assertEqual(result.actions["fair_random_bits"], 4)

    def test_proposal_cap_raises_without_inventing_an_output(self):
        fixture = fixture_three()
        fixture["random_replay"] = {"frames": [[True, True], [True, True]]}
        config = AttentionConfig(mode="rejection", samples=1, max_proposals_per_sample=2, random_backend="replay")
        kernel = make_kernel(config)
        state = build_attention(kernel, fixture, config)
        with self.assertRaises(SamplerCapError):
            kernel.run(mode="event")
        self.assertIsNone(state["output"])
        self.assertEqual(state["local_indices"], [])
        self.assertEqual(state["proposals"], 2)
        self.assertEqual(state["status"], "failed_proposal_cap")

    def test_capacity_error_is_explicit(self):
        config = AttentionConfig(capacity=2)
        with self.assertRaisesRegex(ValueError, "capacity"):
            build_attention(make_kernel(config), fixture_three(), config)

    def test_all_equal_logits_exact_and_systematic_outputs_are_known(self):
        fixture = {"q": [0.0], "k": [[99.0], [-22.0]], "v": [[2.0], [6.0]],
                   "candidate_ids": [1, 0], "random_replay": {"uniforms": [0.5]}}
        exact, _ = self.run_pair(fixture, AttentionConfig(mode="exact", samples=4))
        pv, result = self.run_pair(fixture, AttentionConfig(mode="pv", samples=4))
        self.assertEqual(exact["output"], [4.0])
        self.assertEqual(pv["local_indices"], [0, 0, 1, 1])
        self.assertEqual(pv["output"], [4.0])
        self.assertFalse(pv["provenance"]["independent_samples"])
        self.assertEqual(result.actions["uniform_random_bits"], 32)

    def test_q256_response_matches_frozen_existing_lut_including_ties(self):
        source = _Source({}, AttentionConfig(response="q256"))
        table = SigmoidTable()
        drives = [code/8 for code in range(-255, 256)]
        drives += [(code+0.5)/8+delta for code in range(-255, 255) for delta in (-1e-12, 0.0, 1e-12)]
        drives += [-1000.0, 1000.0]
        self.assertEqual(source.probabilities(drives), [q/256 for q in table.lookup(drives)])
        self.assertEqual(source.probabilities([-1000.0, 1000.0]), [0.0, 1.0])

    def test_finite_source_width_changes_time_not_frozen_frame_semantics(self):
        fixture = fixture_three()
        fixture["random_replay"] = {"frames": [[True, False, False]]*4}
        narrow, narrow_result = self.run_pair(fixture, AttentionConfig(mode="winner", samples=4, source_lanes=1))
        wide, wide_result = self.run_pair(fixture, AttentionConfig(mode="winner", samples=4, source_lanes=64))
        self.assertEqual(narrow["local_indices"], wide["local_indices"])
        self.assertEqual(narrow["output"], wide["output"])
        self.assertEqual(narrow["source_waves"], 12)
        self.assertEqual(wide["source_waves"], 4)
        self.assertGreater(narrow_result.finish_ps, wide_result.finish_ps)
        self.assertEqual(narrow_result.actions["random_bits"], wide_result.actions["random_bits"])

    def test_single_candidate_rejection_needs_no_random_frame(self):
        fixture = {"q": [1.0], "k": [[2.0]], "v": [[7.0]], "candidate_ids": [0]}
        state, result = self.run_pair(fixture, AttentionConfig(mode="rejection", samples=3))
        self.assertEqual(state["local_indices"], [0, 0, 0])
        self.assertEqual(state["output"], [7.0])
        self.assertEqual(state["source_frames"], 0)
        self.assertEqual(state["source_waves"], 0)
        self.assertEqual(state["fair_draws"], 0)
        self.assertEqual(result.actions.get("random_bits", 0), 0)

    def test_quantized_adaptive_rejection_does_not_claim_independent_samples(self):
        fixture = fixture_three()
        fixture["random_replay"] = {"frames": [[False, True]]}
        state, _ = self.run_pair(fixture, AttentionConfig(mode="rejection", samples=1, response="q256"))
        self.assertIsNot(state["provenance"]["independent_samples"], True)


if __name__ == "__main__":
    unittest.main()
