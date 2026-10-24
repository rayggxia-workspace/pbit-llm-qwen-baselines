"""Actual end-to-end source calls and exact accelerator/reference contracts."""
import copy
import random
import unittest
from architecture_tlm.random_service import Endpoint, RandomNetwork, SeedWords
from architecture_tlm.random_service.backends import generate
from architecture_tlm.attention_reference_v3 import selector
from .config import tiny
from .core import Scheduler, Ledger
from .model import FullDecode
from .rng_integrated import (IntegratedRandomService,EventNetwork,FastEndpoint,
                             fast_generate,selector_parameters)


def net(cls=EventNetwork,fast=True,reseed=73):
    ep=FastEndpoint if fast else Endpoint
    return cls({'f':ep('lfsr32',reseed),'b':ep('bivium',reseed)},
        SeedWords('fixture',5,3,fixture_seed=17))


class Protocol(unittest.TestCase):
    def test_bivium_acceleration_exact(self):
        r=random.Random(114)
        for _ in range(1000):
            s=r.randrange(1,1<<177)
            self.assertEqual(fast_generate('bivium',s),generate('bivium',s))

    def test_idle_events_exact_original_cycle_model(self):
        fast=net();slow=net(RandomNetwork,False)
        r=random.Random(52)
        for end in [13,74,101,387,1000,2507]:
            while slow.cycle<end:slow.tick()
            fast.advance_to(end)
            self.assertEqual(fast.report(),slow.report())
            for _ in range(7):
                request={'f':[r.randrange(257)],'b':[r.randrange(257) for _ in range(20)]}
                readies={'f':r.choice([False,True]),'b':r.choice([False,True])}
                self.assertEqual(fast.tick(request,readies),slow.tick(request,readies))

    def test_checkpoint_deferred_reseed_exact(self):
        a,b=net(reseed=20),net(RandomNetwork,False,20)
        for _ in range(16):self.assertEqual(a.tick(),b.tick())
        for cmd in [1,0,0,2,0,3]:
            for _ in range(20):
                req={'f':[127]} if cmd==0 else {}
                self.assertEqual(a.tick(req,commands={'f':cmd}),b.tick(req,commands={'f':cmd}))
            target=a.cycle+31
            a.advance_to(target)
            while b.cycle<target:b.tick()
            self.assertEqual(a.report(),b.report())

    def test_selector_scores_equal_old_reference(self):
        r=random.Random(3);x=[r.gauss(0,1) for _ in range(1003)]
        _,old=selector(x,-1.5,1,r);new=selector_parameters(x,-1.5,1)
        self.assertEqual(new['block_scores'],old['block_scores'])
        p=[1 if i in new['forced'] else 1/(1+__import__('math').exp(-v)) for i,v in enumerate(new['drives'])]
        self.assertEqual(p,old['block_probabilities'])


class Integration(unittest.TestCase):
    def case(self,mode='screen_rejection',ffn='sc',tokens=1,reseed=100000000):
        c,m=tiny();c['random'].update(backend='integrated_service',seed_word_interval_cycles=2,
            seed_startup_cycles=3,reseed_cycles=reseed)
        c['attention']['mode']=mode;c['ffn']['mode']=ffn;c['decode_tokens']=tokens
        return c,m

    def test_clock_mismatch_rejected(self):
        c,m=self.case();c['random']['clock_hz']=200000000
        with self.assertRaises(ValueError):FullDecode(c,m)

    def test_exact_control_has_no_random_hardware(self):
        c,m=self.case('exact','bf16');r=FullDecode(c,m).run()
        self.assertIsNone(r['random_interface']['network'])
        self.assertEqual(r['random_interface']['calibrated_endpoint_area_mm2'],0)

    def test_stream_overlap_replay_lifetime(self):
        c,m=self.case('exact');model=FullDecode(c,m);r=model.run();q=r['random_interface']
        self.assertTrue(q['actual_backend_executed'])
        self.assertEqual(q['network']['clock_ns'],1e9/c['core_hz'])
        self.assertEqual(q['source_counts']['ffn_saves'],q['source_counts']['ffn_releases'])
        self.assertEqual(q['network']['ports']['ffn']['counts']['frames_generated'],q['source_counts']['ffn_samples_consumed'])
        self.assertEqual(q['network']['ports']['ffn']['counts']['responses_consumed'],q['source_counts']['ffn_samples_consumed'])
        self.assertEqual(q['random_stream_SRAM_bytes'],0)
        self.assertGreater(q['simulated_idle_edges_jumped'],0)
        self.assertNotIn('rng_uniform_bit',r['actions'])

    def test_all_new_attention_modes_use_real_words(self):
        for mode in ['pv','screen_exact','screen_pv','screen_winner','screen_rejection']:
            with self.subTest(mode=mode):
                c,m=self.case(mode);r=FullDecode(c,m).run();q=r['random_interface']
                self.assertTrue(q['actual_backend_executed'])
                if mode.startswith('screen_'):self.assertGreater(q['source_counts']['selector_calls'],0)
                if mode in ('pv','screen_pv'):self.assertGreater(q['source_counts']['pv_systematic_offsets'],0)
                if mode in ('screen_winner','screen_rejection'):
                    self.assertGreater(q['source_counts']['biased_frames'],m['num_attention_heads'])
                    self.assertNotIn('local_probability_compare',r['actions'])
                    self.assertNotIn('sampler_delegated_drive_bits',r['actions'])
                    self.assertEqual(r['actions'].get('sampler_config_bits',0),0)

    def test_across_queries_reseed_not_reconstructed(self):
        c,m=self.case('screen_pv',tokens=2,reseed=200)
        r=FullDecode(c,m).run();q=r['random_interface'];ports=q['network']['ports']
        self.assertTrue(all(p['counts']['seed_loads']>1 for p in ports.values()))
        self.assertGreater(ports['ffn']['counts']['reseed_deferred_cycles'],0)
        self.assertEqual(len(r['metrics']['token_ms']),2)
        self.assertGreater(q['network']['cycles'],200)

    def test_determinism(self):
        c,m=self.case('screen_pv');a=FullDecode(c,m).run();b=FullDecode(c,m).run()
        self.assertEqual(a,b)

    def test_source_capacity_8k_GQA(self):
        c,m=self.case();c['context_tokens']=8192
        c['sram']['capacity_bytes']=4*1024**2
        # Test provision rather than running an 8K numerical oracle.
        m.update(hidden_size=896,intermediate_size=4864,num_attention_heads=14,num_key_value_heads=2)
        model=FullDecode(c,m)
        self.assertGreaterEqual(model.rng.biased_capacity,7*128)
        self.assertGreaterEqual(len(model.rng.biased_names)*20,7*128)


if __name__=='__main__':unittest.main()
