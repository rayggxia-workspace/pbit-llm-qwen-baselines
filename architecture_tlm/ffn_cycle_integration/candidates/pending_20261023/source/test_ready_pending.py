"""Full trace/identity regressions and fail-closed backend version gates."""
from contextlib import redirect_stdout
import io
import json
import random
import unittest
from unittest.mock import patch

from architecture_tlm.cycle_v1.kernel import Kernel
from architecture_tlm.cycle_v1.contracts import Clock,Resource,Buffer,Operation
from architecture_tlm.cycle_v1.memory import MemoryPort,MemoryRequest
from architecture_tlm.ffn_cycle_integration.active_memory import ActiveMemoryKernel
from . import ready_pending
from .ready_pending import PendingCandidateKernel


def assert_candidate_set(kernel):
    if not isinstance(kernel,PendingCandidateKernel):return
    expected={ident for ident in kernel._pending
              if kernel._dependency_cache[ident][1] is None or
              kernel._dependency_cache[ident][1]!=kernel._last_stall.get((ident,'accept'))}
    if set(kernel._accept_candidates)!=expected:
        raise AssertionError('candidate/pending stable-dependency partition differs')


def changed_backend_method(self,time_ps):
    raise AssertionError('source guard must reject before this can execute')


def random_graph(cls,seed):
    rng=random.Random(seed);a,b=Clock('a',7),Clock('b',11,3)
    k=cls([Resource('a',a,2,capacity=3,instances=2),Resource('b',b,3,capacity=2),
           Resource('ctrl',a,1,capacity=4)],[Buffer('q',2,2)],
          [MemoryPort('m',b,banks=3,line_bytes=4,window=3,latency_cycles=3,
                      strict_reads=True,initial_data={0:bytes(range(128))})])
    observers=[];names=[f'op{i:02d}' for i in range(50)];rng.shuffle(names)
    for i,name in enumerate(names):
        deps=tuple(rng.sample(names[:i],min(i,rng.randrange(4))))
        resource=rng.choice(('a','b','m'));request=None
        if resource=='m':
            addr=rng.randrange(120);size=rng.randrange(1,9);write=bool(rng.randrange(2))
            request=MemoryRequest(addr,size,write,bytes([i]*size) if write else None)
        callback=None
        if i in (4,17):
            future=f'future{i}'
            k.add(Operation(f'early_waiter{i}','ctrl',deps=(future,),cdc_cycles=3))
            def callback(kernel,op,future=future):
                # A callback must see every actual pending operation, including
                # candidates omitted solely for stable dependency stalls.
                pending=sorted(kernel._pending)
                expected=sorted(set(kernel.operations)-set(kernel.accepted))
                if pending!=expected:raise AssertionError('callback pending view was filtered')
                assert_candidate_set(kernel)
                observers.append(pending)
                kernel.add(Operation(future,'b',deps=(op.id,),cdc_cycles=2))
        k.add(Operation(name,resource,deps=deps,memory=request,on_complete=callback,
                        earliest_ps=rng.randrange(60),cdc_cycles=rng.randrange(4)))
    for i in range(2):
        k.add(Operation(f'held{i}','a',outputs={'q':1}))
        k.add(Operation(f'drain{i}','ctrl',inputs={'q':1},earliest_ps=70+35*i))
        k.add(Operation(f'final_drain{i}','ctrl',deps=(f'held{i}',),inputs={'q':1}))
    return k,observers


