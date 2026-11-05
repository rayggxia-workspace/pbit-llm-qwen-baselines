"""Reproduce BF16 comparison budgets; no new RTL, STA or power simulation.

Run from any directory with --workspace pointing at the authorized data root.
The paper conversion is explicitly conditional on 2 FLOPs per MAC. It is not
a measured 55 nm dot-product implementation or a precision-matched ranking.
"""
from pathlib import Path
import argparse
import hashlib
import json
import statistics


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    ws = args.workspace.resolve()
    sc_path = root / "architecture_tlm/module_energy_20261028/results/FINAL_SUMMARY.json"
    old_path = ws / "digital_circuit_simulation_registry/records/digital-ppa8-20261025-consolidated-review.json"
    sc = json.loads(sc_path.read_text(encoding="utf-8"))
    old = json.loads(old_path.read_text(encoding="utf-8"))
    legacy = []
    bindings = [{"path": str(p), "sha256": digest(p)} for p in (sc_path, old_path)]
    for row in old["cases"]:
        if row["kind"] != 2:
            continue
        p = Path(row["result_path"]) / "summary.json"
        assert digest(p) == row["summary_sha256"], p
        raw = json.loads(p.read_text(encoding="utf-8"))
        stream = [r for r in raw if r["mode"] == "stream"]
        assert len(stream) == 3 and len({r["seed"] for r in stream}) == 3
        for r in stream:
            assert abs(r["total_uW"] * r["duration_ns"] / 1000 - r["window_pJ"]) < 1e-7
            assert abs(r["window_pJ"] / r["inputs"] - r["pJ_per_input"]) < 1e-7
            assert r["setup_slack_ns"] < 0
        legacy.append({
            "corner": row["corner"], "job": row["job"],
            "raw_area_um2": row["area_um2"],
            "area_55eq_um2": row["area_um2"] * 0.81,
            "stream_power_mW": statistics.mean(r["total_uW"] for r in stream) / 1000,
            "mean_gross_pJ_per_accepted_term": statistics.mean(r["pJ_per_input"] for r in stream),
            "original_terms_in_window": [r["inputs"] for r in stream],
            "original_completed_frames": [r["completed_outputs"] for r in stream],
            "setup_slack_ns": row["setup_slack_ns"],
            "status": "TIMING_VIOLATION; not a valid 100 MHz baseline; variable-length old frames are not N64",
            "summary_path": str(p), "summary_sha256": digest(p),
        })
        bindings.append({"path": str(p), "sha256": digest(p)})
    assert len(legacy) == 2
    banks = []
    for row in sc["PPA"]:
        if row["case"]["name"] not in ("bank54", "bank50"):
            continue
        q = row["profiles"]["replay"]
        energy = q["energy_pJ_per_operation"]
        cycles = q["cycles_per_operation"]
        assert cycles == 35
        banks.append({
            "name": row["case"]["name"], "energy_pJ_per_N64_dot": energy,
            "area_55eq_mm2": row["area_55eq_um2"] / 1e6,
            "frame_cycles": cycles, "frame_ns": cycles * 10,
            "logical_MACs_per_dot": 64,
            "break_even_digital_pJ_per_MAC": energy / 64,
            "equivalent_logical_GFLOPS_per_W": 128000 / energy,
        })
    assert len(banks) == 2
    b54 = next(b for b in banks if b["name"] == "bank54")
    efficiency = 1761.41  # Reported BF16 GFLOPS/W, primary HKU/IEEE abstract.
    paper = {
        "url": "https://hub.hku.hk/handle/10722/339469",
        "doi": "10.1109/TCSII.2023.3322259",
        "node_nm": 28, "slow_corner_frequency_GHz": 1.471,
        "reported_BF16_GFLOPS_per_W": efficiency,
        "assumed_FLOPs_per_MAC": 2,
        "conditional_pJ_per_MAC": 2000 / efficiency,
        "conditional_N64_ideal_pJ": 128000 / efficiency,
        "conditional_N64_padded_to_9_terms_pJ": 144000 / efficiency,
        "ideal_energy_over_SC54_core": (128000 / efficiency) / b54["energy_pJ_per_N64_dot"],
        "status": "ABSTRACT_VERIFIED; full arithmetic/operation-count/area/PVT/latency contract unverified; no process scaling",
    }
    budgets = []
    for missing_frontend_pJ in (0, 10, 25, 50):
        e = b54["energy_pJ_per_N64_dot"] + missing_frontend_pJ
        for advantage in (1, 2, 5, 10):
            budgets.append({
                "SC54_extra_cost_scenario_pJ": missing_frontend_pJ,
                "desired_digital_over_SC_energy_ratio": advantage,
                "required_digital_pJ_per_MAC": advantage * e / 64,
                "note": "Budget sensitivity only; extra cost is not measured; digital omitted costs must also be closed",
            })
    # Trace the legacy structural diagnosis without copying another task's RTL.
    rtl_root = ws / "project_archives/digital_ppa8_20261023/delivery_final/digital_ppa8_ss_tt_100_20261023_v1"
    for relative in ("rtl/nr_vector_math.sv", "rtl/nr_fp32_mul.sv", "rtl/nr_digital_probe.sv",
                     "conversion/fc_fp_add.sv", "conversion/fc_fixed_to_fp.sv", "conversion/fc_scale_mag.sv"):
        p = rtl_root / relative
        bindings.append({"path": str(p), "sha256": digest(p)})
    add = (rtl_root / "conversion/fc_fp_add.sv").read_text(encoding="utf-8")
    assert "j<FRAC+3" in add and "sum=sum<<1;e=e-1" in add
    result = {
        "date": "2026-10-28", "evidence": "READ_ONLY_RESEARCH_AND_DERIVED_BUDGETS",
        "new_simulation_count": 0, "new_PPA_run": False,
        "input_bindings": bindings, "SC_core": banks, "legacy_BF16_diagnostic_only": legacy,
        "paper_conditional_conversion": paper, "energy_budget_sensitivity": budgets,
        "speed_budget": {"N": 64, "clock_MHz": 100, "target_full_frame_cycles": 35,
                         "minimum_average_useful_MACs_per_cycle_including_overhead": 64 / 35,
                         "warning": "Lane count alone does not determine latency/II; feedback dependencies and fill/drain/reduction must be implemented"},
        "strict_same_process_BF16_MAC_PPA": None,
        "strict_same_process_BF16_dot_PPA": None,
        "module_candidates": ["BF16xBF16 exact product -> FP32 (range/underflow contract explicit)",
                              "FP32 add with tree LZC + one barrel normalization + RNE",
                              "BF16xBF16+FP32 fused MAC", "DOT2/DOT4/DOT8 with shared alignment/normalization",
                              "N64 frame wrapper with real partial-sum contexts, clock/CE, final reduce and format conversion"],
        "quality_comparison": "BF16 arithmetic and SC W8/T32/OR4 are different numerical contracts; no new model inference or PPL",
    }
    (here / "ESTIMATE.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"legacy_summaries_SHA_verified": len(legacy), "SC_banks": banks,
                      "paper": paper, "new_simulations": 0}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
