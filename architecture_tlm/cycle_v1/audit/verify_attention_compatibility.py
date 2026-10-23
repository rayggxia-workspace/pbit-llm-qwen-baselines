"""Rerun selected pre-GQA cases against immutable v5 full-payload digests.

This is an execution regression check, not an independent numerical oracle.
It never modifies the old summaries, fixtures or their artifact manifests.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

from architecture_tlm.cycle_v1.attention import AttentionConfig,build_attention,make_kernel


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")


def safe_payload(result):
    payload=result.equivalence_payload()
    payload["memory_reads"]={name:{"bytes":len(blob),"sha256":digest(blob)} for name,blob in result.memory_reads.items()}
    return payload


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--results",type=Path,required=True)
    parser.add_argument("--fixture",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new receipt path")
    bundle=json.loads(args.fixture.read_text(encoding="utf-8"))
    layer=bundle["provenance"]["layer"]
    fixture=dict(bundle["attention"],provenance=bundle["provenance"])
    cases=[]
    for mode in ("exact","pv","winner","rejection"):
        seed=0 if mode=="exact" else 2
        name=f"qwen_layer{layer}_{mode}_N128_S32_seed{seed}"
        summary_path=args.results/name/"summary.json"
        summary_bytes=summary_path.read_bytes()
        summary=json.loads(summary_bytes)
        assert summary["fixture_sha256"]==digest(args.fixture.read_bytes())
        config=AttentionConfig(**summary["config"])
        records=[]
        for execution in ("cycle","event"):
            k=make_kernel(config)
            state=build_attention(k,fixture,config)
            result=k.run(execution)
            current=digest(canonical(safe_payload(result)))
            assert current==summary["equivalence_payload_sha256"],(name,execution,current)
            assert state["output"]==summary["output"]
            assert result.buffer_final=={n:b.initial for n,b in k.buffer_specs.items()}
            for field in ("local_indices","physical_indices","histogram"):
                if field in summary.get("sampler",{}):
                    expected=summary["sampler"][field]
                    if field=="histogram": expected={int(k):v for k,v in expected.items()}
                    assert state[field]==expected
            records.append(dict(mode=execution,payload_sha256=current,operations=len(result.accepted_ps),
                finish_ps=result.finish_ps,full_v5_payload_equal=True,output_equal=True,credits_returned=True))
        cases.append(dict(name=name,summary_sha256=digest(summary_bytes),runs=records))
    root=Path(__file__).resolve().parents[3]
    paths=list((root/"architecture_tlm/cycle_v1").glob("*.py"))
    paths.extend(root/"architecture_tlm"/p for p in ("random_service/__init__.py","random_service/model.py",
                 "random_service/backends.py","random_service/service.py","random_service/shared64_mapping.json",
                 "unified_v6/rng_integrated.py"))
    paths.append(Path(__file__).resolve())
    report=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
        scope="Selected unchanged default Attention execution compared to immutable pre-GQA v5 full-payload hashes; not a repeated 68-case matrix or independent math check",
        git_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip(),
        source_sha256={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in sorted(paths)},
        fixture_sha256=digest(args.fixture.read_bytes()),cases=cases,passed=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(passed=True,cases=len(cases),executions=2*len(cases),output=str(args.output))))


if __name__=="__main__":
    main()
