"""Prepare source-bound cases, then explicitly run licensed tools inside Slurm.

prepare never invokes EDA. run requires explicit absolute executables/library,
verified personal ownership and a CPU allocation. Library bytes are not copied.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

try:
    from . import reports
except ImportError:
    import reports

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SIM = HERE.parent / "sim/validate_ready_valid.py"
SEEDS = (20261023, 7, 1234567)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def load_sim():
    spec = importlib.util.spec_from_file_location("er_ppa_stimulus", SIM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_manifest():
    sim = load_sim()
    paths = sim.source_files() + [SIM, HERE.parent / "sim/tb_ready_valid.sv",
        ROOT / "architecture_tlm/digital_ppa_v1/sim/validate.py",
        ROOT / "format_conversion_rtl_20261016/sim/reference.py"]
    paths += sorted(p for p in HERE.rglob("*") if p.suffix in (".py", ".tcl") and "__pycache__" not in p.parts)
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}


def prepare(output):
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("prepare --out must be absolute")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sim = load_sim()
    selected = sim.cases(samples=(16, 32, 64), depths=(3,))
    generated = sim.prepare_inputs(output, selected, list(SEEDS))
    manifest = {"schema": 1, "status": "not_run", "area": None, "power": None, "sta": None,
                "repository_root": str(ROOT), "source_sha256": source_manifest(),
                "rtl_sources": [p.relative_to(ROOT).as_posix() for p in sim.source_files()],
                "cases": generated, "seeds": list(SEEDS), "period_ns": 10.0,
                "constraints": {"setup_uncertainty_ns": 2.0, "hold_uncertainty_ns": .1,
                    "slew_ns": .1, "input_max_ns": 1.0, "input_min_ns": .2,
                    "output_max_ns": 1.0, "output_min_ns": .2, "load_pF": .02},
                "scope": "complete N64/B4 encoder or per-output FUSED0 restoration, DEPTH3",
                "limitations": ["preparation is not synthesis or timing proof", "synthetic active window",
                                "no PDK copied", "no SDF/SPEF/CTS"]}
    write_json(output / "PREPARED.json", manifest)
    return manifest


def contained(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError as error:
        raise ValueError(f"path outside personal root: {path}") from error


def absolute_file(value, label, executable=False):
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        raise ValueError(f"{label} requires an existing absolute file")
    path = path.resolve()
    if executable and not os.access(path, os.X_OK):
        raise ValueError(f"{label} is not executable")
    return path


def environment(prepared, corner, env=None):
    env = os.environ if env is None else env
    required = ("STD_DB", "STD_MODEL", "STD_LIB_NAME", "STD_OC_NAME", "DC_SHELL", "PT_SHELL", "VCS",
                "EDA_PERSONAL_ROOT", "EDA_EXPECTED_USER", "SLURM_JOB_ID", "SLURM_CPUS_PER_TASK")
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise ValueError("missing explicit environment: " + ", ".join(missing))
    if env.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("CPU-only EDA requires CUDA_VISIBLE_DEVICES explicitly empty")
    if os.name != "posix":
        raise ValueError("licensed execution requires the verified POSIX Slurm environment")
    import pwd
    user = pwd.getpwuid(os.getuid())
    if user.pw_name != env["EDA_EXPECTED_USER"] or os.geteuid() != os.getuid():
        raise ValueError("execution identity differs from verified expected user")
    root = Path(env["EDA_PERSONAL_ROOT"])
    if not root.is_absolute() or not root.is_dir() or root.resolve().stat().st_uid != os.getuid():
        raise ValueError("personal root must exist, be absolute and be owned by expected user")
    contained(prepared, root)
    if Path(prepared).resolve().stat().st_uid != os.getuid():
        raise ValueError("prepared snapshot is not owned by expected user")
    if not env["SLURM_JOB_ID"].isdigit() or int(env["SLURM_CPUS_PER_TASK"]) < 1:
        raise ValueError("invalid Slurm CPU allocation identity")
    # Environment variables are necessary, not a substitute for the operator's
    # preceding live identity/home/allocation checks described in README.
    tools = {key: str(absolute_file(env[key], key, True)) for key in ("DC_SHELL", "PT_SHELL", "VCS")}
    libraries = {key: str(absolute_file(env[key], key)) for key in ("STD_DB", "STD_MODEL")}
    config = {"corner": corner, "oc_name": env["STD_OC_NAME"], "library_name": env["STD_LIB_NAME"],
              "tools": tools, "tool_sha256": {k: sha(p) for k, p in tools.items()},
              "libraries": libraries, "library_sha256": {k: sha(p) for k, p in libraries.items()},
              "area_unit": "library_area_unit", "personal_root": str(root.resolve()),
              "user": user.pw_name, "canonical_home": str(Path(user.pw_dir).resolve()),
              "period_ns": 10.0, "cpus": int(env["SLURM_CPUS_PER_TASK"])}
    if env.get("STD_AREA_UNIT"):
        if env["STD_AREA_UNIT"] != "um2" or not env.get("STD_AREA_UNIT_EVIDENCE"):
            raise ValueError("um2 area labeling requires explicit library-unit evidence")
        evidence = absolute_file(env["STD_AREA_UNIT_EVIDENCE"], "STD_AREA_UNIT_EVIDENCE")
        config.update(area_unit="um2", area_unit_evidence_path=str(evidence), area_unit_evidence_sha256=sha(evidence))
    return config


def verify_prepared(folder):
    folder = Path(folder)
    manifest = json.loads((folder / "PREPARED.json").read_text(encoding="utf-8"))
    if manifest["source_sha256"] != source_manifest():
        raise ValueError("source closure changed since prepare; create a new snapshot")
    for case in manifest["cases"]:
        for item in [case["fixed_top"], *case["vectors"]]:
            path = folder / item["path"]
            contained(path, folder)
            if sha(path) != item["sha256"]:
                raise ValueError(f"prepared input changed: {path}")
    return manifest


def stage(folder, required, action):
    """Verified complete stages resume; partial stages remain intact and fail."""
    folder = Path(folder)
    marker = folder / "COMPLETE.json"
    if marker.exists():
        files = json.loads(marker.read_text(encoding="utf-8"))
        if not set(required).issubset(files):
            raise ValueError("incomplete stage marker")
        for name, digest in files.items():
            path = folder / name
            contained(path, folder)
            if not path.is_file() or sha(path) != digest:
                raise ValueError(f"changed completed stage: {path}")
        return
    if folder.exists():
        raise ValueError(f"partial stage preserved: {folder}; use a fresh prepared output after diagnosing")
    folder.mkdir(parents=True)
    action(folder)
    reports.require_reports(folder, required)
    write_json(marker, {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob("*") if p.is_file()})


def command(args, folder, log, env):
    with (folder / log).open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("COMMAND " + json.dumps([str(x) for x in args]) + "\n")
        stream.flush()
        result = subprocess.run([str(x) for x in args], cwd=folder, env=env,
                                stdout=stream, stderr=subprocess.STDOUT, check=False)
    text = (folder / log).read_text(encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"tool exit {result.returncode}: {folder/log}")
    reports.audit_log(text)
    return text


def run(prepared, case_name, corner):
    prepared = Path(prepared).resolve()
    manifest = verify_prepared(prepared)
    case = next((c for c in manifest["cases"] if c["top"] == case_name), None)
    if case is None:
        raise ValueError("case must be one of the prepared fixed tops")
    config = environment(prepared, corner)
    config["prepared_sha256"] = sha(prepared / "PREPARED.json")
    work = prepared / "runs" / corner / case_name
    work.mkdir(parents=True, exist_ok=True)
    lock = work / "RUNNING.lock"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "slurm_job": os.environ["SLURM_JOB_ID"], "time": time.time()}))
    result = {"status": "failed", "area": None, "power": None, "sta": None, "results": []}
    try:
        path = work / "configuration.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) != config:
            raise ValueError("configuration/tools/library changed; use a new snapshot")
        write_json(path, config)
        write_json(work / "allocation.json", {k: os.environ.get(k) for k in
                   ("SLURM_JOB_ID", "SLURM_JOB_NODELIST", "SLURM_CPUS_PER_TASK", "CUDA_VISIBLE_DEVICES")})
        sources = [str(ROOT/p) for p in manifest["rtl_sources"]] + [str(prepared/case["fixed_top"]["path"])]
        (work / "sources.txt").write_text("\n".join(sources)+"\n", encoding="utf-8", newline="\n")
        env = dict(os.environ, ER_TOP=case_name, ER_SOURCE_LIST=str(work/"sources.txt"),
                   ER_FLOW=str(HERE), ER_CPUS=str(config["cpus"]))
        dc = work / "dc"
        stage(dc, ["mapped.v", "mapped.sdc", "mapped.ddc", "DONE", "area.txt", "units.rpt", "library.rpt",
                   "setup.rpt", "hold.rpt", "constraints.rpt", "check_timing.rpt", "design.rpt", "clock.rpt",
                   "inventory.tsv", "check_design.rpt", "link.log", "condition.log"],
              lambda folder: command([config["tools"]["DC_SHELL"], "-f", HERE/"dc.tcl"], folder, "dc.log", env))
        reports.units((dc/"units.rpt").read_text(encoding="utf-8"))
        reports.operating_condition((dc/"library.rpt").read_text(encoding="utf-8"), config["oc_name"], corner)
        build = work / "build"
        defines = [f"+define+ER_DUT_TOP={case_name}", f"+define+KIND={case['kind']}", "+define+DEPTH=3",
                   f"+define+COUNT_W={case['count_width']}", f"+define+T_LOG2={case['t_log2']}"]
        stage(build, ["simv"], lambda folder: command([config["tools"]["VCS"], "-full64", "-sverilog",
              "-top", "tb_ready_valid", "+define+functional", "+notimingcheck", "+delay_mode_zero",
              "-timescale=1ns/1ps", *defines, HERE.parent/"sim/tb_ready_valid.sv", dc/"mapped.v",
              config["libraries"]["STD_MODEL"], "-o", "simv"], folder, "vcs.log", env))
        for vector in case["vectors"]:
            gate = work / f"gate_{vector['seed']}"
            def simulate(folder):
                log = command([build/"simv", "+VECTORS="+str(prepared/vector["path"]),
                     f"+SEED={vector['seed']}", "+VCD="+str(folder/"power.vcd"),
                     "+WINDOW="+str(folder/"window.txt")], folder, "simulation.log", env)
                pass_lines = [line for line in log.splitlines() if line.startswith("PASS ")]
                if len(pass_lines) != 1:
                    raise ValueError("gate simulation lacks unique exact-oracle PASS")
                identity = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", pass_lines[0])}
                expected = {"kind": case["kind"], "depth": case["depth"], "samples": case["samples"],
                            "count_width": case["count_width"], "seed": vector["seed"]}
                if any(identity.get(key) != value for key, value in expected.items()):
                    raise ValueError("gate PASS identity differs from prepared case")
                meta = reports.read_window(folder/"window.txt")
                write_json(folder/"vcd_audit.json", reports.audit_vcd(folder/"power.vcd", meta["start_ps"], meta["end_ps"]))
            stage(gate, ["power.vcd", "window.txt", "simulation.log", "vcd_audit.json"], simulate)
            meta = reports.read_window(gate/"window.txt")
            pt_env = dict(env, ER_NETLIST=str(dc/"mapped.v"), ER_SDC=str(dc/"mapped.sdc"),
                          ER_VCD=str(gate/"power.vcd"), ER_START_NS=str(meta["start_ps"]/1000),
                          ER_END_NS=str(meta["end_ps"]/1000))
            pt = work / f"pt_{vector['seed']}"
            stage(pt, ["power.rpt", "activity.rpt", "check_power.rpt", "DONE", "area.txt", "units.rpt",
                       "library.rpt", "design.rpt", "setup.rpt", "hold.rpt", "constraints.rpt",
                       "check_timing.rpt", "setup_slack.txt", "hold_slack.txt", "clock.rpt", "inventory.tsv",
                       "link.log", "condition.log", "vcd.log", "update_power.log"],
                  lambda folder: command([config["tools"]["PT_SHELL"], "-f", HERE/"pt.tcl"], folder, "pt.log", pt_env))
            row = reports.summarize(pt, meta, config)
            dc_warnings = []
            for report in sorted(dc.iterdir()):
                if report.suffix in (".log", ".rpt"):
                    dc_warnings += reports.audit_log(report.read_text(encoding="utf-8", errors="replace"))
            row["dc_warnings"] = dc_warnings
            row["accepted_for_tlm"] = row["accepted_for_tlm"] and not dc_warnings
            row.update(seed=vector["seed"], case=case)
            result["results"].append(row)
            write_json(work/"RESULT.json", result)
        result["status"] = "calculated_review_required"
        result["accepted_for_tlm"] = all(row["accepted_for_tlm"] for row in result["results"])
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        write_json(work/"RESULT.json", result)
        lock.unlink()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--out", type=Path, required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--prepared", type=Path, required=True)
    execute.add_argument("--case", required=True)
    execute.add_argument("--corner", choices=("SS", "TT"), required=True)
    args = parser.parse_args()
    result = prepare(args.out) if args.action == "prepare" else run(args.prepared, args.case, args.corner)
    print(json.dumps({"status": result["status"], "cases": len(result.get("cases", result.get("results", [])))}))


if __name__ == "__main__":
    main()
