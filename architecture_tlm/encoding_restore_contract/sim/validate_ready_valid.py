"""Bounded ready/valid RTL checks; exact existing arithmetic, synthetic inputs.

Run on a CPU allocation / local machine, never on a shared login node.
Build products are explicitly separated from the small publishable evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import random
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
ORACLE_FILE = ROOT / "architecture_tlm/digital_ppa_v1/sim/validate.py"
spec = importlib.util.spec_from_file_location("er_existing_arithmetic", ORACLE_FILE)
AR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AR)


def vectors(kind: int, seed: int) -> list[tuple[int, int, int, int]]:
    """96 deterministic finite groups / bounded bit-plane count patterns.

    Counts obey each field's 0..64*T bound; arbitrary per-bit combinations do
    not establish reachability from a common stochastic event stream.
    """
    rng = random.Random(seed)
    rows = []
    for index in range(96):
        if kind in (0, 1):
            frac = 7 if kind == 0 else 23
            width = frac + 9
            sign = 1 << (width - 1)
            if index == 0:
                words = [(j & 1) * sign for j in range(64)]
            elif index == 1:
                words = [((j & 1) * sign) | (j + 1) for j in range(64)]
            elif index == 2:
                edge = [0, sign, 1, (1 << frac) - 1, 1 << frac,
                        127 << frac, (254 << frac) | ((1 << frac) - 1)]
                words = [edge[j % len(edge)] for j in range(64)]
            elif index == 3:
                words = [((j & 1) * sign) | ((135 - 2 * (j % 4)) << frac)
                         for j in range(64)]
            else:
                # Include subnormals and very different magnitudes; all finite.
                words = [(rng.getrandbits(1) << (width - 1)) |
                         (rng.randrange(255) << frac) | rng.getrandbits(frac)
                         for _ in range(64)]
            packed = sum(word << (width * j) for j, word in enumerate(words))
            rows.append((packed, 0, 0, AR.encoder(words, frac)))
        elif kind == 2:
            counts = [rng.randrange(2049) for _ in range(64)]
            top = rng.randrange(-132, 101)
            scale = AR.fbits(rng.uniform(0.0001, 2.0))
            if index == 0:
                counts = [0] * 64
            elif index == 1:
                counts = [2048] * 64
            elif 2 <= index < 18:
                # Per-bin and per-input-sign W=-128 and +127 extrema.
                counts = [0] * 64
                bn, sg = (index - 2) // 4, ((index - 2) // 2) % 2
                bits = (7,) if index % 2 == 0 else range(7)
                for bit in bits:
                    counts[(bn * 2 + sg) * 8 + bit] = 2048
                top, scale = 0, 0x3F800000
            elif index == 18:
                # Literal FP32 conversion then multiplication gives 0x00000003.
                # A host-float expression rounded only at the end gives 0x2.
                counts = [0] * 64
                counts[0] = 3
                top, scale = -145, 0x3FC00000
            output = 0
            for bn in range(4):
                integer_bin = sum(
                    (counts[(bn * 2) * 8 + bit] - counts[(bn * 2 + 1) * 8 + bit]) *
                    (-1 if bit == 7 else 1) * (1 << bit) for bit in range(8)
                )
                value = AR.R.pack(integer_bin, top - 2 * bn - 5, 23)[0]
                output = AR.add(output, AR.mul(value, scale))
            rows.append((sum(c << (12 * j) for j, c in enumerate(counts)),
                         top & 65535, scale, output))
        else:
            raise ValueError(kind)
    return rows


def source_files() -> list[Path]:
    digital = ROOT / "architecture_tlm/digital_ppa_v1/rtl"
    return [digital / name for name in
            ("nr_pot_encoder.sv", "nr_bin_restore.sv", "nr_fp32_mul.sv")] + \
        sorted((ROOT / "format_conversion_rtl_20261016/rtl").glob("*.sv")) + \
        sorted((HERE / "rtl").glob("*.sv"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--vvp", type=Path, required=True)
    parser.add_argument("--ivl-lib", type=Path)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[20261023, 7, 1234567])
    parser.add_argument("--depths", type=int, nargs="+", default=[1, 3, 5])
    args = parser.parse_args()
    build, out = args.build_dir.resolve(), args.out.resolve()
    build.mkdir(parents=True, exist_ok=False)
    out.mkdir(parents=True, exist_ok=False)
    sources = source_files()
    metadata_files = sources + [Path(__file__).resolve(), HERE / "sim/tb_ready_valid.sv",
                               ORACLE_FILE, ROOT / "format_conversion_rtl_20261016/sim/reference.py"]
    for path in metadata_files:
        if not path.is_file():
            raise FileNotFoundError(path)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                         capture_output=True, check=False)
    evidence = {
        "scope": "RTL_FUNCTIONAL, synthetic finite inputs; not STA, PPA or model PPL",
        "passed": False,
        "git_head": git.stdout.strip() if git.returncode == 0 else None,
        "git_head_note": "Source hashes below identify the actual files, including uncommitted edits.",
        "python": sys.version, "platform": platform.platform(),
        "tool_sha256": {str(p.resolve()): sha256(p) for p in (args.iverilog, args.vvp)},
        "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in metadata_files},
        "encoding": "B4/N64 q/256 plus true_one; BF16 and FP32",
        "restoration": "T32 input-sign/two's-complement bit planes; FUSED=0 ordered FP32",
        "cycle_convention": "accept and transfer sample pre-edge; first visible result samples post-edge",
        "expected_no_stall": {
            "encoder": {"visible_cycles": 2, "transfer_cycles": 3, "II1_min_slots": 3},
            "restore": {"visible_cycles": 1, "transfer_cycles": 2, "II1_min_slots": 2}},
        "power_area_frequency": None,
        "seeds": args.seeds, "depths": args.depths, "results": [],
    }
    commands = []

    def execute(command: list[str | Path]) -> str:
        command = [str(item) for item in command]
        result = subprocess.run(command, cwd=build, capture_output=True, text=True,
                                timeout=180, check=False)
        commands.append({"command": command, "returncode": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode:
            raise RuntimeError(result.stdout + "\n" + result.stderr)
        return result.stdout

    try:
        # Version switches may have implementation-dependent exit codes; record
        # them but compilation/execution failures always fail validation.
        for exe in (args.iverilog, args.vvp):
            version = subprocess.run([str(exe), "-V"], capture_output=True, text=True, check=False)
            commands.append({"command": [str(exe), "-V"], "returncode": version.returncode,
                             "stdout": version.stdout, "stderr": version.stderr})
        compiler = [args.iverilog]
        runner = [args.vvp]
        if args.ivl_lib:
            compiler += ["-B", args.ivl_lib]
            runner += ["-M", args.ivl_lib]
        for kind in (0, 1, 2):
            for depth in args.depths:
                binary = build / f"er_kind{kind}_depth{depth}.vvp"
                execute(compiler + ["-g2012", "-Wall", f"-DKIND={kind}", f"-DDEPTH={depth}",
                                    "-s", "tb_ready_valid", "-o", binary] + sources +
                        [HERE / "sim/tb_ready_valid.sv"])
                for seed in args.seeds:
                    vector_file = build / f"kind{kind}_seed{seed}.hex"
                    vector_file.write_text("".join(" ".join(f"{value:x}" for value in row) + "\n"
                                                  for row in vectors(kind, seed)),
                                           encoding="ascii", newline="\n")
                    stdout = execute(runner + [binary, "+VECTORS=" + str(vector_file), f"+SEED={seed}"])
                    matches = re.findall(r"^PASS (.+)$", stdout, re.M)
                    if len(matches) != 1:
                        raise AssertionError("simulation did not emit exactly one PASS record")
                    result = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", matches[0])}
                    if (result["kind"], result["depth"], result["seed"]) != (kind, depth, seed):
                        raise AssertionError("case identity mismatch")
                    result["vector_sha256"] = sha256(vector_file)
                    evidence["results"].append(result)
        evidence["passed"] = True
    finally:
        (out / "VALIDATION.json").write_text(json.dumps(evidence, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")
        (out / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n",
                                             encoding="utf-8", newline="\n")
    print(json.dumps({"passed": True, "cases": len(evidence["results"]),
                      "received": sum(row["received"] for row in evidence["results"]),
                      "reset_flushed": sum(row["flushed"] for row in evidence["results"])}))


if __name__ == "__main__":
    main()
