"""Bounded synthetic GQA experiment on an immutable, publicly committed candidate."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tarfile
import time

COMMIT = 'd944081a22dc346a3a50d505633e5d15c857ba78'
CANDIDATE = 'architecture_tlm/ffn_cycle_integration/active_memory.py'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def worker(args):
    sys.path.insert(0, str(args.snapshot.resolve()))
    from architecture_tlm.cycle_v1.attention import AttentionConfig
    from architecture_tlm.cycle_v1.gqa import GQAConfig, default_resources, default_buffers, build_gqa
    from architecture_tlm.cycle_v1.kernel import Kernel
    from architecture_tlm.cycle_v1.contracts import Clock
    from architecture_tlm.cycle_v1.memory import MemoryPort
    from architecture_tlm.cycle_v1.run import canonical, _safe_payload
    spec = importlib.util.spec_from_file_location('published_active_candidate', args.candidate)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    row = lambda n, phase: [math.sin(i*.37+phase)*.17 for i in range(n)]
    fixture = dict(queries=[dict(q=row(64,h*.21),candidate_ids=list(range(args.context))) for h in range(7)],
                   k=[row(64,i*.13) for i in range(args.context)],
                   v=[row(64,i*.27) for i in range(args.context)])
    config, group = AttentionConfig(mode='exact',samples=32,seed=0), GQAConfig()
    previous = previous_state = None
    records = []
    choices = [(Kernel,'cycle'),(Kernel,'event'),(module.ActiveMemoryKernel,'cycle'),(module.ActiveMemoryKernel,'event')] if args.kind == 'equivalence' else [(Kernel if args.kind=='original' else module.ActiveMemoryKernel,'event')]
    for cls, mode in choices:
        begin = time.perf_counter()
        kernel = cls(default_resources(config), default_buffers(fixture,config,group), [
            MemoryPort('dram',Clock('dram',12500),latency_cycles=4,window=4,banks=4,strict_reads=True),
            MemoryPort('sram',Clock('sram',12500),latency_cycles=2,window=4,banks=4,strict_reads=True)])
        state = build_gqa(kernel,fixture,config,group)
        build_wall = time.perf_counter()-begin
        begin = time.perf_counter()
        result = kernel.run(mode)
        run_wall = time.perf_counter()-begin
        assert result.buffer_final == {name:spec.initial for name,spec in kernel.buffer_specs.items()}
        payload = result.equivalence_payload()
        if previous is not None:
            assert payload == previous, 'full equivalence payload mismatch'
            assert state == previous_state, 'full functional state mismatch'
        previous, previous_state = payload, state
        records.append(dict(kernel=cls.__name__,mode=mode,context=args.context,heads=7,dimension=64,
            build_seconds=build_wall,run_seconds=run_wall,operations=len(result.accepted_ps),
            finish_ps=result.finish_ps,visited_edges=result.steps,
            payload_sha256=digest(canonical(_safe_payload(result))),state_sha256=digest(canonical(state)),
            output_sha256=digest(canonical([q['output'] for q in state['queries']])),all_credits_returned=True))
    print(json.dumps(dict(status='pass',fixture_sha256=digest(canonical(fixture)),records=records,
                         full_four_way_equivalence=args.kind=='equivalence')))


def main(args):
    root = Path(__file__).resolve().parents[3]
    args.output.mkdir(parents=True,exist_ok=False)
    snapshot_record = json.loads((root/'work/amlink1219/116/gqa_validation_v1/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    archive = root/'work/amlink1219/116/gqa_validation_v1/source_snapshot.tar.gz'
    assert digest(archive.read_bytes()) == snapshot_record['archive_sha256']
    args.snapshot.mkdir(parents=True,exist_ok=False)
    with tarfile.open(archive) as package:
        assert max(len(str(args.snapshot/m.name)) for m in package.getmembers()) < 250
        package.extractall(args.snapshot,filter='data')
    for name, expected in snapshot_record['files'].items():
        assert digest((args.snapshot/name).read_bytes()) == expected
    source = subprocess.check_output(['git','-C',str(args.published_repository),'show',COMMIT+':'+CANDIDATE])
    source_oid = subprocess.check_output(['git','-C',str(args.published_repository),'rev-parse',COMMIT+':'+CANDIDATE],text=True).strip()
    candidate = args.output/'active_memory_candidate.py'
    candidate.write_bytes(source)
    summary = dict(public_candidate_commit=COMMIT,public_candidate_path=CANDIDATE,candidate_git_blob=source_oid,
        candidate_sha256=digest(source),baseline_core_commit=snapshot_record['core_commit'],
        baseline_source_archive_sha256=snapshot_record['archive_sha256'],source_files_verified=len(snapshot_record['files']),
        scope='synthetic host simulation cost probe only; no private inputs, formal adoption, hardware timing/PPA or full-context claim',
        per_case_hard_timeout_seconds=60,cases=[])
    for kind,n in [('equivalence',8),('original',64),('candidate',64),('original',128),('candidate',128)]:
        before = time.perf_counter()
        command = [sys.executable,'-P','-X','utf8',str(Path(__file__).resolve()),'--worker','--kind',kind,
                   '--context',str(n),'--snapshot',str(args.snapshot.resolve()),'--candidate',str(candidate.resolve())]
        try:
            result = subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=60)
            receipt = json.loads(result.stdout) if result.returncode == 0 else dict(status='failed',returncode=result.returncode,stderr=result.stderr)
        except subprocess.TimeoutExpired:
            receipt = dict(status='timeout',hard_limit_seconds=60)
        receipt.update(kind=kind,context=n,parent_wall_seconds=time.perf_counter()-before)
        summary['cases'].append(receipt)
        (args.output/'RESULT.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(receipt),flush=True)
        if receipt['status'] != 'pass':
            break
    if len(summary['cases']) == 5 and all(c['status']=='pass' for c in summary['cases']):
        for start in (1,3):
            old,new=[summary['cases'][i]['records'][0] for i in (start,start+1)]
            assert all(old[k]==new[k] for k in ('payload_sha256','state_sha256','output_sha256','finish_ps','operations'))
        summary['all_context_payload_and_state_hashes_equal'] = True
        (args.output/'RESULT.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--kind')
    parser.add_argument('--context',type=int)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--published-repository',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    worker(args) if args.worker else main(args)
