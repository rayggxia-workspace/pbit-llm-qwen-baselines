"""External full-shape FFN runner, event-only unless explicitly comparing modes.

The input and derived W8 weights remain external. Reports include declared
resource timing, complete action counts and independent numeric validation,
never a PPL, timing-closure or physical PPA claim. Both x and z use FP32 input
words; a BF16 source fixture is not evidence of a BF16 encoder resource path.
"""
import argparse
from dataclasses import asdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import struct
import time

from . import ffn
from .ffn_contract import CONTRACT
from .run import canonical, digest, json_write, _buffer_accounting
from ..ffn_cycle_integration.ready_pending import PendingCandidateKernel, verify_backend_sources


class ProgressKernel(PendingCandidateKernel):
    """Host stdout heartbeat only; no trace, scheduling or numeric effect."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._host_progress_steps=0
        self._host_last_progress=time.perf_counter()

    def _step(self,time_ps):
        super()._step(time_ps)
        self._host_progress_steps+=1
        if self._host_progress_steps%1024==0:
            now=time.perf_counter()
            if now-self._host_last_progress>=30:
                print(json.dumps(dict(stage='progress',steps=self._host_progress_steps,
                    pending=len(self._pending),completed=len(self.completed),now_ps=self.now_ps)),flush=True)
                self._host_last_progress=now


def stream_hash(items):
    h=hashlib.sha256()
    for item in items:
        h.update(canonical(item)); h.update(b'\n')
    return h.hexdigest()


def file_record(path, root):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return dict(path=path.relative_to(root).as_posix(),bytes=path.stat().st_size,sha256=h.hexdigest())


def source_manifest():
    repository=Path(__file__).resolve().parents[2]
    sources=list((repository/'architecture_tlm/cycle_v1').glob('*.py'))
    sources+=list((repository/'architecture_tlm/encoding_restore_contract').glob('*.py'))
    sources += [repository/path for path in (
        'architecture_tlm/ffn_cycle_integration/active_memory.py',
        'architecture_tlm/ffn_cycle_integration/ready_pending.py',
        'format_conversion_rtl_20261016/sim/reference.py',
        'architecture_tlm/digital_ppa_v1/sim/validate.py',
        'architecture_tlm/unified_v6/rng_integrated.py',
        'architecture_tlm/random_service/__init__.py','architecture_tlm/random_service/model.py',
        'architecture_tlm/random_service/backends.py','architecture_tlm/random_service/service.py',
        'architecture_tlm/random_service/shared64_mapping.json')]
    records=[file_record(p,repository) for p in sorted(set(sources))]
    return dict(schema='ffn.source_manifest.1',path_base='repository root',files=records,
                files_sha256=digest(canonical(records)))


def persist_mode(root, manifest, mode, kernel, state, result, elapsed, *, error=None):
    """Durable evidence precedes all numeric/credit gates; no weights published.

    A failed kernel still has a useful partial trace and any observed threshold
    words. Its files are explicitly marked incomplete, never replay approval.
    """
    directory=root/mode
    directory.mkdir(exist_ok=False)
    trace=result.trace if result is not None else kernel.trace
    trace_path=directory/'trace.jsonl.gz'
    raw_hash=hashlib.sha256(); raw_bytes=0
    with trace_path.open('wb') as sink:
        with gzip.GzipFile(filename='',mode='wb',fileobj=sink,mtime=0) as compressed:
            for event in trace:
                row=canonical(event)+b'\n'
                compressed.write(row); raw_hash.update(row); raw_bytes+=len(row)
    record=file_record(trace_path,root)
    record.update(uncompressed_sha256=raw_hash.hexdigest(),uncompressed_bytes=raw_bytes,
                  records=len(trace),format='one canonical JSON event per line; UTF-8; gzip')
    manifest['artifacts'].append(record)
    def save(name,value):
        path=directory/name
        json_write(path,value)
        manifest['artifacts'].append(file_record(path,root))
    thresholds=ffn.replay_fixture({},state)['thresholds']
    save('thresholds.json',dict(schema='ffn.actual_thresholds.1',mode=mode,
         complete=result is not None,thresholds=thresholds,
         thresholds_sha256=digest(canonical(thresholds)),
         origin='observed x/z words consumed by this execution; native multiwave identity checked by FFN'))
    stages={}
    for name in ('gate','up','z','projected','output'):
        values=state.get(name)
        if values is None:
            stages[name]=None
            continue
        raw=struct.pack('<'+'f'*len(values),*values)
        words=list(struct.unpack('<'+'I'*len(values),raw))
        stages[name]=dict(values=len(values),bytes=len(raw),fp32le_sha256=digest(raw),
                          raw_words_hex=[f'{word:08x}' for word in words])
    save('stages.fp32.json',dict(schema='ffn.stage_words.1',mode=mode,complete=result is not None,
         encoding='IEEE-754 binary32 raw words in hexadecimal; digest uses concatenated little-endian words',
         stages=stages))
    save('native_random.json',dict(schema='ffn.native_random.1',mode=mode,
         report_available='native_random' in state,report=state.get('native_random'),
         note='Final native.report() snapshot; absent on a failure before the FFN final callback'))
    execution=dict(schema='ffn.mode_execution.1',mode=mode,complete=result is not None,
        validation_status='not yet numerically validated',wall_seconds=elapsed,error=error,
        finish_ps=result.finish_ps if result is not None else kernel.now_ps,
        actions=dict(result.actions if result is not None else kernel.actions),
        accepted_ps=dict(result.accepted_ps if result is not None else kernel.accepted),
        completion_ps=dict(result.completion_ps if result is not None else kernel.completed),
        buffer_final=dict(result.buffer_final if result is not None else kernel.buffers))
    save('execution.json',execution)
    manifest['modes'][mode]=dict(complete=result is not None,
        validation_status='not yet numerically validated',trace_stream_sha256=raw_hash.hexdigest())
    json_write(root/'artifact_manifest.json',manifest)


def execute(bundle, config, *, compare_modes=False, memory_latency=4,
            max_time_ps=10**13, max_steps=10**8, artifact_dir=None):
    sources=source_manifest()
    root=Path(artifact_dir) if artifact_dir is not None else None
    manifest=dict(schema='ffn.execution_artifacts.1',path_base='artifact directory',
                  publication='Raw traces and derived numeric data remain on personal server storage; upload indexes and hashes only',
                  config=asdict(config),fixture_provenance=bundle.get('provenance',{}),
                  sources=sources,artifacts=[],modes={})
    if root is not None:
        root.mkdir(parents=True,exist_ok=True)
        if (root/'artifact_manifest.json').exists():
            raise FileExistsError(root/'artifact_manifest.json')
        json_write(root/'source_manifest.json',sources)
        manifest['artifacts'].append(file_record(root/'source_manifest.json',root))
        json_write(root/'artifact_manifest.json',manifest)
    fixture=dict(bundle.get('ffn',bundle))
    fixture['provenance']=bundle.get('provenance',{})
    # Freeze quantization once, outside the independent arithmetic oracle.
    # Real full-shape captures are already W8; synthetic callers may be raw.
    for name in ('wg','wu','wd'):
        matrix=ffn.matrix_spec(fixture[name])
        fixture[name]=dict(codes=matrix['codes'],scales=matrix['scales'])
    executions=[]
    for mode in (('cycle','event') if compare_modes else ('event',)):
        start=time.perf_counter()
        kernel=ffn.make_kernel(config,memory_latency=memory_latency,
                               kernel_factory=ProgressKernel)
        state=ffn.build_ffn(kernel,fixture,config)
        print(json.dumps(dict(stage='built',mode=mode,operations=len(kernel.operations))),flush=True)
        try:
            result=kernel.run(mode,max_time_ps=max_time_ps,max_steps=max_steps)
        except Exception as error:
            if root is not None:
                persist_mode(root,manifest,mode,kernel,state,None,time.perf_counter()-start,
                             error=dict(type=type(error).__name__,message=str(error)))
            raise
        elapsed=time.perf_counter()-start
        if root is not None:
            persist_mode(root,manifest,mode,kernel,state,result,elapsed)
        if result.buffer_final!={n:b.initial for n,b in kernel.buffer_specs.items()}:
            raise AssertionError('local storage credit leak')
        if state.get('complete_ps')!=result.finish_ps:
            raise AssertionError('final output did not commit at completion')
        expected=(b''.join(struct.pack('<f',v)[2:] for v in state['output'])
                  if config.output_bf16 else struct.pack('<'+'f'*len(state['output']),*state['output']))
        stored=kernel.read_memory('sram',state['output_address'],state['output_bytes'])
        if stored!=expected: raise AssertionError('final memory differs from functional output')
        executions.append((kernel,state,result,elapsed,stored))
        print(json.dumps(dict(stage='simulated',mode=mode,wall_seconds=elapsed,
                              finish_ps=result.finish_ps,operations=len(result.accepted_ps))),flush=True)
    kernel,state,result,elapsed,stored=executions[-1]
    if compare_modes and executions[0][2].equivalence_payload()!=result.equivalence_payload():
        raise AssertionError('complete cycle/event payload differs')
    start=time.perf_counter()
    ref=ffn.reference_ffn_tiled(ffn.replay_fixture(fixture,state),config)
    packed=lambda values:struct.pack('<'+'f'*len(values),*values)
    checks={name:packed(state[name])==packed(ref[name]) for name in ('gate','up','z','projected','output')}
    if not all(checks.values()): raise AssertionError('independent complete FFN mismatch: '+str(checks))
    expected_restores=2*len(state['gate'])*math.ceil(len(fixture['x'])/64)+len(state['output'])*math.ceil(len(state['gate'])/64)
    expected_encodes=math.ceil(len(fixture['x'])/64)+math.ceil(len(state['gate'])/64)
    if result.actions.get('complete_restore_output_b4')!=expected_restores:
        raise AssertionError('scalar restore accounting differs from complete shape')
    if result.actions.get('cross_k_fp32_add')!=expected_restores:
        raise AssertionError('cross-k add accounting differs from complete shape')
    if result.actions.get('complete_encode_group64')!=expected_encodes:
        raise AssertionError('shared x/z group encoding accounting differs from complete shape')
    summary=dict(schema='ffn.pr122.integration.1',shape=[len(fixture['x']),len(state['gate']),len(state['output'])],
        config=asdict(config),fixture_provenance=bundle.get('provenance',{}),
        mode_equivalence=dict(checked=compare_modes,equal=True if compare_modes else None,
                              scope='full acceptance/completion, trace, memory, actions, resources, buffers'),
        numerical_validation=dict(oracle='independent integer-significand encoder and signed-W8 accepted-count contraction; separate FP32 FUSED0 rounding',
            bit_equal_fields=checks,wall_seconds=time.perf_counter()-start),
        finish_ps=result.finish_ps,latency_ns=result.finish_ps/1000,
        core_cycles_elapsed=result.finish_ps/10000,
        operations=len(result.accepted_ps),trace_events=len(result.trace),
        execution_modes={r.mode:dict(wall_seconds=t,visited_edges=r.steps) for _,_,r,t,_ in executions},
        actions=result.actions,resource_peak=result.resource_peak,resource_stats=result.resource_stats,
        storage=_buffer_accounting(kernel,result.trace),local_state_bytes=state['local_state_bytes'],
        profile=state['encoding_restore']['profile'],
        peak_live_restore_results=state['encoding_restore']['peak_live_results'],
        output=state['output'],projected=state['projected'],output_memory_sha256=digest(stored),
        trace_stream_sha256=stream_hash(result.trace),
        model_boundary=state['provenance'],native_random=state.get('native_random'),
        source_sha256={item['path']:item['sha256'] for item in sources['files']},
        source_manifest=sources,artifact_manifest=manifest if root is not None else None,
        hardware_status='conditional cycle model; no complete-datapath STA, area, power, energy or silicon result',
        physical_energy='unknown; semantic actions and physical memory byte actions overlap and must not be summed as separate charges',
        host_kernel='PendingCandidateKernel: cached dependency state, per-port live memory, and omission of already-reported unchanged dependency stalls; complete pending state retained; modeled trace unchanged in regression',
        host_kernel_source_guard=verify_backend_sources(),
        python=platform.python_version())
    if 'original_bf16_mlp' in bundle:
        original=bundle['original_bf16_mlp']
        if len(original)!=len(state['projected']): raise ValueError('original MLP shape mismatch')
        differences=[x-y for x,y in zip(state['projected'],original)]
        summary['source_bf16_mlp_difference']=dict(
            rmse=math.sqrt(math.fsum(x*x for x in differences)/len(differences)),
            max_absolute_error=max(map(abs,differences)),
            scope='one token, one layer, before residual; stochastic W8 projection versus original BF16 MLP; descriptive only, no quality acceptance or PPL')
    if root is not None:
        for record in manifest['modes'].values():
            record['validation_status']='independent numerical checks passed'
        manifest['mode_equivalence']=summary['mode_equivalence']
        manifest['numerical_validation']=summary['numerical_validation']
        json_write(root/'artifact_manifest.json',manifest)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True,help='Complete PR122 Profile JSON, all fields explicit')
    parser.add_argument('--config',type=Path,help='Additional FFNConfig overrides')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expect-shape',type=int,nargs=3,required=True,metavar=('D','F','O'))
    parser.add_argument('--compare-modes',action='store_true',help='Small-shape complete trace regression; default event-only')
    parser.add_argument('--memory-latency',type=int,default=4)
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    raw=args.fixture.read_bytes(); bundle=json.loads(raw)
    fixture=bundle.get('ffn',bundle)
    rows=lambda name:fixture[name]['codes'] if isinstance(fixture[name],dict) else fixture[name]
    shape=[len(fixture['x']),len(rows('wg')),len(rows('wd'))]
    if shape!=args.expect_shape: raise ValueError('fixture shape differs from explicit expectation')
    values=json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
    values.update(encoding_restore_contract=CONTRACT,restore_rounding='rtl_fused0_order',
                  encoding_restore_profile=json.loads(args.profile.read_text(encoding='utf-8')))
    config=ffn.FFNConfig(**values); config.validate()
    args.output.mkdir(parents=True)
    try:
        summary=execute(bundle,config,compare_modes=args.compare_modes,
                        memory_latency=args.memory_latency,artifact_dir=args.output)
    except Exception as error:
        json_write(args.output/'failure.json',dict(type=type(error).__name__,message=str(error),
            fixture_sha256=digest(raw),note='Existing mode artifacts were retained; absent summary means no successful full validation'))
        raise
    summary['fixture_sha256']=digest(raw)
    summary['scheduler']={k:os.environ.get(k) for k in ('SLURM_JOB_ID','SLURM_CPUS_PER_TASK','CUDA_VISIBLE_DEVICES')}
    json_write(args.output/'summary.json',summary)
    print(json.dumps(dict(stage='validated',output=str(args.output),shape=shape,
                         numerical_validation=summary['numerical_validation'])),flush=True)


if __name__=='__main__': main()
