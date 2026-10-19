"""Generate golden vectors, compile Icarus, run functional + power testbenches."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

from golden_model import self_check, write_cycle_vectors


def run(command, log):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True)
    log.append({"command": list(map(str, command)), "returncode": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--iverilog", type=Path, required=True)
    p.add_argument("--vvp", type=Path, required=True)
    p.add_argument("--ivl-lib", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--power-cycles", type=int, default=4096)
    args = p.parse_args()
    root = Path(__file__).resolve().parent
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    log = []
    result = {"scope": "RTL functional verification and synthetic activity only; no PPL or silicon power",
              "oracle": self_check(), "functional": [], "power_activity": []}
    try:
        run([sys.executable, root / "generate_lut.py", "--check"], log)
        compile_base = [args.iverilog, "-B", args.ivl_lib, "-g2012", "-Wall", "-I", root]
        functional = out / "functional.vvp"
        run(compile_base + ["-s", "tb_swiglu_functional", "-o", functional,
                           root / "swiglu_epilogue_q10.sv", root / "tb_swiglu_functional.sv"], log)
        for seed in [20261017, 7, 1234567]:
            vectors = out / f"cycle_vectors_{seed}.txt"
            case = write_cycle_vectors(vectors, seed)
            case["vectors_sha256"] = hashlib.sha256(vectors.read_bytes()).hexdigest()
            case["simulation"] = run([args.vvp, "-M", args.ivl_lib, functional,
                                       f"+VECTORS={vectors.as_posix()}"], log)
            result["functional"].append(case)
        power = out / "power.vvp"
        run(compile_base + ["-s", "tb_swiglu_power", "-o", power,
                           root / "swiglu_epilogue_q10.sv", root / "tb_swiglu_power.sv"], log)
        for mode in ["active", "burst", "idle"]:
            vcd = out / f"{mode}.vcd"
            message = run([args.vvp, "-M", args.ivl_lib, power, f"+MODE={mode}",
                           f"+CYCLES={args.power_cycles}", f"+VCD={vcd.as_posix()}"], log)
            result["power_activity"].append({"mode": mode, "cycles": args.power_cycles,
                                            "bytes": vcd.stat().st_size,
                                            "sha256": hashlib.sha256(vcd.read_bytes()).hexdigest(),
                                            "simulation": message})
        result["status"] = "PASS"
    finally:
        (out / "commands.json").write_bytes((json.dumps(log, indent=2) + "\n").encode())
        (out / "validation_summary.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
