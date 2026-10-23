import random
import unittest
from architecture_tlm.cycle_v1.contracts import Buffer, Clock, Operation, Resource
from architecture_tlm.cycle_v1.kernel import Kernel
from architecture_tlm.cycle_v1.memory import MemoryPort, MemoryRequest
from .active_memory import ActiveMemoryKernel


class ActiveMemoryTests(unittest.TestCase):
    def compare(self, build):
        outcomes = [build(cls).run(mode).equivalence_payload()
                    for cls in (Kernel, ActiveMemoryKernel) for mode in ('cycle','event')]
        for result in outcomes[1:]:
            self.assertEqual(outcomes[0], result)
        return outcomes[0]

    def test_raw_war_waw_partial_overlap_registration_order(self):
        def build(cls):
            k = cls([], memory_ports=[MemoryPort('m',Clock('m',10),banks=2,
                initial_data={0:b'abcdefgh'},strict_reads=True,latency_cycles=3)])
            for name, request in (
                ('z_read',MemoryRequest(0,8)),
                ('a_write',MemoryRequest(2,4,True,b'WXYZ')),
                ('b_write',MemoryRequest(4,4,True,b'1234')),
                ('c_read',MemoryRequest(0,8))):
                k.add(Operation(name,'m',memory=request))
            return k
        self.compare(build)

    def test_backpressure_and_dynamic_requests(self):
        def build(cls):
            c=Clock('c',10)
            k=cls([Resource('control',c,1)],[Buffer('out',1,1)],
                [MemoryPort('m',c,window=2,strict_reads=True,initial_data={0:b'OLD!'})])
            def add_next(kernel,op):
                kernel.add(Operation('new_write','m',memory=MemoryRequest(0,4,True,b'NEW!')))
                kernel.add(Operation('new_read','m',memory=MemoryRequest(0,4)))
            k.add(Operation('old_read','m',memory=MemoryRequest(0,4),outputs={'out':1},on_complete=add_next))
            k.add(Operation('drain','control',inputs={'out':1},earliest_ps=80))
            return k
        self.compare(build)

    def test_seeded_mixed_requests_and_independent_ports(self):
        for seed in (0,7,19):
            def build(cls):
                rng=random.Random(seed); c=Clock('c',10)
                ports=[MemoryPort(n,c,banks=4,window=4,latency_cycles=2,
                                  strict_reads=True,initial_data={0:bytes(range(128))}) for n in ('a','b')]
                k=cls([],memory_ports=ports)
                names=[f'op{i:03d}' for i in range(50)];rng.shuffle(names)
                for name in names:
                    address=rng.randrange(120); size=rng.randrange(1,9);write=rng.choice((False,True))
                    k.add(Operation(name,rng.choice(('a','b')),memory=MemoryRequest(address,size,write,
                        bytes(rng.randrange(256) for _ in range(size)) if write else None)))
                return k
            self.compare(build)

    def test_partial_dependencies_clock_phases_and_earliest_visibility(self):
        def build(cls):
            a,b=Clock('a',10),Clock('b',13,3)
            k=cls([Resource('a',a,1,capacity=4),Resource('b',b,1,capacity=4)])
            # Registration, lexical and completion orders intentionally differ.
            k.add(Operation('z_late','a',latency_cycles=6))
            k.add(Operation('a_early','a',latency_cycles=2))
            k.add(Operation('m_middle','b',latency_cycles=3))
            k.add(Operation('join','b',deps=('z_late','m_middle','a_early'),cdc_cycles=3,earliest_ps=200))
            k.add(Operation('cdc_visible','b',deps=('a_early',),cdc_cycles=3))
            return k
        payload=self.compare(build)
        reasons=[e['reason'] for e in payload['trace']
                 if e['kind']=='stall' and e.get('op')=='join' and e['phase']=='accept']
        self.assertEqual(reasons[:4],['dependency:a_early,m_middle,z_late',
                                     'dependency:m_middle,z_late','dependency:z_late','not_visible_yet'])
        self.assertEqual(payload['accepted_ps']['join'],211)
        self.assertGreater(payload['accepted_ps']['cdc_visible'],payload['completion_ps']['a_early'])

    def test_dynamic_future_producer_and_already_completed_dependencies(self):
        def build(cls):
            a,b=Clock('a',10),Clock('b',13,3)
            k=cls([Resource('a',a,1,capacity=4),Resource('b',b,1,capacity=4)])
            def spawn(kernel,operation):
                kernel.add(Operation('future','a',deps=(operation.id,)))
                kernel.add(Operation('dynamic_past','a',deps=(operation.id,)))
                kernel.add(Operation('dynamic_future','b',deps=('future',operation.id),cdc_cycles=2))
            k.add(Operation('initial_waiter','b',deps=('future',),cdc_cycles=3))
            k.add(Operation('producer','a',on_complete=spawn))
            return k
        payload=self.compare(build)
        self.assertEqual(payload['accepted_ps']['dynamic_past'],20)
        self.assertGreater(payload['accepted_ps']['initial_waiter'],payload['completion_ps']['future'])
        self.assertGreater(payload['accepted_ps']['dynamic_future'],payload['completion_ps']['future'])

    def test_completion_backpressure_defers_dependency_notification(self):
        def build(cls):
            clock=Clock('c',10)
            k=cls([Resource('p',clock,1),Resource('c',clock,1,capacity=3)],
                  [Buffer('full',1,1)])
            k.add(Operation('producer','p',outputs={'full':1}))
            k.add(Operation('drain','c',inputs={'full':1},earliest_ps=60))
            k.add(Operation('consumer','c',deps=('producer',),inputs={'full':1}))
            return k
        payload=self.compare(build)
        self.assertEqual(payload['completion_ps']['producer'],70)
        self.assertEqual(payload['accepted_ps']['consumer'],80)
        k=build(ActiveMemoryKernel);k.run('event')
        self.assertFalse(k._dependency_cache)
        self.assertFalse(k._dependency_waiters)
        self.assertFalse(k._missing_dependencies)

    def test_dependency_blocked_writer_still_orders_later_memory(self):
        def build(cls):
            clock=Clock('c',10)
            k=cls([Resource('c',clock,5)],memory_ports=[MemoryPort('m',clock,
                  initial_data={0:b'OLD!'},strict_reads=True)])
            k.add(Operation('z_write','m',deps=('later_producer',),
                            memory=MemoryRequest(0,4,True,b'NEW!')))
            k.add(Operation('a_read','m',memory=MemoryRequest(0,4)))
            k.add(Operation('later_producer','c'))
            return k
        payload=self.compare(build)
        self.assertEqual(payload['memory_reads']['a_read'],b'NEW!')
        self.assertTrue(any(e['kind']=='stall' and e.get('op')=='a_read' and
                            e['reason']=='memory_order:z_write' for e in payload['trace']))
        k=build(ActiveMemoryKernel);k.run('event')
        self.assertFalse(k._live_memory['m'])

    def test_complete_ffn_contract_payload_matches_original_kernel(self):
        from architecture_tlm.cycle_v1 import ffn
        from architecture_tlm.cycle_v1.test_ffn_contract import fixture, config
        data=fixture(d=65,f=65,o=3)
        settings=config(weight_slots=1,engines=1)
        outcomes=[]
        outputs=[]
        for cls in (Kernel,ActiveMemoryKernel):
            kernel=ffn.make_kernel(settings,kernel_factory=cls)
            state=ffn.build_ffn(kernel,data,settings)
            outcomes.append(kernel.run('event').equivalence_payload())
            outputs.append(state['output'])
        self.assertEqual(outcomes[0],outcomes[1])
        self.assertEqual(outputs[0],outputs[1])


if __name__=='__main__':
    unittest.main()
