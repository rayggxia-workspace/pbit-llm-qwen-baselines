import copy
import hashlib
import json
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rng_hierarchy import EntropyBudget,HierarchicalRng,retry_statistics
from rng_reference import Bivium,FunctionalRng,derive_state
from system_decode import DecodeModel,load

ROOT=Path(__file__).resolve().parents[1]


class HierarchyTests(unittest.TestCase):
    def setUp(self):
        self.c=json.loads((ROOT/'configs/rng_hierarchy_v1.json').read_text())

    def test_entropy_block_accounting_and_health_failure(self):
        e=EntropyBudget(self.c['entropy'])
        self.assertEqual(e.request(0,128),267000)
        self.assertEqual(e.request(e.free,128),267000)
        self.assertEqual(e.blocks,1)
        self.assertEqual(e.credit,0)
        self.assertEqual(e.raw_samples,1024)
        e.healthy=False
        with self.assertRaises(RuntimeError):e.request(e.free,1)
        self.c['entropy']['output_bits_per_block']=512
        with self.assertRaises(ValueError):EntropyBudget(self.c['entropy'])

    def test_seed_bus_and_startup_only_policy(self):
        self.c['seed']['reseed_interval_ns']=0
        r=HierarchicalRng(self.c,8,1e8)
        t=r.ensure_seeded(0)
        self.assertEqual(r.stats['seed_wire_bits'],2056*192)
        self.assertEqual(r.entropy.delivered,256)
        self.assertEqual(t,267000+math.ceil(2056*192/256)*10+2056*6*10+50)
        r.shared_words(1e12,100)
        self.assertEqual(r.epoch,0)

    def test_periodic_reseed_waits_for_busy_local_arrays(self):
        self.c['seed']['reseed_interval_ns']=100
        r=HierarchicalRng(self.c,8,1e8)
        t=r.ensure_seeded(0)
        done,_=r.weight_wave(t,8,4096)
        next_done,_=r.shared_words(t+200,128)
        self.assertEqual(r.epoch,1)
        self.assertGreaterEqual(r.events[-1]['start_ns'],done)
        self.assertGreater(next_done,done)
        self.assertEqual(r.entropy.delivered,512)

    def test_local_parallelism_and_inactive_engines(self):
        a=HierarchicalRng(self.c,8,1e8);b=HierarchicalRng(self.c,8,1e8)
        ta=a.ensure_seeded(0);tb=b.ensure_seeded(0)
        _,da=a.weight_wave(ta,1,4096);_,db=b.weight_wave(tb,8,4096)
        self.assertAlmostEqual(da,db,delta=10)
        self.assertEqual(b.stats['local_core_updates_expected'],8*a.stats['local_core_updates_expected'])
        self.assertEqual(b.stats['weight_bernoulli_outputs'],8*4096*4096)
        report=b.finish(b.local_free)
        self.assertGreater(report['energy_J']['RNG_local_updates'],0)
        with self.assertRaises(ValueError):b.finish(0)

    def test_candidate_underprovision_and_retry(self):
        with self.assertRaises(ValueError):retry_statistics(63)
        p,t=retry_statistics(64)
        self.assertAlmostEqual(p,(254/256)**64,places=12)
        self.assertGreater(t,1/p)
        self.assertLess(retry_statistics(80)[1],1.000001)

    def test_integration_keeps_work_and_no_legacy_double_charge(self):
        c,e,s=load();c['decode_tokens']=2;c['samples']=256;c['context_tokens']=128
        s['num_hidden_layers']=1;s['vocab_size']=1024
        old=DecodeModel(c,'dual_sc_sz',e,s).run()
        c['rng']['architecture']='hierarchical_v1';c['rng_hierarchy']=self.c
        new=DecodeModel(c,'dual_sc_sz',e,s).run()
        self.assertEqual(old['actions'],new['actions'])
        self.assertEqual(old['traffic'],new['traffic'])
        self.assertNotIn('RNG_sources',new['energy_J'])
        self.assertNotIn('RNG_fabric_FIFO',new['energy_J'])
        self.assertEqual(new['rng_hierarchy']['local_instances'],2048)
        self.assertLess(new['metrics']['mean_TPOT_ms'],old['metrics']['mean_TPOT_ms'])
        self.assertAlmostEqual(sum(new['energy_J'].values())*500,new['metrics']['scenario_mJ_per_token'])
        self.assertAlmostEqual(sum(new['time_ns'].values())/new['events'][-1]['end_ns'],1)
        self.assertEqual(new['events'][0]['name'],'RNG_startup')
        fixed=DecodeModel(c,'fixed_sc_exact',e,s).run()
        self.assertEqual(fixed['rng_hierarchy']['local_instances'],0)
        digital=DecodeModel(c,'digital_bf16',e,s).run()
        self.assertNotIn('rng_hierarchy',digital)


