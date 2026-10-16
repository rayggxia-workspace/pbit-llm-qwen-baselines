"""Numerical invariants, resource causality, memory traffic, integrated decode."""
import copy
import json
import math
import random
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from attention_reference_v3 import softmax,categorical,selector,ising_random_scan,TraceSource
from attention_tlm_v3 import AttentionDigitalDecode,AttentionLocalDecode,MODES
from run_attention_v3 import configuration


def make(mode='pv',length=64,samples=32):
    cfg,evidence,shape=configuration()
    shape.update(num_hidden_layers=1,vocab_size=1024)
    cfg.update(context_tokens=length,decode_tokens=1)
    cfg['attention_v3'].update(mode=mode,samples=samples,ising_burn_sweeps=4,ising_spacing_sweeps=2)
    return cfg,evidence,shape


class AttentionTests(unittest.TestCase):
    def test_softmax_and_iid(self):
        p=softmax([0,1,-2]);ids=categorical(p,100000,random.Random(1));c=Counter(ids)
        for i,probability in enumerate(p):self.assertAlmostEqual(c[i]/len(ids),probability,delta=.006)

    def test_ising_stationary_and_attempts(self):
        logits=[0.,1.,-2.];n=100000
        ids,s=ising_random_scan(logits,n,32,4,random.Random(7));c=Counter(ids)
        for i,p in enumerate(softmax(logits)):self.assertAlmostEqual(c[i]/n,p,delta=.008)
        self.assertEqual(s['attempts'],2*(32+4*n));self.assertGreater(s['flips'],0)
        self.assertEqual(ising_random_scan([9],3,4,2,random.Random(0))[0],[0,0,0])

    def test_ising_uniform_and_extreme(self):
        ids,_=ising_random_scan([0]*5,50000,16,4,random.Random(3))
        for count in Counter(ids).values():self.assertAlmostEqual(count/len(ids),.2,delta=.012)
        ids,_=ising_random_scan([0,-1000],16,16,4,random.Random(0));self.assertEqual(set(ids),{0})

    def test_selector_forced_and_partial(self):
        indices,info=selector([0.]*257,-100.,1.,random.Random(1))
        self.assertEqual(info['selected_blocks'],[0,3,4])
        self.assertEqual(len(indices),129)
        self.assertEqual(max(indices),256)

    def test_trace_validation(self):
        cfg,e,s=make()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trace.json';path.write_text(json.dumps({'rows':[{'token':0,'layer':0,'head':0,'logits':[1,2]}]}))
            cfg['attention_v3']['trace_file']=str(path);source=TraceSource(cfg['attention_v3'],s)
            self.assertEqual(source.logits(0,0,0,2),[1,2])
            with self.assertRaises(ValueError):source.logits(0,0,0,3)
            with self.assertRaises(ValueError):source.logits(0,0,1,2)

    def test_all_modes_transactions(self):
        for mode in MODES:
            cfg,e,s=make(mode)
            m=AttentionDigitalDecode(cfg,'digital_bf16',e,s);end=m.attention(0,64,0)
            self.assertGreater(end,0)
            self.assertEqual(m.actions['ATT_QK_MAC'],m.actions['ATT_selected_QK_tokens']*64)
            self.assertGreater(m.traffic['attention_scratch_read_bytes'],0)
            resources={}
            for event in m.attn_events:
                self.assertGreaterEqual(event['end_ns'],event['start_ns'])
                resource=event['resource']
                self.assertGreaterEqual(event['start_ns']+1e-8,resources.get(resource,0))
                resources[resource]=event['end_ns']
                if 'address' in event:self.assertEqual(event['address']%64,0)
            if mode in ('pv','ising','screen_pv'):
                self.assertEqual(m.actions['ATT_PV_MAC'],0)
                self.assertEqual(m.actions['ATT_V_additions'],14*32*64)
                self.assertGreater(m.actions['ATT_random_words'],0)
            else:self.assertEqual(m.actions['ATT_PV_MAC'],m.actions['ATT_QK_MAC'])

    def test_bandwidth_and_rng_are_not_free(self):
        cfg,e,s=make('pv',128,64)
        fast=AttentionDigitalDecode(cfg,'digital_bf16',e,s);t0=fast.attention(0,128,0)
        slow=copy.deepcopy(cfg);slow['scratchpad']['bandwidth_GBs']=.01
        m=AttentionDigitalDecode(slow,'digital_bf16',e,s);self.assertGreater(m.attention(0,128,0),t0)
        slow=copy.deepcopy(cfg);slow['attention_v3']['rng_words_per_cycle']=1
        m=AttentionDigitalDecode(slow,'digital_bf16',e,s);self.assertGreater(m.attention(0,128,0),t0)

    def test_duplicate_v_cache(self):
        cfg,e,s=make('pv');m=AttentionDigitalDecode(cfg,'digital_bf16',e,s)
        m.coord=dict(token=0,layer=0)
        from collections import OrderedDict
        cache=OrderedDict();t=m.gather(0,0,0,[4]*32,cache)
        self.assertEqual(m.actions['ATT_V_cache_misses'],1)
        m.gather(t,0,1,[4]*32,cache)
        self.assertEqual(m.actions['ATT_V_cache_misses'],1)
        self.assertEqual(m.actions['ATT_V_cache_hits'],1)
        self.assertEqual(m.actions['ATT_V_additions'],64*64)

    def test_summary_update_charged(self):
        cfg,e,s=make('screen_exact',256);cfg['decode_tokens']=2
        m=AttentionDigitalDecode(cfg,'digital_bf16',e,s)
        t=m.attention(0,256,0);build=m.actions['ATT_summary_build_vector']
        m.attention(t,257,0)
        self.assertEqual(build,m.actions['ATT_summary_build_vector'])
        self.assertEqual(m.actions['ATT_summary_update_vector'],128)
        self.assertGreater(m.traffic['external_ATT_summary_write_burst_bytes'],0)

    def test_sparse_union_traffic(self):
        cfg,e,s=make('screen_exact',512);cfg['attention_v3']['selector_bias']=-100
        cfg['attention_v3']['summary_initialization']='prefill_prebuilt'
        m=AttentionDigitalDecode(cfg,'digital_bf16',e,s);m.attention(0,512,0)
        self.assertEqual(m.actions['ATT_selected_QK_tokens'],14*192)
        self.assertEqual(m.traffic['attention_KV_fused_useful_bytes'],192*512)

    def test_small_integrated_decode_energy_closure(self):
        cfg,e,s=make('pv',64,16)
        for cls,variant in ((AttentionDigitalDecode,'digital_bf16'),(AttentionLocalDecode,'fixed_sc_exact')):
            m=cls(cfg,variant,e,s);d=m.run()
            self.assertAlmostEqual(d['metrics']['scenario_mJ_per_token'],sum(d['energy_J'].values())*1000)
            self.assertAlmostEqual(d['metrics']['mean_TPOT_ms'],sum(d['time_ns'].values())/1e6)
            self.assertIsNone(d['quality_reference_ppl'])
            self.assertEqual(d['actions']['ATT_V_sample_events'],14*16)
            self.assertGreater(d['metrics']['attention_ms_per_token'],0)

    def test_capacity_failure(self):
        cfg,e,s=make('pv',8192);cfg['scratchpad']['capacity_MiB']=.01
        with self.assertRaises(ValueError):
            m=AttentionDigitalDecode(cfg,'digital_bf16',e,s);m.attention(0,8192,0)


if __name__=='__main__':unittest.main(verbosity=2)
