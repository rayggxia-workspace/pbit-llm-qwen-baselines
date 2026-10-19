"""Read-only preflight for this user's completed Issue55 refresh worktrees."""
import concurrent.futures
import json
import pathlib
import subprocess

ROOT = pathlib.Path(r"C:\Users\86134\Documents\a_P_BIT").resolve()
REPO = ROOT / "pbit-llm-qwen-baselines"
OUT = pathlib.Path(__file__).resolve().parent
BASE = "workspace/pbit-tlm-attention-details-20261016"

def git(path, *args):
    p = subprocess.run(["git", "-C", str(path), *args], capture_output=True,
                       encoding="utf-8", errors="replace", timeout=60)
    return p.returncode, p.stdout.strip(), p.stderr.strip()

base = git(REPO, "rev-parse", BASE)[1]
raw = git(REPO, "worktree", "list", "--porcelain")[1]
records = []
for group in raw.split("\n\n"):
    d = dict(x.split(" ", 1) if " " in x else (x, True) for x in group.splitlines())
    if pathlib.Path(d.get("worktree", "")).name.startswith("pr55-resolve-"):
        records.append(d)

def inspect(d):
    path = pathlib.Path(d["worktree"]).resolve()
    status = git(path, "status", "--porcelain=v1", "--untracked-files=all")
    ignored = git(path, "ls-files", "--others", "--ignored", "--exclude-standard")
    ignored_names = ignored[1].splitlines() if ignored[1] else []
    bad_ignored = [p for p in ignored_names if not any(
        n in pathlib.PurePosixPath(p).parts
        for n in ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"))]
    ancestor = git(REPO, "merge-base", "--is-ancestor", d["HEAD"], base)[0] == 0
    branch_ok = str(d.get("branch", "")).startswith("refs/heads/review/55-refresh-pr")
    rel_ok = path.parent == ROOT / "tmp" and path.name.startswith("pr55-resolve-")
    reparse = any(p.is_symlink() for p in [path, path.parent])
    eligible = status[0] == 0 and not status[1] and ignored[0] == 0 and not bad_ignored and ancestor and branch_ok and rel_ok and not reparse
    return dict(path=str(path), head=d["HEAD"], branch=d.get("branch"),
                merged_in=base, ancestor=ancestor, status=status[1],
                ignored_count=len(ignored_names), noncache_ignored=bad_ignored,
                eligible=eligible, author_scope="jieruiz completed Issue55 PR refresh helpers only")

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    checked = list(pool.map(inspect, records))
inventory = json.loads((OUT / "inventory_before.json").read_text(encoding="utf-8"))
sizes = dict(inventory["tmp_children"])
for row in checked:
    row["bytes"] = sizes.get(pathlib.Path(row["path"]).name, 0)
report = dict(base=base, records=checked,
              eligible_bytes=sum(x["bytes"] for x in checked if x["eligible"]))
(OUT / "worktree_preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
print(json.dumps({"base":base,"eligible_GiB":round(report["eligible_bytes"]/2**30,3),
    "rows":[{**{k:r[k] for k in ("path","eligible","ancestor","branch","ignored_count","status")},
             "MiB":round(r["bytes"]/2**20,2),"noncache_ignored":r["noncache_ignored"][:6]} for r in checked]},ensure_ascii=False,indent=2))
