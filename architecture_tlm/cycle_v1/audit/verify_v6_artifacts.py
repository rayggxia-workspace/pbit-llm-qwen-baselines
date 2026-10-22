"""Offline verification of the five explicitly scoped v6 bridge receipts."""
import argparse
import json
from pathlib import Path
import subprocess

from .verify_matrix_artifacts import case_audit, check, digest, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve prior audit result")
    manifest = read(args.results/"MANIFEST.json")
    for item in manifest["files"]:
        blob = (args.results/item["path"]).read_bytes()
        check(len(blob) == item["bytes"] and digest(blob) == item["sha256"], item["path"])
    cases = []
    sources = set()
    for name in ("ffn", "exact", "pv", "winner", "rejection"):
        folder = args.results/name
        start, summary = read(folder/"START.json"), read(folder/"summary.json")
        check(summary["status"] == "passed" and summary["speedup"] is None, "unsupported performance comparison")
        hashes = dict(start["legacy_source_sha256"])
        for path, sha in start["source"]["source_sha256"].items():
            relative = path if path.startswith("architecture_tlm/") else "architecture_tlm/cycle_v1/"+path
            hashes[relative] = sha
        for path, sha in hashes.items():
            blob = subprocess.check_output(["git", "show", start["source"]["commit"]+":"+path], cwd=args.source_root)
            # Git may store LF while the Windows execution used CRLF. Accept
            # only exact recorded hashes of a conventional checkout variant.
            unix = blob.replace(b"\r\n", b"\n")
            candidates = (blob, unix, unix.replace(b"\n", b"\r\n"))
            check(any(digest(candidate) == sha for candidate in candidates), "executed dependency hash: "+path)
            sources.add(path)
        legacy = read(folder/"v6_summary.json")
        current = read(folder/"cycle/summary.json")
        check(legacy["numeric_output"] is None, "legacy workload is not a numerical oracle")
        check(legacy["elapsed_ns"] == summary["legacy"]["elapsed_ns"], "legacy elapsed record")
        check(current["latency_ns"] == summary["cycle"]["elapsed_ns"], "cycle elapsed record")
        check(any("logits can differ" in note for note in summary["boundary"]["no_direct_equivalence"]), "QK arithmetic difference omitted")
        trace = case_audit(folder/"cycle", current, None)
        cases.append(dict(case=name, trace=trace, independent_numeric_or_cross_model_equivalence=False))
    receipt = dict(passed=True, compiled_scope="Python native v6 operator/config bridge; not full-model migration",
                   result_commit="b741427", source_commit=manifest["source_commit"],
                   artifact_files=len(manifest["files"]), execution_sources=len(sources), cases=cases,
                   source_check="fixed executed Git revision; LF/CRLF checkout variants accepted only when exact recorded SHA-256 matches",
                   manifest_sha256=digest((args.results/"MANIFEST.json").read_bytes()),
                   reviewer_sha256=digest(Path(__file__).read_bytes()),
                   shared_trace_checker_sha256=digest(Path(__file__).with_name("verify_matrix_artifacts.py").read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"passed":True,"cases":len(cases),"artifact_files":len(manifest["files"]),"execution_sources":len(sources)}))


if __name__ == "__main__":
    main()
