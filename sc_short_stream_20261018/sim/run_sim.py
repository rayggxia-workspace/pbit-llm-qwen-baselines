"""Actual Icarus functional simulations and isolated one-frame VCD generation.

This script does not estimate technology power. Tool binaries and waveforms
remain outside Git. Use --power to generate the five modes at all five inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRESETS = {
    "iid4096": (0, 12), "iid128": (0, 7), "strat64": (1, 6),
    "strat128": (1, 7), "enum256": (2, 8),
    "strat256_control": (1, 8),
}


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iverilog")
    parser.add_argument("--vvp")
    parser.add_argument("--ivl-base")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "local")
    parser.add_argument("--power", action="store_true")
    parser.add_argument("--presets", nargs="+", choices=PRESETS, default=list(PRESETS)[:5])
    parser.add_argument("--n", nargs="+", type=int, default=[1, 8, 64])
    parser.add_argument("--rng", nargs="+", type=int, choices=[0, 1], default=[0, 1])
    parser.add_argument("--cases", nargs="+", type=int, choices=range(5), default=list(range(5)))
    parser.add_argument("--seeds", nargs="+", type=lambda value: int(value, 0),
                        default=[0x13579BDF, 0x2468ACE1, 0xDEADBEEF])
    parser.add_argument("--sampler-only", action="store_true")
    args = parser.parse_args()
    portable = Path("C:/Users/86134/Documents/a_P_BIT/sc_weight_storage_or4_20261014/tools/iverilog")
    iv = args.iverilog or shutil.which("iverilog")
    vv = args.vvp or shutil.which("vvp")
    if not iv and (portable / "bin/iverilog.exe").exists():
        iv = str(portable / "bin/iverilog.exe")
    if not vv and (portable / "bin/vvp.exe").exists():
        vv = str(portable / "bin/vvp.exe")
    if not iv or not vv:
        parser.error("Provide Icarus on PATH or --iverilog/--vvp (no binaries bundled)")
    base = args.ivl_base
    if base is None and Path(iv).resolve() == (portable / "bin/iverilog.exe").resolve():
        base = str(portable / "lib/ivl")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rtl = sorted((ROOT / "rtl").glob("*.sv"))
    records = []

    def compile_run(top: str, preset: str, params: dict, tag: str, plusargs: list[str]) -> None:
        binary = out / (tag + ".vvp")
        cmd = [iv] + (["-B", base] if base else []) + ["-g2012", "-s", top]
        for key, value in params.items():
            cmd += ["-P", f"{top}.{key}={value}"]
        cmd += ["-o", str(binary)] + [str(x) for x in rtl] + [str(ROOT / "sim" / (top + ".sv"))]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        write_text(out / (tag + "_compile.log"), result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Compile failed: {tag}\n{result.stdout}{result.stderr}")
        # Relative VPI/image paths also work around the portable Windows vvp
        # crash on some absolute paths. POSIX Icarus uses its default VPI path.
        cmd = [vv] + (["-M", os.path.relpath(base, ROOT)] if base else [])
        cmd += [os.path.relpath(binary, ROOT)] + plusargs
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        write_text(out / (tag + ".log"), result.stdout + result.stderr)
        if result.returncode or "ALL_PASS" not in result.stdout:
            raise RuntimeError(f"RTL failed: {tag}\n{result.stdout}{result.stderr}")
        print(tag + ": " + result.stdout.strip().splitlines()[-1], flush=True)
        item = {"tag": tag, "preset": preset, "parameters": params, "passed": True,
                "log": tag + ".log", "log_sha256": sha(out / (tag + ".log"))}
        if top == "tb_function":
            tail = result.stdout.strip().splitlines()[-1]
            item["frames"] = int(tail.split("frames=")[1].split()[0])
            item["accepted_samples_checked"] = int(tail.split("accepted=")[1].split()[0])
            item["stalls_checked"] = int(tail.split("stalls=")[1].split()[0])
        else:
            wave = out / (tag + ".vcd")
            window = out / (tag + "_window.json")
            item["waveform"] = {"name": wave.name, "bytes": wave.stat().st_size, "sha256": sha(wave)}
            item["window"] = json.loads(window.read_text(encoding="utf-8"))
        records.append(item)

    for preset in args.presets:
        mode, log_t = PRESETS[preset]
        for internal in args.rng:
            for seed in args.seeds:
                if not 0 <= seed < (1 << 32):
                    parser.error("Each seed must fit 32 bits")
                if args.power:
                    for case in args.cases:
                        tag = f"power_{preset}_r{internal}_s{int(args.sampler_only)}_c{case}_seed{seed:08x}"
                        compile_run("tb_power", preset,
                                    {"MODE": mode, "LOG_T": log_t, "INTERNAL_RNG": internal,
                                     "SAMPLER_ONLY": int(args.sampler_only)}, tag,
                                    [f"+CASE={case}", f"+SEED={seed:08x}",
                                     f"+VCD={os.path.relpath(out / (tag+'.vcd'), ROOT)}",
                                     f"+WINDOW={os.path.relpath(out / (tag+'_window.json'), ROOT)}"])
                else:
                    for n in args.n:
                        tag = f"function_{preset}_r{internal}_n{n}_seed{seed:08x}"
                        compile_run("tb_function", preset,
                                    {"N": n, "MODE": mode, "LOG_T": log_t, "INTERNAL_RNG": internal}, tag,
                                    [f"+SEED={seed:08x}"])
    versions = {}
    for name, tool in [("iverilog", iv), ("vvp", vv)]:
        result = subprocess.run([tool, "-V"], capture_output=True, text=True)
        versions[name] = (result.stdout + result.stderr).splitlines()[0]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    summary = {
        "schema": "sc_short_stream_rtl_validation_v1",
        "status": "PASS_RTL_FUNCTION_ONLY" if not args.power else "PASS_SYNTHETIC_POWER_STIMULUS_ONLY",
        "source_repository": "rayggxia-workspace/pbit-llm-qwen-baselines",
        "source_base_commit": revision,
        "source_sha256": {str(x.relative_to(ROOT)).replace("\\", "/"): sha(x)
                          for x in rtl + sorted((ROOT / "sim").glob("*.sv")) + [Path(__file__)]},
        "tool_versions": versions, "python_version": sys.version,
        "command": [str(x) for x in sys.argv], "tests": records,
        "total_frames": sum(x.get("frames", 0) for x in records),
        "accepted_samples_checked": sum(x.get("accepted_samples_checked", 0) for x in records),
        "technology_power_measured": False, "llm_ppl_measured": False,
        "stimulus": "Synthetic A8 threshold/comparator and exact signed-W8 tile sums; no model dataset",
    }
    target = out / ("power_summary.json" if args.power else "functional_summary.json")
    write_text(target, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {target}; no technology power or LLM PPL claimed", flush=True)


if __name__ == "__main__":
    main()
