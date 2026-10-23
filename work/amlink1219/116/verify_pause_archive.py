"""Read-only checks of pause documents and already-created archives."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
def digest(blob): return hashlib.sha256(blob).hexdigest()

def main():
    manifest=json.loads((HERE/"pause_archives/MANIFEST.json").read_text(encoding="utf-8"))
    archives=[]
    secret=re.compile(rb"(?:ghp_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
    for item in manifest["files"]:
        path=HERE/"pause_archives"/item["path"]
        assert digest(path.read_bytes())==item["sha256"]
        count=0
        with tarfile.open(path) as archive:
            for member in archive:
                assert not member.issym() and not member.islnk()
                assert not member.name.startswith("/") and ".." not in Path(member.name).parts
                if not member.isfile(): continue
                assert not member.name.endswith((".safetensors",".pt",".pth",".npy",".npz"))
                blob=archive.extractfile(member).read()
                assert secret.search(blob) is None, member.name
                if member.name.endswith("trace.json.gz"):
                    trace=json.loads(gzip.decompress(blob))
                    for value in trace.get("memory_reads",{}).values():
                        if isinstance(value,dict) and "sha256" in value and "bytes" in value:
                            assert isinstance(value["bytes"],int), "raw memory payload in published trace"
                count+=1
        archives.append(dict(path=item["path"],sha256=item["sha256"],regular_members=count))
    doc_paths=[
        "architecture_tlm/cycle_v1/IMPLEMENTATION_ZH.md",
        "work/amlink1219/116/PAUSE_REPORT_ZH.md","work/amlink1219/116/HANDOFF.md",
        "work/amlink1219/116/PLAN_COVERAGE_ZH.md","work/amlink1219/116/PR_BODY.md",
        "work/amlink1219/116/ISSUE_UPDATE.md","work/amlink1219/116/PAUSE_COMMENT.md",
        "progress/amlink1219/STATUS.md"]
    links=[]
    docs={}
    for relative in doc_paths:
        path=ROOT/relative
        blob=path.read_bytes()
        docs[relative]=digest(blob)
        for target in re.findall(r"\]\(([^)]+)\)",blob.decode("utf-8")):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:",target) or target.startswith("#"):
                continue
            target=target.split("#",1)[0]
            assert (path.parent/target).exists(), (relative,target)
            links.append(dict(source=relative,target=target))
    release=json.loads((HERE/"release_validation_v2/RESULT.json").read_text(encoding="utf-8"))
    assert all(digest((ROOT/path).read_bytes())==expected for path,expected in release["source_sha256"].items())
    paused=json.loads((HERE/"PAUSE_STATE.json").read_text(encoding="utf-8"))
    assert paused["goal_status"]=="paused" and paused["automatic_resume"] is False
    jobs=json.loads((HERE/"PAUSE_QUEUE.json").read_text(encoding="utf-8"))
    assert not jobs["queue"]
    procs=json.loads((HERE/"PAUSE_LOCAL_PROCESSES.json").read_text(encoding="utf-8"))
    assert all(not item["exists"] for item in procs["processes"])
    record=dict(checked_utc=datetime.now(timezone.utc).isoformat(),status="PASS",
        kind="static closeout archive/document verification only; no simulation/test experiments",
        archives=archives,document_sha256=docs,relative_links=links,
        unchanged_production_source_files=len(release["source_sha256"]),
        goal_status="paused",automatic_resume=False,queue_empty_at_recorded_check=True,
        local_2k_pids_absent=True,model_weights_or_real_private_fixture_exported=False)
    (HERE/"PAUSE_CLOSEOUT_VALIDATION.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(status="PASS",archives=len(archives),links=len(links),
        unchanged_production_sources=len(release["source_sha256"]),goal_status="paused")))

if __name__=="__main__": main()
