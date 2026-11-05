import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from winner_hold_tlm_v5 import WinnerHoldSampler
from corrected_rejection_tlm_v5 import CorrectedRejectionSampler
from architecture_tlm.random_service import RandomNetwork, Endpoint, SeedWords
from architecture_tlm.random_service.sampler_adapter import TimedSamplerSource

class AdapterTests(unittest.TestCase):
    def source(self,interval):
        n=RandomNetwork({'p':Endpoint('bivium',200),'fair':Endpoint('bivium',200)},
                         SeedWords('fixture',interval,3,fixture_seed=91))
        return TimedSamplerSource(n,['p'],'fair',capacity=8)

    def test_both_real_samplers_use_timed_source(self):
        for cls in (WinnerHoldSampler,CorrectedRejectionSampler):
            src=self.source(3)
            m=cls(dict(record_events=True),capacity=8)
            result,receipt=m.request(0,[0,-.1,-.3,-.5,-1,-1.2,-2,-3],16,
                                     random.Random(1),'fixture',list(range(8)),source=src)
            self.assertEqual(len(result),16)
            self.assertIn('timed_local_prng',receipt['source_backend'])
            self.assertFalse(receipt['numerical_source']['independent_ideal_response'])
            self.assertGreaterEqual(receipt['end_ns'],src.network.cycle*src.network.clock_ns)
            self.assertIsNone(receipt['physical_dynamic_energy_J'])
            self.assertGreater(src.network.ports['p'].counts['prng_updates'],0)

    def test_slow_seed_bus_increases_sampler_time(self):
        times=[]
        for interval in (1,20):
            src=self.source(interval)
            m=WinnerHoldSampler(capacity=8)
            _,r=m.request(0,[0]*8,4,random.Random(0),'same',list(range(8)),source=src)
            times.append(r['end_ns'])
        self.assertGreater(times[1],times[0])

    def test_single_candidate_rejection_has_no_biased_draw(self):
        src=self.source(1);m=CorrectedRejectionSampler(capacity=1)
        result,_=m.request(0,[0],3,random.Random(0),'one',[0],source=src)
        self.assertEqual(result,[0,0,0])
        self.assertEqual(src.network.ports['p'].counts['prng_updates'],0)

if __name__=='__main__':unittest.main()
