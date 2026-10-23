"""Archive existing evidence for a user-requested pause; never execute experiments."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PROJECTS = ROOT.parent
TREES = ["cycle23", "cycle23-audit", "cycle23-core", "cycle23-gqa",
         "cycle23-ops", "cycle23-registry-gqa", "cycle23-sensitivity"]

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def git(tree, *args):
    return subprocess.check_output(["git", "-C", str(tree), *args])

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

def main():
    out = HERE/"pause_archives"
    out.mkdir(exist_ok=False)
    (out/".gitattributes").write_text("*.gz -text\n", encoding="utf-8")
    inventory = []
    archive_inputs = []
    for name in TREES:
        tree = PROJECTS/name
        changes = []
        entries = git(tree, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0")
        for entry in entries:
            if not entry:
                continue
            status, relative = entry[:2].decode(), entry[3:].decode()
            path = tree/relative
            item = dict(status=status, path=relative)
            if path.is_file():
                item.update(bytes=path.stat().st_size, sha256=sha(path))
            if status.strip() == "M":
                original = git(tree, "show", "HEAD:"+relative)
                current = path.read_bytes()
                item["only_crlf_difference"] = original.replace(b"\r\n",b"\n") == current.replace(b"\r\n",b"\n")
                item["preserved_unmodified_by_closeout"] = True
            changes.append(item)
            if status != "??" or not path.is_file():
                continue
            allowed = (
                (name=="cycle23" and any(relative.startswith("work/amlink1219/116/"+p+"/") for p in
                    ("layer-validation-v1","pv-deadlock-reproduction-fixed","reporting-final-smoke-v2","smoke"))) or
                (name=="cycle23-core" and "/v6_adapter_" in relative and "_smoke/" in relative) or
                (name=="cycle23-audit" and relative.startswith("architecture_tlm/cycle_v1/audit/results/")) or
                (name=="cycle23-gqa" and relative.startswith("work/amlink1219/116/gqa_smoke/")) or
                (name=="cycle23-sensitivity" and relative.endswith("/LAST_SCHEDULER.txt")) or
                (name=="cycle23-registry-gqa" and relative.endswith("/gqa_conditional_model_record.json"))
            )
            if allowed:
                archive_inputs.append((path, name+"/"+relative))
        inventory.append(dict(worktree=str(tree), head=git(tree,"rev-parse","HEAD").decode().strip(),
            branch=git(tree,"branch","--show-current").decode().strip() or "(detached)",
            uncommitted=changes))
    archive_path = out/"historical_local_diagnostics.tar.gz"
    member_manifest = []
    with tarfile.open(archive_path, "w:gz") as archive:
        for path, member in sorted(archive_inputs, key=lambda item:item[1]):
            assert path.is_file() and not path.is_symlink()
            member_manifest.append(dict(member=member, bytes=path.stat().st_size, sha256=sha(path)))
            archive.add(path, arcname=member, recursive=False)
    with tarfile.open(archive_path) as archive:
        assert len(archive.getmembers()) == len(member_manifest)
        for item, member in zip(member_manifest, archive.getmembers()):
            assert member.isfile()
            assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == item["sha256"]
    files = [dict(path=archive_path.name, bytes=archive_path.stat().st_size, sha256=sha(archive_path))]
    exports = ROOT.parents[1]/"outputs"/"tlm_cycle_20261023"
    for name in ("matrix-v4-results.tar.gz", "matrix-v5-results.tar.gz",
                 "cycle-source-v1.tar.gz", "cycle-source-v2.tar.gz", "cycle-source-v3.tar.gz", "cycle-source-v5.tar.gz"):
        source = exports/name
        dest = out/name
        shutil.copyfile(source, dest)
        assert sha(source) == sha(dest)
        files.append(dict(path=name, bytes=dest.stat().st_size, sha256=sha(dest), source=str(source)))
    paused_source = PROJECTS/"cycle23-registry-gqa"/"work/amlink1219/116"
    paused_dest = HERE/"active_gqa_2k_paused"
    paused_dest.mkdir(exist_ok=False)
    (paused_dest/".gitattributes").write_text("* -text whitespace=cr-at-eol\n", encoding="utf-8")
    paused_files = []
    for path in sorted((paused_source/"active_gqa_2k_local").iterdir()):
        if path.is_file():
            dest = paused_dest/path.name
            shutil.copyfile(path,dest)
            assert sha(path)==sha(dest)
            paused_files.append(dict(path=dest.name,bytes=dest.stat().st_size,sha256=sha(dest)))
    runner = paused_source/"run_active_gqa_2k.py"
    shutil.copyfile(runner, paused_dest/"run_active_gqa_2k_original.py")
    paused_files.append(dict(path="run_active_gqa_2k_original.py",bytes=runner.stat().st_size,sha256=sha(runner),
        note="archival original; location-dependent draft, not a command to resume"))
    fixture = paused_source/"active_gqa_2k_local/raw/fixture.json"
    fixture_archive = out/"paused_2k_synthetic_input.tar.gz"
    with tarfile.open(fixture_archive,"w:gz") as archive:
        archive.add(fixture, arcname="synthetic_fixture.json", recursive=False)
    files.append(dict(path=fixture_archive.name,bytes=fixture_archive.stat().st_size,sha256=sha(fixture_archive),
        synthetic_input_sha256=sha(fixture),synthetic_input_bytes=fixture.stat().st_size,
        note="deterministic sine fixture; no real model activations"))
    save(paused_dest/"ARCHIVE_MANIFEST.json", paused_files)
    save(out/"MANIFEST.json",dict(created_utc=datetime.now(timezone.utc).isoformat(),files=files,
        historical_diagnostic_members=member_manifest,
        scope="Existing evidence copied only; no experiments executed. Historical failures/preliminary runs are not additional final passes. No real private fixture or model weights included."))
    save(HERE/"PAUSE_WORKTREE_INVENTORY.json",dict(created_utc=datetime.now(timezone.utc).isoformat(),
        pause_head=git(ROOT,"rev-parse","HEAD").decode().strip(),worktrees=inventory,
        retained_local_only="Duplicate extracted source/tool dependencies, raw private model fixtures, and historical worktree byte differences remain in place. No reset/cleanup or rerun."))
    print(json.dumps(dict(archived_files=len(files),diagnostic_members=len(member_manifest),paused_files=len(paused_files))))

if __name__=="__main__":
    main()
