"""Check a small private fixture in place; emit hashes/metadata, never activations."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    manifest_path = args.directory / "private_fixture" / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact, = manifest["artifacts"]
    fixture_path = manifest_path.parent / artifact["path"]
    payload = fixture_path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
    assert len(payload) == artifact["bytes"]
    fixture = json.loads(payload)
    assert len(fixture["queries"]) == 7
    assert len(fixture["k"]) == len(fixture["v"]) == 64
    assert all(len(row) == 64 for row in fixture["k"] + fixture["v"])
    assert all(len(q["q"]) == 64 and q["candidate_ids"] == list(range(64))
               for q in fixture["queries"])
    assert fixture["provenance"] == manifest["provenance"]
    exact = manifest["exact_functional_diagnostic"]
    receipt = {
        "status": "pass",
        "private_payload_retained_on_server": True,
        "fixture_sha_and_schema_verified_in_place": True,
        "fixture_path": str(fixture_path),
        "artifact": artifact,
        "private_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "provenance": manifest["provenance"],
        "exact_functional_diagnostic": {key: exact[key] for key in ("method", "shape", "output_sha256")},
        "log_sha256": {name: hashlib.sha256((args.directory / name).read_bytes()).hexdigest()
                       for name in ("capture-2781.out", "capture-2781.err", "terminal.json")},
        "export_scope": "only identity, shape, SHA-256, numerical boundary and execution metadata; no Q/K/V or diagnostic output arrays",
    }
    print(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
