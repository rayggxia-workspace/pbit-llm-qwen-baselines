"""Replay public Issue95 component prices; no RTL/EDA/model job is launched."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

EXPECTED = {
    "catalog.json": "385814045ac57f5b16f5e9fea06c3dd143b2b6d1917c97381a8fc02fb73c4f9a",
    "model.py": "4346629cc2e6b9ff61c9ad701623f7d64267c67e61b15820f8660ecaa1f24abb",
    "evidence/38427136_SUMMARY.json": "4fa70df1794572e60b659d5482bd0de3b99e51cc5c5703abba2b1661bde41f44",
}


def replay(catalog_root):
    for name, expected in EXPECTED.items():
        actual = hashlib.sha256((catalog_root / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"source SHA mismatch: {name}")
    spec = importlib.util.spec_from_file_location("reused_digital_pbit", catalog_root / "model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    catalog = module.Catalog()
    for entry in catalog.data["source"]["RTL_files"]:
        if hashlib.sha256((catalog_root / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"frozen RTL mismatch: {entry['path']}")
    for code in range(-128, 128):
        if module.sigmoid_code(code) != round(256 / (1 + math.exp(-code / 8))):
            raise ValueError(f"g8 LUT mismatch: {code}")
    for random in range(256):
        if module.compare8(random, 0) != 0 or module.compare8(random, 256) != 1:
            raise ValueError("probability endpoint mismatch")
    primitive = []
    for design in catalog.data["designs"]:
        if design["corner"] == "ss":
            activity = design["modes"]["random"]
            primitive.append(dict(
                top=design["top"], raw_area_um2=design["area_um2"],
                area55eq_um2=design["area_um2"] * catalog.data["area_factor"],
                total_random_pJ_per_call=activity["pJ_per_call"],
                incremental_random_pJ_per_call=activity["incremental_pJ_per_call"],
                idle_uW=design["modes"]["idle"]["total_uW"],
                setup_slack_ns=design["setup_slack_ns"],
                hold_slack_ns=design["hold_slack_ns"]))
    windows = []
    for samples in (32, 128):
        for lanes in (64, 8, 4):
            row = catalog.estimate_window(
                "full_lut" if lanes == 64 else "shared_lut_cached",
                nodes=64, lut_lanes=lanes, samples_per_configuration=samples,
                corner="ss", clock_mhz=100, inputs_held=True, storage_bits=9)
            windows.append(row)
    return dict(
        kind="EXISTING_MEASUREMENTS_REUSED_CONDITIONAL_COMPOSITION",
        date="2026-10-30", issue=204, model_contract_PR=219,
        source_PR=215, source_commit="c0c8189faf0ac73633fe73a0aacea30df863bc23",
        source_files_SHA256=EXPECTED, source=catalog.data["source"],
        verification=dict(frozen_RTL_SHA=True, g8_LUT_codes=256,
                          endpoint_checks=512, new_RTL_EDA_model_jobs=0),
        contract="g8 signed8 /8; q9=round(256*sigmoid(g8/8)); R8<q9",
        g9_adapter="signed9 /16 -> sat8(RNE(code/2)) before existing LUT",
        area_factor=catalog.data["area_factor"],
        measured_primitive_mode="SS1.08V125C;100MHz;random;3-seed mean",
        measured_primitives=primitive, sigma_only_N64_windows=windows,
        window_boundary=[
            "Only sigma sampling branch: no g/u amplitude conversion/comparators/AND/Wd",
            "Includes fused bit/valid output holding; no PRNG or upstream g/u storage",
            "One LUT dynamic update per new g; comparisons and output capture T times",
            "Shared: prepare ceil(64/LUT_lanes) cycles then T; no overlap/double buffer",
            "Shared q9 cache: 576 bits; CE mapping residual proxy, no ICG discount",
            "Source random-mode residuals are estimates for new input-held activity",
            "No physical N64 array PPA; routing/load/decoder and integrated timing remain",
            "Magnitude g branch still needs g or its derived amplitude during sampling"],
        shared_array_reference=dict(
            run="attention-gf64-direct-198-20261030",
            N=128, LUT_options=[4, 128], measured=True,
            contract="unsigned gap/F4 LUT for sigmoid(-gap/16), q8; different from g/F3",
            boundary="whole Ising path includes RNG/arbitration/histogram; reuse bank/ICG design, not whole-query price"),
        new_registry_run=False, new_PPA=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("SIGMOID_REUSE.json"))
    args = parser.parse_args()
    result = replay(args.catalog_root)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Verified 3 source files, 3 RTL files, 256 g8 codes and 512 endpoint checks; replayed 6 windows. No new circuit run.")
