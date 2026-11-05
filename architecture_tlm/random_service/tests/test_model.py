import itertools
import random
import unittest
from architecture_tlm.random_service import Endpoint, SeedIngress, RandomNetwork, SeedWords, RandomPort, FullFrameArray, SigmoidTable
from architecture_tlm.random_service.backends import generate, ROWS, lfsr_step


def rank(rows):
    pivots={}
    for x in rows:
        while x:
            b=x.bit_length()-1
            if b not in pivots:
                pivots[b]=x
                break
            x ^= pivots[b]
    return len(pivots)


class CoreTests(unittest.TestCase):
    def test_shared_pairwise_certificate(self):
        for a,b in itertools.combinations(ROWS,2):
            self.assertEqual(rank(a+b),16)
        self.assertEqual(rank(sum(ROWS,[])),32)  # 512 output bits != 512 independent bits

    def test_bivium_independent_existing_reference(self):
        from architecture_tlm.rng_reference import Bivium
        for seed in (1, 0x123456789abcdef, (1<<176)+67891):
            ref=Bivium(seed,warmup_bits=0)
            state=seed
            for _ in range(20):
                words,state=generate('bivium',state)
                self.assertEqual(sum(w<<(8*i) for i,w in enumerate(words)),ref.read_word(160))
                self.assertEqual(state,ref.state)

    def test_unseeded_and_zero_rejection(self):
        p=Endpoint()
        for _ in range(20): self.assertFalse(p.tick(req_valid=True)['accepted'])
        self.assertTrue(p.tick(seed_valid=True,seed_data=0)['seed_error'])
        self.assertFalse(p.seeded)
        p.tick(seed_valid=True,seed_data=1)
        self.assertTrue(p.tick(req_valid=True)['accepted'])

    def test_hold_and_simultaneous_replace(self):
        for kind in ('lfsr32','lfsr32_shared64','bivium'):
            p=Endpoint(kind,0);p.tick(seed_valid=True,seed_data=1234567)
            while p.warm: p.tick()
            first=p.tick(req_valid=True)
            for _ in range(5):
                r=p.tick(req_valid=True,rsp_ready=False,thresholds=[0]*p.profile['lanes'])
                self.assertFalse(r['accepted']);self.assertEqual(r['words'],first['words'])
                self.assertEqual(r['state'],first['state']);self.assertEqual(r['bits'],first['bits'])
            r=p.tick(req_valid=True,rsp_ready=True)
            self.assertTrue(r['accepted'] and r['consumed'])

    def test_warmup_is_800_steps(self):
        p=Endpoint('bivium',0);p.tick(seed_valid=True,seed_data=123)
        for _ in range(5):self.assertFalse(p.tick(req_valid=True)['accepted'])
        self.assertTrue(p.tick(req_valid=True)['accepted'])
        self.assertEqual(p.counts['warmup_bits_discarded'],800)

    def test_endpoints_and_invalid_q(self):
        p=Endpoint('lfsr32_shared64',0);p.tick(seed_valid=True,seed_data=321)
        q=[0,256]*32
        self.assertEqual(p.tick(req_valid=True,thresholds=q)['bits'],tuple([False,True]*32))
        with self.assertRaises(ValueError):p.tick(thresholds=[257]*64)

    def test_reseed_drains_response(self):
        p=Endpoint('lfsr32',2);p.tick(seed_valid=True,seed_data=1)
        p.tick(req_valid=True);p.tick(rsp_ready=False)
        self.assertTrue(p.due)
        self.assertFalse(p.tick(seed_valid=True,seed_data=2,rsp_ready=False)['seed_accepted'])
        self.assertTrue(p.tick()['consumed'])
        self.assertTrue(p.tick(seed_valid=True,seed_data=2)['seed_accepted'])
        self.assertEqual(p.epoch,2)

    def test_checkpoint_replay_and_deferred_epoch(self):
        p=Endpoint('lfsr32',4);p.tick(seed_valid=True,seed_data=999)
        self.assertTrue(p.tick(command=1)['command_accepted'])
        first=[p.tick(req_valid=True)['words'] for _ in range(10)]
        p.tick();self.assertTrue(p.tick(command=2)['command_accepted'])
        second=[p.tick(req_valid=True)['words'] for _ in range(10)]
        self.assertEqual(first,second);self.assertEqual(p.epoch,1)
        p.tick();p.tick(command=3)
        self.assertFalse(p.tick(req_valid=True)['accepted'])
        p.tick(seed_valid=True,seed_data=1000);self.assertEqual(p.epoch,2)

    def test_exact_work_counts(self):
        p=Endpoint('bivium',0);p.tick(seed_valid=True,seed_data=3)
        for _ in range(5):p.tick()
        for _ in range(17):p.tick(req_valid=True)
        p.tick()
        self.assertEqual(p.counts['prng_updates'],17)
        self.assertEqual(p.counts['recurrence_steps'],800+17*160)
        self.assertEqual(p.counts['threshold_comparisons'],340)
        self.assertEqual(p.counts['responses_consumed'],17)
        self.assertIsNone(p.report()['energy_J'])

    def test_ingress_lsb_packet_padding_and_fault(self):
        g=SeedIngress(177)
        for i in range(6):g.tick(True,False,True,i+1)
        self.assertEqual(g.packet,sum((i+1)<<(32*i) for i in range(6))&((1<<177)-1))
        self.assertTrue(g.valid);self.assertFalse(g.ready(True))
        g.tick(True,True);self.assertFalse(g.valid)
        self.assertEqual(g.counts['padding_bits_discarded'],15)
        g.tick(True,False,True,10,False)
        self.assertTrue(g.fault);self.assertFalse(g.ready(True))

    def test_trace_exhaustion_is_error(self):
        s=SeedWords('trace',1,0,words=[5],provenance='test only')
        self.assertEqual(s.read(0),5)
        with self.assertRaises(RuntimeError):s.read(1)

    def test_network_concurrency_bus_round_robin(self):
        n=RandomNetwork({'b':Endpoint('bivium',0),'a':Endpoint('lfsr32',0)},
                        SeedWords('fixture',2,0,fixture_seed=8))
        for _ in range(40):n.tick({'a':None,'b':None})
        self.assertEqual([x['port'] for x in n.seed_events],['a','b'])
        self.assertEqual(len(n.source.transcript),7)
        self.assertEqual(n.ingress['b'].counts['bus_bits'],192)
        self.assertGreater(n.ports['a'].counts['prng_updates'],n.ports['b'].counts['prng_updates'])

    def test_full_frame_rejects_correlation_and_short_width(self):
        n=RandomNetwork({'a':Endpoint('lfsr32_shared64',0)},SeedWords('fixture',1,0,fixture_seed=1))
        with self.assertRaises(ValueError):FullFrameArray(n,['a'],64)
        with self.assertRaises(ValueError):FullFrameArray(n,['a'],65,True)
        f=FullFrameArray(n,['a'],64,True)
        self.assertEqual(len(f.draw_q([128]*64)['bits']),64)

    def test_full_frame_distinct_bivium_native_padding(self):
        n=RandomNetwork({str(i):Endpoint('bivium',0) for i in range(3)},
                        SeedWords('fixture',1,0,fixture_seed=6))
        f=FullFrameArray(n,['0','1','2'],51)
        r=f.draw_q([256]*51)
        self.assertTrue(all(r['bits']))
        self.assertEqual(f.counts['unused_native_lanes'],9)
        self.assertEqual([p.counts['prng_updates'] for p in n.ports.values()],[1,1,1])

    def test_sigmoid_declares_quantized_law(self):
        t=SigmoidTable()
        self.assertEqual(t.lookup([-100,0,100]),[0,128,256])
        with self.assertRaises(ValueError):t.lookup([float('nan')])

    def test_shared_input_replay_adapter(self):
        n=RandomNetwork({'x':Endpoint('lfsr32',0)},SeedWords('fixture',1,0,fixture_seed=4))
        p=RandomPort(n,'x');p.command(1)
        a=[p.shared_input(list(range(64)))['bits'] for _ in range(32)]
        p.command(2)
        b=[p.shared_input(list(range(64)))['bits'] for _ in range(32)]
        p.command(3)
        self.assertEqual(a,b)

if __name__=='__main__':unittest.main()
