"""Independent offline checks of matrix identity, provenance and trace accounting.

This module deliberately imports no production simulator or numerical oracle.
Stored numerical pass/tolerance fields are checked as receipts, not relabeled
as independently reproduced mathematical results.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import tarfile


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def pack(values):
    return struct.pack("<"+"f"*len(values), *values)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def source_binding(source, files):
    actual = source["source_sha256"]
    required = {"attention.py", "ffn.py", "kernel.py", "memory.py", "contracts.py",
                "rng_protocol.py", "run.py", "matrix.py"}
    required |= {"architecture_tlm/random_service/"+name for name in
                 ("__init__.py", "model.py", "backends.py", "service.py", "shared64_mapping.json")}
    required.add("architecture_tlm/unified_v6/rng_integrated.py")
    check(required <= actual.keys(), "source closure omits an execution dependency")
    for name, sha in actual.items():
        relative = name if name.startswith("architecture_tlm/") else "architecture_tlm/cycle_v1/"+name
        check(files.get(relative) == sha, "source/execution-manifest mismatch: "+relative)
    return len(actual)


def identities(suite):
    expected = {}
    layers = (0, 12, 23) if suite == "real" else (None,)
    seeds = (0, 1, 2) if suite == "real" else (0,)
    for layer in layers:
        prefix = "synthetic" if layer is None else f"qwen_layer{layer}"
        for seed in seeds:
            for bins, samples in ((4, 32), (2, 32), (4, 16), (4, 64)):
                expected[f"{prefix}_ffn_B{bins}T{samples}K{samples}_seed{seed}"] = (
                    "ffn", layer, dict(bins=bins, samples=samples, strata=samples, seed=seed), seed == 0, None)
            for mode in ("exact", "pv", "winner", "rejection"):
                if mode == "exact" and seed:
                    continue
                label = f"{mode}_N128_S32_seed{seed}" if layer is not None else f"{mode}_S32_seed{seed}"
                expected[prefix+"_"+label] = ("attention", layer, dict(mode=mode, samples=32, seed=seed), seed == 0, None)
    if suite == "real":
        for mode in ("winner", "rejection"):
            expected[f"qwen_layer12_{mode}_N512_S512_seed0"] = (
                "attention", 12, dict(mode=mode, samples=512, seed=0), True, 512)
    return expected


def known_reads(operator, fixture):
    """Initial actual-byte regions only; do not invent dynamic partial payloads."""
    regions = []
    if fixture is None:
        return regions
    if operator == "attention":
        regions.append(("sram", 0x70000000, pack(fixture["q"])))
        for field, base in (("k", 0x71000000), ("v", 0x72000000)):
            width = len(fixture[field][0])*4
            regions.extend(("dram", base+i*width, pack(row)) for i, row in enumerate(fixture[field]))
    else:
        regions += [("sram", 0x40000000, pack(fixture["x"])),
                    ("sram", 0x42000000, pack(fixture["residual"]))]
        for field, base in (("wg", 0x10000000), ("wu", 0x20000000), ("wd", 0x30000000)):
            matrix = fixture[field]
            if not isinstance(matrix, dict):
                continue
            rows = matrix["codes"]
            columns = len(rows[0])
            for r in range(0, len(rows), 64):
                for c in range(0, columns, 64):
                    tile = (r//64)*math.ceil(columns/64)+c//64
                    address = base+tile*4160
                    codes = [value for row in rows[r:r+64] for value in row[c:c+64]]
                    regions += [("dram", address, bytes(value & 255 for value in codes)),
                                ("dram", address+4096, pack([matrix["scales"][r//64][c//64]]))]
    return regions


def trace_audit(folder, summary, contracts, fixture):
    artifact = summary.get("trace_artifact")
    if artifact is None:
        check(not (folder/"trace.json.gz").exists(), "unregistered trace artifact")
        return None
    compressed = (folder/artifact["path"]).read_bytes()
    blob = gzip.decompress(compressed)
    check(len(compressed) == artifact["bytes"] and digest(compressed) == artifact["sha256"], "compressed trace hash")
    check(digest(blob) == artifact["uncompressed_sha256"], "trace payload hash")
    trace = json.loads(blob)
    check(len(trace["trace"]) == summary["trace_events"], "trace count")
    resources = {x["name"]: x for x in contracts["resources"]}
    ports = {x["name"]: x for x in contracts["memory_ports"]}
    buffers = contracts["buffers"]
    accepts, completes, actions = {}, {}, Counter()
    per_time = defaultdict(lambda: {"accept": [], "complete": []})
    known = known_reads(summary["operator"], fixture)
    checked_payloads = 0
    memory_reads = set()
    for event in trace["trace"]:
        if event["kind"] not in ("accept", "complete"):
            continue
        target = accepts if event["kind"] == "accept" else completes
        check(event["op"] not in target, "duplicate transaction event")
        target[event["op"]] = event
        per_time[event["time_ps"]][event["kind"]].append(event)
        spec = resources.get(event["resource"], ports.get(event["resource"]))
        clock = spec["clock"]
        check((event["time_ps"]-clock["phase_ps"]) % clock["period_ps"] == 0, "event off resource edge")
        if event["kind"] != "accept":
            continue
        actions.update(event["actions"])
        if "address" not in event:
            continue
        port = ports[event["resource"]]
        direction = "write" if event["write"] else "read"
        address, length = event["address"], event["size_bytes"]
        banks = Counter(line % port["banks"] for line in range(address//port["line_bytes"],
                                                              (address+length-1)//port["line_bytes"]+1))
        check(banks == Counter({int(k):v for k,v in event["bank_beats"].items()}), "address-to-bank mapping")
        actions[f"memory.{event['resource']}.{direction}_requests"] += 1
        actions[f"memory.{event['resource']}.{direction}_bytes"] += length
        actions[f"memory.{event['resource']}.{direction}_beats"] += sum(banks.values())
        if not event["write"]:
            memory_reads.add(event["op"])
            receipt = trace["memory_reads"][event["op"]]
            check(receipt["bytes"] == length and re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"]), "read receipt size/hash")
            for resource, start, data in known:
                if resource == event["resource"] and start <= address and address+length <= start+len(data):
                    check(digest(data[address-start:address-start+length]) == receipt["sha256"], "actual read bytes differ from fixture: "+event["op"])
                    checked_payloads += 1
                    break
    check({k:v["time_ps"] for k,v in accepts.items()} == trace["accepted_ps"], "accept index")
    check({k:v["time_ps"] for k,v in completes.items()} == trace["completion_ps"], "completion index")
    check(accepts.keys() == completes.keys() and len(accepts) == summary["operations"], "operation conservation")
    check(memory_reads == trace["memory_reads"].keys(), "all memory read receipts present")
    check(actions == Counter(summary["actions"]), "semantic+physical action recount")
    check(max(x["time_ps"] for x in completes.values()) == summary["finish_ps"], "final completion")
    credits = {name:spec["initial"] for name,spec in buffers.items()}
    minimum, maximum = dict(credits), dict(credits)
    occupancy, peak, instance = Counter(), Counter(), Counter()
    last_issue, last_complete, bank_ready, bank_occupancy = {}, {}, {}, Counter()
    stats = {name:Counter() for name in resources.keys() | ports.keys()}
    for timestamp, events in sorted(per_time.items()):
        consumed, produced, starts, ends = Counter(), Counter(), Counter(), Counter()
        instance_starts, bank_starts, bank_ends = Counter(), Counter(), Counter()
        for event in events["accept"]:
            name, inst = event["resource"], event["instance"]
            starts[name] += 1
            consumed.update(event["inputs"])
            stats[name]["accepted"] += 1
            if name in resources:
                spec = resources[name]
                key = name, inst
                instance_starts[key] += 1
                check(timestamp >= last_issue.get(key, -1), "resource input II")
                last_issue[key] = timestamp+spec["ii_cycles"]*spec["clock"]["period_ps"]
            else:
                spec = ports[name]
                for bank in event["bank_beats"]:
                    bank_starts[name, int(bank)] += 1
                distributed = Counter()
                for bank, port, beats in event["bank_ports"]:
                    key = name, bank, port
                    check(0 <= port < spec["ports_per_bank"] and timestamp >= bank_ready.get(key, -1), "bank launch collision")
                    bank_ready[key] = timestamp+beats*spec["ii_cycles"]*spec["clock"]["period_ps"]
                    distributed[bank] += beats
                check(distributed == Counter({int(k):v for k,v in event["bank_beats"].items()}), "bank beat distribution")
        for event in events["complete"]:
            name, inst = event["resource"], event["instance"]
            original = accepts[event["op"]]
            check(original["time_ps"] == event["accepted_ps"] < event["due_ps"] <= timestamp, "accept/due/complete ordering")
            check(original["due_ps"] == event["due_ps"], "immutable due time")
            ends[name] += 1
            produced.update(event["outputs"])
            spec = resources.get(name, ports.get(name))
            key = name, inst, event["completion_port"]
            count = spec["completion_ports"] if name in resources else spec["response_ports"]
            ii = spec["output_ii_cycles"] if name in resources else spec["response_ii_cycles"]
            check(0 <= event["completion_port"] < count and timestamp >= last_complete.get(key, -1), "finite completion port")
            last_complete[key] = timestamp+ii*spec["clock"]["period_ps"]
            stats[name].update(completed=1, execution_ps=event["due_ps"]-event["accepted_ps"],
                               held_ps=timestamp-event["accepted_ps"], output_blocked_ps=timestamp-event["due_ps"])
            if name in ports:
                for bank in original["bank_beats"]:
                    bank_ends[name, int(bank)] += 1
        for name,spec in buffers.items():
            check(consumed[name] <= credits[name], "same-edge producer/credit bypass: "+name)
            check(produced[name] <= spec["capacity"]-credits[name], "same-edge buffer-space bypass: "+name)
            credits[name] += produced[name]-consumed[name]
            minimum[name] = min(minimum[name], credits[name])
            maximum[name] = max(maximum[name], credits[name])
        for name,spec in resources.items():
            for inst in range(spec["instances"]):
                key = name, inst
                check(instance[key]+instance_starts[key] <= spec["capacity"], "same-edge resource slot bypass")
                instance[key] += instance_starts[key]-sum(e["resource"] == name and e["instance"] == inst for e in events["complete"])
        for name,spec in ports.items():
            check(occupancy[name]+starts[name] <= spec["window"], "memory window bypass")
            for bank in range(spec["banks"]):
                key = name, bank
                check(bank_occupancy[key]+bank_starts[key] <= spec["bank_capacity"], "bank capacity bypass")
                bank_occupancy[key] += bank_starts[key]-bank_ends[key]
        for name in resources.keys() | ports.keys():
            occupancy[name] += starts[name]-ends[name]
            check(occupancy[name] >= 0, "negative resource occupancy")
            peak[name] = max(peak[name], occupancy[name])
    check(not any(occupancy.values()) and not any(instance.values()) and not any(bank_occupancy.values()), "unretired resources")
    check(dict(peak) == summary["resource_peak"], "resource peak recount")
    for name,spec in buffers.items():
        check(credits[name] == spec["initial"] == spec["final"], "buffer credits not returned")
        check(minimum[name] == spec["minimum_tokens_or_credits"] and maximum[name] == spec["maximum_tokens_or_credits"], "storage extrema recount")
        if spec["initial"] == spec["capacity"]:
            check(spec["capacity"]-minimum[name] == spec["peak_reserved_units"], "used credit peak")
    check(stats.keys() == summary["resource_stats"].keys() and
          all(value == Counter(summary["resource_stats"][name]) for name,value in stats.items()), "resource statistics recount")
    if fixture is not None:
        check(checked_payloads > 0, "no independent initial read payload checked")
    return dict(events=len(trace["trace"]), operations=len(accepts), independent_fixture_read_hashes=checked_payloads,
                all_actions_recounted=True, old_state_capacity_constraints=True, completion_and_bank_ports=True)


def case_audit(folder, summary, fixture):
    config, operator = summary["config"], summary["operator"]
    check(summary["mode_equivalence"]["checked"] is True and summary["mode_equivalence"]["equal"] is True, "reported mode gate")
    check(set(summary["execution_modes"]) == {"cycle", "event"}, "both execution mode receipts")
    validation = summary["numerical_validation"]
    if operator == "ffn":
        check(validation["bit_equal_fields"] == dict.fromkeys(("gate", "up", "z", "projected", "output"), True), "reported numeric field gate")
    else:
        error, bound = validation["max_absolute_error"], validation["absolute_tolerance"]
        check(math.isfinite(error) and math.isfinite(bound) and 0 <= error <= bound, "reported numeric tolerance gate")
    output = pack(summary["output"])
    if operator == "ffn" and config["output_bf16"]:
        check(all(output[i:i+2] == b"\x00\x00" for i in range(0, len(output), 4)), "BF16 values not exact")
        output = b"".join(output[i+2:i+4] for i in range(0, len(output), 4))
    check(digest(output) == summary["output_memory_sha256"], "stored output hash")
    check(summary["energy"]["status"] == "unknown", "uncharacterized PPA must remain unknown")
    check(summary["latency_ns"]*1000 == summary["finish_ps"], "latency units")
    contracts = read(folder/"contracts.json")
    check(contracts["buffers"] == summary["storage"], "storage contract copy")
    for name,spec in summary["storage"].items():
        check(spec["initial"] == spec["final"] and 0 <= spec["minimum_tokens_or_credits"] <= spec["maximum_tokens_or_credits"] <= spec["capacity"], "reported credit gate: "+name)
    native = summary.get("native_random")
    if operator == "attention" and config["mode"] == "exact":
        check(native is None, "exact path should not claim native draws")
    else:
        check(config["random_backend"] == "native" and native is not None, "native source receipt omitted")
        check(native["physical_entropy"] is False and native["physical_timing_characterized"] is False, "native physical evidence overclaim")
        check(native["energy_J"] is None and native["area_mm2"] is None, "native unknown PPA")
        check(native["seed_word_transcript"] and native["ports"] and native["receipts"], "missing native provenance")
        frames = sum(x["kind"] == "frame" for x in native["receipts"])
        commands = sum(x["kind"] == "command" for x in native["receipts"])
        check(frames == summary["actions"].get("native_rng_request", 0), "native frame request count")
        check(commands == summary["actions"].get("native_rng_command", 0), "native command count")
        for receipt in native["receipts"]:
            check(receipt["submit_ps"] < receipt["native_complete_ps"], "native completion before submission")
            if "valid_ps" in receipt:
                check(receipt["submit_ps"] < receipt["valid_ps"] <= receipt["native_complete_ps"], "native valid timing")
    if operator == "attention":
        sampler = summary["sampler"]
        histogram = {int(k):v for k,v in sampler["histogram"].items()}
        if config["mode"] != "exact":
            check(Counter(sampler["physical_indices"]) == histogram and sum(histogram.values()) == config["samples"] == sampler["retained_samples"], "sample multiplicity")
            check(len(histogram) == sampler["unique_V"], "unique V count")
            check(sampler["native_biased_generated_lanes"] == sampler["native_biased_used_lanes"]+sampler["native_biased_padding_lanes"], "biased padding conservation")
            check(sampler["native_fair_generated_bits"] == sampler["native_fair_used_bits"]+sampler["native_fair_unused_bits"], "fair padding conservation")
        if fixture is not None:
            d, dv = len(fixture["q"]), len(fixture["v"][0])
            ids = fixture.get("candidate_ids", list(range(len(fixture["k"]))))
            selected = sorted(ids) if config["mode"] == "exact" else sorted(histogram)
            check(set(selected) <= set(ids), "sampled nonexistent physical candidate")
            check(summary["K_addresses"] == [0x71000000+i*d*4 for i in ids], "physical K addresses")
            check(summary["V_addresses"] == [0x72000000+i*dv*4 for i in selected], "physical unique V addresses")
            check(summary["actions"]["K_read_bytes"] == len(ids)*d*4, "K byte count")
            check(summary["actions"]["V_read_bytes"] == len(selected)*dv*4 and sampler["unique_V"] == len(selected), "V byte count/multiplicity")
    return trace_audit(folder, summary, contracts, fixture)


def suite_audit(folder, suite, execution, fixtures):
    manifest = read(folder/"ARTIFACT_MANIFEST.json")
    declared = set()
    for artifact in manifest["artifacts"]:
        relative = Path(artifact["path"])
        check(not relative.is_absolute() and ".." not in relative.parts, "manifest path escapes suite")
        check(artifact["path"] not in declared, "duplicate artifact")
        declared.add(artifact["path"])
        data = (folder/relative).read_bytes()
        check(len(data) == artifact["bytes"] and digest(data) == artifact["sha256"], "artifact bytes/hash: "+artifact["path"])
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    check(actual == declared | {"ARTIFACT_MANIFEST.json"}, "undeclared or absent suite artifact")
    summary, cases = read(folder/"SUMMARY.json"), read(folder/"CASES.json")
    expected = identities(suite)
    check(len(cases) == len(expected) and {x["name"] for x in cases} == expected.keys(), "case identity set")
    check(summary["suite"] == suite and summary["passed"] == len(expected) and summary["failed"] == 0, "suite reported completion")
    check(len(summary["cases"]) == len(expected) and {x["name"] for x in summary["cases"]} == expected.keys(), "result identity set")
    check(read(folder/"PARTIAL.json") == summary["cases"], "final partial receipt")
    source_binding(summary["source"], execution["source"]["files"])
    declarations = {x["name"]:x for x in cases}
    reports = []
    for item in summary["cases"]:
        name = item["name"]
        operator, layer, config, traced, count = expected[name]
        declared_case = declarations[name]
        check(declared_case["operator"] == operator and declared_case["config"] == config and declared_case["trace"] == traced and declared_case["candidate_count"] == count, "declared configuration: "+name)
        report = read(folder/name/"summary.json")
        check(item["passed"] is True and item["summary"].replace("\\", "/") == name+"/summary.json", "case result path")
        for field in ("operator", "config", "fixture_sha256", "latency_ns", "operations", "numerical_validation", "mode_equivalence", "equivalence_payload_sha256", "output_memory_sha256"):
            check(item[field] == report[field], "case/suite summary mismatch: "+field)
        check(operator == report["operator"] and all(report["config"][key] == value for key,value in config.items()), "effective config differs")
        source_binding(report["source"], execution["source"]["files"])
        fixture = None
        if layer is not None:
            bundle, sha = fixtures[layer]
            check(report["fixture_sha256"] == sha, "fixture source hash")
            fixture = dict(bundle[operator])
            if count:
                context = len(fixture["k"])
                fixture["candidate_ids"] = [i*(context-1)//(count-1) for i in range(count)]
                check(report["fixture_provenance"]["candidate_override"] == count, "candidate override provenance")
        trace = case_audit(folder/name, report, fixture)
        check((trace is not None) == traced, "required full trace missing")
        reports.append(dict(case=name, operator=operator, reported_numeric_gate_rechecked=True,
                            independent_math_recomputed=False, trace_audit=trace))
    return dict(suite=suite, cases=len(reports), artifacts=len(declared),
                artifact_manifest_sha256=digest((folder/"ARTIFACT_MANIFEST.json").read_bytes()), cases_reviewed=reports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", type=Path, required=True)
    parser.add_argument("--smoke", type=Path, required=True)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--archive-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve prior audit result")
    execution = read(args.execution)
    check(execution["cuda_visible"] == "", "CPU job must hide unallocated GPUs")
    archives = {}
    if args.source_archive:
        check(digest(args.source_archive.read_bytes()) == execution["source"]["archive_sha256"], "source archive hash")
        with tarfile.open(args.source_archive) as archive:
            members = {member.name:member for member in archive.getmembers() if member.isfile()}
            check(members.keys() == execution["source"]["files"].keys(), "packaged source closure")
            for name, sha in execution["source"]["files"].items():
                check(digest(archive.extractfile(members[name]).read()) == sha, "packaged runtime source: "+name)
        archives["source_files_verified"] = len(members)
    if args.archive:
        check(args.archive_sha256 is not None and digest(args.archive.read_bytes()) == args.archive_sha256, "result archive hash")
        archives["result_archive_sha256_verified"] = args.archive_sha256
    fixtures = {}
    for layer in (0, 12, 23):
        path = args.fixture_dir/f"qwen_layer{layer}.json"
        fixtures[layer] = read(path), digest(path.read_bytes())
    suites = [suite_audit(args.real, "real", execution, fixtures), suite_audit(args.smoke, "smoke", execution, fixtures)]
    traces = [case["trace_audit"] for suite in suites for case in suite["cases_reviewed"] if case["trace_audit"]]
    result = dict(passed=True, job_id=execution["job_id"], suites=suites,
                  archives=archives, full_traces=len(traces),
                  trace_events_checked=sum(x["events"] for x in traces),
                  traced_operations_checked=sum(x["operations"] for x in traces),
                  independent_fixture_read_hashes=sum(x["independent_fixture_read_hashes"] for x in traces),
                  execution_sha256=digest(args.execution.read_bytes()),
                  source_archive_sha256=execution["source"]["archive_sha256"],
                  fixture_sha256={str(k):v[1] for k,v in fixtures.items()},
                  reviewer_sha256=digest(Path(__file__).read_bytes()),
                  scope="independent offline identity/hash/payload/trace/accounting checks; stored numerical gates are receipts, not a new mathematical proof",
                  independent_numerical_evidence="separate 3 real cropped FFN scalar oracles and 54 independent adversarial tests",
                  physical_ppa="unknown; no physical energy/area/STA/silicon or full-model PPL inferred")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"passed":True, "cases":sum(x["cases"] for x in suites), "artifacts":sum(x["artifacts"] for x in suites)}))


if __name__ == "__main__":
    main()
