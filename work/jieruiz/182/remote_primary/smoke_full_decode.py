"""Issue182 real bridge gates for the frozen full-decode source snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--bridge", type=Path, required=True)
    a = p.parse_args()
    manifest_path = a.source / "work/jieruiz/182/SOURCE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    for rel, expected in manifest["files"].items():
        assert sha(a.source/rel) == expected["sha256"], rel
        assert (a.source/rel).stat().st_size == expected["bytes"], rel
    a.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.source))
    from architecture_tlm.unified_v6.config import tiny
    from architecture_tlm.unified_v6.ffn_latest import defaults
    from architecture_tlm.unified_v6.memory_profiles import apply
    from architecture_tlm.unified_v6.model import FullDecode
    rows = []
    for name, profile, double_buffer in [("tiny_ddr4_legacy_schedule", "ddr4", False),
                                           ("tiny_ddr4_prefetch", "balanced_ddr4", True)]:
        output = a.output / name
        output.mkdir()
        c, m = tiny()
        c["ffn"].update(defaults())
        c["ffn"].update(engines=2, local_weight_bytes=8192)
        c["random"]["backend"] = "integrated_service"
        c["attention"]["mode"] = "exact"
        c["double_buffer"] = double_buffer
        c = apply(c, profile, str(a.bridge), output/"dram")
        assert c["dram"]["backend"] == "dramsys"
        assert sha(c["dram"]["configuration"]) == "ddbdd1aee7f20d5e3eaf12d73b7e300894ad3ab5cc50ae2a8aa5fd121b2fa419"
        start = time.monotonic()
        model = FullDecode(c, m)
        assert model.integrated_rng
        r = model.run()
        elapsed = time.monotonic() - start
        d = r["DRAM"]["details"]
        bursts = sum(v for k,v in r["DRAM"]["traffic"].items() if k.endswith("_bursts"))
        assert bursts > 0 and bursts == d["burst_count"]
        assert d["status"] == "finished"
        assert d["read_bursts"] + d["write_bursts"] == bursts
        assert d["capacity_bytes"] == 16*1024**3
        assert d["peak_pending"] <= 32
        assert r["FFN_activity"]["SC_64x64_tiles"] == 6
        assert r["energy_J"]["external_DRAMPower_core"] > 0
        assert "external_DRAMPower_interface" in r["energy_J"]
        assert r["metrics"]["full_physical_energy_J"] is None
        save(output/"RESULT.json", r)
        row = dict(case=name, source_commit=manifest["commit"], wall_seconds=elapsed,
            TPOT_ms=r["metrics"]["TPOT_ms"], bursts=bursts,
            core_J=r["energy_J"]["external_DRAMPower_core"],
            source_manifest_sha256=sha(manifest_path), bridge_sha256=sha(a.bridge),
            config_sha256=sha(c["dram"]["configuration"]),
            integrated_rng=True, latest_ffn=True, status="passed")
        rows.append(row)
        print(json.dumps(row), flush=True)
    save(a.output/"SUMMARY.json", rows)
    files = {str(f.relative_to(a.output)): dict(bytes=f.stat().st_size, sha256=sha(f))
             for f in a.output.rglob("*") if f.is_file()}
    save(a.output/"MANIFEST.json", dict(status="passed", completed=len(rows), expected=2,
        files=files, slurm_job_id=os.getenv("SLURM_JOB_ID"),
        smoke_script_sha256=sha(__file__), source_manifest_sha256=sha(manifest_path)))


if __name__ == "__main__":
    main()
