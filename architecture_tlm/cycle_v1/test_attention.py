import dataclasses
import math
import struct
import unittest

from .attention import AttentionConfig, SamplerCapError, build_attention, make_kernel, reference_attention


def fixture():
    return dict(q=[1.,-.5,.25],
        k=[[i*.1,(i%3)*.2,-i*.05] for i in range(9)],
        v=[[i,(-1.)**i,i*.125] for i in range(9)],candidate_ids=[7,1,5,3])


def execute(data,c,mode='event',latency=4):
    kernel=make_kernel(c,memory_latency=latency)
    state=build_attention(kernel,data,c)
    result=kernel.run(mode)
    return state,result,kernel


class AttentionTests(unittest.TestCase):
    def assertClose(self,a,b,tol=2e-6):
        for x,y in zip(a,b): self.assertLessEqual(abs(x-y),tol*max(1,abs(y)))

    def test_all_paths_cycle_event_and_address_oracle(self):
        for mode in ('exact','pv','winner','rejection'):
            with self.subTest(mode=mode):
                c=AttentionConfig(mode=mode,samples=7,source_lanes=2,seed=31)
                a,ar,_=execute(fixture(),c,'cycle')
                b,br,_=execute(fixture(),c,'event')
                self.assertEqual(ar.equivalence_payload(),br.equivalence_payload())
                self.assertEqual(a['output'],b['output'])
                ref=reference_attention(fixture(),a['local_indices'] if mode!='exact' else None,c)
                self.assertClose(a['output'],ref['output'])
                self.assertEqual(a['K_addresses'],[0x71000000+i*12 for i in fixture()['candidate_ids']])
                ids=fixture()['candidate_ids'] if mode=='exact' else set(a['physical_indices'])
                self.assertEqual(set(a['V_addresses']),{0x72000000+i*12 for i in ids})
                self.assertEqual(ar.actions['K_read_bytes'],4*3*4)
                self.assertEqual(ar.actions['V_read_bytes'],len(ids)*3*4)
                if mode!='exact': self.assertEqual(sum(a['histogram'].values()),7)

    def test_winner_zero_single_multi_and_rank_rejection(self):
        data=dict(q=[0.],k=[[0.]]*4,v=[[1.],[2.],[4.],[8.]],
            random_replay={'frames':[[False]*4,[False,True,False,False],
                [True,False,True,True],[False]*4], 'fair':[3,1]})
        c=AttentionConfig(mode='winner',samples=4,source_lanes=2)
        state,result,_=execute(data,c)
        self.assertEqual(state['local_indices'],[0,1,2,2])
        self.assertEqual(state['rank_retries'],1)
        self.assertEqual(state['winner_holds'],2)
        self.assertEqual(state['winner_switches'],2)
        self.assertEqual(state['source_frames'],4)
        self.assertEqual(state['source_waves'],8)
        self.assertEqual(state['output'],[2.75])
        self.assertEqual(state['histogram'],{0:1,1:1,2:2})
        self.assertGreater(result.actions['rank_tree_visits'],0)

    def test_rejection_feedback_empty_correction_and_retries(self):
        data=dict(q=[0.],k=[[0.]]*3,v=[[1.],[5.],[9.]],
            random_replay={'frames':[[True,True],[False,False],[False,True],[False,False]],'fair':[1]})
        c=AttentionConfig(mode='rejection',samples=2,source_lanes=1)
        state,result,_=execute(data,c)
        self.assertEqual(state['local_indices'],[2,0])
        self.assertEqual(state['rejected_multi'],1)
        self.assertEqual(state['rejected_empty'],1)
        self.assertEqual(state['proposals'],4)
        self.assertEqual(state['source_waves'],8)
        self.assertEqual(state['output'],[5.])
        self.assertEqual(result.actions['offset_changes'],2)
        self.assertEqual([f['next_shift'] for f in state['frames']],[1,0,0,0])

    def test_output_backpressure_preserves_sampler_trajectory(self):
        data=fixture()
        base=AttentionConfig(mode='winner',samples=24,source_lanes=4,seed=9)
        a,ar,_=execute(data,base)
        b,br,_=execute(data,dataclasses.replace(base,histogram_delay_cycles=40))
        self.assertEqual(a['local_indices'],b['local_indices'])
        self.assertEqual(a['output'],b['output'])
        self.assertGreater(br.finish_ps,ar.finish_ps)
        self.assertLessEqual(br.buffer_peak['attention.samples'],1)
        self.assertTrue(any('output' in str(t) for t in br.trace))

    def test_one_candidate_needs_no_biased_random_frame(self):
        data=dict(q=[1.],k=[[2.]],v=[[7.]])
        state,result,_=execute(data,AttentionConfig(mode='rejection',samples=4))
        self.assertEqual(state['output'],[7.])
        self.assertEqual(state['local_indices'],[0]*4)
        self.assertEqual(state['source_frames'],0)
        self.assertEqual(state['source_waves'],0)
        self.assertEqual(state['proposals'],4)
        self.assertEqual(result.actions.get('biased_random_lanes',0),0)

    def test_cap_overflow_and_bad_addresses_fail(self):
        with self.assertRaises(ValueError): execute(fixture(),AttentionConfig(capacity=3))
        data=fixture();data['candidate_ids']=[1,1]
        with self.assertRaises(ValueError): execute(data,AttentionConfig())
        data=dict(q=[0.],k=[[0.]]*3,v=[[1.]]*3,random_replay={'frames':[[True,True]]})
        with self.assertRaises(SamplerCapError):
            execute(data,AttentionConfig(mode='rejection',samples=1,max_proposals_per_sample=1))

    def test_qkv_bytes_are_checked(self):
        kernel=make_kernel()
        build_attention(kernel,fixture())
        kernel.load_memory('dram',0x71000000+7*12,bytes(12))
        with self.assertRaisesRegex(AssertionError,'payload mismatch'): kernel.run()

    def test_output_bytes_and_local_storage_capacity(self):
        state,result,kernel=execute(fixture(),AttentionConfig(mode='pv',samples=9))
        self.assertEqual(kernel.read_memory('sram',state['output_address'],state['output_bytes']),
                         struct.pack('<3f',*state['output']))
        self.assertEqual(state['complete_ps'],result.finish_ps)
        required=sum(state['local_state_bytes'].values())
        with self.assertRaises(ValueError):
            execute(fixture(),AttentionConfig(mode='pv',samples=9,score_capacity_bytes=required-1))


if __name__=='__main__': unittest.main()
