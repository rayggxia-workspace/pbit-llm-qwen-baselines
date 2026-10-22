"""Read-only publication-scope and public synthetic artifact checks."""
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import tarfile


def sha(blob): return hashlib.sha256(blob).hexdigest()
def canonical(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def check(condition,label):
    if not condition: raise AssertionError(label)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--base",default="885c6a0")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError("fresh result required")
    root=args.root.resolve()
    def git(*parts): return subprocess.check_output(["git",*parts],cwd=root)
    head=git("rev-parse","HEAD").decode().strip()
    changed=git("diff","--name-only",args.base,head).decode().splitlines()
    prefixes=("architecture_tlm/cycle_v1/","work/amlink1219/116/","progress/amlink1219/")
    check(all(n.startswith(prefixes) for n in changed),"changed another task/member path")
    tracked=git("ls-tree","-r","--name-only",head).decode().splitlines()
    forbidden_suffix=(".safetensors",".pt",".pth",".ckpt",".bin",".npy",".npz")
    check(not any(n.lower().endswith(forbidden_suffix) for n in changed),"new raw/model tensor file")
    check(not any("private_fixture" in n.lower() or "qwen_layer12_gqa7_context64.json" in n for n in tracked),"tracked private real fixture")
    # Return only paths if any high-specificity credential signature is found.
    secret=re.compile(rb"(?:ghp_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
    for name in changed:
        if name.endswith((".gz",".tar")): continue
        check(secret.search(git("show",head+":"+name)) is None,"credential signature in "+name)
    manifest_reports=[]
    for folder in ("work/amlink1219/116/gqa_validation/f94c9db","work/amlink1219/116/gqa_scaling"):
        manifest=json.loads((root/folder/"MANIFEST.json").read_text(encoding="utf-8"))
        for relative,digest in manifest.items():
            blob=(root/folder/relative).read_bytes()
            check(sha(blob)==digest,"local manifest artifact: "+relative)
            check(sha(git("show",head+":"+folder+"/"+relative))==digest,"committed manifest artifact: "+relative)
        manifest_reports.append(dict(path=folder,artifacts=len(manifest),local_and_git_bytes_equal=True))
    # Reconstruct public sin fixture without calling production constructors.
    row=lambda n,phase:[math.sin(i*.37+phase)*.17 for i in range(n)]
    fixture=dict(provenance=dict(kind="deterministic_synthetic_GQA",version=1,KV_heads=1),
        queries=[dict(q=row(16,h*.21),candidate_ids=[10,2,1,11,3] if h%2==0 else [3,2,8,10]) for h in range(7)],
        k=[row(16,i*.13) for i in range(12)],v=[row(12,i*.27) for i in range(12)])
    fixture_hash=sha(canonical(fixture))
    cases=[]
    for mode in ("exact","pv","winner","rejection"):
        folder=root/"work/amlink1219/116/gqa_validation/f94c9db"/mode
        summary=json.loads((folder/"summary.json").read_text(encoding="utf-8"))
        start=json.loads((folder/"START.json").read_text(encoding="utf-8"))
        check(summary["fixture_sha256"]==start["fixture_sha256"]==fixture_hash,"not the public synthetic fixture")
        check(summary["fixture_provenance"]==fixture["provenance"],"synthetic provenance")
        check(summary["query_heads"]==7 and summary["KV_heads"]==1,"synthetic shape")
        trace=json.loads(gzip.decompress((folder/"trace.json.gz").read_bytes()))
        by_id={r["op"]:r for r in trace["trace"] if r["kind"]=="accept"}
        checked=0
        for field,kind in (("k","K"),("v","V")):
            width=len(fixture[field][0])*4
            base=next(r["address"] for r in summary["shared"]["address_regions"] if r["name"]==kind)
            for token,ident in summary["shared"][kind+"_read_ids"].items():
                token=int(token);entry=by_id[ident]
                payload=struct.pack("<"+"f"*len(fixture[field][token]),*fixture[field][token])
                check(entry["address"]==base+token*width and entry["size_bytes"]==width,"synthetic actual address")
                check(trace["memory_reads"][ident]["sha256"]==sha(payload),"synthetic actual read hash")
                checked+=1
        cases.append(dict(mode=mode,fixture_sha256=fixture_hash,synthetic_actual_KV_reads_checked=checked,
                          operations=summary["operations"],latency_ns=summary["latency_ns"]))
    archive_members={}
    for filename in ("source_snapshot.tar.gz","public_receipts.tar.gz"):
        folder="work/amlink1219/116/gqa_validation_v1/"
        with tarfile.open(root/folder/filename,"r:gz") as archive:
            members=archive.getmembers()
            check(all(m.isfile() for m in members),"non-file archive member")
            check(not any("private_fixture" in m.name or m.name.endswith(forbidden_suffix) for m in members),"private archive member")
            if filename=="source_snapshot.tar.gz":
                check(all(m.name.endswith((".py",".json")) for m in members),"unexpected source archive payload")
                check(all(secret.search(archive.extractfile(m).read()) is None for m in members),"credential signature in source archive")
            archive_members[filename]=len(members)
    event=json.loads((root/"work/amlink1219/116/gqa_validation/event_only_receipt.json").read_text(encoding="utf-8"))
    check(event["mode_equivalence"]["checked"] is False and event["mode_equivalence"]["equal"] is None,"event-only overclaims comparison")
    report=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),git_head=head,base=args.base,passed=True,
        changed_paths=len(changed),scope_paths=list(prefixes),other_member_paths_changed=False,
        private_real_fixture_tracked=False,high_specificity_credential_signatures=False,
        manifests=manifest_reports,synthetic_cases=cases,archive_members=archive_members,event_only_scope_correct=True,
        limits="No simulation rerun. Public synthetic fixture reconstructed independently and actual addressed read hashes checked. Real private payload was not opened, downloaded or copied; separately authenticated public receipts establish server execution.")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(passed=True,changed_paths=len(changed),synthetic_cases=len(cases),manifest_artifacts=sum(x["artifacts"] for x in manifest_reports))))


if __name__=="__main__": main()
