"""Run a shared-KV group with strict cycle/event, payload and capacity gates."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path
import struct
import time

from .attention import AttentionConfig
from .gqa import GQAConfig, make_gqa, _prepare
from .reporting import timeline_summary, write_inspector
from .run import canonical, digest, json_write, source_provenance, _safe_payload, _buffer_accounting, _numeric


def synthetic_gqa(heads=2):
    if type(heads) is not int or heads<1: raise ValueError('positive query head count required')
    row=lambda n,p:[math.sin(i*.37+p)*.17 for i in range(n)]
    return dict(provenance={'kind':'deterministic_synthetic_GQA','version':1,'KV_heads':1},
        queries=[dict(q=row(16,h*.21),candidate_ids=[10,2,1,11,3] if h%2==0 else [3,2,8,10]) for h in range(heads)],
        k=[row(16,i*.13) for i in range(12)],v=[row(12,i*.27) for i in range(12)])


def public_report(summary):
    """Allowlisted non-payload receipt for private server-side activation runs.

    Do not recursively copy arbitrary fixture provenance, traces, native words,
    sampled indices, score/output arrays or histogram contents into this file.
    """
    shared=summary['shared']
    return dict(schema='cycle_v1.gqa.public.1',status=summary['status'],source=summary['source'],
        fixture_sha256=summary['fixture_sha256'],query_configs=summary['query_configs'],group_config=summary['group_config'],
        query_heads=summary['query_heads'],KV_heads=summary['KV_heads'],
        finish_ps=summary['finish_ps'],latency_ns=summary['latency_ns'],operations=summary['operations'],
        mode_equivalence=summary['mode_equivalence'],execution_modes=summary['execution_modes'],
        actions=summary['actions'],storage=summary['storage'],resource_peak=summary['resource_peak'],
        resource_stats=summary['resource_stats'],equivalence_payload_sha256=summary['equivalence_payload_sha256'],
        shared=dict(K_union_count=len(shared['K_union']),V_union_count=len(shared['V_union']),
            K_union_sha256=digest(canonical(shared['K_union'])),V_union_sha256=digest(canonical(shared['V_union'])),
            K_capacity_bytes=shared['K_capacity_bytes'],V_capacity_bytes=shared['V_capacity_bytes'],
            operand_capacity_bytes=shared['operand_capacity_bytes'],metadata_bytes=shared['metadata_bytes'],
            query_state_capacity_bytes=shared['query_state_capacity_bytes']),
        queries=[dict(head=q['head'],numeric_validation=q['numeric_validation'],output_sha256=q['output_sha256'],
            complete_ps=q['complete_ps'],retained_samples=len(q['local_indices']),unique_V_count=len(q['physical_weights']),
            histogram_sum=sum(q['histogram'].values()),proposals=q['proposals'],source_frames=q['source_frames'],
            source_waves=q['source_waves'],native_report_sha256=digest(canonical(q['native_random']))) for q in summary['queries']],
        source_instances=summary['model_boundary']['source_instances'],
        boundary='precompiled K candidate plan; timed V union scan/compact after all head histograms; finite row/operand/metadata credits; per-head source state',
        privacy='raw fixture, logits, output arrays, probabilities, indices, histogram maps, native reports and full trace stay in private execution directory',
        physical_status=summary['physical_status'])


def run_gqa_case(fixture,attention_configs,group_config,output,*,fixture_sha256=None,
                 memory_latency=4,memory_window=4,memory_banks=4,write_public_report=False,compare_modes=True):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    source=source_provenance()
    gc,configs,data=_prepare(fixture,attention_configs,group_config)
    fixture_hash=fixture_sha256 or digest(canonical(fixture))
    start=dict(schema='cycle_v1.gqa.start.1',source=source,fixture_sha256=fixture_hash,
        fixture_provenance=fixture.get('provenance',{}),query_configs=[asdict(c) for c in configs],
        group_config=asdict(gc),memory=dict(latency_cycles=memory_latency,window=memory_window,banks=memory_banks),
        created_utc=datetime.now(timezone.utc).isoformat())
    json_write(output/'START.json',start)
    try:
        runs=[]
        for mode in (('cycle','event') if compare_modes else ('event',)):
            before=time.perf_counter()
            k,state=make_gqa(fixture,configs,gc,memory_latency=memory_latency,
                             memory_window=memory_window,memory_banks=memory_banks)
            result=k.run(mode)
            wall=time.perf_counter()-before
            if result.buffer_final!={name:spec.initial for name,spec in k.buffer_specs.items()}:
                raise AssertionError('GQA query or cache credit leaked')
            for query in state['queries']:
                expected=struct.pack('<'+'f'*len(query['output']),*query['output'])
                if k.read_memory('sram',query['output_address'],query['output_bytes'])!=expected:
                    raise AssertionError('GQA head output bytes did not commit')
                if query['complete_ps']>result.finish_ps:
                    raise AssertionError('GQA result finished before a query write')
            runs.append((k,state,result,wall))
        k,state,result,wall=runs[-1]
        if compare_modes and (runs[0][2].equivalence_payload()!=result.equivalence_payload() or runs[0][1]!=state):
            raise AssertionError('GQA cycle/event full payload or head state mismatch')
        d,dv=len(data[0][1]),len(data[0][3][0])
        if result.actions['K_read_bytes']!=len(state['K_union'])*d*4 or result.actions['V_read_bytes']!=len(state['V_union'])*dv*4:
            raise AssertionError('physical shared read byte accounting mismatch')
        if result.actions['memory.dram.read_requests']!=len(state['K_union'])+len(state['V_union']):
            raise AssertionError('extra/missing physical DRAM request')
        for kind in ('K','V'):
            for token,release in state[kind+'_release_ids'].items():
                if any(result.accepted_ps[release]<=result.completion_ps[consumer]
                       for consumer in state[kind+'_consumers'][token]):
                    raise AssertionError('shared row credit released before every consumer completed')
        heads=[]
        for h,query in enumerate(state['queries']):
            numeric=_numeric('attention',data[h][0],configs[h],query)
            heads.append(dict(head=h,output=query['output'],output_address=query['output_address'],
                output_bytes=query['output_bytes'],complete_ps=query['complete_ps'],
                output_sha256=digest(k.read_memory('sram',query['output_address'],query['output_bytes'])),
                logits=query['logits'],local_indices=query['local_indices'],physical_indices=query['physical_indices'],
                histogram=query['histogram'],physical_weights=state['physical_weight_maps'][h],
                local_state_bytes=query['local_state_bytes'],numeric_validation=numeric,
                proposals=query['proposals'],source_frames=query['source_frames'],source_waves=query['source_waves'],
                native_random=query.get('native_random'),sampler_frames=query['frames']))
        details,rows=timeline_summary(k,result)
        payload=_safe_payload(result)
        specs=dict(resources=[asdict(r) for r in k.resources.values()],
                   memory_ports=[{key:value for key,value in asdict(m).items() if key!='initial_data'} for m in k.memory_ports.values()],
                   buffers=_buffer_accounting(k,result.trace))
        shared={key:state[key] for key in ('K_union','V_union','K_addresses','V_addresses',
            'K_read_ids','V_read_ids','K_consumers','V_consumers','K_release_ids','V_release_ids',
            'K_capacity_bytes','V_capacity_bytes','operand_capacity_bytes','metadata_bytes',
            'query_state_capacity_bytes','address_regions','V_barrier_id','V_union_ready_id')}
        summary=dict(schema='cycle_v1.gqa.execution.1',operator='gqa_group',status='passed',
            source=source,fixture_sha256=fixture_hash,fixture_provenance=fixture.get('provenance',{}),
            query_configs=[asdict(c) for c in configs],group_config=asdict(gc),
            query_heads=len(heads),KV_heads=1,queries=heads,shared=shared,
            finish_ps=result.finish_ps,latency_ns=result.finish_ps/1000,
            operations=len(result.accepted_ps),actions=result.actions,storage=specs['buffers'],
            resource_peak=result.resource_peak,resource_stats=result.resource_stats,
            mode_equivalence=dict(checked=compare_modes,equal=True if compare_modes else None,
                fields='full trace, accept/complete, actual returned bytes, actions, final buffers/resources, all per-head state'),
            execution_modes={r.mode:dict(visited_edges=r.steps,wall_seconds=t) for _,_,r,t in runs},
            equivalence_payload_sha256=digest(canonical(payload)),timing_details=details,
            model_boundary=state['provenance'],
            numeric_scope='per-query exact weighted-V or retained-sample trajectory; no PPL or full-model accuracy',
            energy=dict(status='unknown',accounting='semantic bytes and memory.* bytes overlap; never add as separate energy'),
            physical_status='configured uncharacterized cache/compute/clock contract; not STA, PPA or optimal streaming schedule')
        trace=canonical(dict(trace=result.trace,accepted_ps=result.accepted_ps,
                             completion_ps=result.completion_ps,memory_reads=payload['memory_reads']))
        compressed=gzip.compress(trace,mtime=0)
        (output/'trace.json.gz').write_bytes(compressed)
        summary['trace_artifact']=dict(path='trace.json.gz',sha256=digest(compressed),uncompressed_sha256=digest(trace))
        json_write(output/'contracts.json',specs)
        json_write(output/'summary.json',summary)
        write_inspector(output/'timeline.html',dict(operator='gqa_group',finish_ps=result.finish_ps,
                        model_boundary=state['provenance']),rows)
        if write_public_report:
            receipt=public_report(summary)
            receipt['private_artifact_hashes']={p.name:digest(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}
            json_write(output/'public_report.json',receipt)
        json_write(output/'MANIFEST.json',{p.name:digest(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()})
        return summary
    except Exception as exc:
        json_write(output/'FAILED.json',dict(type=type(exc).__name__,message=str(exc),source=source,fixture_sha256=fixture_hash))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--heads',type=int,default=2,help='synthetic fixture only')
    parser.add_argument('--mode',choices=('exact','pv','winner','rejection'),default='exact')
    parser.add_argument('--samples',type=int,default=32)
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--attention-config',type=Path,help='AttentionConfig overrides, or per-query override list')
    parser.add_argument('--k-slots',type=int,default=2)
    parser.add_argument('--v-slots',type=int,default=2)
    parser.add_argument('--cache-bytes-per-cycle',type=int,default=64)
    parser.add_argument('--query-state-capacity',type=int,default=1048576)
    parser.add_argument('--operand-slots',type=int,default=2)
    parser.add_argument('--metadata-capacity',type=int,default=65536)
    parser.add_argument('--union-scan-lanes',type=int,default=16)
    parser.add_argument('--public-report',action='store_true',help='also write allowlisted metrics/hashes; keep raw output and trace in execution directory')
    parser.add_argument('--event-only',action='store_true',help='explicitly skip cycle/event comparison; receipt records checked=false')
    parser.add_argument('--memory-window',type=int,default=4)
    parser.add_argument('--memory-banks',type=int,default=4)
    parser.add_argument('--memory-latency',type=int,default=4)
    args=parser.parse_args()
    fixture=json.loads(args.fixture.read_text(encoding='utf-8')) if args.fixture else synthetic_gqa(args.heads)
    base=dict(mode=args.mode,samples=args.samples,seed=args.seed)
    override=json.loads(args.attention_config.read_text(encoding='utf-8')) if args.attention_config else {}
    configs=([AttentionConfig(**(base|v)) for v in override] if isinstance(override,list)
             else AttentionConfig(**(base|override)))
    gc=GQAConfig(k_slots=args.k_slots,v_slots=args.v_slots,cache_bytes_per_cycle=args.cache_bytes_per_cycle,
                 query_state_capacity_bytes=args.query_state_capacity,operand_slots=args.operand_slots,
                 metadata_capacity_bytes=args.metadata_capacity,union_scan_lanes=args.union_scan_lanes)
    summary=run_gqa_case(fixture,configs,gc,args.output,
        fixture_sha256=digest(args.fixture.read_bytes()) if args.fixture else None,
        memory_latency=args.memory_latency,memory_window=args.memory_window,memory_banks=args.memory_banks,
        write_public_report=args.public_report,compare_modes=not args.event_only)
    print(json.dumps({key:summary[key] for key in ('status','query_heads','KV_heads','latency_ns','operations','mode_equivalence')}))


if __name__=='__main__': main()
