"""Reproduce explicit sample-length energy scenarios; no new PPA or PPL.

Keep the inherited Qwen scheduler/costs and vary only cfg.samples. The model
does not simulate stratified switching or the new RTL. Output paths must be new.
"""
from __future__ import annotations
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "architecture_tlm"))
from run_local_shared_v2 import configs
from system_decode_local_shared_v2 import LocalSharedDecode


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("Use a new output directory; preserve old evidence bytes")
    rel = Path(__file__).resolve().relative_to(ROOT).as_posix()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "show", head + ":" + rel], cwd=ROOT) != Path(__file__).read_bytes():
        raise ValueError("Commit the exact LF estimator before generating evidence")
    cases, evidence, shape = configs()
    base_cfg = next(c for n, c in cases if n == "new_A8_per_tile")
    profile = evidence["profiles"]["g1_case3"]
    hz = profile["frequency_hz"]
    old_mW = profile["total_W"] * 1000
    old_nJ = old_mW * (4096 + 1) / hz * 1e6
    assert abs(old_nJ - profile["energy_nJ"]) < 1e-9
    a.output.mkdir(parents=True)
    rows = []
    full_runs = {}
    for T in [4096, 256, 128, 64]:
        cfg = copy.deepcopy(base_cfg)
        cfg["samples"] = T
        model = LocalSharedDecode(cfg, "fixed_sc_exact", evidence, shape)
        try:
            result = model.run()
        finally:
            if hasattr(model.ext, "close"):
                model.ext.close()
        assert result["config"]["samples"] == T
        assert result["config"]["external_memory"].get("backend", "link") != "dramsys"
        result["new_evidence_boundary"] = {
            "task": 22, "type": "inherited_same_power_sample_length_sensitivity",
            "source_commit": head, "estimator_sha256": digest(Path(__file__)),
            "new_stratified_switching_simulated": False,
            "new_prng_counter_ppa_measured": False,
            "new_qwen_ppl_measured": False,
            "external_memory": "simplified Link, not a new DRAMSys run",
        }
        write_new(a.output / f"tlm_T{T}.json", result)
        full_runs[T] = result
        n = cfg["decode_tokens"]
        sc = (result["energy_J"]["SC_logic_active"] +
              result["energy_J"]["SC_shared_input_frontend"]) / n * 1000
        us = (T + 1) / hz * 1e6
        rows.append({
            "T": T, "single_column_frame_us": us,
            "old_power_proxy_frame_nJ": old_mW * us,
            "old_power_proxy_plus_extra_power_frame_nJ": {
                str(extra): (old_mW + extra) * us for extra in [0.1, 0.25, 1.0]
            },
            "extra_power_units": "mW; illustrative only, not measured counter power",
            "frame_energy_saving_vs4096": 1 - (old_mW * us / old_nJ),
            "qwen_SC_logic_and_frontend_mJ_per_token": sc,
            "qwen_total_scenario_mJ_per_token": result["metrics"]["scenario_mJ_per_token"],
            "qwen_TPOT_scenario_ms": result["metrics"]["mean_TPOT_ms"],
            "qwen_energy_items_mJ_per_token": {k: v/n*1000 for k, v in result["energy_J"].items()},
        })
    baseline = rows[0]
    for row in rows:
        row["total_saving_vs4096"] = 1 - row["qwen_total_scenario_mJ_per_token"] / baseline["qwen_total_scenario_mJ_per_token"]
    shape_check = {
        "hidden": 896, "ffn_width": 4864, "layers": 24,
        "ffn_MACs_per_decode_token": 3 * 896 * 4864 * 24,
        "64input_1output_column_frames_per_token": 3 * 896 * 4864 * 24 // 64,
        "64x64_tiles_per_token": 3 * 896 * 4864 * 24 // 4096,
    }
    sources = ["architecture_tlm/system_decode.py", "architecture_tlm/system_decode_local_shared_v2.py",
               "architecture_tlm/run_local_shared_v2.py", "architecture_tlm/rng_local_shared_v2.py",
               "architecture_tlm/configs/local_shared_v2.json", "architecture_tlm/configs/evidence_contract.json",
               "architecture_tlm/evidence/grouped_38015538/breakdown.csv", rel]
    summary = {
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_commit": head, "command": sys.argv,
        "classification": "conditional algorithm/TLM estimate, not new PT, chip, GPU or PPL measurement",
        "old_ppa_anchor": {**profile, "scope": "old P_W12 independent thresholds and DFF storage; RNG excluded"},
        "shape": shape_check, "rows": rows,
        "given_random_source_fJ_per_raw_bit": 120.80e-6/(450e6*16)*1e15,
        "random_source_note": "given 450MHz 16-bit source; not the new xorshift32 and not added as same-domain measured power",
        "sources": {f: digest(ROOT/f) for f in sources},
        "limits": ["same legacy active power at every T", "no new short-stream Qwen PPL",
                   "no new stratified activity or counter/PRNG PPA", "simplified Link external memory",
                   "inherited SRAM/digital/route costs include uncalibrated parameters", "not matched-accuracy claims"],
    }
    write_new(a.output / "summary.json", summary)
    write_new(a.output / "ARTIFACT_MANIFEST.json", {f.name: {"bytes": f.stat().st_size, "sha256": digest(f)} for f in sorted(a.output.iterdir()) if f.is_file()})
    print(json.dumps({"rows": [{k: r[k] for k in ["T", "old_power_proxy_frame_nJ", "qwen_SC_logic_and_frontend_mJ_per_token", "qwen_total_scenario_mJ_per_token", "qwen_TPOT_scenario_ms"]} for r in rows], "output": str(a.output)}))


if __name__ == "__main__":
    main()
