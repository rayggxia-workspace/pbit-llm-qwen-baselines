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


def vectors(kind: int, seed: int, samples: int = 32) -> list[tuple[int, int, int, int]]:
    """96 deterministic finite groups / bounded bit-plane count patterns.

    Counts obey each field's 0..64*T bound; arbitrary per-bit combinations do
    not establish reachability from a common stochastic event stream.
    """
    if samples not in (16, 32, 64):
        raise ValueError("restoration samples must be 16, 32 or 64")
    t_log2 = samples.bit_length() - 1
    count_max = 64 * samples
    count_width = count_max.bit_length()
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
            counts = [rng.randrange(count_max + 1) for _ in range(64)]
            top = rng.randrange(-132, 101)
            scale = AR.fbits(rng.uniform(0.0001, 2.0))
            if index == 0:
                counts = [0] * 64
            elif index == 1:
                counts = [count_max] * 64
            elif 2 <= index < 18:
                # Per-bin and per-input-sign W=-128 and +127 extrema.
                counts = [0] * 64
                bn, sg = (index - 2) // 4, ((index - 2) // 2) % 2
                bits = (7,) if index % 2 == 0 else range(7)
                for bit in bits:
                    counts[(bn * 2 + sg) * 8 + bit] = count_max
                top, scale = 0, 0x3F800000
            elif index == 18:
                # Literal FP32 conversion then multiplication gives 0x00000003.
                # A host-float expression rounded only at the end gives 0x2.
                counts = [0] * 64
                counts[0] = 3
                top, scale = t_log2 - 150, 0x3FC00000
            output = 0
            for bn in range(4):
                integer_bin = sum(
                    (counts[(bn * 2) * 8 + bit] - counts[(bn * 2 + 1) * 8 + bit]) *
                    (-1 if bit == 7 else 1) * (1 << bit) for bit in range(8)
                )
                value = AR.R.pack(integer_bin, top - 2 * bn - t_log2, 23)[0]
                output = AR.add(output, AR.mul(value, scale))
            rows.append((sum(c << (count_width * j) for j, c in enumerate(counts)),
                         top & 65535, scale, output))
        else:
            raise ValueError(kind)
    return rows


def cases(samples=(16, 32, 64), depths=(1, 3, 5)) -> list[dict]:
    """Fixed elaborations; encoder sample/count fields are 0 (not applicable)."""
    if not samples or any(t not in (16, 32, 64) for t in samples):
        raise ValueError("samples must select T16/T32/T64")
    if not depths or any(type(d) is not int or d < 1 for d in depths):
        raise ValueError("depths must be positive integers")
    if len(samples) != len(set(samples)) or len(depths) != len(set(depths)):
        raise ValueError("duplicate elaboration selections")
    output = []
    for kind in (0, 1, 2):
        for sample in (samples if kind == 2 else (0,)):
            for depth in depths:
                output.append({"kind": kind, "samples": sample, "depth": depth,
                               "count_width": (64 * sample).bit_length() if sample else 0,
                               "t_log2": sample.bit_length() - 1 if sample else 0,
                               "top": f"er_contract_k{kind}_t{sample}_d{depth}"})
    return output


