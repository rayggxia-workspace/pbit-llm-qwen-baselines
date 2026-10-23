"""Check immutable external-framework evidence, without requiring ONNXim locally."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def verify(repo: Path) -> dict:
    result_dir = repo / "architecture_tlm/cycle_v1/results/onnxim_probe_20261023"
    evidence = repo / "work/amlink1219/116/framework"
    checked = []
    for line in (evidence / "2772-remote.sha256").read_text(encoding="utf-8").splitlines():
        expected, remote = line.split(maxsplit=1)
        path = result_dir / Path(remote).name if remote.startswith("framework-probe-2772-results/") else evidence / Path(remote).name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
        checked.append(path.relative_to(repo).as_posix())
    receipt = json.loads((evidence / "framework-source-edits-2772.json").read_text(encoding="utf-8"))
    probe = repo / "architecture_tlm/cycle_v1/external/onnxim/PBitThresholdTransportProbeTest.cc"
    assert hashlib.sha256(probe.read_bytes()).hexdigest() == receipt["probe_sha256"]
    terminal = json.loads((evidence / "framework-probe-2772-terminal.json").read_text(encoding="utf-8"))
    assert terminal == {"job_id": "2772", "stage": "done", "exit_code": 0}
    scheduler = (evidence / "2772-first-terminal.txt").read_text(encoding="utf-8-sig")
    assert "JobState=COMPLETED" in scheduler and "ExitCode=0:0" in scheduler
    assert "[  PASSED  ] 2 tests." in (evidence / "framework-official-tests-2772.txt").read_text(encoding="utf-8")
    assert "[  PASSED  ] 1 test." in (evidence / "framework-custom-tests-2772.txt").read_text(encoding="utf-8")
    summaries = []
    for name, cycles, active in [("baseline", 17, 8), ("bounded_long_memory", 45, 8),
                                  ("out_of_order", 25, 8), ("narrow_vector", 25, 16)]:
        record = json.loads((result_dir / f"{name}.json").read_text(encoding="utf-8"))
        assert record["finish_cycles"] == cycles and record["vector_active_cycles"] == active
        inflight, returned, refused = {}, set(), None
        peak = 0
        for event in record["events"]:
            identity = (event["address"], event["write"])
            if event["event"] == "accept":
                assert event["id"] not in inflight and event["id"] not in returned
                if refused is not None:
                    assert (event["id"], identity) == refused
                    refused = None
                inflight[event["id"]] = identity
            elif event["event"] == "return":
                assert inflight.pop(event["id"]) == identity
                returned.add(event["id"])
            else:
                assert event["event"] == "refuse" and len(inflight) == record["window"]
                assert refused in (None, (event["id"], identity))
                refused = (event["id"], identity)
            peak = max(peak, len(inflight))
            assert len(inflight) <= record["window"]
        assert not inflight and not refused and len(returned) == 3
        assert peak == record["peak_inflight"]
        assert record["write_accept"] > record["last_read_return"]
        summaries.append({k: record[k] for k in ("name", "finish_cycles", "vector_active_cycles", "peak_inflight", "refused_cycles")})
    return {"passed": True, "remote_hashes_verified": len(checked), "source_hash_verified": True,
            "official_tests": 2, "custom_scenarios": summaries, "job_id": "2772"}


if __name__ == "__main__":
    print(json.dumps(verify(Path(__file__).resolve().parents[4]), indent=2))
