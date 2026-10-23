"""Independent private-fixture GQA audit; public output contains no tensors.

Run inside the approved personal compute allocation. Full addressed traces and
the source fixture remain under --private-trace-dir / their existing server
location. Only --output is intended for retrieval. Never export exception text,
Q/K/V, output arrays, histogram entries, or sample indices in the public receipt.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

from architecture_tlm.cycle_v1.attention import AttentionConfig
from architecture_tlm.cycle_v1.gqa import GQAConfig,make_gqa
from architecture_tlm.cycle_v1.audit.gqa_oracles import scalar_query
from architecture_tlm.cycle_v1.audit.scalar_oracles import f32
from architecture_tlm.cycle_v1.audit.verify_matrix_artifacts import trace_audit


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def pack(row):
    return struct.pack("<"+"f"*len(row),*row)


def check(condition,label):
    if not condition:
        raise AssertionError(label)


def trace_contract(kernel,result):
    credits={n:b.initial for n,b in kernel.buffer_specs.items()}
    low,high=dict(credits),dict(credits)
    changes={}
    for event in result.trace:
        if event["kind"] not in ("accept","complete"):
            continue
        sign,field=(-1,"inputs") if event["kind"]=="accept" else (1,"outputs")
        delta=changes.setdefault(event["time_ps"],Counter())
        for name,count in event.get(field,{}).items():
            delta[name]+=sign*count
    for _,delta in sorted(changes.items()):
        for name,count in delta.items():
            credits[name]+=count
            low[name]=min(low[name],credits[name]);high[name]=max(high[name],credits[name])
    buffers={}
    for name,spec in kernel.buffer_specs.items():
        check(credits[name]==spec.initial,"credit final")
        check(0<=low[name]<=high[name]<=spec.capacity,"credit bounds")
        buffers[name]={**asdict(spec),"minimum_tokens_or_credits":low[name],
                       "maximum_tokens_or_credits":high[name],"final":credits[name]}
        if spec.initial==spec.capacity:
            buffers[name]["peak_reserved_units"]=spec.capacity-low[name]
    return dict(resources=[asdict(s) for s in kernel.resources.values()],
        memory_ports=[{k:v for k,v in asdict(s).items() if k!="initial_data"} for s in kernel.memory_ports.values()],buffers=buffers)


def shared_checks(fixture,kernel,state,result,mode):
    expected_k=sorted({i for query in fixture["queries"] for i in query["candidate_ids"]})
    expected_v=set()
    checks=[]
    frames=commands=0
    for h,(query,actual) in enumerate(zip(fixture["queries"],state["queries"])):
        counts=None if mode=="exact" else Counter(actual["physical_indices"])
        if counts is not None:
            check(dict(counts)==actual["histogram"],"histogram multiplicity")
            check(sum(counts.values())==16,"retained sample count")
            check(set(counts)<=set(query["candidate_ids"]),"sampled candidate identity")
        expected_v.update(query["candidate_ids"] if counts is None else counts)
        oracle=scalar_query(fixture,query,physical_counts=counts)
        current=actual["output"]
        check(pack(current)==pack(oracle),"independent scalar FP32 weighted V")
        raw=kernel.read_memory("sram",actual["output_address"],actual["output_bytes"])
        check(raw==pack(oracle),"actual output memory")
        logits=[]
        import math
        q=list(map(f32,query["q"]))
        for token in query["candidate_ids"]:
            logits.append(f32(math.fsum(a*f32(b) for a,b in zip(q,fixture["k"][token]))/math.sqrt(len(q))))
        check(pack(logits)==pack(actual["logits"]),"independent scalar QK")
        checks.append(dict(head=h,values=len(current),bit_equal=True,max_absolute_error=max(abs(a-b) for a,b in zip(current,oracle)),
            output_sha256=sha(pack(current)),oracle_sha256=sha(pack(oracle)),logits_sha256=sha(pack(logits)),
            unique_V=len(query["candidate_ids"]) if counts is None else len(counts),
            native_report_sha256=sha(canonical(actual["native_random"])) if actual["native_random"] is not None else None))
        native=actual["native_random"]
        if mode!="exact":
            check(native is not None and native["physical_entropy"] is False,"native scope")
            frames+=sum(r["kind"]=="frame" for r in native["receipts"])
            commands+=sum(r["kind"]=="command" for r in native["receipts"])
    check(frames==result.actions.get("native_rng_request",0),"native requests conserved")
    check(commands==result.actions.get("native_rng_command",0),"native commands conserved")
    check(state["K_union"]==expected_k,"K union")
    check(state["V_union"]==sorted(expected_v),"V union")
    checked_reads=0
    for kind,field in (("K","k"),("V","v")):
        ids=state[kind+"_read_ids"]
        check(sorted(ids)==state[kind+"_union"],"union read identity")
        width=len(fixture[field][0])*4
        region=next(r for r in state["address_regions"] if r["name"]==kind)
        check(result.actions[kind+"_read_bytes"]==len(ids)*width,"physical unique traffic")
        for token,read in ids.items():
            op=kernel.operations[read]
            check(op.memory.address==region["address"]+token*width,"shared read address")
            check(kernel.memory_reads[read]==pack(list(map(f32,fixture[field][token]))),"actual source bytes")
            release=state[kind+"_release_ids"][token]
            consumers=state[kind+"_consumers"][token]
            check(set(kernel.operations[release].deps)==set(consumers),"all-consumer lifetime")
            for consumer in consumers:
                check(result.completion_ps[read]<result.accepted_ps[consumer],"read before MAC")
                check(result.completion_ps[consumer]<result.accepted_ps[release],"MAC before slot release")
            checked_reads+=1
    return dict(heads=checks,actual_shared_reads_checked=checked_reads,K_unique_rows=len(expected_k),V_unique_rows=len(expected_v),
                K_bytes=len(expected_k)*len(fixture["k"][0])*4,V_bytes=len(expected_v)*len(fixture["v"][0])*4)


def run_case(fixture,mode,tight,private):
    config=AttentionConfig(mode=mode,samples=16)
    gc=GQAConfig(k_slots=1,v_slots=1,operand_slots=1) if tight else GQAConfig()
    records=[]
    before=None
    state_before=None
    for execution in ("cycle","event"):
        start=time.perf_counter()
        kernel,state=make_gqa(fixture,config,gc,memory_window=1 if tight else 4,memory_banks=1 if tight else 4)
        result=kernel.run(execution)
        payload=result.equivalence_payload()
        if before is not None:
            check(before==payload,"cycle event full payload")
            check(state_before==state,"cycle event group state")
        before=payload;state_before=state
        numeric=shared_checks(fixture,kernel,state,result,mode)
        records.append(dict(mode=execution,finish_ps=result.finish_ps,operations=len(result.accepted_ps),
                            wall_seconds=time.perf_counter()-start))
    safe=dict(payload,memory_reads={n:dict(bytes=len(v),sha256=sha(v)) for n,v in result.memory_reads.items()})
    blob=canonical(safe);compressed=gzip.compress(blob,mtime=0)
    private.mkdir(parents=True,exist_ok=False)
    (private/"trace.json.gz").write_bytes(compressed)
    # Native transcript and index/history arrays remain in this private folder.
    (private/"state.json").write_bytes(canonical(state))
    artifact=dict(path="trace.json.gz",bytes=len(compressed),sha256=sha(compressed),uncompressed_sha256=sha(blob))
    summary=dict(operator="gqa",trace_artifact=artifact,trace_events=len(result.trace),operations=len(result.accepted_ps),
        actions=result.actions,finish_ps=result.finish_ps,resource_peak=result.resource_peak,resource_stats=result.resource_stats)
    contracts=trace_contract(kernel,result)
    (private/"contracts.json").write_bytes(canonical(contracts))
    trace_report=trace_audit(private,summary,contracts,None)
    return dict(mode=mode,tight=tight,config=asdict(config),group_config=asdict(gc),runs=records,
        cycle_event_equal=True,numeric=numeric,trace_check=trace_report,private_trace=artifact,
        group_state_sha256=sha(canonical(state)),payload_sha256=sha(blob),all_credits_returned=True,
        actions=result.actions,energy_status="unknown",hardware_scope="configured uncharacterized cycle model")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--fixture",type=Path,required=True)
    parser.add_argument("--expected-fixture-sha256",required=True)
    parser.add_argument("--private-trace-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.private_trace_dir.exists():
        raise FileExistsError("fresh result paths required")
    report=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),passed=False,cases=[],
        scope="Independent scalar QK and FP32 weighted-V checks on a real preprojected GQA group. Sampled modes condition on observed native indices; no distribution/IID, full-attention, full-model, PPL or PPA claim.",
        export_policy="No input/output tensors, sample indices, histogram entries or exception text in this public receipt; traces/state remain in the private server directory.")
    status=1
    try:
        blob=args.fixture.read_bytes()
        check(sha(blob)==args.expected_fixture_sha256,"fixture hash")
        fixture=json.loads(blob)
        report["fixture_sha256"]=sha(blob)
        report["shape"]=dict(query_heads=len(fixture["queries"]),context=len(fixture["k"]),
                            d=len(fixture["k"][0]),dv=len(fixture["v"][0]))
        root=Path(__file__).resolve().parents[3]
        paths=list((root/"architecture_tlm/cycle_v1").glob("*.py"))
        paths.extend(root/"architecture_tlm"/p for p in ("random_service/__init__.py","random_service/model.py",
            "random_service/backends.py","random_service/service.py","random_service/shared64_mapping.json","unified_v6/rng_integrated.py"))
        paths.extend(Path(__file__).resolve().parent/p for p in ("verify_gqa_fixture.py","gqa_oracles.py","scalar_oracles.py","verify_matrix_artifacts.py"))
        report["source_sha256"]={p.relative_to(root).as_posix():sha(p.read_bytes()) for p in sorted(paths)}
        args.private_trace_dir.mkdir(parents=True)
        for mode,tight in (("exact",False),("exact",True),("pv",False),("pv",True),("winner",False),("rejection",False)):
            result=run_case(fixture,mode,tight,args.private_trace_dir/(mode+("_tight" if tight else "_default")))
            report["cases"].append(result)
            print(json.dumps(dict(case=mode,tight=tight,passed=True)),flush=True)
        report["passed"]=True
        status=0
    except Exception as error:
        # Deliberately suppress message/traceback: an implementation exception
        # could include private values. Debug in place if this receipt fails.
        report["failure_exception_type"]=type(error).__name__
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(passed=report["passed"],completed_cases=len(report["cases"]))))
    return status


if __name__=="__main__":
    sys.exit(main())
