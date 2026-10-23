"""Fail-closed parsers for explicit Synopsys reports and measured windows.

No fallback coefficients. Unknown report formats are an execution failure,
not evidence of zero power, zero area, or met timing.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
SCALE = {"W": 1.0, "mW": 1e-3, "uW": 1e-6, "nW": 1e-9, "pW": 1e-12}


def finite(value, label):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"nonfinite {label}")
    return result


def one(pattern, text, label, flags=re.M):
    found = re.findall(pattern, text, flags)
    if len(found) != 1:
        raise ValueError(f"expected one {label}, found {len(found)}")
    return found[0]


def units(text):
    """Only the ns/pF constraint convention this flow actually implements."""
    result = {}
    for label, target in (("Time", "ns"), ("Capacitive Load", "pf")):
        value, unit = one(r"^\s*" + label + r"\s+Units?\s*[:=]\s*(" + NUMBER +
                          r")\s*([A-Za-z]+)\s*$", text, label, re.M | re.I)
        if finite(value, label) != 1 or unit.lower() != target:
            raise ValueError(f"unsupported {label} unit {value}{unit}")
        result[label] = f"1{target}"
    return result


def operating_condition(text, name, corner):
    """Read named-field or table-style report_lib operating conditions."""
    expected = {"TT": (1.2, 25.0), "SS": (1.08, 125.0)}[corner]
    blocks = re.split(r"Operating Condition Name\s*:\s*", text, flags=re.I)[1:]
    found = []
    for block in blocks:
        if block.splitlines()[0].strip().strip("\"'") == name:
            v = one(r"^\s*Voltage\s*:\s*(" + NUMBER + r")\s*$", block, "voltage")
            t = one(r"^\s*Temperature\s*:\s*(" + NUMBER + r")\s*$", block, "temperature")
            found.append((finite(v, "voltage"), finite(t, "temperature")))
    if not found:
        columns = None
        for line in text.splitlines():
            tokens = line.split()
            lower = [s.lower() for s in tokens]
            if lower and lower[0] == "name" and "process" in lower:
                columns = lower
            elif columns and tokens and tokens[0].strip("*()") == name:
                vi = next((columns.index(s) for s in ("volt", "voltage") if s in columns), None)
                ti = next((columns.index(s) for s in ("temp", "temperature") if s in columns), None)
                if vi is None or ti is None or max(vi, ti) >= len(tokens):
                    raise ValueError("unrecognized operating condition table")
                found.append((finite(tokens[vi], "voltage"), finite(tokens[ti], "temperature")))
    if len(found) != 1 or any(abs(a-b) > 1e-6 for a, b in zip(found[0], expected)):
        raise ValueError(f"missing/ambiguous/wrong PVT {name}: {found}, expected {expected}")
    return {"name": name, "corner": corner, "voltage_V": found[0][0], "temperature_C": found[0][1]}


def power(text):
    values = {}
    # report_power may label each total explicitly or declare dynamic/leakage units.
    declared = {}
    for category in ("Dynamic", "Leakage"):
        matches = re.findall(category + r"\s+Power\s+Units?\s*[:=]\s*(" + NUMBER +
                             r")\s*(mW|uW|nW|pW|W)\b", text, re.I)
        if len(matches) == 1:
            number, unit = matches[0]
            unit = next(u for u in SCALE if u.lower() == unit.lower())
            declared[category] = finite(number, "power scale") * SCALE[unit]
    for key, label in (("internal_W", "Cell Internal Power"), ("switching_W", "Net Switching Power"),
                       ("leakage_W", "Cell Leakage Power"), ("total_W", "Total Power")):
        number, unit = one(r"^\s*" + label + r"\s*=\s*(" + NUMBER +
                           r")(?:\s*(mW|uW|nW|pW|W))?\b[^\n]*$", text, label)
        if unit:
            scale = SCALE[unit]
        else:
            category = "Leakage" if key == "leakage_W" else "Dynamic"
            if category not in declared:
                raise ValueError("missing explicit power units")
            scale = declared[category]
        values[key] = finite(number, key) * scale
        if values[key] < 0:
            raise ValueError("negative power")
    if values["total_W"] <= 0 or not math.isclose(
            values["internal_W"] + values["switching_W"] + values["leakage_W"],
            values["total_W"], rel_tol=.02, abs_tol=1e-15):
        raise ValueError("inconsistent total power")
    return values


def activity(text):
    result = {}
    for key, label in (("total_nets", "Total number of nets"),
                       ("annotated_nets", "Number of annotated nets"),
                       ("leaf_cells", "Total number of leaf cells"),
                       ("fully_annotated_cells", "Number of fully annotated leaf cells")):
        result[key] = int(one(re.escape(label) + r"\s*=\s*(\d+)", text, label))
    if not 0 < result["annotated_nets"] <= result["total_nets"]:
        raise ValueError("missing/invalid VCD net annotation")
    if not 0 < result["fully_annotated_cells"] <= result["leaf_cells"]:
        raise ValueError("missing/invalid VCD cell annotation")
    result["net_fraction"] = result["annotated_nets"] / result["total_nets"]
    result["cell_fraction"] = result["fully_annotated_cells"] / result["leaf_cells"]
    # Incomplete coverage is preserved and prevents accepted per-operation PPA.
    result["complete"] = result["net_fraction"] == result["cell_fraction"] == 1
    return result


def window(data):
    for key in ("start_ps", "end_ps", "accepted", "completed"):
        if type(data.get(key)) is not int:
            raise ValueError(f"integer {key} required")
    if data["start_ps"] < 0 or data["end_ps"] <= data["start_ps"]:
        raise ValueError("invalid measurement window")
    if data["accepted"] <= 0 or data["completed"] <= 0:
        raise ValueError("active window has no completed operations")
    if data["accepted"] != data["completed"]:
        raise ValueError("active window contains an unbalanced pipeline boundary")
    if data.get("period_ps") != 10000 or data.get("scenario") != "synthetic_active":
        raise ValueError("unsupported clock/scenario")
    if data.get("contains_reset") != 0 or data.get("contains_drain") != 0:
        raise ValueError("reset/drain contaminated active window")
    if data.get("warmup_continuous_cycles", 0) < 32:
        raise ValueError("missing continuous warmup")
    return dict(data, duration_ns=(data["end_ps"]-data["start_ps"])/1000)


def read_window(path):
    data = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if not sep or key in data:
            raise ValueError("malformed/duplicate window key")
        data[key] = int(value) if re.fullmatch(r"\d+", value) else value
    return window(data)


def audit_vcd(path, start_ps, end_ps):
    """Stream all dumped identifiers; reject unknown state overlapping window."""
    values = {}
    tick_ps = None
    now_ps = 0
    scale_text = None
    definitions = True
    last_ps = 0
    checked_intervals = 0
    with Path(path).open(encoding="ascii") as stream:
        for raw in stream:
            line = raw.strip()
            if scale_text is not None:
                scale_text += " " + line
                if "$end" not in scale_text:
                    continue
                match = re.search(r"\$timescale\s+(1|10|100)\s*(ps|ns)\s+\$end", scale_text)
                if not match:
                    raise ValueError("unsupported VCD timescale")
                tick_ps = int(match[1]) * (1000 if match[2] == "ns" else 1)
                scale_text = None
                continue
            if line.startswith("$timescale"):
                scale_text = line
                if "$end" in line:
                    match = re.search(r"\$timescale\s+(1|10|100)\s*(ps|ns)\s+\$end", line)
                    if not match:
                        raise ValueError("unsupported VCD timescale")
                    tick_ps = int(match[1]) * (1000 if match[2] == "ns" else 1)
                    scale_text = None
            elif line.startswith("$var"):
                fields = line.split()
                values[fields[3]] = None
            elif line.startswith("$enddefinitions"):
                definitions = False
            elif not definitions and line.startswith("#"):
                if tick_ps is None:
                    raise ValueError("missing VCD timescale")
                next_ps = int(line[1:]) * tick_ps
                if next_ps < now_ps:
                    raise ValueError("nonmonotonic VCD")
                if max(now_ps, start_ps) < min(next_ps, end_ps):
                    checked_intervals += 1
                    if any(value is None or "x" in value or "z" in value for value in values.values()):
                        raise ValueError("VCD X/Z/uninitialized signal overlaps active window")
                now_ps = last_ps = next_ps
                if next_ps >= end_ps:
                    break
            elif not definitions and line and line[0].lower() in "01xzbr":
                if line[0].lower() in "br":
                    fields = line.split()
                    if len(fields) != 2:
                        raise ValueError("malformed VCD value")
                    value, code = fields[0][1:].lower(), fields[1]
                else:
                    value, code = line[0].lower(), line[1:]
                if code not in values:
                    raise ValueError("undeclared VCD identifier")
                values[code] = value
    if not values or last_ps < end_ps or checked_intervals == 0:
        raise ValueError("VCD does not cover complete window")
    return {"dumped_identifiers": len(values), "checked_intervals": checked_intervals,
            "start_ps": start_ps, "end_ps": end_ps, "xz_signals": 0}


def require_reports(folder, names):
    for name in names:
        path = Path(folder) / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"missing/empty report {path}")


def audit_log(text):
    errors = re.findall(r"^.*(?:\bError:|\bFatal:|\bError-|\bFATAL\b).*$", text, re.M)
    warnings = re.findall(r"^.*\bWarning:.*$", text, re.M)
    if errors:
        raise ValueError("tool emitted error: " + errors[0][:240])
    return warnings


def summarize(folder, meta, config):
    folder = Path(folder)
    names = ("units.rpt", "library.rpt", "design.rpt", "clock.rpt", "setup.rpt", "hold.rpt",
             "constraints.rpt", "check_timing.rpt", "power.rpt", "activity.rpt",
             "check_power.rpt", "area.txt", "inventory.tsv", "setup_slack.txt", "hold_slack.txt",
             "link.log", "condition.log", "vcd.log", "update_power.log", "pt.log", "DONE")
    require_reports(folder, names)
    read = lambda name: (folder/name).read_text(encoding="utf-8")
    units(read("units.rpt"))
    pvt = operating_condition(read("library.rpt"), config["oc_name"], config["corner"])
    if not re.search(r"(?<!\S)" + re.escape(config["oc_name"]) + r"(?!\S)", read("design.rpt")):
        raise ValueError("report_design does not bind the requested operating condition")
    measured = window(meta)
    powers, coverage = power(read("power.rpt")), activity(read("activity.rpt"))
    area = finite(read("area.txt").strip(), "area")
    setup = finite(read("setup_slack.txt").strip(), "setup slack")
    hold = finite(read("hold_slack.txt").strip(), "hold slack")
    if area <= 0:
        raise ValueError("empty mapped area")
    warnings = []
    for path in sorted(folder.iterdir()):
        if path.suffix in (".rpt", ".log"):
            warnings += audit_log(path.read_text(encoding="utf-8"))
    constraint_violations = [line.strip() for line in read("constraints.rpt").splitlines()
                             if re.search(r"\bVIOLATED\b", line, re.I)]
    # Warnings are never silently waived. A reviewer can inspect preserved reports.
    timing_met = setup >= 0 and hold >= 0
    physical_area_unit_known = config.get("area_unit") == "um2" and bool(config.get("area_unit_evidence_sha256"))
    accepted = timing_met and coverage["complete"] and not warnings and not constraint_violations and physical_area_unit_known
    return {"status": "calculated_review_required", "accepted_for_tlm": accepted,
            "evidence": "DC_GATE_PT_PRELAYOUT", "pvt": pvt, "window": measured,
            "area_library_units": area,
            "area_um2": area if physical_area_unit_known else None,
            "setup_slack_ns": setup, "hold_slack_ns": hold, "timing_met": timing_met,
            "activity": coverage, "warnings": warnings, "constraint_violations": constraint_violations, **powers,
            "energy_pJ_per_completed": powers["total_W"] * measured["duration_ns"] * 1000 /
                                       measured["completed"],
            "limitations": ["synthetic active window", "no SDF/SPEF/CTS", "not silicon measurement",
                            "unknown constraints/warnings require review; not signoff"]}
