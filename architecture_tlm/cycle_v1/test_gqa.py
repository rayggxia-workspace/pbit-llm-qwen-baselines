import dataclasses
import math
import struct
import unittest

from .attention import AttentionConfig, reference_attention
from .gqa import GQAConfig, make_gqa, address_layout, build_gqa


def fixture(heads=2,d=3,dv=2):
    candidates=([1,2,10],[10,3,2],[11,2,1])
    return dict(queries=[dict(q=[0.]*d,candidate_ids=list(candidates[h%3])) for h in range(heads)],
                k=[[0.]*d for _ in range(12)],
                v=[[float(i)*(j+1) for j in range(dv)] for i in range(12)])


def run(data,configs=None,gc=None,**kw):
    runs=[]
    for mode in ('cycle','event'):
        k,s=make_gqa(data,configs,gc,**kw)
        r=k.run(mode)
        runs.append((k,s,r))
    assert runs[0][2].equivalence_payload()==runs[1][2].equivalence_payload()
    assert runs[0][1]==runs[1][1]
    return runs[-1]


class GQATests(unittest.TestCase):
    def check_lifetimes(self,k,s,r):
        for kind in ('K','V'):
            for token,read in s[kind+'_read_ids'].items():
                release=s[kind+'_release_ids'][token]
                for consumer in s[kind+'_consumers'][token]:
                    self.assertGreater(r.accepted_ps[release],r.completion_ps[consumer])
                    self.assertGreater(r.accepted_ps[consumer],r.completion_ps[read])
        self.assertEqual(r.buffer_final,{name:spec.initial for name,spec in k.buffer_specs.items()})

    def test_two_and_seven_heads_minimal_slots_and_window(self):
        for heads in (2,7):
            data=fixture(heads)
            k,s,r=run(data,gc=GQAConfig(k_slots=1,v_slots=1),memory_window=1,memory_banks=1)
            for head,query in enumerate(s['queries']):
                ids=data['queries'][head]['candidate_ids']
                expected=[sum(data['v'][i][j] for i in ids)/len(ids) for j in range(2)]
                for a,b in zip(query['output'],expected): self.assertAlmostEqual(a,b,places=5)
                self.assertEqual(k.read_memory('sram',query['output_address'],query['output_bytes']),
                                 struct.pack('<2f',*query['output']))
            self.assertEqual(r.actions['K_read_bytes'],len(s['K_union'])*3*4)
            self.assertEqual(r.actions['V_read_bytes'],len(s['V_union'])*2*4)
            self.check_lifetimes(k,s,r)

    def test_per_head_multiplicity_and_post_histogram_union_barrier(self):
        data=fixture()
        data['queries'][0].update(candidate_ids=[10,2,1],random_replay={'frames':[
            [True,False,False],[False,True,False],[False,True,False],[False,True,False]]})
        data['queries'][1].update(candidate_ids=[2,10,3],random_replay={'frames':[
            [False,False,True],[False,False,True],[False,True,False],[False,False,True]]})
        c=AttentionConfig(mode='winner',samples=4,random_backend='replay',source_lanes=3)
        configs=[c,dataclasses.replace(c,histogram_delay_cycles=20)]
        k,s,r=run(data,configs,GQAConfig(k_slots=1,v_slots=1),memory_window=1)
        self.assertEqual([q['histogram'] for q in s['queries']],[{10:1,2:3},{3:3,10:1}])
        self.assertEqual(s['V_union'],[2,3,10])
        self.assertEqual([q['output'] for q in s['queries']],[[4.,8.],[4.75,9.5]])
        barrier=s['V_barrier_id']
        for event in r.trace:
            if event['kind']=='complete' and '.histogram.' in event['op'] and event['op'].endswith('.write'):
                self.assertLess(event['time_ps'],r.accepted_ps[barrier])
        for read in s['V_read_ids'].values(): self.assertGreater(r.accepted_ps[read],r.completion_ps[barrier])
        self.check_lifetimes(k,s,r)

    def test_reordered_dma_still_uses_actual_rows(self):
        data=fixture(d=16,dv=16)
        gc=GQAConfig(k_slots=2,v_slots=2)
        layouts,_=address_layout(data,group_config=gc)
        slow={layouts[0]['k']+1*64:30,layouts[0]['v']+1*64:30}
        k,s,r=run(data,gc=gc,memory_banks=4,memory_window=4,memory_latency_by_address=slow)
        self.assertLess(r.completion_ps[s['K_read_ids'][2]],r.completion_ps[s['K_read_ids'][1]])
        self.assertLess(r.completion_ps[s['V_read_ids'][2]],r.completion_ps[s['V_read_ids'][1]])
        self.check_lifetimes(k,s,r)

    def test_query_registration_order_changes_neither_values_nor_union(self):
        data=fixture(3)
        _,s,_=run(data,gc=GQAConfig(k_slots=1,v_slots=1),memory_window=1)
        reversed_data=dict(data,queries=list(reversed(data['queries'])))
        _,t,_=run(reversed_data,gc=GQAConfig(k_slots=1,v_slots=1),memory_window=1)
        self.assertEqual([q['output'] for q in s['queries']],list(reversed([q['output'] for q in t['queries']])))
        self.assertEqual(s['K_union'],t['K_union'])
        self.assertEqual(s['V_union'],t['V_union'])

    def test_shared_cache_port_bandwidth_is_real(self):
        data=fixture(2,d=16,dv=16)
        _,a,ar=run(data,gc=GQAConfig(cache_bytes_per_cycle=64))
        _,b,br=run(data,gc=GQAConfig(cache_bytes_per_cycle=4))
        self.assertEqual([q['output'] for q in a['queries']],[q['output'] for q in b['queries']])
        self.assertGreater(br.finish_ps,ar.finish_ps)
        self.assertEqual(ar.actions['shared_cache_read_bytes'],12*64)

    def test_corrupted_shared_K_and_V_are_not_bypassed_by_fixture(self):
        for name in ('k','v'):
            data=fixture()
            # K zeros become nonzero; V physical token 1 becomes zero.
            k,s=make_gqa(data)
            layouts,_=address_layout(data)
            width=3 if name=='k' else 2
            address=layouts[0][name]+width*4
            k.load_memory('dram',address,struct.pack('<'+'f'*width,*([1.]*width if name=='k' else [0.]*width)))
            with self.assertRaisesRegex(AssertionError,'payload mismatch'): k.run('event')

    def test_addresses_are_disjoint_and_existing_owner_is_rejected(self):
        data=fixture(7,d=23,dv=5)
        _,regions=address_layout(data)
        for i,a in enumerate(regions):
            self.assertEqual(a['address']%64,0)
            for b in regions[i+1:]:
                self.assertTrue(a['address']+a['size_bytes']<=b['address'] or b['address']+b['size_bytes']<=a['address'])
        k,_=make_gqa(data)
        with self.assertRaisesRegex(ValueError,'overlaps'): build_gqa(k,data,prefix='another')

    def test_explicit_capacity_and_resource_rejections(self):
        data=fixture()
        for gc in (GQAConfig(k_slots=0),GQAConfig(v_slots=0),GQAConfig(query_state_capacity_bytes=65535)):
            with self.assertRaises(ValueError): make_gqa(data,group_config=gc)
        for field,value in (('exp_latency',9),('mac_lanes',32),('vector_lanes',32),('exp_lanes',8),
                            ('reciprocal_latency',13),('drive_latency',4),('lut_latency',3)):
            with self.assertRaisesRegex(ValueError,'shared physical'):
                make_gqa(data,[AttentionConfig(),dataclasses.replace(AttentionConfig(),**{field:value})])

    def test_native_source_instances_are_explicit_and_drained(self):
        data=fixture()
        c=AttentionConfig(mode='pv',samples=4,random_backend='native')
        k,s,r=run(data,c,GQAConfig(k_slots=1,v_slots=1),memory_window=1)
        self.assertEqual([x['seed'] for x in s['provenance']['source_instances']],[0,1])
        self.assertTrue(all(x['native_network'] for x in s['provenance']['source_instances']))
        for q in s['queries']:
            self.assertEqual(sum(q['histogram'].values()),4)
            self.assertIsNotNone(q['native_random'])
        self.assertEqual(r.actions['native_rng_request'],2)
        self.check_lifetimes(k,s,r)


if __name__=='__main__': unittest.main()
