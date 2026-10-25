import unittest
from unittest.mock import patch
import numpy as np
from .ideal_readout import conditioned, packets, simulate, TimedWords, RandomNetwork, skip_wait
from ..model import Endpoint


class TimedReplayTests(unittest.TestCase):
    def test_vn_time_and_tail(self):
        b, t = conditioned([0,1,1,1,1,0,0], np.arange(7), 'vn')
        self.assertEqual(b.tolist(), [0,1])
        self.assertEqual(t.tolist(), [1,5])

    def test_pack_waits_for_last_raw_sample(self):
        b = np.arange(64,dtype=np.uint8)%2
        e = packets(b,np.arange(64))
        s = TimedWords(e,'test')
        self.assertIsNone(s.read(3100))
        self.assertEqual(s.read(3101), 0xaaaaaaaa)
        self.assertEqual(s.read(6301), 0xaaaaaaaa)
        with self.assertRaises(RuntimeError):s.read(9999)

    def test_exact_idle_contraction(self):
        b = np.random.default_rng(19).integers(0,2,512,dtype=np.uint8)
        for kind in ('lfsr32','lfsr32_shared64','bivium'):
            for mode in ('raw','vn'):
                # Extra input ensures two Bivium packets after VN.
                bits = np.tile(b,8)
                c, t = conditioned(bits,np.arange(len(bits)),mode)
                e = packets(c,t,cycles_per_sample=2)
                nets = []
                def capture(*args, **kwargs):
                    n = RandomNetwork(*args, **kwargs)
                    nets.append(n)
                    return n
                with patch('architecture_tlm.random_service.quality.ideal_readout.RandomNetwork', capture):
                    fast, x, y, cycles = simulate(kind,e,256,True)
                    slow, xx, yy, cc = simulate(kind,e,256,False)
                self.assertEqual(fast['status'],'complete')
                self.assertEqual(fast['network'],slow['network'])
                for port in ('a','b'):
                    self.assertEqual(vars(nets[0].ports[port]),vars(nets[1].ports[port]))
                    self.assertEqual(vars(nets[0].ingress[port]),vars(nets[1].ingress[port]))
                self.assertEqual((nets[0].rr,nets[0].target,nets[0].source.index),
                                 (nets[1].rr,nets[1].target,nets[1].source.index))
                np.testing.assert_array_equal(x,xx)
                np.testing.assert_array_equal(y,yy)
                np.testing.assert_array_equal(cycles,cc)

    def test_skip_stops_at_reseed_due_edge(self):
        nets = []
        for _ in range(2):
            n = RandomNetwork({k:Endpoint('lfsr32',10) for k in ('a','b')},
                              TimedWords([dict(word=7,available_cycle=100)],'test'))
            n.ports['a'].seeded = True
            n.ports['a'].state = 11
            n.ports['a'].age = 5
            n.target = 'b'
            nets.append(n)
        self.assertEqual(skip_wait(nets[0],200),5)
        for _ in range(5):nets[1].tick()
        self.assertTrue(nets[0].ports['a'].due)
        for port in ('a','b'):
            self.assertEqual(vars(nets[0].ports[port]),vars(nets[1].ports[port]))
        self.assertEqual(nets[0].cycle,nets[1].cycle)
        self.assertEqual(nets[0].source.transcript,nets[1].source.transcript)

    def test_exhaustion_does_not_repeat(self):
        r, x, y, c = simulate('bivium',packets(np.ones(32,dtype=np.uint8),np.arange(32)),256)
        self.assertEqual(r['status'],'incomplete')
        self.assertIn('exhausted',r['failure'])
        self.assertEqual(len(x),0)

    def test_reject_zero_without_repair(self):
        b = np.concatenate([np.zeros(32,dtype=np.uint8),np.ones(64,dtype=np.uint8)])
        r, x, y, c = simulate('lfsr32',packets(b,np.arange(len(b))),256)
        self.assertEqual(r['status'],'complete')
        self.assertEqual(sum(p['counts'].get('zero_seeds_rejected',0) for p in r['network']['ports'].values()),1)
        self.assertEqual(len(r['network']['seed_word_transcript']),3)


if __name__=='__main__':unittest.main()
