"""Offline audit of reduced decoder traces, storage, traffic and output bytes."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import struct


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve prior audit receipt")
    suite = read(args.results/"SUITE.json")
    cases = []
    for name, receipt in suite["success_cases"].items():
        folder = args.results/name
        summary = read(folder/"summary.json")
        contracts = read(folder/"contracts.json")
        compressed = (folder/"trace.json.gz").read_bytes()
        assert hashlib.sha256(compressed).hexdigest() == summary["trace_sha256"]
        trace = json.loads(gzip.decompress(compressed))
        output = b"".join(struct.pack("<f", value)[2:] for value in summary["output"])
        assert hashlib.sha256(output).hexdigest() == receipt["output_memory_sha256"] == summary["output_memory_sha256"]
        accepts, completes = {}, {}
        traffic = Counter()
        changes = defaultdict(Counter)
        for event in trace["trace"]:
            if event["kind"] == "accept":
                assert event["op"] not in accepts
                accepts[event["op"]] = event["time_ps"]
                for buffer, amount in event["inputs"].items():
                    changes[event["time_ps"]][buffer] -= amount
                if "address" in event:
                    direction = "write" if event["write"] else "read"
                    traffic[f"memory.{event['resource']}.{direction}_bytes"] += event["size_bytes"]
                    traffic[f"memory.{event['resource']}.{direction}_requests"] += 1
            elif event["kind"] == "complete":
                assert event["op"] not in completes
                completes[event["op"]] = event["time_ps"]
                for buffer, amount in event["outputs"].items():
                    changes[event["time_ps"]][buffer] += amount
        assert accepts == trace["accepted_ps"] and completes == trace["completion_ps"]
        assert set(accepts) == set(completes) and len(accepts) == summary["operations"] == receipt["operations"]
        assert all(completes[name] > accepts[name] for name in accepts)
        for metric, total in traffic.items():
            assert summary["actions"][metric] == total == trace["actions"][metric]
        credits = {spec["name"]:spec["initial"] for spec in contracts["buffers"]}
        minimum = dict(credits)
        capacities = {spec["name"]:spec["capacity"] for spec in contracts["buffers"]}
        for time in sorted(changes):
            for buffer, amount in changes[time].items():
                credits[buffer] += amount
                minimum[buffer] = min(minimum[buffer], credits[buffer])
                assert 0 <= credits[buffer] <= capacities[buffer]
        assert credits == trace["buffer_final"]
        for spec in contracts["buffers"]:
            name_ = spec["name"]
            assert credits[name_] == spec["initial"]
            assert minimum[name_] == summary["storage"][name_]["minimum_tokens_or_credits"]
            if spec["initial"] == spec["capacity"]:
                assert spec["capacity"]-minimum[name_] == summary["storage"][name_]["peak_reserved_units"]
        assert summary["energy"]["status"] == "unknown" and summary["full_model_ppl"] is None
        cases.append({"case":name,"operations":len(accepts),"trace_hash_verified":True,
                      "output_hash_verified":True,"traffic_recounted":True,"all_storage_credits_returned":True})
    base = suite["success_cases"]["exact"]
    for name in ("bank_conflict", "slow_memory", "capacity_exact"):
        assert suite["success_cases"][name]["output_memory_sha256"] == base["output_memory_sha256"]
    for name in ("bank_conflict", "slow_memory"):
        assert suite["success_cases"][name]["latency_ns"] > base["latency_ns"]
    assert [guard["case"] for guard in suite["capacity_guards"]] == ["layer_state_underflow", "candidate_capacity_overflow"]
    assert "working storage" in suite["capacity_guards"][0]["reason"]
    assert "candidate capacity exceeded" in suite["capacity_guards"][1]["reason"]
    result = {"passed":True,"scope":"offline artifact checks; independent numerical layer tests are separate",
              "cases":cases,"capacity_guards_verified":2,
              "suite_sha256":hashlib.sha256((args.results/"SUITE.json").read_bytes()).hexdigest(),
              "reviewer_script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"passed":True,"cases":len(cases),"capacity_guards":2}))


if __name__ == "__main__":
    main()
