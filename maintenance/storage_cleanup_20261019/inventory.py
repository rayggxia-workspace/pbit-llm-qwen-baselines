"""Read-only disk inventory; never follows Windows reparse points."""
import collections
import datetime
import heapq
import json
import os
import pathlib
import shutil
import stat

ROOT = pathlib.Path(r"C:\Users\86134\Documents\a_P_BIT").resolve()
OUT = pathlib.Path(__file__).resolve().parent
totals = collections.Counter()
counts = collections.Counter()
tmp_totals = collections.Counter()
suffixes = collections.Counter()
large = []
caches = collections.defaultdict(lambda: [0, 0])
errors = []
skipped = []
stack = [ROOT]
files = 0
while stack:
    parent = stack.pop()
    try:
        entries = list(os.scandir(parent))
    except OSError as exc:
        errors.append([str(parent), str(exc)])
        continue
    for entry in entries:
        try:
            s = entry.stat(follow_symlinks=False)
            if s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                skipped.append(str(entry.path))
                continue
            if stat.S_ISDIR(s.st_mode):
                stack.append(pathlib.Path(entry.path))
                continue
            if not stat.S_ISREG(s.st_mode):
                continue
            rel = pathlib.Path(entry.path).relative_to(ROOT)
            parts = rel.parts
            top = parts[0] if len(parts) > 1 else "[root files]"
            totals[top] += s.st_size
            counts[top] += 1
            files += 1
            suffixes[pathlib.Path(entry.name).suffix.lower()] += s.st_size
            if parts[0] == "tmp" and len(parts) > 2:
                tmp_totals[parts[1]] += s.st_size
            row = {"path": str(rel), "bytes": s.st_size,
                   "mtime": s.st_mtime, "nlink": s.st_nlink}
            if s.st_size >= 10 * 1024**2:
                large.append(row)
            for name in ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"):
                if name in parts:
                    p = str(pathlib.Path(*parts[:parts.index(name) + 1]))
                    caches[p][0] += s.st_size
                    caches[p][1] += 1
                    break
        except OSError as exc:
            errors.append([entry.path, str(exc)])
report = dict(root=str(ROOT), created=datetime.datetime.now().astimezone().isoformat(),
              disk=shutil.disk_usage(ROOT)._asdict(), files=files,
              total_bytes=sum(totals.values()), top=totals.most_common(),
              top_file_counts=dict(counts), tmp_children=tmp_totals.most_common(),
              suffixes=suffixes.most_common(),
              large_files=sorted(large, key=lambda x: x['bytes'], reverse=True),
              caches=dict(caches), skipped_reparse=skipped, errors=errors)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "inventory_before.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
print(json.dumps({"files": files, "total_GiB": round(report['total_bytes']/2**30,3),
    "top_GiB": [(p,round(n/2**30,3)) for p,n in report['top'][:30]],
    "tmp_top_GiB": [(p,round(n/2**30,3)) for p,n in report['tmp_children'][:25]],
    "largest": [{"path":r['path'],"MiB":round(r['bytes']/2**20,2)} for r in report['large_files'][:35]],
    "cache_MiB": round(sum(r[0] for r in caches.values())/2**20,2),
    "errors": errors[:10], "skipped_reparse_count":len(skipped)}, ensure_ascii=False, indent=2))
