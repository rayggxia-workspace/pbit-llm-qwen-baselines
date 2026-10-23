"""Adversarial preparation/parser tests; never invoke licensed executables."""
import json
from pathlib import Path
import tempfile
import unittest

from . import driver, reports


class FlowTests(unittest.TestCase):
    def temporary(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-ppa-", dir=driver.HERE)
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def test_five_cases_are_source_bound_and_explicitly_not_run(self):
        root = self.temporary() / "prepared"
        result = driver.prepare(root)
        self.assertEqual(result["status"], "not_run")
        self.assertIsNone(result["area"])
        self.assertIsNone(result["power"])
        self.assertIsNone(result["sta"])
        self.assertEqual(len(result["cases"]), 5)
        self.assertEqual([(c["samples"], c["count_width"]) for c in result["cases"] if c["kind"] == 2],
                         [(16, 11), (32, 12), (64, 13)])
        self.assertTrue(all(c["depth"] == 3 and len(c["vectors"]) == 3 for c in result["cases"]))
        self.assertEqual(driver.verify_prepared(root), result)
        vector = root / result["cases"][0]["vectors"][0]["path"]
        vector.write_text("0 0 0 0\n", encoding="ascii")
        with self.assertRaisesRegex(ValueError, "input changed"):
            driver.verify_prepared(root)

    def test_resume_hash_checks_and_preserves_partial_stage(self):
        root = self.temporary()
        stage = root / "stage"
        calls = []
        def produce(folder):
            calls.append(1)
            (folder/"done").write_text("first", encoding="utf-8")
        driver.stage(stage, ["done"], produce)
        driver.stage(stage, ["done"], produce)
        self.assertEqual(calls, [1])
        (stage/"done").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed completed"):
            driver.stage(stage, ["done"], produce)
        partial = root/"partial"
        partial.mkdir()
        with self.assertRaisesRegex(ValueError, "partial stage preserved"):
            driver.stage(partial, ["done"], produce)

    def test_environment_is_explicit_and_paths_do_not_escape(self):
        with self.assertRaisesRegex(ValueError, "missing explicit"):
            driver.environment(self.temporary(), "SS", {})
        with self.assertRaises(ValueError):
            driver.absolute_file("relative.db", "STD_DB")
        root = self.temporary()
        with self.assertRaises(ValueError):
            driver.contained(root/".."/"outside", root)

    def test_pvt_named_and_table_reports(self):
        named = "Operating Condition Name : ss\n Process : 1\n Temperature : 125\n Voltage : 1.08\n"
        self.assertEqual(reports.operating_condition(named, "ss", "SS")["voltage_V"], 1.08)
        table = "Name Process Volt Temp\nss 1 1.08 125\n"
        self.assertEqual(reports.operating_condition(table, "ss", "SS")["temperature_C"], 125)
        with self.assertRaises(ValueError):
            reports.operating_condition(named, "ss", "TT")
        with self.assertRaises(ValueError):
            reports.operating_condition(named+named, "ss", "SS")

    def test_units_reject_incompatible_constraints(self):
        reports.units("Time Units : 1ns\nCapacitive Load Units : 1pf\n")
        for text in ("Time Units : 1ps\nCapacitive Load Units : 1pf\n",
                     "Time Units : 1ns\nCapacitive Load Units : 1ff\n", ""):
            with self.assertRaises(ValueError):
                reports.units(text)

    def test_power_units_and_conservation(self):
        explicit = "Cell Internal Power = 2 mW\nNet Switching Power = 3 mW\nCell Leakage Power = 1 uW\nTotal Power = 5.001 mW\n"
        self.assertAlmostEqual(reports.power(explicit)["total_W"], .005001)
        declared = "Dynamic Power Units = 1mW\nLeakage Power Units = 1uW\n" + explicit.replace(" mW", "").replace(" uW", "")
        self.assertAlmostEqual(reports.power(declared)["total_W"], .005001)
        for bad in (explicit.replace("5.001", "50"), explicit.replace("5.001 mW", "NaN mW"),
                    explicit.replace(" mW", "").replace(" uW", ""), ""):
            with self.assertRaises(ValueError):
                reports.power(bad)

    def test_activity_incomplete_is_not_full_coverage(self):
        text = "Total number of nets = 100\nNumber of annotated nets = 99\nTotal number of leaf cells = 20\nNumber of fully annotated leaf cells = 20\n"
        self.assertFalse(reports.activity(text)["complete"])
        self.assertTrue(reports.activity(text.replace("= 99", "= 100"))["complete"])
        with self.assertRaises(ValueError):
            reports.activity(text.replace("= 99", "= 101"))

    def test_window_rejects_reset_wrong_clock_and_unbalanced_counts(self):
        data = dict(start_ps=100, end_ps=640100, accepted=64, completed=64, period_ps=10000,
                    scenario="synthetic_active", contains_reset=0, contains_drain=0, warmup_continuous_cycles=32)
        self.assertEqual(reports.window(data)["duration_ns"], 640)
        for change in ({"completed": 63}, {"contains_reset": 1}, {"period_ps": 12500},
                       {"warmup_continuous_cycles": 0}, {"start_ps": 1.0}):
            with self.assertRaises(ValueError):
                reports.window(dict(data, **change))

    def test_vcd_x_before_window_allowed_but_persistent_or_in_window_rejected(self):
        folder = self.temporary()
        path = folder/"activity.vcd"
        prefix = "$timescale 1ps $end\n$var wire 1 ! clk $end\n$enddefinitions $end\n#0\nx!\n"
        path.write_text(prefix+"#5\n0!\n#10\n1!\n#20\n0!\n#30\n", encoding="ascii")
        self.assertEqual(reports.audit_vcd(path, 10, 30)["xz_signals"], 0)
        for body in ("#10\nx!\n#30\n", "#5\n0!\n#15\nz!\n#30\n", "#5\n0!\n#20\n"):
            path.write_text(prefix+body, encoding="ascii")
            with self.assertRaises(ValueError):
                reports.audit_vcd(path, 10, 30)

    def test_missing_report_or_tool_error_is_failure(self):
        with self.assertRaises(ValueError):
            reports.require_reports(self.temporary(), ["missing.rpt"])
        with self.assertRaises(ValueError):
            reports.audit_log("Error: unresolved module\n")
        self.assertEqual(len(reports.audit_log("Warning: PWR-981 model extrapolation\n")), 1)

    def test_summary_keeps_unknown_area_units_and_rejects_constraint_violations(self):
        folder = self.temporary()
        for name in ("clock.rpt", "setup.rpt", "hold.rpt", "constraints.rpt", "check_timing.rpt",
                     "check_power.rpt", "inventory.tsv", "link.log", "condition.log", "vcd.log",
                     "update_power.log", "pt.log", "DONE"):
            (folder/name).write_text("fixture only\n", encoding="utf-8")
        content = {
            "units.rpt": "Time Units : 1ns\nCapacitive Load Units : 1pf\n",
            "library.rpt": "Operating Condition Name : ss\nTemperature : 125\nVoltage : 1.08\n",
            "design.rpt": "Operating Conditions : ss\n",
            "power.rpt": "Cell Internal Power = 2 mW\nNet Switching Power = 3 mW\nCell Leakage Power = 1 uW\nTotal Power = 5.001 mW\n",
            "activity.rpt": "Total number of nets = 100\nNumber of annotated nets = 100\nTotal number of leaf cells = 20\nNumber of fully annotated leaf cells = 20\n",
            "area.txt": "100.0\n", "setup_slack.txt": "0.2\n", "hold_slack.txt": "0.1\n"}
        for name, text in content.items():
            (folder/name).write_text(text, encoding="utf-8")
        meta = dict(start_ps=0, end_ps=640000, accepted=64, completed=64, period_ps=10000,
                    scenario="synthetic_active", contains_reset=0, contains_drain=0, warmup_continuous_cycles=32)
        config = dict(oc_name="ss", corner="SS", area_unit="library_area_unit")
        row = reports.summarize(folder, meta, config)
        self.assertIsNone(row["area_um2"])
        self.assertFalse(row["accepted_for_tlm"])
        self.assertAlmostEqual(row["energy_pJ_per_completed"], 50.01)
        config.update(area_unit="um2", area_unit_evidence_sha256="synthetic-fixture-evidence")
        self.assertTrue(reports.summarize(folder, meta, config)["accepted_for_tlm"])
        (folder/"constraints.rpt").write_text("max_transition (VIOLATED)\n", encoding="utf-8")
        self.assertFalse(reports.summarize(folder, meta, config)["accepted_for_tlm"])
        (folder/"constraints.rpt").write_text("fixture only\n", encoding="utf-8")
        (folder/"hold_slack.txt").write_text("-0.1\n", encoding="utf-8")
        self.assertFalse(reports.summarize(folder, meta, config)["accepted_for_tlm"])

    def test_actual_window_text_schema_and_duplicate_rejection(self):
        path = self.temporary()/"window.txt"
        text = "scenario=synthetic_active\ntimescale=1ns/1ps\nstart_ps=1000000\nend_ps=1640000\nperiod_ps=10000\naccepted=64\ncompleted=64\ncontains_reset=0\ncontains_drain=0\nwarmup_continuous_cycles=32\n"
        path.write_text(text, encoding="utf-8")
        self.assertEqual(reports.read_window(path)["duration_ns"], 640)
        path.write_text(text+"completed=64\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            reports.read_window(path)


if __name__ == "__main__":
    unittest.main()
