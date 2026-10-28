import copy
import unittest
from .config import load
from .model import FullDecode
from .resource_sweep import apply,PROFILES
from .test_memory_pipeline_contracts import case


class ResourceSweep(unittest.TestCase):
    def matrix(self,prefill,macs=1,bandwidth=1000.,name='L0/gu'):
        c,m=case();c.update(schedule_policy='shared_tiles',macs_per_cycle=macs,
            trace_event_limit=100000,digital_shared_prefill=prefill)
        c['ffn']['mode']='bf16';c['dram']['bandwidth_GBs']=bandwidth
        d=FullDecode(c,m);t=d.matrix(0,name)
        return d,t

    def test_same_storage_bytes_and_work(self):
        a,ta=self.matrix(False);b,tb=self.matrix(True)
        self.assertEqual(dict(a.mem.traffic),dict(b.mem.traffic))
        self.assertEqual(dict(a.dram.traffic),dict(b.dram.traffic))
        self.assertEqual(dict(a.e.actions),dict(b.e.actions))
        self.assertEqual(a.tile_pipeline.digital_capacity,b.tile_pipeline.digital_capacity)
        self.assertEqual(a.arena.regions,b.arena.regions)
        self.assertLess(tb,ta)
        self.assertGreater(b.tile_pipeline.counts['digital']['prefill_ready_before_previous_compute_end'],0)

    def test_ownership_and_dependencies(self):
        d,t=self.matrix(True)
        r=d.tile_pipeline.report()['digital'];self.assertFalse(r['pending'] or r['active'] or r['staged'])
        for i,row in enumerate(r['records']):
            self.assertLessEqual(row['dma_done_ns'],row['fill_done_ns'])
            self.assertLessEqual(row['fill_done_ns'],row['compute_start_ns'])
            self.assertLessEqual(row['compute_done_ns'],row['retire_done_ns'])
            if i:self.assertGreaterEqual(row['compute_start_ns'],r['records'][i-1]['retire_done_ns'])
            if i>=2:self.assertGreaterEqual(row['fill_start_ns'],r['records'][i-2]['retire_done_ns'])
        self.assertEqual(t,d.s.end())

    def test_fabric_reservations_never_overlap(self):
        for rate in [.01,1.,1000.]:
            d,t=self.matrix(True,macs=512,bandwidth=rate,name='lm_head')
            intervals=sorted((x['start_ns'],x['end_ns']) for x in d.s.events if 'sram_fabric' in x['resources'])
            for a,b in zip(intervals,intervals[1:]):self.assertLessEqual(a[1],b[0]+1e-6)
            self.assertEqual(t,d.s.end())

    def test_single_buffer_has_no_prefill(self):
        c,m=case();c.update(schedule_policy='shared_tiles',digital_shared_prefill=True,double_buffer=False)
        c['ffn']['mode']='bf16';d=FullDecode(c,m);d.matrix(0,'L0/gu')
        self.assertEqual(d.tile_pipeline.counts['digital'].get('prefilled',0),0)

    def test_unvalidated_w8_prefill_rejected(self):
        c,m=case();c.update(schedule_policy='shared_tiles',digital_shared_prefill=True)
        c['ffn']['mode']='w8'
        with self.assertRaises(ValueError):FullDecode(c,m)

    def test_resource_profiles_fixed_E_capacity_and_clock(self):
        c,m=load('qwen3_4b');c['ffn']['mode']='bf16';c['attention']['mode']='exact';c['schedule_policy']='shared_tiles'
        for name in PROFILES:
            a=apply(c,name);d=FullDecode(a,m)
            self.assertEqual(d.mem.physical_capacity,8*1024**2)
            self.assertEqual(a['core_hz'],100000000)
            self.assertLessEqual(a['sram']['fabric_GBs'],a['sram']['banks']*16*.08)
            self.assertEqual(d.mem.macros,128 if name=='anchor_F64' else 2048)


if __name__=='__main__':unittest.main()
