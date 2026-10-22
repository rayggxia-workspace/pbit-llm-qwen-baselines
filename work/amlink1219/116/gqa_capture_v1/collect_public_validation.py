"""Package only pre-reviewed public GQA metadata; leave numeric payloads in place."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile


parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
args = parser.parse_args()
directory = args.directory.resolve(strict=True)
terminal = json.loads((directory / "terminal.json").read_text(encoding="utf-8"))
assert terminal["exit_code"] == 0 and terminal["gpu_requested"] is False
files = {}
for mode in ("exact", "pv", "winner", "rejection", "exact_narrow"):
    path = directory / "private_runs" / mode / "public_report.json"
    payload = path.read_bytes()
    report = json.loads(payload)
    assert report["schema"] == "cycle_v1.gqa.public.1"
    assert report["status"] == "passed" and report["mode_equivalence"]["equal"]
    files[mode + ".json"] = payload
for name in ("public_audit.json", "SOURCE_VERIFIED.json", "terminal.json"):
    files[name] = (directory / name).read_bytes()
for name in ("validation-2782.out", "validation-2782.err"):
    files[name] = (directory / name).read_bytes()
forbidden = {"q", "k", "v", "logits", "output", "probabilities", "physical_indices",
             "local_indices", "histogram", "frames", "sampler_frames", "native_random",
             "memory_reads", "trace", "thresholds", "gate", "up", "down", "z"}
def inspect(value):
    if isinstance(value, dict):
        assert not forbidden.intersection(value), sorted(forbidden.intersection(value))
        for child in value.values():
            inspect(child)
    elif isinstance(value, list):
        for child in value:
            inspect(child)
for name, payload in files.items():
    if name.endswith(".json"):
        inspect(json.loads(payload))
manifest = {
    "export_scope": "allowlisted public reports, counters, SHA-256, errors, timing and job receipts only; numeric tensors and raw traces retained on server",
    "private_execution_root": str(directory),
    "files": {name: hashlib.sha256(payload).hexdigest() for name, payload in files.items()},
}
files["PUBLIC_MANIFEST.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
archive_path = directory / "public_receipts.tar.gz"
assert not archive_path.exists()
with tarfile.open(archive_path, "w:gz") as archive:
    for name, payload in files.items():
        entry = tarfile.TarInfo(name)
        entry.size = len(payload)
        entry.mode = 0o644
        archive.addfile(entry, io.BytesIO(payload))
print(json.dumps({"path": str(archive_path), "files": len(files),
                  "bytes": archive_path.stat().st_size,
                  "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()}))
