"""Algorithm semantics, finite resources, accounting and integration contracts."""
import copy
import math
import random
import sys
import unittest
from itertools import product
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from parallel_sampler_v5 import DEFAULT, ENERGY_ACTIONS, AREA_KEYS, SamplingCapError, sigmoid
from winner_hold_tlm_v5 import WinnerHoldSampler
from corrected_rejection_tlm_v5 import CorrectedRejectionSampler
from screen_parallel_tlm_v5 import ScreenParallelDigital
from run_screen_ising_v4 import setup


class Scripted:
    kind='scripted_independent-interface_fixture'
    def __init__(self,frames,fair=()):
        self.frames=iter(frames);self.coins=iter(fair);self.drives=[]
    def draw(self,drives):
        self.drives.append(list(drives));return next(self.frames)
    def fair(self,width):return next(self.coins)


class Zero:
    kind='deterministic_fixture_not_distribution_evidence'
    def draw(self,drives):return [False]*len(drives)
    def fair(self,width):return 0


class Tests(unittest.TestCase):
    def test_winner_holds_are_real_samples_uniform_rank(self):
        m=WinnerHoldSampler(dict(record_events=True),4)
        source=Scripted([[False,True,True,False],[True,False,True,False],[False]*4],[1])
        ids,r=m.request(0,[3,2,1,0],3,random.Random(0),(0,0,0),[10,20,30,40],source=source)
        self.assertEqual(ids,[2,2,2]);self.assertEqual(r['actions']['biased_bit_draws'],12)
        self.assertEqual(r['actions']['fair_bit_draws'],1)
        self.assertEqual(r['actions']['winner_holds'],2)
        self.assertEqual(r['biased_parallel_lanes'],4)
        self.assertTrue(all(e['service_waves']==1 for e in r['events'] if e['name']=='parallel_source_read'))

    def test_rank_rejection_is_charged(self):
        m=WinnerHoldSampler(capacity=4)
        ids,r=m.request(0,[3,2,1,0],1,None,(0,0,0),[0,1,2,3],
                        source=Scripted([[False,True,True,True]],[3,1]))
        self.assertEqual(ids,[2]);self.assertEqual(r['actions']['rank_retries'],1)
        self.assertEqual(r['actions']['fair_bit_draws'],4)

    def test_rejection_empty_correction_and_feedback(self):
        m=CorrectedRejectionSampler(dict(record_events=True),3)
        source=Scripted([[True,True],[False,False],[False,False],[True,False]],[1])
        ids,r=m.request(0,[3,2,1],2,None,(0,0,0),[10,20,30],source=source)
        self.assertEqual(ids,[0,1]);self.assertEqual(r['actions']['proposal_frames'],4)
        self.assertEqual(r['actions']['biased_bit_draws'],8)
        self.assertEqual(r['actions']['fair_bit_draws'],1)
        self.assertEqual([f['shift'] for f in r['frames']],[0,1,0,0])
        self.assertEqual(r['actions']['offset_changes'],2)
        self.assertEqual(r['actions']['config_bits'],2*32+2+2*2*32)
        self.assertEqual(len(r['output_timestamps']),2)

    def test_rejection_cap_has_no_fallback_and_charges_failure(self):
        m=CorrectedRejectionSampler(dict(max_proposals_per_sample=2),3)
        with self.assertRaises(SamplingCapError) as cm:
            m.request(0,[0,0,0],2,None,(0,0,0),[0,1,2],source=Scripted([[True,True]]*4))
        r=cm.exception.receipt
        self.assertEqual(r['status'],'failed_cap');self.assertEqual(r['samples'],0)
        self.assertEqual(r['actions']['proposal_frames'],4)
        self.assertEqual(m.calls,1);self.assertEqual(m.free,r['end_ns'])

    def test_feedback_modes_change_cost_not_sample_law_or_draws(self):
        rows=[]
        for mode in ('per_candidate','shared_scalar'):
            m=CorrectedRejectionSampler(dict(offset_update_mode=mode),64)
            rows.append(m.request(0,[0]*64,128,random.Random(31),(0,0,0),list(range(64))))
        (a,x),(b,y)=rows
        self.assertEqual(a,b)
        for key in ('proposal_frames','biased_bit_draws','fair_bit_draws','offset_changes'):
            self.assertEqual(x['actions'][key],y['actions'][key])
        self.assertGreater(x['actions']['config_bits'],y['actions']['config_bits'])
        self.assertGreater(x['elapsed_cycles'],y['elapsed_cycles'])

    def test_rank_cap_has_no_priority_fallback(self):
        m=WinnerHoldSampler(dict(rank_retry_cap=2),4)
        with self.assertRaises(SamplingCapError) as cm:
            m.request(0,[0]*4,1,None,(0,0,0),list(range(4)),
                      source=Scripted([[False,True,True,True]],[3,3]))
        self.assertEqual(cm.exception.receipt['actions']['fair_bit_draws'],4)

    def test_one_source_transaction_independent_of_candidate_width(self):
        spans=[]
        for n in (64,512,2048):
            m=WinnerHoldSampler(dict(record_events=True),n)
            _,r=m.request(0,[0]*n,2,None,(0,0,0),list(range(n)),source=Zero())
            draws=[e for e in r['events'] if e['name']=='parallel_source_read']
            self.assertEqual(len(draws),2)
            self.assertEqual([e['parallel_lanes'] for e in draws],[n,n])
            spans.append(draws[0]['end_cycle']-draws[0]['start_cycle'])
        self.assertEqual(spans,[4,4,4])

    def test_output_backpressure_preserves_samples_and_increases_time(self):
        a=WinnerHoldSampler(capacity=3);b=WinnerHoldSampler(capacity=3)
        x,r=a.request(0,[2,1,0],8,None,(0,0,0),[0,1,2],source=Zero())
        y,s=b.request(0,[2,1,0],8,None,(0,0,0),[0,1,2],output_ns_per_index=25,source=Zero())
        self.assertEqual(x,y);self.assertEqual(s['elapsed_cycles']-r['elapsed_cycles'],8*3)
        self.assertEqual(s['samples'],8)

    def test_minimum_source_interval_and_query_sharing(self):
        m=WinnerHoldSampler(dict(source_min_interval_cycles=100,record_events=True),4)
        _,r=m.request(3,[0]*4,2,None,(0,0,0),list(range(4)),source=Zero())
        self.assertEqual(r['start_ns'],10.)
        self.assertTrue(any(e['name']=='source_interval_wait' for e in r['events']))
        _,s=m.request(0,[0]*4,1,None,(0,0,1),list(range(4)),source=Zero())
        self.assertGreaterEqual(s['start_ns'],r['end_ns'])
        draws=[e for e in r['events']+s['events'] if e['name']=='parallel_source_read']
        self.assertTrue(all(b['start_cycle']-a['start_cycle']>=100 for a,b in zip(draws,draws[1:])))

    def test_unknown_ppa_is_null_not_zero(self):
        m=WinnerHoldSampler(capacity=4)
        _,r=m.request(0,[0]*4,4,None,(0,0,0),list(range(4)),source=Zero())
        self.assertIsNone(r['physical_dynamic_energy_J'])
        self.assertIsNone(m.area_receipt()['physical_area_mm2'])
        self.assertTrue(r['uncharacterized_energy_actions'])
        self.assertIsNone(m.finish(r['end_ns'])['physical_energy_J'])

    def test_explicit_costs_ledger_and_area(self):
        c=dict(energy_pJ={k:1. for k in ENERGY_ACTIONS},idle_W=0.,
               area={k:0.01 for k in AREA_KEYS})
        m=WinnerHoldSampler(c,4)
        _,r=m.request(0,[0]*4,4,None,(0,0,0),list(range(4)),source=Zero())
        self.assertAlmostEqual(r['physical_dynamic_energy_J'],sum(r['actions'].get(k,0) for k in ENERGY_ACTIONS)*1e-12)
        self.assertAlmostEqual(m.finish(r['end_ns'])['physical_energy_J'],r['physical_dynamic_energy_J'])
        self.assertGreater(m.area_receipt()['physical_area_mm2'],0)

    def test_single_candidate_and_burn(self):
        for cls in (WinnerHoldSampler,CorrectedRejectionSampler):
            m=cls(capacity=1);ids,r=m.request(0,[0],9,random.Random(3),(0,0,0),[99])
            self.assertEqual(ids,[0]*9)
        m=WinnerHoldSampler(dict(burn_updates=7),3)
        ids,r=m.request(0,[0]*3,5,None,(0,0,0),[0,1,2],source=Zero())
        self.assertEqual(len(ids),5);self.assertEqual(r['actions']['proposal_frames'],12)

    def test_input_and_configuration_guards(self):
        for c in (dict(clock_ns=0),dict(tree_levels_per_cycle=0),dict(record_events=1),
                  dict(drive_bits=8,drive_step=.1,drive_max_code=256),dict(energy_pJ={'oops':1})):
            with self.assertRaises(ValueError):WinnerHoldSampler(c)
        with self.assertRaises(ValueError):CorrectedRejectionSampler(dict(burn_updates=1))
        m=WinnerHoldSampler(capacity=2)
        for z,ids in (([0,1,2],[0,1,2]),([0,1],[4,4]),([float('nan')],[0]),([0],[-1])):
            with self.assertRaises(ValueError):m.request(0,z,1,random.Random(),(0,0,0),ids)

    def test_quantization_is_explicit_and_bounded(self):
        m=WinnerHoldSampler(dict(drive_bits=8,drive_step=.125),3)
        src=Scripted([[False]*3]);_,r=m.request(0,[0,-.1,-1000],1,None,(0,0,0),[0,1,2],source=src)
        self.assertEqual(src.drives,[[0.,-.125,-31.875]])
        self.assertTrue(r['numerical_source']['quantization_changes_target'])

    def test_stationary_winner_kernel_exact_enumeration(self):
        z=[0.,-.7,-2.];p=[sigmoid(x) for x in z];n=len(z)
        target=[math.exp(x)/sum(math.exp(v) for v in z) for x in z]
        kernel=[[0.]*n for _ in range(n)]
        for bits in product((False,True),repeat=n):
            mass=math.prod(p[i] if b else 1-p[i] for i,b in enumerate(bits))
            active=[i for i,b in enumerate(bits) if b]
            for old in range(n):
                if bits[old] or not active:kernel[old][old]+=mass
                else:
                    for new in active:kernel[old][new]+=mass/len(active)
        for j in range(n):
            self.assertAlmostEqual(sum(target[i]*kernel[i][j] for i in range(n)),target[j],places=14)

    def test_behavioral_distributions_not_iid_fallback(self):
        z=[1.,0.,-1.];w=[math.exp(x) for x in z];target=[x/sum(w) for x in w]
        for cls in (WinnerHoldSampler,CorrectedRejectionSampler):
            m=cls(capacity=3);ids,r=m.request(0,z,16000,random.Random(71),(0,0,0),[0,1,2])
            for i,p in enumerate(target):self.assertLess(abs(ids.count(i)/len(ids)-p),.02)
            if cls is CorrectedRejectionSampler:self.assertGreater(r['actions']['proposal_frames'],len(ids))

    def test_attention_adapter_no_duplicate_softmax_or_rng(self):
        cfg,e,shape=setup(context=128)
        cfg['screen_ising_v4']['samples']=8
        cfg['parallel_sampler_v5']=dict(kind='winner_hold',options={})
        m=ScreenParallelDigital(cfg,'digital_bf16',e,shape)
        m.attention(0,128,0)
        self.assertEqual(m.actions['ATT_QK_MAC'],14*128*64)
        self.assertEqual(m.actions['ATT_V_additions'],14*8*64)
        self.assertEqual(m.actions['ATT_PV_MAC'],0)
        self.assertEqual(m.actions['ATT_softmax_nonlinear'],0)
        self.assertEqual(m.actions['ATT_ising_bias_encode_vector'],0)
        self.assertEqual(m.actions['ATT_random_words'],14*2) # router only
        self.assertEqual(m.macro.calls,14)

    def test_full_decode_unknown_ppa_not_reported_as_complete(self):
        cfg,e,shape=setup(context=128)
        shape.update(num_hidden_layers=1,vocab_size=1024)
        cfg['screen_ising_v4']['samples']=8
        cfg['parallel_sampler_v5']=dict(kind='corrected_rejection',options={})
        d=ScreenParallelDigital(cfg,'digital_bf16',e,shape).run()
        self.assertIsNone(d['metrics']['scenario_mJ_per_token'])
        self.assertIsNone(d['metrics']['parameterized_area_mm2'])
        self.assertIsNone(d['quality_reference_ppl'])
        self.assertEqual(len(d['attention_v5']['requests']),14)
        self.assertGreater(d['metrics']['mean_TPOT_ms'],0)


if __name__=='__main__':unittest.main(verbosity=2)
