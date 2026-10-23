"""Read only a published Git blob; compare it in process, without adoption."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import types
import unittest


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--published-repo', type=Path, required=True)
    p.add_argument('--target-repo', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    sha = 'd944081a22dc346a3a50d505633e5d15c857ba78'
    path = 'architecture_tlm/ffn_cycle_integration/active_memory.py'
    def git(repo, *argv):
        return subprocess.check_output(['git', '-C', str(repo), *argv])
    source = git(args.published_repo, 'show', sha+':'+path)
    source_hash = hashlib.sha256(source).hexdigest()
    assert source_hash == '7e4c9534e40b493956a2ae94b6b6b1cd97e4a0d6052e6aff75637828941d4296'
    sys.path.insert(0, str(args.target_repo.resolve()))
    from architecture_tlm.cycle_v1 import gqa
    from architecture_tlm.cycle_v1.kernel import Kernel
    from architecture_tlm.cycle_v1.contracts import Clock, Resource, Operation
    from architecture_tlm.cycle_v1.memory import MemoryPort, MemoryRequest
    from architecture_tlm.cycle_v1.audit import test_gqa_adversarial as ga
    from architecture_tlm.cycle_v1.audit import test_core_adversarial as ca
    candidate = types.ModuleType('published_active_memory_candidate')
    exec(compile(source, sha+':'+path, 'exec'), candidate.__dict__)
    Active = candidate.ActiveMemoryKernel
    pairs = []
    original = ga.IndependentGQAAudit.run_pair
    def four_way(self, *argv, **kw):
        gqa.Kernel = Kernel
        baseline = original(self, *argv, **kw)
        try:
            gqa.Kernel = Active
            optimized = original(self, *argv, **kw)
        finally:
            gqa.Kernel = Kernel
        self.assertEqual(baseline[1], optimized[1], 'base vs candidate full GQA state')
        self.assertEqual(baseline[2].equivalence_payload(), optimized[2].equivalence_payload(),
                         'base vs candidate full GQA observable payload')
        self.assertEqual(optimized[0]._live_memory, {'dram': {}, 'sram': {}})
        pairs.append(dict(test=self.id(), operations=len(baseline[0].operations),
                          finish_ps=baseline[2].finish_ps, trace_events=len(baseline[2].trace)))
        return baseline
    ga.IndependentGQAAudit.run_pair = four_way
    ca.Kernel = Active
    log = io.StringIO()
    started = time.perf_counter()
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromModule(ga),
        unittest.defaultTestLoader.loadTestsFromModule(ca)])
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    assert result.wasSuccessful(), log.getvalue()
    # Dynamic RAW/WAR/WAW, late-created producer, partial-dependency stall
    # changes, cross-clock visibility, and callback-created memory requests.
    def dynamic(kind):
        c, m = Clock('compute', 10000), Clock('memory', 12500, 2500)
        k = kind([Resource('a',c,1,capacity=2),Resource('b',c,4,capacity=2)],
                 memory_ports=[MemoryPort('ram',m,banks=2,window=2,strict_reads=True,
                                          latency_by_address={0:7,64:1})])
        k.load_memory('ram',0,b'ABCD')
        k.load_memory('ram',64,b'EFGH')
        k.add(Operation('future_consumer','a',deps=('p','late'),cdc_cycles=3))
        def create(kernel, op):
            kernel.add(Operation('late','ram',memory=MemoryRequest(64,4),cdc_cycles=3))
            kernel.add(Operation('dynamic_write','ram',deps=('late',),
                                 memory=MemoryRequest(0,4,write=True,data=b'WXYZ')))
            kernel.add(Operation('dynamic_read','ram',memory=MemoryRequest(0,4)))
        k.add(Operation('creator','a',on_complete=create))
        k.add(Operation('p','b'))
        k.add(Operation('initial_read','ram',memory=MemoryRequest(0,4)))
        k.add(Operation('initial_write','ram',memory=MemoryRequest(0,4,write=True,data=b'1234')))
        return k
    dynamic_results = []
    for cls in (Kernel,Active):
        for mode in ('cycle','event'):
            k = dynamic(cls)
            r = k.run(mode=mode)
            assert r.memory_reads['initial_read'] == b'ABCD'
            assert r.memory_reads['dynamic_read'] == b'WXYZ'
            assert r.accepted_ps['dynamic_write'] > r.completion_ps['initial_read']
            dynamic_results.append(r.equivalence_payload())
    assert all(r == dynamic_results[0] for r in dynamic_results)
    runtime = time.perf_counter()-started
    sources = {}
    for module in list(sys.modules.values()):
        filename = getattr(module,'__file__',None)
        if not filename:
            continue
        file = Path(filename).resolve()
        if file.is_file() and file.is_relative_to(args.target_repo.resolve()) and file.suffix=='.py':
            sources[file.relative_to(args.target_repo.resolve()).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    report = dict(successful=True, published_commit=sha, published_path=path,
                  published_blob=git(args.published_repo,'rev-parse',sha+':'+path).decode().strip(),
                  published_source_sha256=source_hash,
                  target_head=git(args.target_repo,'rev-parse','HEAD').decode().strip(),
                  target_source_sha256=sources, tests_run=result.testsRun,
                  gqa_four_way_cases=len(pairs), gqa_four_way_runs=4*len(pairs),
                  gqa_cases=pairs,dynamic_memory_four_way_runs=4,
                  elapsed_seconds=runtime,
                  scope='Compatibility candidate only; no production adoption, 2K run, PPA or universal proof. '
                        'Each GQA pair compares full state and equivalence_payload, excluding only mode/visited steps. '
                        'Core independent tests run on candidate; GQA runs both base and candidate in both modes.')
    args.output.mkdir(parents=True)
    (args.output/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (args.output/'TEST_LOG.txt').write_text(log.getvalue(),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('successful','tests_run','gqa_four_way_cases','elapsed_seconds')}))


if __name__=='__main__':
    main()
