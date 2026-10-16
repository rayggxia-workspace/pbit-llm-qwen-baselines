import copy
import json
import random
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_screen_ising_v4 import setup
from screen_ising_tlm_v4 import ScreenIsingLocal,ScreenIsingDigital,budget_blocks
from ising_macro_v4 import IsingMacro


class Tests(unittest.TestCase):
    def test_budget_overflow_underfill_and_forced(self):
        scores=list(range(12))
        for chosen in ([],list(range(12)),[1,2,3]):
            result=budget_blocks(scores,chosen,5)
            self.assertEqual(len(result),5);self.assertTrue({0,10,11}<=set(result))
        with self.assertRaises(ValueError):budget_blocks(scores,[],2)

    def test_short_context(self):
        self.assertEqual(budget_blocks([2],[0],8),[0])
        self.assertEqual(budget_blocks([2,1],[0,1],8),[0,1])

    def macro(self):
        cfg,_,_=setup();return IsingMacro(cfg['screen_ising_v4']['ising'],512)

    def test_mask_and_configuration_capacity(self):
        m=self.macro();ids,s=m.request(0,[0.,2.,-1.],64,random.Random(0),(0,0,0),[1,8,99])
        self.assertTrue(set(ids)<={0,1,2});self.assertEqual(s['masked_slots'],509)
        self.assertEqual(s['config_bits'],512*17);self.assertEqual(s['retained_internal_output_indices'],1)
        with self.assertRaises(ValueError):m.request(0,[0]*513,1,random.Random(1),(0,0,0),list(range(513)))

    def test_sample_time_and_idle_energy(self):
        a=self.macro();b=self.macro()
        _,x=a.request(0,[0,1],16,random.Random(1),(0,0,0),[1,2])
        _,y=b.request(0,[0,1],32,random.Random(1),(0,0,0),[1,2])
        self.assertAlmostEqual(y['end_ns']-x['end_ns'],16*100)
        self.assertEqual(a.area_mm2,b.area_mm2)
        self.assertGreater(a.finish(x['end_ns']+1000)['idle_J'],0)

    def test_output_backpressure(self):
        m=self.macro();_,s=m.request(0,[0,1],8,random.Random(0),(0,0,0),[1,2],output_ns_per_index=200)
        self.assertEqual(s['effective_sample_period_ns'],200)
        self.assertEqual(s['end_ns']-s['first_sample_ns'],8*200)

    def test_trace_contract(self):
        cfg,_,_=setup();c=copy.deepcopy(cfg['screen_ising_v4']['ising'])
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'trace.json';p.write_text(json.dumps({'rows':[dict(token=0,layer=0,head=0,candidate_ids=[4,9],local_indices=[1,0])]}))
            c.update(numerical_source='sample_trace',sample_trace_file=str(p))
            m=IsingMacro(c,512);ids,_=m.request(0,[0,1],2,random.Random(),(0,0,0),[4,9]);self.assertEqual(ids,[1,0])
            with self.assertRaises(ValueError):m.request(0,[0,1],2,random.Random(),(0,0,0),[4,8])

    def test_fixed_compact_path_no_double_sampling(self):
        cfg,e,s=setup(context=2048);cfg['screen_ising_v4']['samples']=16
        m=ScreenIsingDigital(cfg,'digital_bf16',e,s);m.attention(0,2048,0)
        self.assertEqual(m.actions['ATT_QK_MAC'],14*512*64)
        self.assertEqual(m.actions['ATT_random_words'],14*32) # router only
        self.assertEqual(m.actions['ATT_Ising_output_indices'],14*16)
        self.assertEqual(m.actions['ATT_V_additions'],14*16*64)
        self.assertEqual(m.actions['ATT_PV_MAC'],0)
        self.assertEqual(m.actions['ATT_softmax_nonlinear'],0)
        self.assertEqual(m.actions['ATT_cdf_vector'],0)
        self.assertEqual(m.actions['ATT_ising_attempts'],0)
        self.assertTrue(all(r['selected_tokens']==512 for r in m.attn_rows))

    def test_tail_padding_and_mapping(self):
        cfg,e,s=setup(context=2049);cfg['screen_ising_v4']['samples']=8
        m=ScreenIsingDigital(cfg,'digital_bf16',e,s);m.attention(0,2049,0)
        self.assertTrue(all(r['selected_tokens']==449 and r['masked_slots']==63 for r in m.attn_rows))
        for r in m.attn_rows:self.assertIn(2048,r['candidate_map'])

    def test_variable_overflow_rejected(self):
        cfg,e,s=setup('variable',512);cfg['screen_ising_v4']['candidate_capacity']=128
        cfg['attention_v3'].update(selector_bias=100,calibration_file=None)
        m=ScreenIsingDigital(cfg,'digital_bf16',e,s)
        with self.assertRaises(ValueError):m.attention(0,512,0)

    def test_full_decode_ledger_and_resource_causality(self):
        cfg,e,s=setup(context=128);s.update(num_hidden_layers=1,vocab_size=1024)
        cfg['screen_ising_v4']['samples']=16
        m=ScreenIsingLocal(cfg,'fixed_sc_exact',e,s);d=m.run()
        self.assertAlmostEqual(d['metrics']['scenario_mJ_per_token'],sum(d['energy_J'].values())*1000)
        self.assertAlmostEqual(d['metrics']['mean_TPOT_ms'],sum(d['time_ns'].values())/1e6)
        self.assertEqual(d['attention_v4']['ising']['calls'],14)
        resources=defaultdict(float)
        for ev in d['attention_v4']['events']:
            r=ev['resource'];self.assertGreaterEqual(ev['start_ns']+1e-7,resources[r]);resources[r]=ev['end_ns']
        self.assertIsNone(d['quality_reference_ppl'])


if __name__=='__main__':unittest.main(verbosity=2)
