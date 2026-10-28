#!/usr/bin/env python3
"""Independent integer oracle and cycle receipts for ffn_counter.

Public integration API:
  generate_case(output_dir, *, n, m, bins, t, seed) -> artifact/receipt dict
  parse_run(stdout, expected_receipt) -> checked summary dict

Compile rtl/ffn_counter.sv plus tests/tb_ffn_counter.sv with matching TB
parameters N/M/BINS/T. Run the simulator with +VECTORS=<stimulus path>.
These two functions are simulator independent (including VCS). The CLI below
provides a portable Icarus adapter; all tool/library paths are CLI options.
No design import, floating point, PRNG model, or RTL tree is used by the oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import time


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packed(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((value & mask) << (index * width) for index, value in enumerate(values))


def integer_sample(weights: list[list[int]], x_sign: list[int], bins: list[int],
                   bits: int, bucket_count: int) -> list[int]:
    """Plain mathematical sum, independent of the hardware implementation."""
    totals = [0] * (len(weights) * bucket_count)
    for output, row in enumerate(weights):
        for index, weight in enumerate(row):
            if (bits >> index) & 1:
                signed_input = -1 if x_sign[index] else 1
                totals[output * bucket_count + bins[index]] += weight * signed_input
    return totals


class ContractOracle:
    def __init__(self, n: int, m: int, bins: int, t: int):
        if n < 2 or n & (n - 1) or m < 1 or not 1 <= bins <= 7 or t < 1:
            raise ValueError("invalid counter parameters")
        self.n, self.m, self.bins, self.t = n, m, bins, t
        self.levels = n.bit_length() - 1
        self.cw = 1 + (n * 127 * t).bit_length()
        self.state = "IDLE"
        self.cycle = 0
        self.due = None
        self.active = None
        self.counts = [0] * (m * bins)
        self.rows: list[str] = []
        self.frames: list[dict] = []
        self.receipt = dict(cycles=0, frames_started=0, frames_completed=0,
                            samples_accepted=0, output_stall_cycles=0, reset_aborts=0)
        self.payload = dict(weights=[[0] * n for _ in range(m)], x_sign=[0] * n,
                            bins=[0] * n, negative_zero=[0] * (m * n))

    def step(self, *, rst: int = 1, frame: int = 0, sample: int = 0,
             ready: int = 0, bits: int = 0, label: str = "") -> None:
        self.cycle += 1
        old_state = self.state
        if not rst:
            if self.active is not None:
                self.active["reset_cycle"] = self.cycle
                self.active["status"] = "reset_aborted"
                self.frames.append(self.active)
                self.receipt["reset_aborts"] += 1
            self.state, self.active, self.due = "IDLE", None, None
            self.counts = [0] * (self.m * self.bins)
        else:
            if old_state == "IDLE" and frame:
                self.state = "RUN"
                self.counts = [0] * (self.m * self.bins)
                self.active = dict(label=label, frame_cycle=self.cycle,
                                   samples=0, first_sample_cycle=None, last_sample_cycle=None)
                self.receipt["frames_started"] += 1
            elif old_state == "RUN" and sample:
                contribution = integer_sample(self.payload["weights"], self.payload["x_sign"],
                                              self.payload["bins"], bits, self.bins)
                self.counts = [a + b for a, b in zip(self.counts, contribution)]
                self.active["samples"] += 1
                self.active["first_sample_cycle"] = self.active["first_sample_cycle"] or self.cycle
                self.active["last_sample_cycle"] = self.cycle
                self.receipt["samples_accepted"] += 1
                if self.active["samples"] == self.t:
                    self.state = "DRAIN"
                    self.due = self.cycle + self.levels
            elif old_state == "OUT":
                if ready:
                    self.active.update(status="completed", output_accept_cycle=self.cycle,
                                       counts=list(self.counts))
                    self.frames.append(self.active)
                    self.active = None
                    self.state = "IDLE"
                    self.receipt["frames_completed"] += 1
                else:
                    self.receipt["output_stall_cycles"] += 1
            if self.state == "DRAIN" and self.cycle == self.due:
                self.state = "OUT"
                self.active["output_valid_cycle"] = self.cycle
                self.active["drain_cycles"] = self.levels
        flags = (int(self.state == "IDLE") << 2) | (int(self.state == "RUN") << 1) | int(self.state == "OUT")
        flat_weights = [weight for row in self.payload["weights"] for weight in row]
        magnitude = packed([abs(weight) for weight in flat_weights], 7)
        signs = packed([int(weight < 0) if weight else self.payload["negative_zero"][i]
                        for i, weight in enumerate(flat_weights)], 1)
        row = [rst, frame, sample, ready, magnitude, signs, packed(self.payload["x_sign"], 1),
               packed(self.payload["bins"], 3), bits, flags, packed(self.counts, self.cw)]
        self.rows.append(" ".join(format(value, "x") for value in row))
        self.receipt["cycles"] = self.cycle


def generate_case(output_dir: str | Path, *, n: int = 64, m: int = 1,
                  bins: int = 4, t: int = 64, seed: int = 0) -> dict:
    """Generate deterministic independent goldens and directed/random traffic."""
    output_dir = Path(output_dir).resolve()
    rng = random.Random(seed)
    model = ContractOracle(n, m, bins, t)
    ones = (1 << n) - 1

    def configure(kind: int) -> None:
        signs = [rng.randrange(2) for _ in range(n)]
        bin_values = [i % bins for i in range(n)]
        weights = [[rng.randint(-127, 127) for _ in range(n)] for _ in range(m)]
        if kind in (0, 1):
            # Force both mathematical extrema in the highest bucket, including 6.
            bin_values = [bins - 1] * n
            weights = [[127 * (-1 if signs[i] else 1) * (-1 if kind else 1)
                        for i in range(n)] for _ in range(m)]
        elif kind == 2:
            weights = [[0] * n for _ in range(m)]
        elif kind == 3:
            weights = [[127 * (-1 if (output + i) % 2 else 1)
                        for i in range(n)] for output in range(m)]
        elif kind == 6:
            weights = [[((output * n + i) % 127 + 1) * (-1 if (output ^ i) & 1 else 1)
                        for i in range(n)] for output in range(m)]
        elif kind >= 4:
            bin_values = [rng.randrange(bins) for _ in range(n)]
            if bins == 7:
                bin_values[0] = 6
        model.payload = dict(weights=weights, x_sign=signs, bins=bin_values,
                             negative_zero=[rng.randrange(2) for _ in range(n * m)])

    def accepted_bit_pattern(kind: int, index: int) -> int:
        if kind in (0, 1, 2):
            return ones
        if kind == 3:
            return sum(((index + i) & 1) << i for i in range(n))
        if kind == 6:
            return 1 << (index % n)
        if kind == 7:
            return 0
        return rng.getrandbits(n)

    def start(kind: int, label: str) -> None:
        assert model.state == "IDLE"
        configure(kind)
        # A coincident sample_valid must not count on the frame-start edge.
        model.step(frame=1, sample=1, ready=1, bits=ones, label=label)
        assert model.active["samples"] == 0

    def send_samples(kind: int, count: int) -> None:
        for index in range(count):
            if kind >= 2:
                for _ in range(rng.randrange(3)):
                    model.step(frame=1, sample=0, ready=rng.randrange(2), bits=rng.getrandbits(n))
            model.step(frame=1, sample=1, ready=rng.randrange(2), bits=accepted_bit_pattern(kind, index))

    def wait_output() -> None:
        while model.state != "OUT":
            # Excess valid samples and new frame requests are ignored in drain.
            model.step(frame=1, sample=1, ready=0, bits=rng.getrandbits(n))

    def finish() -> None:
        wait_output()
        for _ in range(2 + rng.randrange(6)):
            model.step(frame=1, sample=1, ready=0, bits=rng.getrandbits(n))
        model.step(frame=1, sample=1, ready=1, bits=ones)
        assert model.state == "IDLE"

    model.step(rst=0, frame=1, sample=1, ready=1, bits=ones)
    model.step(rst=0)
    model.step(sample=1, bits=ones)
    # Flush nonempty pipeline/partial accumulation with synchronous reset.
    start(5, "reset_during_sampling_or_drain")
    send_samples(5, max(1, t // 2))
    model.step(rst=0, frame=1, sample=1, ready=1, bits=ones)
    model.step(sample=1, bits=ones)
    for kind, label in enumerate(("max_positive", "max_negative", "signed_zero", "alternating_sign",
                                 "random_a", "random_b", "lane_order_sparse", "zero_samples")):
        start(kind, label)
        send_samples(kind, t)
        finish()
    # A synchronous reset must also drop a held valid output.
    start(5, "reset_during_output_stall")
    send_samples(5, t)
    wait_output()
    model.step(frame=1, sample=1, ready=0, bits=ones)
    model.step(rst=0, frame=1, sample=1, ready=1, bits=ones)
    model.step()
    start(5, "recovery_after_reset")
    send_samples(5, t)
    finish()
    model.step(sample=1, bits=ones)
    model.step()
    assert model.active is None
    # Explicit oracle checks ensure extrema and bucket-six coverage are present.
    completed = [frame for frame in model.frames if frame["status"] == "completed"]
    bound = n * 127 * t
    assert completed[0]["counts"][bins - 1] == bound
    assert completed[1]["counts"][bins - 1] == -bound
    assert all(-bound <= value <= bound for frame in completed for value in frame["counts"])
    stimulus = output_dir / "stimulus.txt"
    oracle = output_dir / "oracle.json"
    write_text(stimulus, "\n".join(model.rows) + "\n")
    metadata = dict(schema_version=1, config=dict(N=n, M=m, BINS=bins, T=t, CW=model.cw),
                    seed=seed, pipeline_levels=model.levels,
                    expected_receipt=model.receipt, frames=model.frames,
                    stimulus_sha256=sha256(stimulus),
                    scope="Integer functional/cycle contract only; no synthesis, STA, power, or model accuracy.")
    write_text(oracle, json.dumps(metadata, indent=2) + "\n")
    return dict(stimulus=str(stimulus), oracle=str(oracle), expected_receipt=model.receipt,
                stimulus_sha256=sha256(stimulus), oracle_sha256=sha256(oracle),
                config=metadata["config"], seed=seed)


def parse_run(stdout: str, expected_receipt: dict) -> dict:
    matches = re.findall(r"^COUNTER_PASS (.+)$", stdout, re.MULTILINE)
    if len(matches) != 1 or "FATAL" in stdout or "ERROR" in stdout:
        raise AssertionError("simulation did not return exactly one clean COUNTER_PASS receipt")
    observed = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", matches[0])}
    if observed != expected_receipt:
        raise AssertionError(f"receipt mismatch: {observed!r} != {expected_receipt!r}")
    return dict(passed=True, **observed)


def resolve_tool(value: str) -> str:
    candidate = shutil.which(value)
    if candidate:
        return str(Path(candidate).resolve())
    if Path(value).is_file():
        return str(Path(value).resolve())
    raise FileNotFoundError(f"tool not found: {value}")


def execute(command: list[str], log: Path, timeout: int = 180) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    output = result.stdout + result.stderr
    write_text(log, output)
    if result.returncode:
        raise RuntimeError(f"command returned {result.returncode}; see {log}\n{output[-3000:]}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "counter_functional_output")
    parser.add_argument("--rtl", type=Path, default=Path(__file__).resolve().parents[1] / "rtl" / "ffn_counter.sv")
    parser.add_argument("--tb", type=Path, default=Path(__file__).with_name("tb_ffn_counter.sv"))
    parser.add_argument("--n", type=int, default=64)
    parser.add_argument("--m", type=int, default=1)
    parser.add_argument("--bins", type=int, default=4)
    parser.add_argument("--t", type=int, default=64)
    parser.add_argument("--seed", type=int, action="append", help="repeat for multiple seeds; default 0,1,2")
    parser.add_argument("--matrix", action="store_true", help="eight N64 configurations and three small boundary configurations")
    parser.add_argument("--generate-only", action="store_true", help="generate vectors/oracles for another simulator")
    parser.add_argument("--iverilog", default="iverilog")
    parser.add_argument("--vvp", default="vvp")
    parser.add_argument("--iverilog-base", type=Path)
    parser.add_argument("--vvp-module-dir", type=Path)
    args = parser.parse_args()
    seeds = args.seed if args.seed is not None else [0, 1, 2]
    configs = ([(64, m, bins, t) for m in (1, 8) for bins in (4, 7) for t in (64, 128)]
               + [(4, 1, 4, 1), (4, 2, 4, 3), (8, 2, 7, 5)] if args.matrix
               else [(args.n, args.m, args.bins, args.t)])
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rtl, tb = args.rtl.resolve(), args.tb.resolve()
    started = time.monotonic()
    summary = dict(schema_version=1, simulator="generate_only" if args.generate_only else "iverilog/vvp",
                   source_sha256={"ffn_counter.sv": sha256(rtl), "tb_ffn_counter.sv": sha256(tb),
                                  "counter_verify.py": sha256(Path(__file__))}, configurations=[],
                   scope="Functional and clock-edge simulation only; no technology synthesis/STA/power.")
    if not args.generate_only:
        iverilog, vvp = resolve_tool(args.iverilog), resolve_tool(args.vvp)
    for n, m, bins, t in configs:
        name = f"N{n}_M{m}_B{bins}_T{t}"
        build = output_dir / name
        build.mkdir(parents=True, exist_ok=True)
        config_result = dict(N=n, M=m, BINS=bins, T=t, runs=[])
        binary = build / "counter.vvp"
        if not args.generate_only:
            compile_command = [iverilog]
            if args.iverilog_base:
                compile_command += ["-B", str(args.iverilog_base.resolve())]
            compile_command += ["-g2012", "-Wall", "-s", "tb_ffn_counter", "-o", str(binary)]
            for key, value in (("N", n), ("M", m), ("BINS", bins), ("T", t)):
                compile_command += [f"-Ptb_ffn_counter.{key}={value}"]
            compile_command += [str(rtl), str(tb)]
            execute(compile_command, build / "compile.log")
            config_result["compile_command"] = compile_command
        for seed in seeds:
            case_dir = build / f"seed_{seed}"
            artifacts = generate_case(case_dir, n=n, m=m, bins=bins, t=t, seed=seed)
            if args.generate_only:
                result = dict(generated=True)
            else:
                run_command = [vvp]
                if args.vvp_module_dir:
                    run_command += ["-M", str(args.vvp_module_dir.resolve())]
                run_command += [str(binary), "+VECTORS=" + artifacts["stimulus"]]
                stdout = execute(run_command, case_dir / "simulation.log")
                result = parse_run(stdout, artifacts["expected_receipt"])
                result["command"] = run_command
                result["simulation_log_sha256"] = sha256(case_dir / "simulation.log")
            config_result["runs"].append(dict(artifacts=artifacts, result=result))
            print(f"{name} seed={seed}: {'GENERATED' if args.generate_only else 'PASS'}", flush=True)
        summary["configurations"].append(config_result)
        summary["elapsed_seconds"] = time.monotonic() - started
        summary["passed"] = not args.generate_only and all(
            run["result"].get("passed", False) for conf in summary["configurations"] for run in conf["runs"])
        write_text(output_dir / "summary.json", json.dumps(summary, indent=2) + "\n")
    print(f"Receipt: {output_dir / 'summary.json'}", flush=True)


if __name__ == "__main__":
    main()
