"""Normalize generated one-frame VCD windows to time zero, reject X/Z.

Run after run_sim.py --power. Original waveforms/summary remain unchanged.
This audits RTL synthetic activity, not gate-level annotation or power.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing power_summary.json")
    args = parser.parse_args()
    folder = args.folder.resolve()
    summary_path = folder / "power_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    records = []
    for record in summary["tests"]:
        raw = folder / record["waveform"]["name"]
        if sha(raw) != record["waveform"]["sha256"]:
            raise RuntimeError(f"Raw waveform changed after simulation: {raw}")
        text = raw.read_text(encoding="ascii")
        timescale = re.search(r"\$timescale\s+(\d+)\s*(fs|ps|ns|us|ms|s)\s+\$end", text)
        if not timescale:
            raise RuntimeError(f"Unsupported or absent VCD timescale: {raw}")
        unit_ps = {"fs": 0.001, "ps": 1, "ns": 1000, "us": 1_000_000,
                   "ms": 1_000_000_000, "s": 1_000_000_000_000}[timescale[2]] * int(timescale[1])
        timestamps = [int(x) for x in re.findall(r"^#(\d+)\s*$", text, re.M)]
        if not timestamps:
            raise RuntimeError(f"No VCD timestamps: {raw}")
        window = record["window"]
        first, last = timestamps[0], timestamps[-1]
        if first * unit_ps != window["start_ns"] * 1000:
            raise RuntimeError(f"VCD/window start mismatch: {raw}")
        if last * unit_ps != window["end_ns"] * 1000:
            raise RuntimeError(f"VCD/window end mismatch: {raw}")
        if window["duration_ns"] != (window["sample_cycles"] + 1) * window["clock_period_ns"]:
            raise RuntimeError(f"Not exactly one startup plus T samples: {raw}")
        # Icarus $dumpoff emits artificial all-X values only at the final
        # endpoint. Delete that control block; retain the final timestamp.
        text, removed = re.subn(r"\$dumpoff\s*.*?\$end", "", text, flags=re.S)
        if removed != 1:
            raise RuntimeError(f"Expected one final dumpoff block: {raw}")
        text = re.sub(r"^#(\d+)\s*$", lambda match: "#" + str(int(match[1]) - first), text, flags=re.M)
        changes = []
        for line in text.splitlines():
            stripped = line.strip()
            if re.match(r"^[xXzZ][^\s]+$", stripped) or re.match(r"^[bB][01xXzZ]+\s+[^\s]+$", stripped):
                if re.match(r"^[xXzZ]", stripped) or re.match(r"^[bB][01]*[xXzZ]", stripped):
                    changes.append(stripped)
        if changes:
            raise RuntimeError(f"Unknown X/Z inside active DUT waveform: {raw}; {changes[:5]}")
        active = raw.with_name(raw.stem + "_active.vcd")
        active.write_text(text, encoding="ascii", newline="\n")
        active_stamps = [int(x) for x in re.findall(r"^#(\d+)\s*$", text, re.M)]
        if active_stamps[0] != 0 or (active_stamps[-1] * unit_ps != window["duration_ns"] * 1000):
            raise RuntimeError(f"Normalized duration mismatch: {active}")
        records.append({
            "tag": record["tag"], "raw_file": raw.name, "raw_sha256": sha(raw),
            "active_file": active.name, "active_sha256": sha(active),
            "active_bytes": active.stat().st_size, "timescale_ps": unit_ps,
            "subtracted_timestamp_units": first, "removed_final_dumpoff_block": True,
            "active_first_timestamp": 0, "active_last_timestamp": active_stamps[-1],
            "duration_ns": window["duration_ns"], "unknown_dut_changes": 0,
            "strip_path": "tb_power.sampler.dut" if window["sampler_only"] else "tb_power.integrated.dut",
        })
    target = folder / "active_vcd_manifest.json"
    target.write_text(json.dumps({
        "schema": "sc_short_stream_active_vcd_v1", "status": "PASS_RTL_ACTIVITY_WINDOW_ONLY",
        "power_summary_sha256": sha(summary_path), "generator_sha256": sha(Path(__file__)),
        "gate_level_annotation_verified": False, "technology_power_measured": False,
        "tests": records,
    }, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS active windows={len(records)}; all start at 0, no X/Z; {target}")


if __name__ == "__main__":
    main()
