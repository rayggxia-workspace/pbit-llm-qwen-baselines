"""Exact-object API fallback for this task only; no force-push, credentials never printed."""
import base64
import concurrent.futures
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
REPO = "rayggxia-workspace/pbit-llm-qwen-baselines"
PREFIX = "/repos/" + REPO
BRANCH = "task/136-qwen3-bf16"
BASE = "6966739a5223680888bf0315f7bb4f73423a1ae6"
os.environ["GCM_INTERACTIVE"] = "Never"
os.environ["GIT_TERMINAL_PROMPT"] = "0"
credential_result = subprocess.run(["git", "credential", "fill"],
    input="protocol=https\nhost=github.com\nusername=jieruiz\n\n", cwd=ROOT,
    text=True, capture_output=True, check=True, timeout=20)
credential = dict(line.split("=", 1) for line in credential_result.stdout.splitlines() if "=" in line)


def api(method, path, payload=None):
    request = urllib.request.Request("https://api.github.com" + path, method=method,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + credential["password"],
                 "Accept": "application/vnd.github+json", "Content-Type": "application/json",
                 "User-Agent": "pbit-qwen3-issue136"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def save(name, value):
    with (OUT / name).open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def person(text):
    match = re.fullmatch(r"(.*) <(.*)> (\d+) ([+-])(\d\d)(\d\d)", text)
    assert match
    offset = (1 if match[4] == "+" else -1) * (60 * int(match[5]) + int(match[6]))
    date = datetime.datetime.fromtimestamp(int(match[3]), datetime.timezone(datetime.timedelta(minutes=offset)))
    return {"name": match[1], "email": match[2], "date": date.isoformat()}


def allowed(path):
    return path.startswith(("qwen3/", "work/jieruiz/136/")) or path in ("progress/jieruiz/STATUS.md", "PROJECT_MEMORY_ZH.md")


def publish():
    assert api("GET", "/user")["login"] == "jieruiz"
    assert api("GET", PREFIX)["permissions"]["push"]
    refs = api("GET", PREFIX + "/git/matching-refs/heads/" + BRANCH)
    current = next((r for r in refs if r["ref"] == "refs/heads/" + BRANCH), None)
    original = current["object"]["sha"] if current else BASE
    parent = original
    head = git("rev-parse", "HEAD").decode().strip()
    subprocess.run(["git", "merge-base", "--is-ancestor", parent, head], cwd=ROOT, check=True)
    commits = git("rev-list", "--reverse", parent + ".." + head).decode().splitlines()
    for commit in commits:
        header, message = git("cat-file", "commit", commit).decode().split("\n\n", 1)
        fields = dict(line.split(" ", 1) for line in header.splitlines())
        assert fields.get("parent") == parent and header.count("\nparent ") == 1
        paths = git("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", commit).decode().strip("\0").split("\0")
        assert all(allowed(p) for p in paths), paths
        def blob(path):
            raw = git("show", commit + ":" + path)
            assert len(raw) < 3000000
            result = api("POST", PREFIX + "/git/blobs", {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
            assert result["sha"] == git("rev-parse", commit + ":" + path).decode().strip()
            return {"path": path, "mode": "100644", "type": "blob", "sha": result["sha"]}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            entries = list(pool.map(blob, paths))
        tree = api("POST", PREFIX + "/git/trees", {"base_tree": git("rev-parse", parent + "^{tree}").decode().strip(), "tree": entries})
        assert tree["sha"] == fields["tree"]
        result = api("POST", PREFIX + "/git/commits", {"message": message, "tree": tree["sha"], "parents": [parent],
                     "author": person(fields["author"]), "committer": person(fields["committer"])})
        assert result["sha"] == commit
        parent = commit
        print(json.dumps({"uploaded_exact_commit": commit}), flush=True)
    if current:
        assert api("GET", PREFIX + "/git/ref/heads/" + BRANCH)["object"]["sha"] == original
        result = api("PATCH", PREFIX + "/git/refs/heads/" + BRANCH, {"sha": head, "force": False})
    else:
        result = api("POST", PREFIX + "/git/refs", {"ref": "refs/heads/" + BRANCH, "sha": head})
    assert result["object"]["sha"] == head
    save("PUSH.json", {"repo": REPO, "branch": BRANCH, "head": head, "previous": original, "exact_objects": True})


if __name__ == "__main__":
    if sys.argv[1] == "push":
        publish()
    elif sys.argv[1] == "verify":
        assert api("GET", "/user")["login"] == "jieruiz"
        head = api("GET", PREFIX + "/git/ref/heads/" + BRANCH)["object"]["sha"]
        assert head == git("rev-parse", "HEAD").decode().strip()
        paths = git("diff", "--name-only", BASE, head).decode().splitlines()
        checked = []
        for path in paths:
            assert allowed(path)
            raw = git("show", head + ":" + path)
            oid = git("rev-parse", head + ":" + path).decode().strip()
            remote = base64.b64decode(api("GET", PREFIX + "/git/blobs/" + oid)["content"])
            assert raw == remote, path
            checked.append({"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        save("REMOTE_VERIFY.json", {"head": head, "verified": checked, "status": "PASS"})
        print(json.dumps({"verified_files": len(checked), "head": head, "status": "PASS"}))
    else:
        raise ValueError(sys.argv[1])
