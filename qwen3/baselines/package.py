"""Create an immutable execution tar from committed source, without editing checkout."""
import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(root), *arguments])
    assert not git("status", "--porcelain", "--", "qwen3/baselines").strip()
    revision = git("rev-parse", "HEAD").decode().strip()
    paths = git("ls-tree", "-r", "--name-only", revision, "qwen3/baselines").decode().splitlines()
    files = {}
    output = Path(args.output)
    with tarfile.open(output, "x:gz") as archive:
        for path in paths:
            raw = git("show", f"{revision}:{path}")
            name = Path(path).name
            files[name] = hashlib.sha256(raw).hexdigest()
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            member.mode = 0o444
            archive.addfile(member, io.BytesIO(raw))
        manifest = {"repository": "https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines",
                    "commit": revision, "source_prefix": "qwen3/baselines", "files_sha256": files}
        raw = (json.dumps(manifest, indent=2) + "\n").encode()
        member = tarfile.TarInfo("execution.json")
        member.size = len(raw)
        member.mode = 0o444
        archive.addfile(member, io.BytesIO(raw))
    print(json.dumps({"path": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "source": manifest}, indent=2))


if __name__ == "__main__":
    main()
