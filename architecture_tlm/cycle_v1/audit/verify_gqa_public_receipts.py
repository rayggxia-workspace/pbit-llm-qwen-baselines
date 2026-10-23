"""Verify allowlisted real-GQA receipts without accessing private tensors.

The independent numerical/trace code executed on the allocated server. This
offline step authenticates that code and the returned counts/decisions; it does
not pretend to locally replay private numerical data or absent raw traces.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile


def sha(blob): return hashlib.sha256(blob).hexdigest()
def read(path): return json.loads(path.read_text(encoding="utf-8"))
def check(condition,label):
    if not condition: raise AssertionError(label)


def verify_allowlist(value):
    forbidden={"q","k","v","logits","output","local_indices","physical_indices","histogram",
               "probabilities","sampler_frames","native_random","physical_weights","K_union","V_union","trace"}
    if isinstance(value,dict):
        check(not forbidden.intersection(value),"public report contains a forbidden payload field")
        for item in value.values(): verify_allowlist(item)
    elif isinstance(value,list):
        for item in value: verify_allowlist(item)


def archive_files(path):
    with tarfile.open(path,"r:gz") as archive:
        files={}
        for member in archive.getmembers():
            check(member.isfile(),"archive nonregular member")
            check(not member.name.startswith("/") and ".." not in member.name.split("/"),"archive escaping path")
            check(member.name not in files,"archive duplicate path")
            files[member.name]=archive.extractfile(member).read()
        return files


def fixed_git_sources(manifest,root,published_map=None):
    names=list(manifest["files"])
    revisions=[manifest["audit_commit"] if n in manifest["audit_paths"] else manifest["core_commit"] for n in names]
    if published_map is not None:
        # Preserve original execution identities. A publication may use different
        # commit IDs; replacements are valid only with exact per-file bytes and
        # ancestry in the explicitly selected published head.
        check(published_map["original_core_commit"]==manifest["core_commit"],"mapped core identity")
        check(published_map["original_audit_commit"]==manifest["audit_commit"],"mapped audit identity")
        mappings=published_map["matched_files"]
        check(set(mappings)==set(names),"published map source closure")
        revisions=[mappings[n]["commit"] for n in names]
        check(all(mappings[n]["sha256"]==manifest["files"][n] for n in names),"published map hash binding")
        for revision in set(revisions):
            proc=subprocess.run(["git","merge-base","--is-ancestor",revision,published_map["published_ancestor_of"]],
                cwd=root,env={**os.environ,"GIT_NO_LAZY_FETCH":"1"},capture_output=True)
            check(proc.returncode==0,"mapped source is not a published ancestor")
    requests="".join(rev+":"+name+"\n" for rev,name in zip(revisions,names)).encode()
    proc=subprocess.run(["git","cat-file","--batch"],input=requests,capture_output=True,cwd=root,
                        env={**os.environ,"GIT_NO_LAZY_FETCH":"1"},check=True)
    cursor=0
    for name in names:
        end=proc.stdout.index(b"\n",cursor)
        header=proc.stdout[cursor:end].split()
        check(len(header)==3 and header[1]==b"blob","fixed source missing from local object database")
        size=int(header[2]);start=end+1
        check(sha(proc.stdout[start:start+size])==manifest["files"][name],"source differs from fixed Git object: "+name)
        cursor=start+size+1
    check(cursor==len(proc.stdout),"extra source object response")


def binding(values,manifest):
    for name,digest in values.items():
        relative=name if name.startswith("architecture_tlm/") else "architecture_tlm/cycle_v1/"+name
        check(manifest["files"].get(relative)==digest,"execution source mismatch: "+relative)
    required={"kernel.py","memory.py","contracts.py","gqa.py","attention.py","rng_protocol.py"}
    normalized={Path(name).name for name in values}
    check(required<=normalized,"missing execution source closure")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--results",type=Path,required=True)
    parser.add_argument("--execution",type=Path,required=True)
    parser.add_argument("--capture",type=Path,required=True)
    parser.add_argument("--artifacts-commit",help="also verify committed archive bytes, independent of checkout attributes")
    parser.add_argument("--published-source-map",type=Path,help="exact file/hash/ancestor mapping when original execution commits were not published")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError("fresh receipt path required")
    root=Path(__file__).resolve().parents[3]
    source=read(args.execution/"SOURCE_MANIFEST.json")
    source_archive=args.execution/"source_snapshot.tar.gz"
    check(sha(source_archive.read_bytes())==source["archive_sha256"],"source archive SHA")
    source_files=archive_files(source_archive)
    check({n:sha(b) for n,b in source_files.items()}==source["files"],"all source archive members")
    source_map=read(args.published_source_map) if args.published_source_map else None
    fixed_git_sources(source,root,source_map)
    public_archive=args.execution/"public_receipts.tar.gz"
    archive_receipt=read(args.execution/"PUBLIC_ARCHIVE_RECEIPT.json")
    check(sha(public_archive.read_bytes())==archive_receipt["sha256"],"public archive SHA")
    if args.artifacts_commit:
        for filename,expected in (("source_snapshot.tar.gz",source["archive_sha256"]),
                                  ("public_receipts.tar.gz",archive_receipt["sha256"])):
            blob=subprocess.check_output(["git","show",args.artifacts_commit+":work/amlink1219/116/gqa_validation_v1/"+filename],
                                         cwd=root,env={**os.environ,"GIT_NO_LAZY_FETCH":"1"})
            check(sha(blob)==expected,"committed archive bytes")
    files=archive_files(public_archive)
    check(len(files)==archive_receipt["files"]==11,"public archive count")
    declared=json.loads(files["PUBLIC_MANIFEST.json"])
    check(set(files)==set(declared["files"])|{"PUBLIC_MANIFEST.json"},"allowlisted archive membership")
    for name,blob in files.items():
        check((args.results/name).read_bytes()==blob,"local public artifact differs from archive")
        if name!="PUBLIC_MANIFEST.json": check(sha(blob)==declared["files"][name],"public member SHA")
    scheduler=(args.execution/"FIRST_TERMINAL_SCHEDULER.txt").read_text(encoding="utf-8")
    check("JobId=2782" in scheduler and "JobState=COMPLETED" in scheduler and "ExitCode=0:0" in scheduler,"first terminal scheduler")
    check("TRES=cpu=2,node=1,billing=2" in scheduler,"CPU allocation")
    terminal=read(args.results/"terminal.json")
    check(terminal==dict(job_id="2782",exit_code=0,gpu_requested=False),"terminal receipt")
    verified=read(args.results/"SOURCE_VERIFIED.json")
    check(verified["status"]=="pass" and verified["CUDA_VISIBLE_DEVICES"]=="","CPU GPU visibility")
    check(verified["files_verified"]==len(source_files)==74,"source count")
    for key in ("archive_sha256","core_commit","audit_commit"):
        check(verified[key]==source[key],"executed snapshot identity")
    capture=read(args.capture)
    fixture_sha=capture["artifact"]["sha256"]
    check(fixture_sha=="ee5722b38a1acb94daf4d09e49651c9a4610dbc9a9b0ac444b29bb1ef2280080","known capture identity")
    audit=read(args.results/"public_audit.json")
    verify_allowlist(audit)
    check(audit["passed"] and audit["fixture_sha256"]==fixture_sha,"independent server audit gate")
    check(audit["shape"]==dict(query_heads=7,context=64,d=64,dv=64),"real group shape")
    binding(audit["source_sha256"],source)
    identities={("exact",False),("exact",True),("pv",False),("pv",True),("winner",False),("rejection",False)}
    check(len(audit["cases"])==6 and {(c["mode"],c["tight"]) for c in audit["cases"]}==identities,"six independent cases")
    counters=dict(head_checks=0,output_values=0,trace_events=0,operations=0,actual_shared_reads_checked=0)
    cases=[]
    for case in audit["cases"]:
        check(case["config"]["samples"]==16 and case["config"]["mode"]==case["mode"],"audit S16 identity")
        check(case["cycle_event_equal"] and case["all_credits_returned"],"audit mode/credit gate")
        check(case["energy_status"]=="unknown","unknown PPA preserved")
        if case["tight"]:
            check(all(case["group_config"][k]==1 for k in ("k_slots","v_slots","operand_slots")),"single slot stress")
        check({r["mode"] for r in case["runs"]}=={"cycle","event"},"both modes executed")
        a,b=case["runs"]
        check(a["finish_ps"]==b["finish_ps"] and a["operations"]==b["operations"],"mode totals")
        numeric=case["numeric"]
        check(numeric["K_unique_rows"]==64 and numeric["K_bytes"]==16384,"shared K bytes")
        check(numeric["V_bytes"]==numeric["V_unique_rows"]*256,"shared V bytes")
        check(numeric["actual_shared_reads_checked"]==64+numeric["V_unique_rows"],"actual payload check coverage")
        check(len(numeric["heads"])==7 and {h["head"] for h in numeric["heads"]}==set(range(7)),"seven scalar head checks")
        for head in numeric["heads"]:
            check(head["values"]==64 and head["bit_equal"] and head["max_absolute_error"]==0,"scalar bit equality")
            check(head["output_sha256"]==head["oracle_sha256"],"independent output hash")
            check((head["native_report_sha256"] is None)==(case["mode"]=="exact"),"native use scope")
            counters["head_checks"]+=1;counters["output_values"]+=head["values"]
        trace=case["trace_check"]
        check(all(trace[k] for k in ("all_actions_recounted","old_state_capacity_constraints","completion_and_bank_ports")),"server independent trace gates")
        check(trace["operations"]==a["operations"],"trace operation count")
        counters["trace_events"]+=trace["events"];counters["operations"]+=trace["operations"]
        counters["actual_shared_reads_checked"]+=numeric["actual_shared_reads_checked"]
        cases.append(dict(mode=case["mode"],tight=case["tight"],finish_ps=a["finish_ps"],operations=a["operations"],
                          K_bytes=numeric["K_bytes"],V_bytes=numeric["V_bytes"]))
    cli=[]
    for name in ("exact","exact_narrow","pv","winner","rejection"):
        case=read(args.results/(name+".json"));verify_allowlist(case)
        check(case["status"]=="passed" and case["fixture_sha256"]==fixture_sha,"CLI fixture/gate")
        binding(case["source"]["source_sha256"],source)
        check(case["query_heads"]==7 and case["KV_heads"]==1,"CLI group shape")
        check(case["mode_equivalence"]["checked"] and case["mode_equivalence"]["equal"],"CLI mode equality")
        check({r["samples"] for r in case["query_configs"]}=={32},"CLI S32 separated from S16 audit")
        check(case["shared"]["K_union_count"]==64 and case["actions"]["K_read_bytes"]==16384,"CLI shared K")
        check(case["actions"]["V_read_bytes"]==case["shared"]["V_union_count"]*256,"CLI shared V")
        for head in case["queries"]:
            value=head["numeric_validation"]
            check(value["max_absolute_error"]<=value["absolute_tolerance"],"CLI reported numeric tolerance")
        check(all(b["initial"]==b["final"] for b in case["storage"].values()),"CLI credit return")
        cli.append(dict(name=name,latency_ns=case["latency_ns"],operations=case["operations"]))
    report=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),passed=True,job_id="2782",source_files=74,
        public_archive_files=11,public_members_with_manifest_sha=10,source_archive_sha256=source["archive_sha256"],
        public_archive_sha256=archive_receipt["sha256"],fixture_sha256=fixture_sha,
        source_git_objects_verified=True,core_commit=source["core_commit"],audit_commit=source["audit_commit"],
        source_binding="exact published ancestor blobs" if source_map else "original execution commits",
        published_source_map_sha256=sha(args.published_source_map.read_bytes()) if source_map else None,
        artifacts_commit=args.artifacts_commit,committed_archive_bytes_verified=bool(args.artifacts_commit),
        independent_server_cases=6,independent_server_executions=12,independent_server_checks=counters,
        independent_cases=cases,production_cli_cases=cli,
        privacy_check="Only allowlisted counts/configuration/hash/error metrics were retrieved; private tensors and raw traces remain on server",
        scope="Offline authentication of server-executed independent scalar and trace audits; no local private-data replay. S16 independent cases and S32 production checks are distinct. Sampled math is conditional on native retained indices, not a distribution/IID or full-model/physical claim.")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(passed=True,**counters)))


if __name__=="__main__": main()
