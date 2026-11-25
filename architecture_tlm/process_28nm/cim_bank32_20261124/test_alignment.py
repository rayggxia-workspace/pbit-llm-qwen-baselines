"""Clock, finite storage and RTL-derived stream partition reference tests."""
import json
from pathlib import Path
import random
import unittest
from types import SimpleNamespace
from collections import Counter
from alignment import Events, ResultSlots, cycles, physical_bytes, tile_identity, mark_unpriced_counter_delta
from rng_reference import Jump

HERE=Path(__file__).resolve().parent


class Alignment(unittest.TestCase):
    def setUp(self):
        self.contract=json.loads((HERE/'ALIGNMENT_CONTRACT.json').read_bytes())

    def test_current_clock_not_legacy_delay_conversion(self):
        class Hub:
            now=0
            def delay(self,ns):
                self.now+=ns
                if False:yield
        m=SimpleNamespace(h=Hub(),alignment=self.contract,compute=Counter())
        list(cycles(m,18,'GU')); self.assertEqual(m.h.now,72)
        list(cycles(m,34,'Wd')); self.assertEqual(m.h.now,208)
        self.assertEqual(dict(m.compute),{'GU':72,'Wd':136})

    def test_scale_bytes_use_actual_16B_words_once(self):
        self.assertEqual(physical_bytes(0,1),16)
        self.assertEqual(physical_bytes(7,2),16)
        self.assertEqual(physical_bytes(15,2),32)
        self.assertEqual(physical_bytes(80,80),80)
        self.assertEqual(physical_bytes(8192,128),128)

    def test_two_entity_slots_hold_until_accepted(self):
        e=Events(SimpleNamespace(now=0),4)
        r=ResultSlots(5,self.contract['result'],e)
        a=r.reserve(0,{'transaction_id':'A'});b=r.reserve(0,{'transaction_id':'B'})
        self.assertFalse(r.available(0))
        with self.assertRaises(ValueError):r.reserve(0,{'transaction_id':'C'})
        with self.assertRaises(AssertionError):r.read(0,a)
        r.capture(0,a);r.read(0,a);self.assertFalse(r.available(0))
        r.release(0,a);self.assertTrue(r.available(0))
        self.assertEqual(r.report()['payload_bits'],5*2*128*21)
        self.assertEqual(r.report()['metadata_bits'],5*2*33)
        self.assertFalse(r.report()['duplicate_storage_charge'])

    def test_RTL_transition_jump_matches_scalar_update(self):
        c=json.loads((HERE/'RNG_TRANSITION.json').read_bytes());j=Jump(c['row_masks'])
        for seed in (1,0x12345678,0xFEDCBA98,0xFFFFFFFF):
            s=seed
            for steps in range(513):
                if steps in (0,1,2,15,16,31,32,63,128,256,512):
                    self.assertEqual(j.jump(seed,steps),s)
                s=j.step(s)
            self.assertEqual(j.jump(j.jump(seed,12345),67890),j.jump(seed,80235))

    def test_counter128_and_result_interface_no_truncation(self):
        r=self.contract['result'];bound=64*127*128
        self.assertEqual(bound,1040384)
        for value in (-bound,bound):
            bits=value&((1<<r['stored_count_bits'])-1)
            decoded=bits-(1<<21) if bits&(1<<20) else bits
            self.assertEqual(decoded,value)
        self.assertGreater(bound,2**19-1)
        self.assertEqual(r['local_counter_bits'],r['core_output_wire_bits'])

    def test_old_PPA_is_not_presented_as_counter21(self):
        row=dict(component='FFN_shared_GU_Wd',area_mm2=1.,energy_mJ=2.)
        budget=dict(rows=[row],conditional_subsystem_area_mm2=6.)
        mark_unpriced_counter_delta(budget,self.contract)
        self.assertIsNone(budget['conditional_subsystem_area_mm2'])
        self.assertEqual(budget['reference19_conditional_subsystem_area_mm2'],6.)
        self.assertIsNone(row['area_mm2'])
        self.assertEqual(budget['reference19_FFN_core_row']['area_mm2'],1.)

    def test_logical_streams_independent_of_core_and_arrival_order(self):
        c=json.loads((HERE/'RNG_TRANSITION.json').read_bytes());j=Jump(c['row_masks'])
        seeds=(1,0x12345678,0x89ABCDEF,0xFEDCBA98);identities=[];expected={}
        for mode,samples in (('GU',16),('Wd',32)):
            streams=seeds[:1] if mode=='GU' else seeds[1:]
            for out in range(4):
                for k in range(5):
                    identity=(mode,out,k);identities.append(identity);expected[identity]=streams
                    streams=tuple(j.step(s) for s in streams) if samples==1 else tuple(j.jump(s,samples) for s in streams)
        random.Random(73).shuffle(identities)
        for index,(mode,out,k) in enumerate(identities):
            self.assertEqual(j.tile(seeds,mode,out,k,5,16 if mode=='GU' else 32),expected[(mode,out,k)])
            m=SimpleNamespace(alignment_command=7)
            ident=tile_identity(m,3,mode,out,k,5)
            self.assertEqual(ident['reference_ordinal'],out*5+k)
            self.assertEqual(ident['transaction_id'],'7/L3/%s/O%d/K%d'%(mode,out,k))


if __name__=='__main__':unittest.main()
