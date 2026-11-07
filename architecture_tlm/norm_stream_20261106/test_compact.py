import unittest
from .compact import make_model,compact_memory
from .test_model import norms_only
from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM


def create():
    return make_model(AnalyticDRAM(latency_ns=80,bandwidth_GBs=136.46),mode='ising',
        ffn='sc',samples={},layers=36,include_lm=True)


class CompactContracts(unittest.TestCase):
    def test_no_unallocated_capacity_or_phantom_ports(self):
        h,m=create()
        self.assertEqual(h.mem.capacity,2008*1024)
        self.assertEqual(h.mem.nbank,502)
        self.assertEqual(sum(h.mem.bank_allocated),h.mem.capacity)
        self.assertTrue(all(n==4096 for n in h.mem.bank_allocated))
        self.assertEqual(m.sram_compaction_contract['removed_banks'],10)
        self.assertEqual(len(h.mem.bank_depths),502)

    def test_no_physical_storage_aliases(self):
        h,m=create();locations=set()
        for r in h.mem.regions.values():
            count={b:0 for b in r.banks}
            for word in range(r.size//16):
                bank=r.banks[word%len(r.banks)]
                row=m.sram_bank_row_bases[r.name][bank]+count[bank]
                count[bank]+=1
                self.assertLess(row,256)
                self.assertNotIn((bank,row),locations)
                locations.add((bank,row))
        self.assertEqual(len(locations)*16,h.mem.capacity)

    def test_attention_capacity_and_ports_preserved(self):
        _,m=create()
        for i,r in enumerate(m.att):
            self.assertEqual(r.size,128*1024)
            self.assertEqual(r.banks,tuple(range(246+32*i,246+32*(i+1))))
        self.assertEqual(m.common_cores,12)
        self.assertEqual(m.mac_lanes,1024)

    def test_all_norm_consumers_and_real_beat_access(self):
        h,m=create();r=norms_only(m)
        self.assertEqual(r['streamed_bytes'],392192)
        self.assertEqual(r['load_counts'],{i:1 for i in range(37)})
        self.assertFalse(h.descriptors)
        self.assertFalse(h.mem.queue)
        self.assertEqual(h.report()['SRAM']['capacity_bytes'],2008*1024)

    def test_runtime_remap_rejected(self):
        h,m=create();h.now=10
        with self.assertRaises(ValueError):compact_memory(h,m)

    def test_removed_macros_really_reduce_area_and_idle(self):
        from .test_model import create as original
        h,m=create();old,_=original('stream_2m',36)
        a,b=h.mem.report(1000),old.mem.report(1000)
        self.assertAlmostEqual(b['area55eq_mm2']-a['area55eq_mm2'],10*.03322622205*.81)
        self.assertAlmostEqual(b['leakage_mJ']-a['leakage_mJ'],10*7.7544e-6*1000*1e-6)
        self.assertEqual(len(h.mem.bank_allocated),len(old.mem.bank_allocated)-10)


if __name__=='__main__':unittest.main()