def gen_fixed_top(case: dict) -> str:
    """Same explicit ports for RTL elaboration and a future mapped replacement.

    No synthesis or gate-level result is implied by generating this wrapper.
    The DUT has no parameters; parameters are fixed below at generation time.
    """
    kind, depth = case["kind"], case["depth"]
    cw = max(1, depth.bit_length())
    header = f'''`timescale 1ns/1ps
module {case["top"]}(
 input wire clk,rst_n,in_valid,
 output wire in_ready,
 input wire [2047:0] data_in,
 input wire [15:0] exp_in,
 input wire [31:0] scale_in,in_tag,
 output wire out_valid,
 input wire out_ready,
 output wire [784:0] data_out,
 output wire [31:0] out_tag,
 output wire [{cw - 1}:0] reserved_count,queued_count
);
'''
    if kind == 2:
        width, t_log2 = case["count_width"], case["t_log2"]
        body = f''' er_bin_restore_rv #(.COUNT_W({width}),.T_LOG2({t_log2}),.DEPTH({depth})) core(
  clk,rst_n,in_valid,in_ready,data_in[{64 * width - 1}:0],exp_in,scale_in,in_tag,
  out_valid,out_ready,data_out[31:0],out_tag,reserved_count,queued_count);
 assign data_out[784:32]=0;
'''
    elif kind in (0, 1):
        frac = 7 if kind == 0 else 23
        body = f''' er_pot_encoder_rv #(.FRAC({frac}),.DEPTH({depth})) core(
  clk,rst_n,in_valid,in_ready,data_in[{64 * (frac + 9) - 1}:0],in_tag,
  out_valid,out_ready,data_out[511:0],data_out[639:512],data_out[703:640],
  data_out[767:704],data_out[783:768],data_out[784],out_tag,reserved_count,queued_count);
'''
    else:
        raise ValueError(kind)
    return header + body + "endmodule\n"


def vector_text(kind: int, seed: int, samples: int = 32) -> str:
    return "".join(" ".join(f"{value:x}" for value in row) + "\n"
                   for row in vectors(kind, seed, samples))


