"""Archive committed GQA/audit source bytes without results or fixture payloads."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--core-commit", required=True)
    parser.add_argument("--audit-commit", required=True)
    parser.add_argument("--audit-path", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("fresh source package directory required")
    def git(*command):
        return subprocess.check_output(["git", "-C", str(args.repository), *command])
    core = git("rev-parse", args.core_commit + "^{commit}").decode().strip()
    audit = git("rev-parse", args.audit_commit + "^{commit}").decode().strip()
    names = git("ls-tree", "-r", "--name-only", core).decode().splitlines()
    prefixes = ("architecture_tlm/cycle_v1/", "architecture_tlm/random_service/",
                "architecture_tlm/unified_v6/")
    selected = {name for name in names if name.startswith(prefixes)
                and "/results/" not in name
                and (name.endswith(".py") or "/configs/" in name and name.endswith(".json"))}
    selected.add("architecture_tlm/random_service/shared64_mapping.json")
    assert all(name in names for name in selected)
    files = {name: git("show", core + ":" + name) for name in sorted(selected)}
    for name in args.audit_path:
        if not name.startswith("architecture_tlm/cycle_v1/audit/") or not name.endswith(".py"):
            raise ValueError("audit override must be a Python file inside the audit scope")
        files[name] = git("show", audit + ":" + name)
    args.output.mkdir(parents=True)
    archive_path = args.output / "source_snapshot.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, payload in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(payload))
    manifest = {
        "core_commit": core, "audit_commit": audit, "audit_paths": args.audit_path,
        "files": {name: hashlib.sha256(payload).hexdigest() for name, payload in files.items()},
        "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "scope": "committed Python/config source and required shared64 mapping only; no fixture/model/result/environment payloads",
    }
    with tarfile.open(archive_path) as archive:
        assert {m.name: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                for m in archive.getmembers()} == manifest["files"]
    (args.output / "SOURCE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"files": len(files), "core_commit": core,
                      "archive_sha256": manifest["archive_sha256"]}))


if __name__ == "__main__":
    main()
