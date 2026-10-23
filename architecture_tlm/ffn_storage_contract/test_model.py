"""Independent contract checks, including adversarial replay mutations."""

import copy
from dataclasses import replace
from fractions import Fraction
import unittest

from .model import (ContractError, _RANK, candidate_config, edge_at_or_after,
                    edge_ps, simulate, validate)


def ordered(events):
    return sorted(events, key=lambda e: (e["t_ps"], _RANK[e["kind"]], e.get("read_id", -1)))


class WeightInterfaceTests(unittest.TestCase):
    def tiny(self, mode="resident", **kwargs):
        return candidate_config(mode, inputs=8, outputs=4, tiles=2, samples=3, **kwargs)

    def assert_bad(self, cfg, events, addresses=None, tokens=None, message=None):
        with self.assertRaises(ContractError) as raised:
            validate(cfg, ordered(events), addresses, tokens)
        if message:
            self.assertIn(message, str(raised.exception))

    def test_both_candidates_cover_exact_words_and_samples(self):
        for mode in ("resident", "reread"):
            with self.subTest(mode=mode):
                cfg = self.tiny(mode)
                result = simulate(cfg, sample_tokens=["draw_A", "draw_B", "draw_C"])
                summary = result["summary"]
                self.assertEqual(summary["samples_completed"], 3)
                self.assertEqual(summary["source_advancements"], 3)
                self.assertEqual(summary["weight_bytes_consumed"], 192)
                self.assertEqual(summary["sram_read_bytes"], 64 if mode == "resident" else 192)
                self.assertIsNone(summary["area_um2"])
                self.assertIsNone(summary["energy_pJ"])
                self.assertEqual(validate(cfg, result["events"], result["addresses"], result["sample_tokens"]), summary)

    def test_full_t32_resident_wave_and_local_state(self):
        result = simulate(candidate_config())
        s = result["summary"]
        self.assertEqual(s["wave_bytes"], 32768)
        self.assertEqual(s["read_transactions"], 2048)
        self.assertEqual(s["sram_read_bytes"], 32768)
        self.assertEqual(s["weight_bytes_consumed"], 32768 * 32)
        self.assertEqual(s["state_bits"]["local_weights_peak"], 32768 * 8)
        self.assertEqual(s["state_bits"]["sample_bit_sign_bin_required"], 256)
        self.assertEqual(s["state_bits"]["signed_bin_accumulators_required"], 40960)
        self.assertEqual(s["accepted_sample_interval_core_cycles"], [1] * 31)
        self.assertGreater(s["first_sample_ps"], s["weight_transfer_resource_lower_bound_ps_per_wave"])

    def test_full_t32_reread_with_only_one_response_word(self):
        result = simulate(candidate_config("reread"))
        s = result["summary"]
        self.assertEqual(s["read_transactions"], 2048 * 32)
        self.assertEqual(s["sram_read_bytes"], 32768 * 32)
        self.assertEqual(s["state_bits"]["local_weights_peak"], 0)
        self.assertEqual(s["state_bits"]["response_and_inflight_peak"], 128)
        self.assertGreater(min(s["accepted_sample_interval_core_cycles"]), 2048)

    def test_parallel_banks_are_finite_and_hot_bank_serializes(self):
        cfg = self.tiny()
        ordinary = simulate(cfg)
        hot = [i * cfg.word_bytes * cfg.banks for i in range(cfg.word_count)]
        conflicted = simulate(cfg, hot)
        a = [e for e in ordinary["events"] if e["kind"] == "read_issue"]
        b = [e for e in conflicted["events"] if e["kind"] == "read_issue"]
        self.assertEqual([e["sram_cycle"] for e in a], [0] * cfg.word_count)
        self.assertEqual([e["sram_cycle"] for e in b], list(range(cfg.word_count)))
        self.assertGreater(conflicted["summary"]["first_sample_ps"], ordinary["summary"]["first_sample_ps"])

    def test_small_response_capacity_and_slower_fabric_are_honored(self):
        cfg = self.tiny()
        wide = simulate(cfg)["summary"]
        narrow = simulate(replace(cfg, response_buffer_bytes=16))["summary"]
        slow = simulate(replace(cfg, fabric_bytes_per_second=100_000_000))["summary"]
        self.assertGreater(narrow["first_sample_ps"], wide["first_sample_ps"])
        self.assertEqual(narrow["state_bits"]["response_and_inflight_peak"], 128)
        self.assertGreater(slow["first_sample_ps"], wide["first_sample_ps"])
        self.assertEqual(slow["fabric_word_service_ps"], 160000)

    def test_odd_frequency_uses_absolute_rational_edges(self):
        hz = 79_999_997
        for cycle in (0, 1, 2, 101, 4097, 100000):
            exact = Fraction(cycle * 10**12, hz)
            expected = (exact.numerator + exact.denominator - 1) // exact.denominator
            self.assertEqual(edge_ps(cycle, hz), expected)
            self.assertEqual(edge_at_or_after(expected, hz), cycle)
            self.assertEqual(edge_at_or_after(expected + 1, hz), cycle + 1)
        cfg = self.tiny("reread", core_hz=100_000_003, sram_hz=hz,
                        fabric_bytes_per_second=13_000_000_007,
                        read_latency_sram_cycles=3, cdc_delay_ps=17_003)
        result = simulate(cfg)
        self.assertTrue(all(type(e["t_ps"]) is int for e in result["events"]))
        for issue in (e for e in result["events"] if e["kind"] == "read_issue"):
            ready = next(e for e in result["events"] if e["kind"] == "read_ready" and e["read_id"] == issue["read_id"])
            self.assertEqual(ready["t_ps"], edge_ps(issue["sram_cycle"] + 3, hz) + 17003)

    def test_macro_period_screen_rejects_100mhz_without_claiming_sta(self):
        cfg = self.tiny()
        self.assertEqual(simulate(cfg)["summary"]["sram_timing_screen"]["shortest_clock_interval_ps"], 12500)
        with self.assertRaisesRegex(ContractError, "macro minimum cycle"):
            simulate(replace(cfg, sram_hz=100_000_000))
        # An explicitly slower macro is also respected, independently of access.
        with self.assertRaisesRegex(ContractError, "macro minimum cycle"):
            simulate(replace(cfg, sram_min_cycle_ps=12501))
        with self.assertRaisesRegex(ContractError, "shorter than declared SRAM access"):
            simulate(replace(cfg, sram_read_access_ps=12501, cdc_delay_ps=1_000_000))

    def test_multicycle_compute_and_minimum_sample_ii(self):
        cfg = self.tiny(sample_ii_core_cycles=7, resident_sample_core_cycles=3,
                        local_hold_write_cycles=2, local_hold_write_ports=1)
        self.assertEqual(simulate(cfg)["summary"]["accepted_sample_interval_core_cycles"], [7, 7])
        fast = simulate(self.tiny("reread"))["summary"]["end_ps"]
        slow = simulate(self.tiny("reread", chunk_compute_core_cycles=5))["summary"]["end_ps"]
        self.assertGreater(slow, fast)

    def test_t16_t32_t64_counter_state_and_signed_positive_boundaries(self):
        for samples, width in ((16, 19), (32, 20), (64, 21)):
            cfg = candidate_config("reread", samples=samples)
            self.assertEqual(cfg.accumulator_bits, width)
            self.assertEqual(cfg.required_counter_bits, 8 * 64 * 4 * width)
            with self.assertRaisesRegex(ContractError, "positive input-sign/W8"):
                simulate(replace(cfg, accumulator_bits=width - 1))
        # -128 weight times negative input sign gives +8192, beyond signed14.
        cfg = candidate_config("resident", samples=1)
        self.assertEqual(cfg.accumulator_bits, 15)
        with self.assertRaisesRegex(ContractError, "positive input-sign/W8"):
            simulate(replace(cfg, accumulator_bits=14))

    def test_no_hold_direct_full_wave_feed_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "no-hold/direct-feed"):
            simulate(candidate_config("direct_without_hold"))
        with self.assertRaisesRegex(ContractError, "complete local weight holding"):
            simulate(candidate_config("resident", local_weight_hold_bytes=0))
        # A 16B response cannot authorize a 32KiB/10ns consumption event.
        cfg = self.tiny("reread")
        events = simulate(cfg)["events"]
        consume = next(e for e in events if e["kind"] == "consume_chunk")
        consume["kind"] = "consume_resident"
        consume["nbytes"] = cfg.wave_bytes
        self.assert_bad(cfg, events, message="invalid/repeated resident consume")

    def test_invalid_capacities_addresses_and_zero_latencies(self):
        cfg = self.tiny()
        invalid = [dict(response_buffer_bytes=15), dict(local_weight_hold_bytes=63),
                   dict(sample_hold_capacity_bits=cfg.sample_state_bits - 1),
                   dict(counter_capacity_bits=cfg.required_counter_bits - 1),
                   dict(read_latency_sram_cycles=0), dict(sram_hz=0),
                   dict(core_hz=1.5), dict(word_bytes=3)]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ContractError):
                simulate(replace(cfg, **change))
        for addr in ([0, 0, 32, 48], [0, 16, 32], [0, 16, 32, 49], [0, 16, 32, cfg.sram_capacity_bytes]):
            with self.subTest(addr=addr), self.assertRaises(ContractError):
                simulate(cfg, addr)

    def test_validator_rejects_same_bank_same_edge(self):
        cfg = self.tiny()
        addresses = [i * cfg.word_bytes * cfg.banks for i in range(cfg.word_count)]
        events = simulate(cfg, addresses)["events"]
        issue = next(e for e in events if e["kind"] == "read_issue" and e["read_id"] == 1)
        issue.update(t_ps=0, sram_cycle=0)
        self.assert_bad(cfg, events, addresses, message="bank conflict")

    def test_validator_rejects_off_edge_issue_and_faster_return(self):
        cfg = self.tiny()
        events = simulate(cfg)["events"]
        next(e for e in events if e["kind"] == "read_issue")["t_ps"] += 1
        self.assert_bad(cfg, events, message="exact SRAM edge")
        events = simulate(cfg)["events"]
        next(e for e in events if e["kind"] == "read_ready")["t_ps"] -= 1
        self.assert_bad(cfg, events, message="read return latency")

    def test_validator_rejects_fabric_overlap_and_invented_rate(self):
        cfg = self.tiny()
        events = simulate(cfg)["events"]
        first = next(e for e in events if e["kind"] == "fabric_start" and e["read_id"] == 0)
        second = next(e for e in events if e["kind"] == "fabric_start" and e["read_id"] == 1)
        second.update(t_ps=first["t_ps"], end_ps=first["end_ps"])
        next(e for e in events if e["kind"] == "read_complete" and e["read_id"] == 1)["t_ps"] = first["end_ps"]
        self.assert_bad(cfg, events, message="fabric occupancy")
        events = simulate(cfg)["events"]
        next(e for e in events if e["kind"] == "fabric_start")["end_ps"] -= 1
        self.assert_bad(cfg, events, message="fabric service rate")

    def test_validator_rejects_capacity_excess_independent_of_bandwidth(self):
        cfg = self.tiny()
        events = simulate(cfg)["events"]
        self.assert_bad(replace(cfg, response_buffer_bytes=16), events, message="reservation capacity")
        self.assert_bad(replace(cfg, local_hold_write_ports=1), events, message="local hold write occupancy")

    def test_validator_rejects_use_before_completion_or_missing_return(self):
        cfg = self.tiny("reread")
        events = simulate(cfg)["events"]
        consume = next(e for e in events if e["kind"] == "consume_chunk")
        consume.update(start_ps=0, start_core_cycle=0, end_core_cycle=1, t_ps=10000)
        self.assert_bad(cfg, events, message="before valid read completion")
        events = simulate(cfg)["events"]
        events = [e for e in events if not (e["kind"] == "read_complete" and e["read_id"] == 0)]
        self.assert_bad(cfg, events, message="before valid read completion")

    def test_validator_rejects_early_resident_sample_and_new_load(self):
        cfg = self.tiny()
        events = simulate(cfg)["events"]
        first = next(e for e in events if e["kind"] == "sample_begin")
        first.update(t_ps=40000, core_cycle=4)
        self.assert_bad(cfg, events, message="before complete local weight commit")
        events = simulate(cfg)["events"]
        fake = copy.deepcopy(next(e for e in events if e["kind"] == "read_issue"))
        fake.update(read_id=999, t_ps=75000, sram_cycle=6)
        events.append(fake)
        self.assert_bad(cfg, events, message="preload transactions")

    def test_validator_rejects_duplicate_word_replacing_missing_word(self):
        cfg = self.tiny("reread")
        events = simulate(cfg)["events"]
        for e in events:
            if e.get("read_id") == 1:
                e.update(word_index=0, address=0, bank=0)
        self.assert_bad(cfg, events, message="duplicate word read")

    def test_validator_rejects_dropped_chunk_extra_read_and_sample_scan(self):
        cfg = self.tiny("reread")
        events = simulate(cfg)["events"]
        events = [e for e in events if not (e["kind"] == "consume_chunk" and e["read_id"] == 3)]
        self.assert_bad(cfg, events, message="missing weight words")
        events = simulate(cfg)["events"]
        fake = copy.deepcopy(next(e for e in events if e["kind"] == "read_issue"))
        fake["read_id"] = 999
        events.append(fake)
        self.assert_bad(cfg, events)
        events = simulate(cfg)["events"]
        events = [e for e in events if e.get("sample") != 2]
        self.assert_bad(cfg, events, message="incomplete sample stream")

    def test_validator_rejects_sample_identity_and_sequence_changes(self):
        cfg = self.tiny("reread")
        events = simulate(cfg)["events"]
        next(e for e in events if e["kind"] == "consume_chunk")["token"] = "new_draw"
        self.assert_bad(cfg, events, message="transaction identity changed")
        events = simulate(cfg)["events"]
        next(e for e in events if e["kind"] == "sample_begin")["sequence_index"] = 1
        self.assert_bad(cfg, events, message="out of sequence")
        events = simulate(cfg)["events"]
        first = next(e for e in events if e["kind"] == "sample_begin" and e["sample"] == 1)
        first.update(t_ps=10000, core_cycle=1)
        self.assert_bad(cfg, events, message="earlier sample was incomplete")

    def test_validator_accepts_independently_delayed_legal_schedule(self):
        cfg = self.tiny()
        result = simulate(cfg)
        events = copy.deepcopy(result["events"])
        # 50ns is 5 core cycles and 4 SRAM cycles. This is a legal schedule
        # intentionally different from the scheduler's earliest start.
        for e in events:
            for key in ("t_ps", "start_ps", "end_ps"):
                if key in e:
                    e[key] += 50000
            if "sram_cycle" in e:
                e["sram_cycle"] += 4
            for key in ("core_cycle", "start_core_cycle", "end_core_cycle"):
                if key in e:
                    e[key] += 5
        delayed = validate(cfg, events)
        self.assertEqual(delayed["end_ps"], result["summary"]["end_ps"] + 50000)


if __name__ == "__main__":
    unittest.main()
