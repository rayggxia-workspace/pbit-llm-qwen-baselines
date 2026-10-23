"""Independently reparse immutable RTL stdout and regenerate kernel expectations.

This is offline evidence verification, not a new invocation of Icarus Verilog.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from architecture_tlm.cycle_v1.rtl.validate_rtl import cdc_reference, pipeline_reference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve existing audit receipt")
    cycle = Path(__file__).resolve().parents[1]
    root = cycle.parents[1]
    folder = cycle/"results/rtl_contract_20261023"
    evidence = root/"work/amlink1219/116/rtl"
    report = json.loads((folder/"RTL_CONTRACT_VALIDATION.json").read_text(encoding="utf-8"))
    archive = evidence/"rtl-contract-2764-results.tar.gz"
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert archive_hash == (evidence/(archive.name+".sha256")).read_text(encoding="utf-8").split()[0]
    checked = 0
    with tarfile.open(archive, "r:gz") as saved:
        for name, digest in report["artifact_sha256"].items():
            archived = saved.extractfile("results/"+name).read()
            assert hashlib.sha256(archived).hexdigest() == digest, name
            local = folder/name
            if local.exists():
                assert local.read_bytes() == archived, name
            checked += 1
    sources = {}
    for name, digest in report["source_sha256"].items():
        actual = hashlib.sha256((cycle/name).read_bytes()).hexdigest()
        assert actual == digest, name
        sources[name] = actual
    cases = []
    for case in report["cases"]:
        config = case["configuration"]
        fresh, properties = pipeline_reference(config) if case["case"].startswith("pipeline") else cdc_reference(config)
        raw = (folder/case["case"]/"simulate.stdout.txt").read_text(encoding="utf-8")
        observed = {key:[] for key in fresh}
        for line in raw.splitlines():
            words = line.split()
            if words and words[0] in observed:
                observed[words[0]].append([int(word) for word in words[1:]])
        assert observed == fresh, case["case"]
        assert observed == json.loads((folder/case["case"]/"observed.json").read_text(encoding="utf-8"))
        assert "PASS" in raw
        cases.append({"case":case["case"], "handshakes":sum(map(len, observed.values())), "matched":True})
    result = {"scope":"offline audit of independent SystemVerilog protocol evidence; no new RTL simulation or physical validation",
              "passed":True, "cases":cases, "handshakes":sum(case["handshakes"] for case in cases),
              "artifacts_verified":checked, "archive_sha256":archive_hash, "source_sha256":sources,
              "reviewer_script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("passed","handshakes","artifacts_verified")}))


if __name__ == "__main__":
    main()