def prepare_inputs(build: Path, selected_cases: list[dict], seeds: list[int]) -> list[dict]:
    """Write fixed tops/vectors and return their relative-path/hash manifest."""
    prepared = []
    for case in selected_cases:
        source = build / (case["top"] + ".sv")
        source.write_text(gen_fixed_top(case), encoding="utf-8", newline="\n")
        item = dict(case, fixed_top={"path": source.name, "sha256": sha256(source)}, vectors=[])
        for seed in seeds:
            vector_file = build / f"kind{case['kind']}_t{case['samples']}_seed{seed}.hex"
            content = vector_text(case["kind"], seed, case["samples"] or 32)
            if vector_file.exists() and vector_file.read_text(encoding="ascii") != content:
                raise ValueError("inconsistent shared vector identity")
            vector_file.write_text(content, encoding="ascii", newline="\n")
            item["vectors"].append({"seed": seed, "path": vector_file.name,
                                     "sha256": sha256(vector_file), "rows": 96})
        prepared.append(item)
    return prepared


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
    parser.add_argument("--iverilog", type=Path)
    parser.add_argument("--vvp", type=Path)
    parser.add_argument("--ivl-lib", type=Path)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[20261023, 7, 1234567])
    parser.add_argument("--depths", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--samples", type=int, nargs="+", default=[16, 32, 64])
    parser.add_argument("--prepare-only", action="store_true",
                        help="generate reproducible fixed tops, vectors and INPUT_MANIFEST; do not simulate")
    parser.add_argument("--vcd", action="store_true", help="retain DUT VCDs in build directory")
    args = parser.parse_args()
    if not args.prepare_only and (args.iverilog is None or args.vvp is None):
        parser.error("--iverilog and --vvp are required for simulation")
    selected_cases = cases(args.samples, args.depths)
    if not args.seeds or len(args.seeds) != len(set(args.seeds)) or any(s < 0 for s in args.seeds):
        parser.error("seeds must be distinct nonnegative integers")
    build, out = args.build_dir.resolve(), args.out.resolve()
    build.mkdir(parents=True, exist_ok=False)
    out.mkdir(parents=True, exist_ok=False)
    sources = source_files()
    metadata_files = sources + [Path(__file__).resolve(), HERE / "sim/tb_ready_valid.sv",
                               ORACLE_FILE, ROOT / "format_conversion_rtl_20261016/sim/reference.py"]
    for path in metadata_files:
        if not path.is_file():
            raise FileNotFoundError(path)
    prepared_cases = prepare_inputs(build, selected_cases, args.seeds)
    source_sha = {p.relative_to(ROOT).as_posix(): sha256(p) for p in metadata_files}
    manifest = {
        "schema_version": 1, "stage": "PREPARED_INPUTS_NOT_SIMULATED",
        "repository_root": str(ROOT), "build_dir": str(build),
        "rtl_sources": [p.relative_to(ROOT).as_posix() for p in sources],
        "tb_file": (HERE / "sim/tb_ready_valid.sv").relative_to(ROOT).as_posix(),
        "source_sha256": source_sha, "cases": prepared_cases,
        "seeds": args.seeds, "planned_simulations": len(prepared_cases) * len(args.seeds),
        "compile_interface": {
            "testbench_top": "tb_ready_valid", "fixed_top_macro": "ER_DUT_TOP",
            "case_macros": ["KIND", "DEPTH", "T_LOG2", "COUNT_W"],
            "required_plusargs": ["VECTORS", "SEED"],
            "optional_plusargs": ["VCD", "WINDOW"],
            "generated_paths_relative_to": "build_dir",
            "mapped_replacement": "Same named fixed top/ports; supply mapped netlist and cell models instead of RTL sources. Separate tool evidence is required."
        }
    }
    (out / "INPUT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                            encoding="utf-8", newline="\n")
    if args.prepare_only:
        print(json.dumps({"stage": manifest["stage"], "elaborations": len(prepared_cases),
                          "planned_simulations": manifest["planned_simulations"]}))
        return
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                         capture_output=True, check=False)
    evidence = {
        "scope": "RTL_FUNCTIONAL, synthetic finite inputs; not STA, PPA or model PPL",
        "passed": False,
        "git_head": git.stdout.strip() if git.returncode == 0 else None,
        "git_head_note": "Source hashes below identify the actual files, including uncommitted edits.",
        "python": sys.version, "platform": platform.platform(),
        "tool_sha256": {str(p.resolve()): sha256(p) for p in (args.iverilog, args.vvp)},
        "source_sha256": source_sha,
        "input_manifest_sha256": sha256(out / "INPUT_MANIFEST.json"),
        "encoding": "B4/N64 q/256 plus true_one; BF16 and FP32",
        "restoration": "T16/T32/T64 input-sign/two's-complement bit planes; FUSED=0 ordered FP32",
        "samples": args.samples,
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
        for case in prepared_cases:
            kind, depth, sample = case["kind"], case["depth"], case["samples"]
            binary = build / (case["top"] + ".vvp")
            execute(compiler + ["-g2012", "-Wall", f"-DKIND={kind}", f"-DDEPTH={depth}",
                                f"-DT_LOG2={case['t_log2']}", f"-DCOUNT_W={case['count_width']}",
                                f"-DER_DUT_TOP={case['top']}",
                                "-s", "tb_ready_valid", "-o", binary] + sources +
                    [build / case["fixed_top"]["path"], HERE / "sim/tb_ready_valid.sv"])
            for vector in case["vectors"]:
                seed = vector["seed"]
                vector_file = build / vector["path"]
                prefix = f"{case['top']}_seed{seed}"
                window_file, vcd_file = build / (prefix + "_window.txt"), build / (prefix + ".vcd")
                run_args = [binary, "+VECTORS=" + str(vector_file), f"+SEED={seed}",
                            "+WINDOW=" + str(window_file)]
                if args.vcd:
                    run_args += ["+VCD=" + str(vcd_file)]
                stdout = execute(runner + run_args)
                matches = re.findall(r"^PASS (.+)$", stdout, re.M)
                if len(matches) != 1:
                    raise AssertionError("simulation did not emit exactly one PASS record")
                result = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", matches[0])}
                if (result["kind"], result["depth"], result["seed"], result["samples"], result["count_width"]) != \
                        (kind, depth, seed, sample, case["count_width"]):
                    raise AssertionError("case identity mismatch")
                result["vector_sha256"] = sha256(vector_file)
                result["fixed_top_sha256"] = case["fixed_top"]["sha256"]
                result["top"] = case["top"]
                result["activity_window"] = dict(line.split("=", 1) for line in
                                                  window_file.read_text(encoding="utf-8").splitlines())
                result["activity_window_sha256"] = sha256(window_file)
                if args.vcd:
                    result["vcd_sha256"] = sha256(vcd_file)
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
