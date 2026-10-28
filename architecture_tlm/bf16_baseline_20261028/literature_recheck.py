"""Reproduce second-search literature normalization; no new circuit simulation."""
from pathlib import Path
import argparse
import hashlib
import json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    archive = args.workspace / "project_archives/matrix204_bf16_literature_20261028"
    manifest = json.loads((archive / "MANIFEST.json").read_text(encoding="utf-8"))
    for p in manifest["papers"]:
        assert sha(Path(p["path"])) == p["sha256"]
        assert sha(Path(p["png_path"])) == p["png_sha256"]
        assert sha(archive / (p["name"] + ".table.txt")) == p["table_text_sha256"]
    sc_path = root / "architecture_tlm/module_energy_20261028/results/FINAL_SUMMARY.json"
    sc = json.loads(sc_path.read_text(encoding="utf-8"))
    sc54 = next(r for r in sc["PPA"] if r["case"]["name"] == "bank54")["profiles"]["replay"]["energy_pJ_per_operation"]
    power, ops = 1.85, 1.024
    mfsa = {
        "title": "MFSA: A Multi-Format Systolic Array with Native Micro Scaling Support",
        "url": "https://arxiv.org/html/2610.19645v1", "version": "2610.19645v1; 2026-10-14 preprint",
        "table": "II; PDF page6", "node_nm": 28, "corner": "SS", "voltage_V": 0.72,
        "temperature_C": 125, "MHz": 1000, "array": [16, 16], "BF16_products_per_PE_per_cycle": 2,
        "input_format": "BF16", "accumulator": "FP32", "power_W": power, "throughput_TOPS": ops,
        "MAC_operation_count": 2, "reported_pJ_per_op_rounded": 1.80,
        "derived_pJ_per_op": power / ops, "derived_pJ_per_MAC": 2 * power / ops,
        "steady_state_64_MAC_work_pJ": 128 * power / ops,
        "rounded_table_64_MAC_work_pJ": 128 * 1.80,
        "reported_power_over_throughput_to_SC54_core_ratio": (128 * power / ops) / sc54,
        "signoff_cell_area_mm2_all_formats": 3.27, "die_dimensions_mm": [2.4, 2.4],
        "evidence": "author-reported RTL/post-route power estimation; not measured silicon or independently reproduced",
        "activity": "gate-level GEMM traces; Qwen2.5-7B prefill, post-RMSNorm distributions",
        "window": "steady activation-stream window; reset/weight preload/drain excluded",
        "physical_flow": "Genus/Innovus/Joules, post-route RC, automatic clock gating",
        "not_inferred": ["55nm power or area", "cold N64 transaction energy or latency", "BF16-only array area", "whole accelerator or SRAM/DRAM energy"],
    }
    assert ops == 16 * 16 * 2 * 2 * 1e9 / 1e12
    # Table entries are rounded independently. Preserve both the reported and
    # derived energy instead of silently choosing a favorable representation.
    assert abs(mfsa["derived_pJ_per_op"] - 1.80) < 0.01
    flex_power, flex_ops = 9.84, 1.77
    flex = {
        "title": "FlexBlock author-hosted paper, TPU-like SA baseline",
        "url": "https://jongse-park.github.io/files/paper/2023-tc-flexblock.pdf",
        "embedded_version": "arXiv2203.06673v1; 2022-03-13 (filename is not a version identifier)",
        "table": "V; PDF page10", "node_nm": 65, "MHz": 333, "array": [128, 128],
        "precision": "bfloat16 baseline (not the proposed block-floating FB16)",
        "area_mm2": 74.38, "power_W": flex_power, "reported_throughput_TFLOPS": flex_ops,
        "reported_efficiency_GFLOPS_per_W": 179.6,
        "P_over_reported_throughput_pJ_per_MAC": 2 * flex_power / flex_ops,
        "workload_normalized_64_MAC_work_pJ": 128 * flex_power / flex_ops,
        "using_reported_rounded_efficiency_64_MAC_work_pJ": 128000 / 179.6,
        "ideal_multiplier_count_peak_TFLOPS": 128 * 128 * 333e6 * 2 / 1e12,
        "reported_throughput_over_ideal_peak": flex_ops / (128 * 128 * 333e6 * 2 / 1e12),
        "evidence": "author-implemented RTL baseline, DC/SAIF power and workload/cycle modeling; no silicon measurement",
        "boundary": "TableV core comparison; SRAM modeled separately with CACTI; workload utilization and buffering affect throughput",
        "not_inferred": ["pure scalar MAC energy", "same steady-state window as MFSA", "55nm-scaled area/power", "10x SC advantage"],
    }
    out = {"checked_on": "2026-10-28", "primary_paper_artifacts": manifest["papers"],
           "MFSA28": mfsa, "FlexBlock65_BF16_control": flex,
           "SC54_core_reference": {"source": str(sc_path), "sha256": sha(sc_path), "N64_frame_pJ": sc54,
                                   "frame_ns": 350, "input_contract": "W8/T32/OR4, predecoded magnitudes/signs; frontends omitted"},
           "new_simulation_count": 0,
           "decision": "Usable primary 28nm digital BF16/FP32 array evidence found. Do not claim literature is absent. No EDA triggered by the user's conditional fallback; same-process55 characterization remains a distinct future task."}
    (here / "LITERATURE_RECHECK.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"primary_PDFs_SHA_verified": len(manifest["papers"]),
                      "MFSA28_pJ_per_MAC": mfsa["derived_pJ_per_MAC"],
                      "MFSA28_per_64_MACs_pJ": mfsa["steady_state_64_MAC_work_pJ"],
                      "MFSA28_over_SC54_core": mfsa["reported_power_over_throughput_to_SC54_core_ratio"],
                      "Flex65_workload_per_64_MACs_pJ": flex["workload_normalized_64_MAC_work_pJ"],
                      "Flex65_utilization_diagnostic": flex["reported_throughput_over_ideal_peak"],
                      "new_simulations": 0}, indent=2))


if __name__ == "__main__":
    main()
