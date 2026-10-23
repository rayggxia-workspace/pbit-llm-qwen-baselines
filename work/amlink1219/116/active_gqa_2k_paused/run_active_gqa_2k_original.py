"""One authorized local synthetic 2K candidate run, with same-process independent audit."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
SNAPSHOT=ROOT.parent/'gqa-active-snapshot'
OUT=ROOT/'work/amlink1219/116/active_gqa_2k_local'
CANDIDATE=ROOT/'work/amlink1219/116/active_gqa_probe/active_memory_candidate.py'


def sha(value): return hashlib.sha256(value).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def write(path,value): path.write_bytes(canonical(value)+b'\n')


def verified_source():
    manifest=json.loads((ROOT/'work/amlink1219/116/gqa_validation_v1/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():
        assert sha((SNAPSHOT/name).read_bytes())==expected, name
    assert sha(CANDIDATE.read_bytes())=='7e4c9534e40b493956a2ae94b6b6b1cd97e4a0d6052e6aff75637828941d4296'
    return manifest


def worker():
    manifest=verified_source()
    sys.path.insert(0,str(SNAPSHOT))
    from architecture_tlm.cycle_v1.attention import AttentionConfig
    from architecture_tlm.cycle_v1.gqa import GQAConfig,default_resources,default_buffers,build_gqa
    from architecture_tlm.cycle_v1.contracts import Clock
    from architecture_tlm.cycle_v1.memory import MemoryPort
    from architecture_tlm.cycle_v1.audit.verify_gqa_fixture import shared_checks,trace_contract
    from architecture_tlm.cycle_v1.audit.verify_matrix_artifacts import trace_audit
    spec=importlib.util.spec_from_file_location('public_active_candidate_2k',CANDIDATE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    row=lambda n,p:[math.sin(i*.37+p)*.17 for i in range(n)]
    fixture=dict(provenance=dict(kind='synthetic_sine_GQA',heads=7,context=2048,d=64,dv=64,
        generator='sin(i*0.37+phase)*0.17; q phase=head*0.21; k phase=token*0.13; v phase=token*0.27',
        candidates='all physical IDs 0..2047 for each query',model=None,seed=0),
        queries=[dict(q=row(64,h*.21),candidate_ids=list(range(2048))) for h in range(7)],
        k=[row(64,i*.13) for i in range(2048)],v=[row(64,i*.27) for i in range(2048)])
    raw=OUT/'raw';raw.mkdir(exist_ok=False)
    write(raw/'fixture.json',fixture)
    c=AttentionConfig(mode='exact',samples=32,seed=0,capacity=2048,score_capacity_bytes=65536)
    gc=GQAConfig(k_slots=2,v_slots=2,operand_slots=2,query_state_capacity_bytes=1048576,metadata_capacity_bytes=65536)
    begin=time.perf_counter()
    kernel=module.ActiveMemoryKernel(default_resources(c),default_buffers(fixture,c,gc),[
        MemoryPort('dram',Clock('dram',12500),latency_cycles=4,window=4,banks=4,strict_reads=True),
        MemoryPort('sram',Clock('sram',12500),latency_cycles=2,window=4,banks=4,strict_reads=True)])
    state=build_gqa(kernel,fixture,c,gc)
    build_seconds=time.perf_counter()-begin
    write(OUT/'BUILT.json',dict(utc=datetime.now(timezone.utc).isoformat(),build_seconds=build_seconds,initial_operations=len(kernel.operations)))
    begin=time.perf_counter();result=kernel.run('event');run_seconds=time.perf_counter()-begin
    write(OUT/'EXECUTED.json',dict(utc=datetime.now(timezone.utc).isoformat(),run_seconds=run_seconds,
        finish_ps=result.finish_ps,operations=len(result.accepted_ps),trace_events=len(result.trace),audit_pending=True))
    assert result.buffer_final=={name:spec.initial for name,spec in kernel.buffer_specs.items()}
    assert set(result.accepted_ps)==set(result.completion_ps)==set(kernel.operations)
    for ident,op in kernel.operations.items():
        accepted=result.accepted_ps[ident]; clock=kernel.clock_for(op.resource)
        assert accepted>=op.earliest_ps and accepted>kernel._born_ps[ident]
        for dep in op.deps:
            completed=result.completion_ps[dep]
            if op.cdc_cycles and kernel.clock_for(kernel.operations[dep].resource)!=clock:
                assert accepted>=clock.next_edge(completed,strict=True)+(op.cdc_cycles-1)*clock.period_ps
            else:
                assert accepted>completed
    before=time.perf_counter()
    numeric=shared_checks(fixture,kernel,state,result,'exact')
    assert len(numeric['heads'])==7 and all(h['values']==64 for h in numeric['heads'])
    assert numeric['actual_shared_reads_checked']==4096
    assert numeric['K_unique_rows']==numeric['V_unique_rows']==2048
    assert numeric['K_bytes']==numeric['V_bytes']==524288
    contracts=trace_contract(kernel,result)
    payload=result.equivalence_payload()
    safe=dict(payload,memory_reads={name:dict(bytes=len(value),sha256=sha(value)) for name,value in result.memory_reads.items()})
    uncompressed=hashlib.sha256()
    with (raw/'trace.json.gz').open('wb') as output:
        with gzip.GzipFile(fileobj=output,mode='wb',mtime=0) as compressed:
            for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(safe):
                block=chunk.encode('utf-8');uncompressed.update(block);compressed.write(block)
    write(raw/'state.json',state);write(raw/'contracts.json',contracts)
    compressed=(raw/'trace.json.gz').read_bytes()
    artifact=dict(path='trace.json.gz',bytes=len(compressed),sha256=sha(compressed),uncompressed_sha256=uncompressed.hexdigest())
    write(OUT/'ARCHIVED.json',dict(utc=datetime.now(timezone.utc).isoformat(),trace_artifact=artifact,scalar_checks_passed=True))
    audit_summary=dict(operator='gqa',trace_artifact=artifact,trace_events=len(result.trace),operations=len(result.accepted_ps),
        actions=result.actions,finish_ps=result.finish_ps,resource_peak=result.resource_peak,resource_stats=result.resource_stats)
    trace_review=trace_audit(raw,audit_summary,contracts,None)
    report=dict(status='pass',scope='local synthetic candidate backend evidence; not real model/PPL/default adoption/hardware PPA',
        candidate_adopted=False,event_only=True,cycle_event_checked=False,
        source_manifest_sha256=sha((ROOT/'work/amlink1219/116/gqa_validation_v1/SOURCE_MANIFEST.json').read_bytes()),
        baseline_commit=manifest['core_commit'],audit_commit=manifest['audit_commit'],
        public_candidate_commit='d944081a22dc346a3a50d505633e5d15c857ba78',candidate_sha256=sha(CANDIDATE.read_bytes()),
        wrapper_sha256=sha(Path(__file__).read_bytes()),fixture_sha256=sha((raw/'fixture.json').read_bytes()),
        fixture_provenance=fixture['provenance'],attention_config=asdict(c),group_config=asdict(gc),
        memory=dict(window=4,banks=4,dram_latency_cycles=4,sram_latency_cycles=2),
        build_seconds=build_seconds,run_seconds=run_seconds,audit_and_archive_seconds=time.perf_counter()-before,
        finish_ps=result.finish_ps,latency_ns=result.finish_ps/1000,operations=len(result.accepted_ps),visited_edges=result.steps,
        numeric=numeric,trace_review=trace_review,all_credits_returned=True,storage=contracts['buffers'],actions=result.actions,
        payload_sha256=uncompressed.hexdigest(),state_sha256=sha(canonical(state)),area=None,power=None,energy=None,
        retained_artifacts={p.name:dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in raw.iterdir()})
    write(OUT/'SUMMARY.json',report)
    print(json.dumps(dict(status='pass',run_seconds=run_seconds,audit_seconds=report['audit_and_archive_seconds'],
        operations=report['operations'],finish_ps=result.finish_ps,scalar_heads=len(numeric['heads']))),flush=True)


def main():
    if datetime.now(timezone.utc)>=datetime(2026,10,22,19,43,tzinfo=timezone.utc):
        raise RuntimeError('missed 19:43 UTC start gate; no run permitted')
    manifest=verified_source()
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'.gitignore').write_text('/raw/\n',encoding='utf-8',newline='\n')
    write(OUT/'START.json',dict(utc=datetime.now(timezone.utc).isoformat(),hard_timeout_seconds=1200,
        core_commit=manifest['core_commit'],audit_commit=manifest['audit_commit'],candidate_sha256=sha(CANDIDATE.read_bytes()),
        wrapper_sha256=sha(Path(__file__).read_bytes()),execution='one local child; event only; synthetic N2048 H7 D64',
        full_trace_policy='raw/ retained locally and excluded from Git'))
    begin=time.perf_counter()
    try:
        with (OUT/'stdout.txt').open('wb') as stdout,(OUT/'stderr.txt').open('wb') as stderr:
            result=subprocess.run([sys.executable,'-P','-X','utf8',str(Path(__file__).resolve()),'--worker'],
                stdout=stdout,stderr=stderr,timeout=1200)
        status=dict(status='completed' if result.returncode==0 else 'failed',exit_code=result.returncode)
    except subprocess.TimeoutExpired:
        status=dict(status='timeout',hard_limit_seconds=1200)
    status.update(utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-begin)
    write(OUT/'TERMINAL.json',status);print(json.dumps(status),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    worker() if args.worker else main()
