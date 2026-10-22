"""Single-variable configuration diagnostics, not PPA or design ranking."""
import argparse
from dataclasses import asdict,replace
from datetime import datetime,timezone
import gzip
from pathlib import Path
import struct
import time

from . import ffn
from .run import synthetic_fixture,canonical,digest,json_write,source_provenance,_buffer_accounting,_safe_payload
from .reporting import timeline_summary


def configurations():
    base=ffn.FFNConfig(samples=32,strata=32,bins=4,seed=0,random_backend='native')
    cases=[('baseline','baseline',None,base,4)]
    cases.extend(('engines_'+str(n),'engines',n,replace(base,engines=n),4) for n in (1,2,4))
    cases.extend(('lanes_'+str(n),'vector_lanes',n,replace(base,vector_lanes=n),4) for n in (8,32))
    cases.extend(('memory_'+str(n),'memory_latency',n,base,n) for n in (1,16))
    return cases


def execute(fixture,config,memory_latency):
    completed=[]
    for mode in ('cycle','event'):
        start=time.perf_counter()
        kernel=ffn.make_kernel(config,memory_latency=memory_latency)
        state=ffn.build_ffn(kernel,fixture,config)
        result=kernel.run(mode)
        elapsed=time.perf_counter()-start
        if state['output'] is None or state['complete_ps']!=result.finish_ps:
            raise AssertionError('output memory write did not complete')
        if result.buffer_final!={name:spec.initial for name,spec in kernel.buffer_specs.items()}:
            raise AssertionError('finite credits did not return')
        storage=_buffer_accounting(kernel,result.trace)
        observed=ffn.replay_fixture(fixture,state)
        expected=ffn.reference_ffn_tiled(observed,config)
        numeric={name:state[name]==expected[name] for name in ('gate','up','z','projected','output')}
        if not all(numeric.values()):
            raise AssertionError('count-compressed oracle mismatch: '+str(numeric))
        actual=kernel.read_memory('sram',state['output_address'],state['output_bytes'])
        payload=struct.pack('<'+'f'*len(state['output']),*state['output'])
        if config.output_bf16:
            payload=b''.join(payload[i+2:i+4] for i in range(0,len(payload),4))
        if actual!=payload:
            raise AssertionError('actual output bytes differ from functional output')
        completed.append((kernel,state,result,elapsed,storage,numeric,actual))
    first,last=completed
    if first[2].equivalence_payload()!=last[2].equivalence_payload():
        raise AssertionError('cycle/event full equivalence payload mismatch')
    for field in ('gate','up','z','projected','output','thresholds'):
        if first[1][field]!=last[1][field]:
            raise AssertionError('cycle/event numeric or trajectory mismatch: '+field)
    kernel,state,result,elapsed,storage,numeric,actual=last
    trajectories=ffn.replay_fixture({},state)['thresholds']
    timing,_=timeline_summary(kernel,result)
    record={'config':asdict(config),'memory_latency':memory_latency,'finish_ps':result.finish_ps,
        'latency_ns':result.finish_ps/1000,'core_cycles_elapsed':result.finish_ps/10000,
        'operations':len(kernel.operations),'trace_events':len(result.trace),
        'mode_equivalence':{'checked':True,'equal':True,'scope':'full trace, accept/complete, read bytes, actions, credits and resource state'},
        'execution_modes':{x[2].mode:{'visited_edges':x[2].steps,'wall_seconds':x[3],
                                   'numeric_bit_equal_fields':x[5],'credits_restored':True} for x in completed},
        'storage':storage,'output':state['output'],'output_memory_sha256':digest(actual),
        'thresholds':trajectories,'thresholds_sha256':digest(canonical(trajectories)),
        'numeric_fields':{name:state[name] for name in ('gate','up','z','projected','output')},
        'actions':result.actions,'native_random':state['native_random'],
        'timing_details':timing,'model_boundary':state['provenance'],
        'equivalence_payload_sha256':digest(canonical(_safe_payload(result)))}
    return record,result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    bundle=synthetic_fixture()
    fixture=dict(bundle['ffn'],provenance=bundle['provenance'])
    source=source_provenance()
    cases=[]
    start=time.perf_counter()
    for name,axis,value,config,memory_latency in configurations():
        record,result=execute(fixture,config,memory_latency)
        record.update(case=name,varied_parameter=axis,varied_value=value)
        frozen=gzip.compress(canonical(_safe_payload(result)),mtime=0)
        trace_name=name+'.trace.json.gz'
        (args.output/trace_name).write_bytes(frozen)
        record['trace_artifact']={'path':trace_name,'sha256':digest(frozen),'bytes':len(frozen)}
        baseline=record if not cases else cases[0]
        record['comparison_to_baseline']={
            'output_bits_equal':record['output_memory_sha256']==baseline['output_memory_sha256'],
            'threshold_trajectory_equal':record['thresholds']==baseline['thresholds'],
            'numeric_fields_equal':{key:record['numeric_fields'][key]==baseline['numeric_fields'][key]
                                    for key in ('gate','up','z','projected','output')},
            'max_output_absolute_delta':max(abs(x-y) for x,y in zip(record['output'],baseline['output'])),
            'latency_ratio':record['finish_ps']/baseline['finish_ps']}
        if record['comparison_to_baseline']['threshold_trajectory_equal']:
            record['trajectory_note']='Observed group trajectories equal; this is not a general seed-only pairing guarantee.'
        else:
            record['trajectory_note']='Observed trajectories differ. Native absolute-clock idle/reseed and request histories are retained; do not force identical outputs or infer the cause without inspecting them.'
        cases.append(record)
        json_write(args.output/(name+'.json'),record)
        print(name,record['latency_ns'],'ns',record['comparison_to_baseline'],flush=True)
    summary={'schema':'cycle_v1.ffn_configuration_sensitivity.1','created_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'single synthetic 67->70->16 FFN; conditional configuration sensitivity only; no PPA or architecture ranking',
        'fixture_sha256':digest(canonical(fixture)),'fixture_provenance':bundle['provenance'],
        'source':source,'seed':0,'B':4,'T':32,'K':32,
        'axes':{'engines':[1,2,4,8],'vector_lanes':[8,16,32],'memory_latency':[1,4,16]},
        'baseline':{'engines':8,'vector_lanes':16,'memory_latency':4},
        'deduplication':'10 axis entries share the same baseline three times, yielding 8 distinct configurations',
        'case_count':len(cases),'total_wall_seconds':time.perf_counter()-start,
        'all_cycle_event_equal':all(x['mode_equivalence']['equal'] for x in cases),
        'all_numeric_oracles_equal':all(all(m['numeric_bit_equal_fields'].values()) for x in cases for m in x['execution_modes'].values()),
        'all_credits_restored':all(m['credits_restored'] for x in cases for m in x['execution_modes'].values()),
        'all_outputs_equal_to_baseline':all(x['comparison_to_baseline']['output_bits_equal'] for x in cases),
        'all_trajectories_equal_to_baseline':all(x['comparison_to_baseline']['threshold_trajectory_equal'] for x in cases),
        'cases':[{k:x[k] for k in ('case','varied_parameter','varied_value','latency_ns','operations',
                    'comparison_to_baseline','trace_artifact')} for x in cases],
        'boundaries':['one seed and one synthetic fixture, not a statistical robustness sweep',
            'engine count changes only configured issue resources; total W8/counter capacities remain fixed',
            'vector_lanes jointly controls restoration, nonlinear and residual vector contracts',
            'memory_latency changes DRAM port base latency only; SRAM stays at 2 cycles, widths/windows/banks stay fixed',
            'same output does not establish full-model quality, physical IID, area, energy or an architecture advantage',
            'native frame count includes repeated waves; unique group trajectories and actual source activity are distinct',
            'wall times measure Python execution, not hardware latency; no repeated wall-time trials']}
    json_write(args.output/'summary.json',summary)
    lines=['# FFN 配置敏感性诊断','',
        '固定 synthetic_fixture 67→70→16、seed=0、B4/T32/K32、native source；三个轴共享默认配置，因此是 8 个去重配置。',
        '全部 cycle/event 完整 trace、真实字节、动作与资源状态一致；每种模式均通过 count-compressed oracle、输出字节与有限 credit 检查。',
        '', '| 配置 | 条件延迟 ns | 相对 baseline | 原生 frames | 输出相同 | 轨迹相同 |',
        '|---|---:|---:|---:|---|---|']
    for x in cases:
        comp=x['comparison_to_baseline']
        frames=x['native_random']['ports']['ffn']['counts']['frames_generated']
        lines.append(f"| {x['case']} | {x['latency_ns']:.2f} | {comp['latency_ratio']:.6f} | {frames} | {comp['output_bits_equal']} | {comp['threshold_trajectory_equal']} |")
    lines.extend(['','此表只诊断配置变化的模型响应，不用于 PPA 或架构优劣排名。weight/counter 容量保持不变；memory_latency 只改变 DRAM 基础延迟；vector_lanes 同时影响恢复、非线性与残差向量阶段。',
        '实际门限轨迹、各字段数值、原生源 epoch/seed 回执及配置保留在每个 JSON；跨配置输出/轨迹差异被记录，而非通过断言强行排除。',
        '源文件 SHA、基线提交、fixture SHA、完整验证摘要见 summary.json；压缩 trace 的 SHA 在对应 case 中。单 seed、单输入不代表统计稳健性、完整模型 PPL 或物理源 IID。'])
    (args.output/'README_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
