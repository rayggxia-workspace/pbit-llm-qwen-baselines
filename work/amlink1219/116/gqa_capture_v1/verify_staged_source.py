"""Verify the committed source package in a CPU-only allocated execution."""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

directory = Path(sys.argv[1]).resolve(strict=True)
assert os.environ.get("SLURM_JOB_ID")
assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
manifest = json.loads((directory / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
assert hashlib.sha256((directory / "source_snapshot.tar.gz").read_bytes()).hexdigest() == manifest["archive_sha256"]
for name, expected in manifest["files"].items():
    path = (directory / "source" / name).resolve(strict=True)
    assert path.is_relative_to(directory / "source")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
receipt = {"status": "pass", "job_id": os.environ["SLURM_JOB_ID"],
           "CUDA_VISIBLE_DEVICES": "", "python": platform.python_version(),
           "files_verified": len(manifest["files"]),
           "archive_sha256": manifest["archive_sha256"],
           "core_commit": manifest["core_commit"], "audit_commit": manifest["audit_commit"]}
(directory / "SOURCE_VERIFIED.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
