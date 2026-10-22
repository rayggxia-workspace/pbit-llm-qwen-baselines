"""Compare kernel handshakes with independently implemented synthesizable SV.

Run from the repository root with ``python -m ...rtl.validate_rtl``. This tests
protocol contracts, NOT the current SC datapath, DRAM commands, STA, or power.
The external simulator runs in a user-selected output directory; each command
and raw stdout/stderr are preserved, including failing cases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import time

from architecture_tlm.cycle_v1.contracts import Buffer, Clock, Operation, Resource
from architecture_tlm.cycle_v1.kernel import Kernel


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pipeline_reference(c):
    clock = Clock("core", 10_000)
    k = Kernel([
        Resource("pipe", clock, c["LATENCY"], ii_cycles=c["II"], capacity=c["CAPACITY"],
                 output_ii_cycles=c["OUTPUT_II"]),
        Resource("sink", clock, 1, ii_cycles=c["DRAIN_II"], capacity=2),
    ], [Buffer("q", c["FIFO_CAPACITY"], c["INITIAL_FILL"])])
    for i in range(c["N"]):
        k.add(Operation(f"p{i:04d}", "pipe", outputs={"q": 1}))
    for i in range(c["N"] + c["INITIAL_FILL"]):
        k.add(Operation(f"s{i:04d}", "sink", inputs={"q": 1},
                        earliest_ps=(c["DRAIN_START"] + i * c["DRAIN_II"]) * 10_000))
    result = k.run("event")
    events = {"P_ACCEPT": [], "P_COMPLETE": [], "Q_CONSUME": []}
    for i in range(c["N"]):
        events["P_ACCEPT"].append([result.accepted_ps[f"p{i:04d}"], i])
        events["P_COMPLETE"].append([result.completion_ps[f"p{i:04d}"], i])
    tokens = [65535] * c["INITIAL_FILL"] + list(range(c["N"]))
    for i, token in enumerate(tokens):
        events["Q_CONSUME"].append([result.accepted_ps[f"s{i:04d}"], token])
    return events, {"inflight": result.resource_peak["pipe"], "fifo": result.buffer_peak["q"]}


def cdc_reference(c):
    source, dest = Clock("src", 10_000), Clock("dst", 12_500, c["DST_PHASE"])
    k = Kernel([Resource("src", source, c["SRC_LATENCY"]),
                Resource("dst", dest, c["DST_LATENCY"]),
                Resource("ack", source, 1)], [Buffer("credit", 1, 1)])
    for i in range(c["N"]):
        k.add(Operation(f"s{i:04d}", "src", inputs={"credit": 1}))
        # Two request synchronizer flops update on destination edges 1/2.
        # A synchronous consumer reading old state accepts on edge 3.
        k.add(Operation(f"d{i:04d}", "dst", deps=(f"s{i:04d}",), cdc_cycles=3))
        # Ack flop1 captures on source edge 1, flop2 commits on edge 2;
        # producer sees returned credit at source edge 3.
        k.add(Operation(f"a{i:04d}", "ack", deps=(f"d{i:04d}",), cdc_cycles=1,
                        outputs={"credit": 1}))
    result = k.run("event")
    events = {"S_ACCEPT": [], "S_COMPLETE": [], "D_ACCEPT": [], "D_COMPLETE": []}
    for i in range(c["N"]):
        events["S_ACCEPT"].append([result.accepted_ps[f"s{i:04d}"], i])
        events["S_COMPLETE"].append([result.completion_ps[f"s{i:04d}"], i])
        events["D_ACCEPT"].append([result.accepted_ps[f"d{i:04d}"], i])
        events["D_COMPLETE"].append([result.completion_ps[f"d{i:04d}"], i])
    return events, {"mailbox_capacity": 1, "request_synchronizer_flops": 2,
                    "ack_synchronizer_flops": 2, "consumer_visible_destination_edge": 3}


def run_command(command, directory, label):
    command = [str(x) for x in command]
    (directory / f"{label}.command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
    completed = subprocess.run(command, cwd=directory, text=True, encoding="utf-8", capture_output=True, timeout=120)
    (directory / f"{label}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (directory / f"{label}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"{label} failed with exit {completed.returncode}: {completed.stderr[-2000:]}")
    return completed.stdout


def validate_case(args, top, name, config):
    directory = args.out / name
    directory.mkdir()
    (directory / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    expected, properties = pipeline_reference(config) if top == "tb_cycle_contract" else cdc_reference(config)
    (directory / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    binary = directory / "design.vvp"
    command = [args.iverilog, "-g2012", "-Wall", "-s", top, "-o", binary]
    if args.ivl_lib:
        command += ["-B", args.ivl_lib]
    command += [f"-P{top}.{key}={value}" for key, value in config.items()]
    command += [HERE / "cycle_contract_pipeline.sv", HERE / "cycle_contract_mailbox.sv", HERE / f"{top}.sv"]
    run_command(command, directory, "compile")
    command = [args.vvp]
    if args.ivl_lib:
        command += ["-M", args.ivl_lib]
    stdout = run_command(command + [binary], directory, "simulate")
    observed = {name: [] for name in expected}
    states = []
    for line in stdout.splitlines():
        words = line.split()
        if words and words[0] in observed:
            observed[words[0]].append([int(x) for x in words[1:]])
        elif words and words[0] == "STATE":
            states.append([int(x) for x in words[1:]])
    (directory / "observed.json").write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    if "PASS" not in stdout or observed != expected:
        differences = {key: {"expected": expected[key], "observed": observed[key]}
                       for key in expected if expected[key] != observed[key]}
        raise AssertionError(f"{name}: handshake mismatch {differences}")
    if states:
        actual_peak = {"inflight": max(row[1] for row in states), "fifo": max(row[2] for row in states)}
        if actual_peak != properties:
            raise AssertionError(f"{name}: state peaks {actual_peak} != {properties}")
    return {"case": name, "top": top, "configuration": config,
            "checked_handshakes": sum(len(x) for x in expected.values()),
            "properties": properties, "status": "passed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--vvp", type=Path, required=True)
    parser.add_argument("--ivl-lib", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.iverilog, args.vvp, args.out = args.iverilog.resolve(), args.vvp.resolve(), args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    report = {"scope": "synthesizable ready-valid protocol and one-entry CDC mailbox contract only",
              "not_validated": ["SC/FFN/Attention datapath RTL", "memory controller RTL", "STA", "power", "metastability MTBF"],
              "python": sys.version, "platform": platform.platform(), "cases": [],
              "tool_sha256": {str(p): sha(p) for p in (args.iverilog, args.vvp)},
              "source_sha256": {str(p.relative_to(HERE.parent)): sha(p)
                                for p in [HERE.parent / "contracts.py", HERE.parent / "kernel.py", HERE.parent / "memory.py",
                                          *sorted(HERE.glob("*.sv")), Path(__file__).resolve()]}}
    start = time.monotonic()
    try:
        report["iverilog_version"] = run_command([args.iverilog, "-V"], args.out, "iverilog_version").splitlines()[0]
        configurations = [
            (3, 1, 4, 1, 8, 3, 3, 12, 2),
            (5, 2, 3, 2, 12, 2, 2, 15, 3),
            (1, 1, 1, 1, 6, 1, 1, 8, 2),
            (2, 1, 4, 3, 12, 3, 0, 0, 1),
            (7, 1, 8, 2, 16, 4, 4, 20, 2),
        ]
        keys = ("LATENCY", "II", "CAPACITY", "OUTPUT_II", "N", "FIFO_CAPACITY", "INITIAL_FILL", "DRAIN_START", "DRAIN_II")
        for i, values in enumerate(configurations):
            report["cases"].append(validate_case(args, "tb_cycle_contract", f"pipeline_{i}", dict(zip(keys, values))))
        for i, phase in enumerate((0, 2500, 6250, 10000)):
            config = {"DST_PHASE": phase, "N": 5, "SRC_LATENCY": 1 + i % 3, "DST_LATENCY": 2 + i % 2}
            report["cases"].append(validate_case(args, "tb_cycle_cdc", f"cdc_{i}", config))
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        raise
    finally:
        report["wall_seconds"] = time.monotonic() - start
        report["artifact_sha256"] = {p.relative_to(args.out).as_posix(): sha(p)
                                      for p in sorted(args.out.rglob("*")) if p.is_file()}
        (args.out / "RTL_CONTRACT_VALIDATION.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "cases": len(report["cases"]),
                      "checked_handshakes": sum(c["checked_handshakes"] for c in report["cases"])}))


if __name__ == "__main__":
    main()
