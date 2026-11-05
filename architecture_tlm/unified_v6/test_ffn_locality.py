"""Locality conservation/finite-capacity checks; not LLM PPL or physical PPA."""
import copy
import random
import unittest
from .config import tiny
from .ffn_latest import defaults
from .ffn_locality import configure
from .model import FullDecode


def case(tile=64,engines=2,retain=8,source_groups=1):
    c,m=tiny();m.update(hidden_size=256,intermediate_size=512)
    c['ffn'].update(defaults());c['attention']['mode']='exact'
    c['schedule_policy']='shared_tiles';c['sram'].update(banks=16,fabric_GBs=16.)
    c['ffn']['local_weight_load_bytes_per_cycle']=256
    configure(c,tile=tile,engines=engines,retain=retain,source_groups=source_groups)
    return c,m


def stats(result):return result['FFN_contract']['locality_counts']


class LocalityContracts(unittest.TestCase):
    def test_same_work_less_partial_traffic(self):
        c,m=case(retain=1);a=FullDecode(c,m).run()
        c['ffn']['locality']['retain_k64_groups']=8;b=FullDecode(c,m).run()
        for k in ['SC_W8_magnitude_AND','SC_weighted_bitplane_compress_bit_work',
                  'SC_coefficient16_restore','SC_bucket_shift_reduce']:
            self.assertEqual(a['actions'][k],b['actions'][k],k)
        self.assertEqual(stats(a)['weight_bytes'],stats(b)['weight_bytes'])
        self.assertLess(stats(b).get('partial_read_bytes',0)+stats(b)['partial_write_bytes'],
                        stats(a).get('partial_read_bytes',0)+stats(a)['partial_write_bytes'])
        self.assertEqual(b['FFN_contract']['local_state']['resident_output_partial_bits'],2*64*64)

    def test_retention_formula(self):
        for r in [1,2,4,8]:
            c,m=case(retain=r);x=FullDecode(c,m).run();s=stats(x)
            h,F=m['hidden_size'],m['intermediate_size']
            expect=2*F*8*(2*((h//64+r-1)//r)-1)+h*8*(2*((F//64+r-1)//r)-1)
            self.assertEqual(s.get('partial_read_bytes',0)+s['partial_write_bytes'],expect)

    def test_128_preserves_k64_quantization_work(self):
        c,m=case(64,8,8);a=FullDecode(c,m).run()
        c,m=case(128,2,8);b=FullDecode(c,m).run()
        for k in ['SC_W8_magnitude_AND','SC_product_sign_XOR','SC_bucket_shift_reduce',
                  'SC_coefficient16_restore']:
            self.assertEqual(a['actions'][k],b['actions'][k])
        self.assertEqual(stats(a)['logical_64_tiles'],stats(b)['logical_64_tiles'])
        self.assertEqual(a['FFN_contract']['local_state']['weight_hold_bytes'],
                         b['FFN_contract']['local_state']['weight_hold_bytes'])

    def test_finite_source_rate(self):
        c,m=case(128,2,8,1);a=FullDecode(c,m).run()
        c['ffn']['locality']['source_groups']=2;b=FullDecode(c,m).run()
        self.assertGreater(stats(a)['sample_cycles'],stats(b)['sample_cycles'])
        self.assertEqual(a['actions']['SC_W8_magnitude_AND'],b['actions']['SC_W8_magnitude_AND'])

    def test_attention_unchanged(self):
        c,m=case();a=FullDecode(c,m).run();c['ffn'].pop('locality');b=FullDecode(c,m).run()
        self.assertEqual(a['attention_activity'],b['attention_activity'])
        self.assertEqual(a['row_receipts'],b['row_receipts'])

    def test_capacity_and_mask(self):
        c,m=case(128,2,8);d=FullDecode(c,m);x=d.run()
        self.assertLessEqual(d.arena.peak,c['sram']['capacity_bytes'])
        self.assertFalse(x['tile_pipeline']['sc']['pending']);self.assertFalse(x['tile_pipeline']['sc']['active'])
        self.assertIsNone(x['metrics']['full_physical_area_mm2'])
        self.assertFalse(x['FFN_contract']['nonlinear_random']['actual_endpoint_executed'])
        self.assertGreater(x['FFN_contract']['local_state']['nonlinear_context_bank_bits'],0)

    def test_resource_causality(self):
        c,m=case();c['trace_event_limit']=100000;x=FullDecode(c,m).run();by={}
        for e in x['events']:
            for r in e['resources']:by.setdefault(r,[]).append((e['start_ns'],e['end_ns']))
        for r,events in by.items():
            events.sort()
            for a,b in zip(events,events[1:]):self.assertLessEqual(a[1],b[0]+1e-5,r)
        self.assertAlmostEqual(sum(x['phase_ns'].values()),x['metrics']['elapsed_ns'])

    def test_scale_and_rounding_preserved_per_k64(self):
        # Each block's scale/rounding occurs BEFORE the local wide add. Signed
        # integer data include cancellation; compare different loop orders.
        rng=random.Random(91);K,O=10,13
        raw=[[rng.randrange(-100000,100001) for _ in range(O)] for _ in range(K)]
        coeff=[[rng.randrange(1,65536) for _ in range(O)] for _ in range(K)]
        shifts=[[rng.randrange(0,12) for _ in range(O)] for _ in range(K)]
        block=[[round(raw[k][j]*coeff[k][j]/(1<<shifts[k][j])) for j in range(O)] for k in range(K)]
        expected=[sum(block[k][j] for k in range(K)) for j in range(O)]
        for r in [1,2,4,8,16]:
            for n in [2,4,8]:
                out=[0]*O
                for kw in range(0,K,r):
                    for jo in range(0,O,n):
                        local=out[jo:jo+n]
                        for k in range(kw,min(K,kw+r)):
                            for j in range(jo,min(O,jo+n)):local[j-jo]+=block[k][j]
                        out[jo:jo+n]=local
                self.assertEqual(out,expected)

    def test_invalid_geometry(self):
        c,m=case();c['ffn']['locality']['tile']=128;c['ffn']['locality']['retain_k64_groups']=3
        with self.assertRaises(ValueError):FullDecode(c,m)

    def test_prefetch_crosses_every_window_boundary(self):
        c,m=case(retain=2);r=FullDecode(c,m).run()
        self.assertEqual(stats(r)['cross_window_prefetches'],(4//2-1)+(8//2-1))
        self.assertFalse(r['tile_pipeline']['sc']['pending'])

if __name__=='__main__':unittest.main()