class ReferenceTests(unittest.TestCase):
    def test_recurrence_against_separate_bit_array_oracle(self):
        state=int.from_bytes(hashlib.sha256(b'oracle').digest(),'little')&((1<<177)-1)
        bits=[(state>>i)&1 for i in range(177)]
        expected=0
        for k in range(1024):
            first=bits[65]^bits[92];second=bits[161]^bits[176]
            expected|=(first^second)<<k
            left=second^(bits[174]&bits[175])^bits[68]
            right=first^(bits[90]&bits[91])^bits[170]
            bits=[left]+bits[:92]+[right]+bits[93:176]
        r=Bivium(state,0)
        self.assertEqual(r.read_word(1024),expected)
        self.assertEqual(r.state,sum(b<<i for i,b in enumerate(bits)))
        a=Bivium(state,0)
        self.assertEqual(a.read_word(160)|(a.read_word(864)<<160),expected)
        with self.assertRaises(ValueError):Bivium(0)

    def test_domains_epochs_persistent_state_and_replay_contract(self):
        seed=hashlib.sha256(b'test').digest()
        states={derive_state(seed,e,d,(i,)) for e in range(2) for d in ('weight','shared-input') for i in range(32)}
        self.assertEqual(len(states),128)
        a=FunctionalRng(seed);b=FunctionalRng(seed)
        p=[[0,127,64,32]*16 for _ in range(2)]
        wa,_=a.weight_bits(0,p);wb,_=b.weight_bits(0,p)
        self.assertEqual(wa,wb)
        self.assertTrue(all(row[0]==0 and row[1]==1 for row in wa))
        self.assertNotEqual(a.weight_bits(0,p)[0],wa)
        x=a.input_bits([0,2048,4096],replay_key='token/row/sample')
        self.assertEqual(x,a.input_bits([0,2048,4096],replay_key='token/row/sample'))
        self.assertEqual((x[0],x[2]),(0,1))
        with self.assertRaises(ValueError):a.input_bits([1],replay_key='token/row/sample')
        with self.assertRaises(ValueError):a.reseed(seed,0)
        a.reseed(seed,1)
        self.assertNotEqual(a.weight_bits(0,p)[0],wa)

    def test_uniform127_conversion_is_exact_and_probability_mean(self):
        bins=[0]*127
        for value in range(254):bins[value//2]+=1
        self.assertEqual(set(bins),{2})
        r=FunctionalRng(hashlib.sha256(b'mean-check').digest())
        count=0;total=0
        for _ in range(128):
            bits,diag=r.weight_bits(0,[[64]*64 for _ in range(4)])
            count+=sum(map(sum,bits));total+=256
            self.assertGreaterEqual(diag['cycles'],1)
        self.assertAlmostEqual(count/total,64/127,delta=.02)

    def test_functional_underflow_retries_match_macro_expectation(self):
        r=FunctionalRng(hashlib.sha256(b'underflow').digest(),output_bits=128,warmup_cycles=6)
        cycles=updates=0
        for _ in range(512):
            _,d=r.weight_bits(0,[[64]*64 for _ in range(4)])
            cycles+=d['cycles'];updates+=d['core_updates']
        success,expected=retry_statistics(64,64,4)
        self.assertGreater(cycles,512)
        self.assertAlmostEqual(cycles/512,expected,delta=.2)
        self.assertAlmostEqual(updates/(512*4*4),1/success,delta=.1)


if __name__=='__main__':unittest.main(verbosity=2)
