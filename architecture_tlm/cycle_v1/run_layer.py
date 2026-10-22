"""Execute a reduced decoder in one kernel; never label it full Qwen inference."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
from pathlib import Path
import time

from . import attention, ffn
from .layer import LayerConfig, make_layer, synthetic_layer, norm, linear, rope, pack
from .run import canonical, digest, json_write, source_provenance, _safe_payload, _buffer_accounting, _numeric
from .reporting import timeline_summary, write_inspector


def validate_numeric(data, state, lc, fc, ac):
    """Functional regression plus independently audited primitive contracts."""
    n1=norm(data['x'],data['norm1'],lc.epsilon)
    expected={'norm1':n1}
    for name in ('q','k','v'):
        expected[name]=linear(n1,data['w'+name])
    for name in ('q','k'):
        expected[name+'rope']=rope(expected[name],len(data['past_k']),lc.rope_theta)
    expected['wo']=linear(state['attention']['output'],data['wo'])
    expected['residual']=[ffn.fp32(a+b) for a,b in zip(expected['wo'],data['x'])]
    expected['norm2']=norm(expected['residual'],data['norm2'],lc.epsilon)
    checks={name:state['vectors'][name]==value for name,value in expected.items()}
    if not all(checks.values()): raise AssertionError('decoder stage regression: '+str(checks))
    return {'stage_bit_equal':checks,
        'attention':_numeric('attention',state['query_fixture'],ac,state['attention']),
        'ffn':_numeric('ffn',state['ffn_fixture'],fc,state['ffn']),
        'oracle_scope':'functional regression reuses primitive routines; see audit for independent formulas and memory mutation tests'}


def run_case(output, *, mode='exact', banks=4, window=4, memory_latency=4, working_bytes=4096):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    data=synthetic_layer()
    # Values entering the memory interface are FP32.
    data['x']=[ffn.fp32(v) for v in data['x']]
    for name in ('norm1','norm2'):
        data[name]=[ffn.fp32(v) for v in data[name]]
    for name in ('wq','wk','wv','wo'):
        data[name]=[[ffn.fp32(v) for v in row] for row in data[name]]
    lc=LayerConfig(working_bytes=working_bytes)
    fc=ffn.FFNConfig(); ac=attention.AttentionConfig(mode=mode)
    completed=[]
    for execution_mode in ('cycle','event'):
        start=time.perf_counter()
        k,s=make_layer(data,lc,fc,ac,memory_latency,banks,window)
        result=k.run(execution_mode)
        assert result.finish_ps==s['complete_ps'] and s['output'] is not None
        assert result.buffer_final=={name:b.initial for name,b in k.buffer_specs.items()}
        completed.append((k,s,result,time.perf_counter()-start))
    k,s,r,_=completed[-1]
    assert completed[0][2].equivalence_payload()==r.equivalence_payload()
    assert completed[0][1]['output_bytes']==s['output_bytes']
    assert completed[0][1]['ffn']['thresholds']==s['ffn']['thresholds']
    assert completed[0][1]['attention']['histogram']==s['attention']['histogram']
    validation=validate_numeric(data,s,lc,fc,ac)
    details,rows=timeline_summary(k,r)
    payload=_safe_payload(r)
    blob=gzip.compress(canonical(payload),mtime=0)
    (output/'trace.json.gz').write_bytes(blob)
    summary={'schema':'cycle_v1.reduced_decoder.1','created_utc':datetime.now(timezone.utc).isoformat(),
        'source':source_provenance(),'boundary':s['provenance'],'fixture':data['provenance'],
        'configs':s['configs'],'memory':{'banks':banks,'window':window,'latency_cycles':memory_latency},
        'mode_equivalence':True,'numeric_validation':validation,'operations':len(r.accepted_ps),
        'finish_ps':r.finish_ps,'latency_ns':r.finish_ps/1000,'output':s['output'],
        'output_memory_sha256':digest(s['output_bytes']),'actions':r.actions,
        'storage':_buffer_accounting(k,r.trace),'timing_details':details,
        'execution_modes':{rr.mode:{'visited_edges':rr.steps,'wall_seconds':elapsed} for _,_,rr,elapsed in completed},
        'trace_sha256':digest(blob),'native_random':{n:s[n].get('native_random') for n in ('attention','ffn')},
        'energy':{'status':'unknown','action_namespaces_overlap':True},
        'full_model_ppl':None,'rtl_datapath_validated':False}
    json_write(output/'summary.json',summary)
    json_write(output/'contracts.json',{'resources':[asdict(v) for v in k.resources.values()],
        'buffers':[asdict(v) for v in k.buffer_specs.values()],
        'memory_ports':[{key:value for key,value in asdict(v).items() if key!='initial_data'} for v in k.memory_ports.values()]})
    write_inspector(output/'timeline.html',{'operator':'reduced decoder','finish_ps':r.finish_ps,'boundary':s['provenance']},rows)
    return summary


def run_suite(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    cases={}
    for mode in ('exact','pv','winner','rejection'):
        cases[mode]=run_case(output/mode,mode=mode)
    cases['bank_conflict']=run_case(output/'bank_conflict',banks=1,window=1)
    cases['slow_memory']=run_case(output/'slow_memory',memory_latency=20)
    cases['capacity_exact']=run_case(output/'capacity_exact',working_bytes=768)
    base=cases['exact']
    for name in ('bank_conflict','slow_memory','capacity_exact'):
        assert cases[name]['output_memory_sha256']==base['output_memory_sha256'],name
    assert cases['bank_conflict']['finish_ps']>base['finish_ps']
    assert cases['slow_memory']['finish_ps']>base['finish_ps']
    guards=[]
    for name,kwargs,expected_error in [('layer_state_underflow',{'layer_config':LayerConfig(working_bytes=767)},'layer live vector state exceeds'),
                        ('candidate_capacity_overflow',{'attention_config':attention.AttentionConfig(capacity=9)},'candidate capacity exceeded')]:
        try:
            k,_=make_layer(**kwargs);k.run('event')
        except ValueError as exc:
            if expected_error not in str(exc): raise
            guards.append({'case':name,'rejected':True,'reason':str(exc)})
        else: raise AssertionError('capacity guard failed: '+name)
    summary={'passed':True,'scope':'reduced synthetic single-head decoder only',
        'success_cases':{name:{key:case[key] for key in ('operations','latency_ns','mode_equivalence','output_memory_sha256')} for name,case in cases.items()},
        'capacity_guards':guards,'backpressure_preserves_exact_output':True,
        'boundary':'Not a full Qwen/Llama layer; no GQA, learned screening, whole-model PPL or calibrated PPA'}
    json_write(output/'SUITE.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    import json
    print(json.dumps(run_suite(args.output),indent=2))


if __name__=='__main__': main()
