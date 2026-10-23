"""Independent checks for the isolated candidate; no repository files changed."""
from pathlib import Path
import gc
import hashlib
import importlib
import json
import random
import sys
import time
import unittest

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]/'workspace_projects/fi23'
sys.path.insert(0,str(REPO));sys.path.insert(0,str(HERE))
from architecture_tlm.cycle_v1.kernel import Kernel
from architecture_tlm.cycle_v1.contracts import Clock,Resource,Buffer,Operation
from architecture_tlm.cycle_v1.memory import MemoryPort,MemoryRequest
from architecture_tlm.ffn_cycle_integration.active_memory import ActiveMemoryKernel
from pending_candidate import PendingCandidateKernel


def original_tests():
    names=('architecture_tlm.cycle_v1.test_ffn_contract','architecture_tlm.cycle_v1.test_ffn',
           'architecture_tlm.ffn_cycle_integration.test_active_memory')
    modules=[importlib.import_module(name) for name in names]
    # Inject only the isolated candidate at the existing test factory binding.
    # The original Kernel stays untouched, so differential tests retain it.
    for module in modules:
        if hasattr(module,'ActiveMemoryKernel'):module.ActiveMemoryKernel=PendingCandidateKernel
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in modules)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():raise AssertionError('existing regressions failed')
    return dict(tests=result.testsRun,passed=True)


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
                observers.append(pending)
                kernel.add(Operation(future,'b',deps=(op.id,),cdc_cycles=2))
        k.add(Operation(name,resource,deps=deps,memory=request,on_complete=callback,
                        earliest_ps=rng.randrange(60),cdc_cycles=rng.randrange(4)))
    for i in range(2):
        k.add(Operation(f'held{i}','a',outputs={'q':1}))
        k.add(Operation(f'drain{i}','ctrl',inputs={'q':1},earliest_ps=70+35*i))
        k.add(Operation(f'final_drain{i}','ctrl',deps=(f'held{i}',),inputs={'q':1}))
    return k,observers


def random_checks():
    seeds=(0,1,2,7,19,31,83,127)
    for seed in seeds:
        reference=None
        for cls,mode in ((Kernel,'cycle'),(Kernel,'event'),(ActiveMemoryKernel,'event'),
                         (PendingCandidateKernel,'cycle'),(PendingCandidateKernel,'event')):
            k,seen=random_graph(cls,seed)
            current=(k.run(mode).equivalence_payload(),seen)
            if reference is None:reference=current
            elif current!=reference:raise AssertionError((seed,cls.__name__,mode))
    return dict(seeds=list(seeds),executions=len(seeds)*5,full_payload_equal=True,
                checks='random DAG/memory/clock phases/CDC/earliest/future producers/callback full pending/output backpressure')


class StopPrefix(Exception):pass


def prefix(cls,data,c,steps):
    from architecture_tlm.cycle_v1 import ffn
    class Probe(cls):
        def _step(self,t):
            if self.prefix_steps==steps:raise StopPrefix
            self.prefix_steps+=1;super()._step(t)
    k=ffn.make_kernel(c,kernel_factory=Probe);ffn.build_ffn(k,data,c);k.prefix_steps=0
    gc.collect();start=time.perf_counter()
    try:k.run('event')
    except StopPrefix:pass
    seconds=time.perf_counter()-start
    payload=dict(now=k.now_ps,accepted=k.accepted,completed=dict(k.completed),actions=dict(k.actions),
                 trace=k.trace,memory_reads=k.memory_reads,buffer_peak=k.buffer_peak,buffers=k.buffers,
                 resource_peak=k.resource_peak,resource_stats=k._stats,
                 process_ticks={n:p.ticks for n,p in k._processes.items()})
    return seconds,payload,dict(pending=len(k._pending),candidates=len(getattr(k,'_accept_candidates',k._pending)))


def performance():
    from architecture_tlm.cycle_v1.test_ffn_contract import fixture,config
    data=fixture(64,4864,64);c=config(samples=32,strata=32)
    result=[]
    for count in (55,300):
        old,oldp,olds=prefix(ActiveMemoryKernel,data,c,count)
        new,newp,news=prefix(PendingCandidateKernel,data,c,count)
        if oldp!=newp:raise AssertionError('prefix trace/state mismatch')
        result.append(dict(steps=count,baseline_seconds=old,candidate_seconds=new,speedup=old/new,
            full_prefix_payload_equal=True,time_ps=newp['now'],trace_events=len(newp['trace']),
            pending_state=news,sc_sample_frames=newp['actions'].get('sc_sample_frames',0),
            restore_outputs=newp['actions'].get('complete_restore_output_b4',0)))
    return result


if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='tests':report=dict(original_tests=original_tests(),random=random_checks())
    elif mode=='performance':report=dict(performance=performance())
    else:raise ValueError(mode)
    report['candidate_sha256']=hashlib.sha256((HERE/'pending_candidate.py').read_bytes()).hexdigest()
    report['scope']='isolated host experiment; current job/source unchanged; prefix speed is not a full-run bound'
    (HERE/(mode+'_receipt.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)
