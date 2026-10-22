"""Executable interface checks using the unchanged merged Issue95 backend.

This is a connection proof, not full-model source timing or PPL validation.
"""
import copy
import random
import unittest

from architecture_tlm.random_service import Endpoint, RandomNetwork, SeedWords
from architecture_tlm.random_service.sampler_adapter import TimedSamplerSource
from architecture_tlm.random_service.service import FullFrameArray, RandomPort
from .model import bucket_code, bitplane_reference
from .rng_frontend import stratified_shared64, uniform32
from corrected_rejection_tlm_v5 import CorrectedRejectionSampler
from winner_hold_tlm_v5 import WinnerHoldSampler


def network(ports, seed=0, interval=1):
    return RandomNetwork(ports, SeedWords('fixture', interval, 2, fixture_seed=seed))


def sampler_probe(cls, seed):
    net = network({'biased':Endpoint('bivium',0), 'fair':Endpoint('bivium',0)}, seed)
    src = TimedSamplerSource(net,['biased'],'fair',capacity=16)
    sampler = cls(dict(record_events=True,max_proposals_per_sample=128),capacity=16)
    result, receipt = sampler.request(0,[-i/7 for i in range(16)],16,random.Random(seed),
        ('interface',seed),list(range(16)),source=src,output_ns_per_index=30)
    return net,src,sampler,result,receipt


class InterfaceTests(unittest.TestCase):
    def port(self,seed=0,reseed=0):
        n=network({'ffn':Endpoint('lfsr32',reseed)},seed)
        return RandomPort(n,'ffn')

    def test_stratified64_replay_three_seeds(self):
        for seed in range(3):
            p=self.port(seed,16)
            codes=bucket_code([((-1)**i)*i/13 for i in range(64)],4)
            p.command(1)
            first=list(stratified_shared64(p,codes))
            self.assertEqual([r['threshold']//8 for r in first],list(range(32)))
            self.assertEqual(len({r['epoch'] for r in first}),1)
            p.command(2)
            second=list(stratified_shared64(p,codes))
            self.assertEqual([(r['threshold'],r['bits']) for r in first],
                             [(r['threshold'],r['bits']) for r in second])
            self.assertEqual(p.endpoint.counts['seed_loads'],1)
            self.assertGreater(p.endpoint.counts['reseed_deferred_cycles'],0)
            p.command(3)
            for _ in range(20):p.network.tick()
            self.assertGreaterEqual(p.endpoint.counts['seed_loads'],2)
            self.assertFalse(p.endpoint.locked)

    def test_frontend_matches_v6_exact_bitplane_oracle(self):
        p=self.port()
        codes=bucket_code([((-1)**i)*i/17 for i in range(64)],4)
        weights=[(i*7)%256-128 for i in range(64)]
        emitted=list(stratified_shared64(p,codes))
        direct=sum(sum(w*c['sign']*c['scale']*b for w,c,b in zip(weights,codes,r['bits']))
                   for r in emitted)/len(emitted)
        oracle=bitplane_reference(weights,codes,[r['threshold'] for r in emitted],4)
        self.assertAlmostEqual(direct,oracle,places=11)

    def test_exact_zero_and_one(self):
        codes=[dict(q=0,one=False),dict(q=255,one=True)]*32
        rows=list(stratified_shared64(self.port(),codes))
        self.assertTrue(all(not b for r in rows for b in r['bits'][::2]))
        self.assertTrue(all(b for r in rows for b in r['bits'][1::2]))

    def test_native_shared_input_is_not_stratified_shortcut(self):
        p=self.port(); codes=[dict(q=128,one=False)]*64
        p.command(1); strat=list(stratified_shared64(p,codes))
        p.command(2); native=[p.shared_input([128]*64)['bits'] for _ in range(32)]
        self.assertNotEqual([r['bits'] for r in strat],native)
        p.command(3)

    def test_reject_invalid_strata_and_GF64_frontend(self):
        codes=[dict(q=0,one=False)]*64
        for k in (0,3,512):
            with self.assertRaises(ValueError):list(stratified_shared64(self.port(),codes,strata=k))
        p=RandomPort(network({'gf':Endpoint('lfsr32_shared64',0)}),'gf')
        with self.assertRaises(ValueError):list(stratified_shared64(p,codes))

    def test_PV_uniform32_has_four_real_single_word_updates(self):
        p=self.port(); r=uniform32(p)
        self.assertTrue(0<=r['value']<2**32)
        self.assertEqual(p.endpoint.counts['prng_updates'],4)
        self.assertEqual(p.endpoint.counts['random_word_bits_generated'],32)
        self.assertGreaterEqual(r['service_cycles'],4)

    def test_PV_native_wide_generation_charges_unused_words(self):
        p=RandomPort(network({'pv':Endpoint('bivium',0)}),'pv')
        uniform32(p)
        self.assertEqual(p.endpoint.counts['prng_updates'],1)
        self.assertEqual(p.endpoint.counts['random_word_bits_generated'],160)
        self.assertEqual(p.counts['unused_native_bytes'],16)

    def test_full512_frame_really_has_26_Bivium_ports(self):
        names=['b%02d'%i for i in range(26)]
        n=network({name:Endpoint('bivium',0) for name in names},17)
        array=FullFrameArray(n,names,512)
        result=array.draw_q([0,256]*256)
        self.assertEqual(result['bits'],[False,True]*256)
        self.assertEqual(array.counts['unused_native_lanes'],8)
        self.assertEqual(sum(p.counts['prng_updates'] for p in n.ports.values()),26)
        self.assertEqual(sum(g.counts['bus_beats'] for g in n.ingress.values()),156)

    def test_attention_rejects_insufficient_capacity_and_GF(self):
        n=network({'b':Endpoint('bivium',0)})
        with self.assertRaises(ValueError):FullFrameArray(n,['b'],512)
        g=network({'g':Endpoint('lfsr32_shared64',0)})
        with self.assertRaises(ValueError):FullFrameArray(g,['g'],32)

    def test_both_samplers_connect_three_seeds_without_double_source_time(self):
        for cls in (WinnerHoldSampler,CorrectedRejectionSampler):
            for seed in range(3):
                net,src,_,out,r=sampler_probe(cls,seed)
                self.assertEqual(len(out),16)
                self.assertTrue(all(0<=i<16 for i in out))
                self.assertEqual(r['source_backend'],src.kind)
                self.assertFalse(r['numerical_source']['independent_ideal_response'])
                self.assertGreaterEqual(r['end_ns'],net.cycle*net.clock_ns)
                self.assertIsNone(r['physical_dynamic_energy_J'])

    def test_successive_queries_keep_source_clock_and_cumulative_ledger(self):
        net,src,sampler,_,r=sampler_probe(WinnerHoldSampler,0)
        before=copy.deepcopy(net.report()); t=r['end_ns']
        _,second=sampler.request(t+100,[0]*16,4,random.Random(2),'second',list(range(16)),source=src)
        after=net.report()
        self.assertGreater(after['cycles'],before['cycles'])
        self.assertGreaterEqual(second['start_ns'],t+100)
        delta=after['ports']['biased']['counts']['prng_updates']-before['ports']['biased']['counts']['prng_updates']
        self.assertEqual(delta,second['actions']['proposal_frames'])
        self.assertEqual(after['ports']['biased']['counts']['seed_loads'],1)


if __name__=='__main__':unittest.main()