class ReadyPendingTests(unittest.TestCase):
    def test_random_full_trace_and_callback_pending_identity(self):
        for seed in (0,1,2,7,19,31,83,127):
            reference=None
            for cls,mode in ((Kernel,'cycle'),(Kernel,'event'),(ActiveMemoryKernel,'event'),
                             (PendingCandidateKernel,'cycle'),(PendingCandidateKernel,'event')):
                with self.subTest(seed=seed,kernel=cls.__name__,mode=mode):
                    kernel,seen=random_graph(cls,seed)
                    actual=(kernel.run(mode).equivalence_payload(),seen)
                    if reference is None:reference=actual
                    else:self.assertEqual(reference,actual)
                    assert_candidate_set(kernel)

    def test_stable_partial_and_future_dependency_candidates(self):
        def build(cls):
            a,b=Clock('a',10),Clock('b',13,3)
            k=cls([Resource('a',a,1,capacity=4),Resource('b',b,1,capacity=4)])
            observations=[]
            def observe(kernel):
                assert_candidate_set(kernel)
                observations.append((kernel.now_ps,sorted(kernel._pending)))
                return kernel.now_ps<120
            k.register_clock_process('observe',a,observe);k.wake_clock_process('observe')
            def spawn(kernel,op):
                assert_candidate_set(kernel)
                kernel.add(Operation('future','b',deps=(op.id,),cdc_cycles=2))
                kernel.add(Operation('dynamic_past','a',deps=(op.id,)))
                assert_candidate_set(kernel)
            k.add(Operation('early','a',latency_cycles=2,on_complete=spawn))
            k.add(Operation('late','b',latency_cycles=8))
            k.add(Operation('join','a',deps=('late','early'),earliest_ps=160,cdc_cycles=3))
            k.add(Operation('wait_future','b',deps=('future',),cdc_cycles=2))
            return k,observations
        reference=None
        for cls in (Kernel,PendingCandidateKernel):
            for mode in ('cycle','event'):
                kernel,observations=build(cls)
                actual=(kernel.run(mode).equivalence_payload(),observations)
                if reference is None:reference=actual
                else:self.assertEqual(reference,actual)
        reasons=[e['reason'] for e in reference[0]['trace'] if e['kind']=='stall' and e.get('op')=='join']
        self.assertEqual(reasons[:3],['dependency:early,late','dependency:late','not_visible_yet'])

    def test_four_backend_source_guards_reject_changed_methods(self):
        for owner,name in ((Kernel,'_step'),(Kernel,'_next_event_time'),
                           (ActiveMemoryKernel,'_next_event_time'),
                           (ActiveMemoryKernel,'_dependency_completed')):
            with self.subTest(owner=owner.__name__,method=name):
                with patch.object(owner,name,changed_backend_method):
                    with self.assertRaisesRegex(RuntimeError,'source guard mismatch'):
                        PendingCandidateKernel([])

    def test_uninspectable_backend_is_rejected(self):
        with patch.object(Kernel,'_step',lambda self,t:None):
            with patch.object(ready_pending.inspect,'getsource',side_effect=OSError('source absent')):
                with self.assertRaisesRegex(RuntimeError,'cannot inspect'):
                    PendingCandidateKernel([])

    def test_source_inspection_is_cached_per_method(self):
        ready_pending._source_sha256.cache_clear()
        original=ready_pending.inspect.getsource
        with patch.object(ready_pending.inspect,'getsource',wraps=original) as read:
            PendingCandidateKernel([]);PendingCandidateKernel([])
            self.assertEqual(read.call_count,4)

    def test_progress_obeys_step_and_wall_gates_without_trace_changes(self):
        from architecture_tlm.cycle_v1 import run_contract_ffn
        stream=io.StringIO()
        with patch.object(run_contract_ffn.time,'perf_counter',side_effect=(0.,29.9,30.,61.)):
            with redirect_stdout(stream):
                kernel=run_contract_ffn.ProgressKernel([])
                for step in range(3072):kernel._step(step)
        reports=[json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual([item['steps'] for item in reports],[2048,3072])
        self.assertTrue(all(item['pending']==item['completed']==0 for item in reports))
        self.assertEqual(kernel.trace,[])
        self.assertFalse(kernel.accepted)
        self.assertFalse(kernel.completed)


if __name__=='__main__':unittest.main()

