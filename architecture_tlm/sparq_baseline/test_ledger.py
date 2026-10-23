import json
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from .ledger import Config, Rates, bitonic_comparisons, build_ledger, burst_traffic, synthetic_indices
from .run import main


def ledger(c, pattern="contiguous", rates=None):
    fixture = synthetic_indices(c, pattern)
    return build_ledger(c, fixture["channel_ids"], fixture["token_ids"], rates,
                        provenance=fixture["provenance"])


class LedgerTests(unittest.TestCase):
    def test_dense_fallback_has_no_selector_and_matches_dense_core(self):
        x = ledger(Config(128), rates=Rates())
        self.assertTrue(x["effective"]["dense_fallback"])
        self.assertEqual(x["operations"], x["dense_baseline_operations"])
        self.assertEqual(x["traffic"]["core_physical_read_bytes"], 524288)
        self.assertEqual(x["traffic"]["core_read_ratio"], 1)
        self.assertEqual(x["storage"]["cache_capacity_ratio"], 1.5)
        # Dense fallback must not silently erase dual-cache maintenance.
        self.assertGreater(x["traffic"]["append_physical_write_bytes"], x["traffic"]["dense_append_physical_write_bytes"])

    def test_gqa_arithmetic_does_not_disappear_with_shared_reads(self):
        x = ledger(Config(2048))
        self.assertEqual(x["operations"]["approx_qk"]["approx_qk_mac"], 32*2048*32)
        self.assertEqual(x["operations"]["exact_qk"]["exact_qk_mac"], 32*128*128)
        self.assertEqual(x["operations"]["exact_pv"]["exact_pv_mac"], 32*128*128)
        self.assertEqual(x["operations"]["approx_qk"]["scale_multiply"], 32*32)
        self.assertEqual(x["operations"]["exact_qk"]["scale_multiply"], 32*128)
        self.assertEqual(x["operations"]["approx_softmax"]["exp"], 32*2048)
        self.assertEqual(x["operations"]["group_probability_sum"]["head_sum_add"], 24*2048)
        self.assertEqual(x["traffic"]["core_logical_read_bytes"], 8*2*(2048*32+2*128*128))
        self.assertEqual(x["traffic"]["core_read_ratio"], 0.1875)

    def test_spread_channels_expose_single_layout_burst_amplification(self):
        dual = ledger(Config(2048), "spread")
        single = ledger(Config(2048, layout="token_major"), "spread")
        contiguous = ledger(Config(2048, layout="token_major"), "contiguous")
        self.assertEqual(dual["traffic"]["core_logical_read_bytes"], single["traffic"]["core_logical_read_bytes"])
        self.assertEqual(single["traffic"]["by_stage"]["approx_K_read"]["physical_bytes"], 8*2048*256)
        self.assertEqual(contiguous["traffic"]["by_stage"]["approx_K_read"]["physical_bytes"], 8*2048*64)
        self.assertEqual(dual["traffic"]["by_stage"]["approx_K_read"]["physical_bytes"], 8*2048*32*2)

    def test_dual_append_strided_writes_are_counted_and_not_amortized(self):
        x = ledger(Config(8192, capacity_tokens=32768))
        self.assertEqual(x["traffic"]["append_logical_write_bytes"], 8*128*2*3)
        self.assertEqual(x["traffic"]["by_stage"]["append_transposed_K_write"]["physical_bytes"], 8*128*64)
        self.assertEqual(x["traffic"]["append_physical_write_bytes"], 69632)
        self.assertEqual(x["storage"]["total_cache_allocated_bytes"], 8*32768*128*2*3)
        self.assertEqual(x["traffic"]["construction_extra_read_bytes"], 8*8192*128*2)
        self.assertEqual(x["traffic"]["construction_extra_write_bytes"], 8*8192*128*2)

    def test_exact_small_unaligned_ranges_against_enumerated_byte_oracle(self):
        ranges = [(3, 2), (5, 8), (12, 6), (20, 0), (24, 2), (4, 1)]
        actual = burst_traffic(ranges, 8)
        expected = {a//8 for start,size in ranges for a in range(start,start+size)}
        self.assertEqual(actual, {"burst_transactions":len(expected), "physical_bytes":len(expected)*8})
        # Odd row widths and capacity padding exercise the non-aligned scan.
        c = Config(9, query_heads=4, kv_heads=2, head_dim=5, channels=2,
                   selected_tokens=3, local_tokens=1, layout="token_major", burst_bytes=8, capacity_tokens=11)
        f = synthetic_indices(c,"spread")
        x = build_ledger(c,f["channel_ids"],f["token_ids"])
        stride = 112
        touched = set()
        for g in range(2):
            for t in range(9):
                for ch in (0,2):
                    for byte in range(2): touched.add((g*stride+t*10+ch*2+byte)//8)
        self.assertEqual(x["traffic"]["by_stage"]["approx_K_read"]["physical_bytes"], len(touched)*8)

    def test_gqa_different_indices_and_local_are_respected(self):
        c = Config(10,query_heads=4,kv_heads=2,head_dim=8,channels=2,selected_tokens=3,local_tokens=1,burst_bytes=8)
        x = build_ledger(c,[[0,1],[0,7]],[[0,2,9],[3,4,9]])
        self.assertEqual(x["traffic"]["by_stage"]["selected_K_read"]["physical_bytes"], 6*16)
        with self.assertRaisesRegex(ValueError,"mandatory"):
            build_ledger(c,[[0,1],[0,7]],[[0,2,9],[3,4,8]])

    def test_bad_shape_duplicates_boolean_or_out_of_range_rejected(self):
        c = Config(512)
        f = synthetic_indices(c)
        for bad in ([f["channel_ids"][0]], [[0]*32]*8, [[True]+list(range(1,32))]*8, [list(range(1,33))]*7+[list(range(96,128))]):
            if len(bad)==8 and bad[-1]==list(range(96,128)):
                bad[-1][-1]=128
            with self.assertRaises(ValueError): build_ledger(c,bad,f["token_ids"])
        duplicate = [list(row) for row in f["token_ids"]]
        duplicate[0][1]=duplicate[0][0]
        with self.assertRaises(ValueError): build_ledger(c,f["channel_ids"],duplicate)

    def test_invalid_profiles_do_not_silently_repair(self):
        for kwargs in ({"query_heads":31}, {"channels":129}, {"local_tokens":129},
                       {"capacity_tokens":127}, {"reallocation":True}, {"reallocation":1},
                       {"burst_bytes":3}, {"storage_dtype":"fp32"}, {"n_tokens":True}):
            args={"n_tokens":128};args.update(kwargs)
            with self.assertRaises(ValueError): Config(**args).validate()
        with self.assertRaises(ValueError): Rates(macs_per_cycle=0).validate()

    def test_mixed_zero_l1_fallback_charges_full_group_reads_and_compute(self):
        c=Config(512)
        f=synthetic_indices(c)
        f["token_ids"][2]=list(range(512))
        x=build_ledger(c,f["channel_ids"],f["token_ids"],dense_fallback_kv_heads=[2])
        self.assertEqual(x["effective"]["dense_fallback_kv_heads"],[2])
        self.assertEqual(x["operations"]["approx_qk"]["approx_qk_mac"],7*4*512*32)
        self.assertEqual(x["operations"]["exact_qk"]["exact_qk_mac"],4*(7*128+512)*128)
        self.assertEqual(x["operations"]["exact_softmax"]["exp"],4*(7*128+512))
        self.assertEqual(x["traffic"]["core_logical_read_bytes"],2*(7*512*32+2*(7*128+512)*128))
        # All heads participated in the channel/zero-L1 test before this fallback.
        self.assertEqual(x["operations"]["tau"]["zero_selected_l1_test"],32)
        self.assertEqual(x["reference_implementation_extra"]["finite_validation_if_enabled"]["logical_read_bytes"],8*2*512*128*2)
        with self.assertRaises(ValueError):
            build_ledger(c,f["channel_ids"],f["token_ids"],dense_fallback_kv_heads=[2,2])
        with self.assertRaises(ValueError):
            build_ledger(c,f["channel_ids"],synthetic_indices(c)["token_ids"],dense_fallback_kv_heads=[2])

    def test_all_zero_l1_fallback_keeps_detection_but_skips_approx_scan(self):
        c=Config(512)
        f=synthetic_indices(c)
        x=build_ledger(c,f["channel_ids"],[list(range(512)) for _ in range(8)],dense_fallback_kv_heads=list(range(8)))
        self.assertTrue(x["effective"]["dense_fallback"])
        self.assertIn("channel_selection",x["operations"])
        self.assertNotIn("approx_qk",x["operations"])
        self.assertEqual(x["traffic"]["core_read_ratio"],1)

    def test_masked_fallback_trace_uses_empty_unused_channels_not_fake_indices(self):
        c=Config(512)
        f=synthetic_indices(c)
        f["channel_ids"][2]=[]
        f["token_ids"][2]=list(range(512))
        x=build_ledger(c,f["channel_ids"],f["token_ids"],dense_fallback_kv_heads=[2])
        self.assertEqual(x["effective"]["dense_fallback_kv_heads"],[2])
        with self.assertRaises(ValueError):
            build_ledger(c,f["channel_ids"],synthetic_indices(c)["token_ids"])
        dense=build_ledger(Config(128),[[] for _ in range(8)], [list(range(128)) for _ in range(8)])
        self.assertEqual(dense["operations"],dense["dense_baseline_operations"])

    def test_selection_is_declared_sort_cost_not_one_op(self):
        self.assertEqual(bitonic_comparisons(1),0)
        self.assertEqual(bitonic_comparisons(3),6)
        self.assertEqual(bitonic_comparisons(128),1792)
        x = ledger(Config(512))
        self.assertEqual(x["operations"]["token_selection"]["compare_exchange"],8*11520)
        self.assertEqual(x["selection_reference"]["token_sort_input_count"],480)

    def test_all_requested_lengths_have_null_physical_prices(self):
        for n in (128,512,2048,8192,32768):
            x=ledger(Config(n))
            self.assertEqual(x["hardware"]["sta_status"],"not_run")
            for name in ("area_um2","power_W","energy_J"): self.assertIsNone(x["hardware"][name])
            self.assertIsNone(x["conditional_cycles"])
            self.assertTrue(all(x["disabled"].values()))

    def test_rates_only_change_conditional_work_and_use_integer_ceil(self):
        c=Config(512)
        a=ledger(c,rates=Rates(clock_hz=81_000_001,macs_per_cycle=3))
        b=ledger(c,rates=Rates(clock_hz=81_000_001,macs_per_cycle=6))
        self.assertEqual(a["traffic"],b["traffic"])
        self.assertEqual(a["operations"],b["operations"])
        cycles=a["conditional_cycles"]
        self.assertEqual(cycles["cycles_by_resource"]["mac"],(cycles["work"]["mac"]+2)//3)
        self.assertGreaterEqual(cycles["no_overlap_service_work_cycles"],cycles["capacity_lower_bound_cycles"])
        self.assertIsNone(cycles["latency_ns"])

    def test_cli_replay_provenance_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path=Path(tmp)/"ledger.json"
            args=["--tokens","128","512","--layouts","dual_k","--patterns","spread","--out",str(path)]
            with redirect_stdout(io.StringIO()): self.assertEqual(main(args),0)
            d=json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(d["cases"]),2)
            self.assertIn("ledger.py",d["source_sha256"])
            self.assertFalse(d["model_target"]["weights_loaded"])
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): main(args)


if __name__ == "__main__":
    unittest.main()
