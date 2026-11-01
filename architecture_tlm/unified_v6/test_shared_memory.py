"""Mechanism checks for real concurrency/accounting; no model-quality claim."""
import unittest
from architecture_tlm.unified_v6.shared_memory import SharedMemory,AnalyticDRAM


class SharedTests(unittest.TestCase):
    def hub(self,**kwargs):
        return SharedMemory(AnalyticDRAM(latency_ns=100),**kwargs)
    def workload(self,h,owners=4,bytes_each=256):
        regions=[h.mem.region(str(j),4096,[j+20]) for j in range(owners)]
        def flow(j):
            yield from h.fetch('owner'+str(j),65536+j*4096,bytes_each,regions[j],0,'input')
            return h.now
        h.execute([flow(j) for j in range(owners)])
        return h.report()
    def test_async_vs_descriptor_barrier(self):
        async_h=self.hub();serial_h=self.hub(descriptor_serial=True)
        a=self.workload(async_h);s=self.workload(serial_h)
        self.assertLess(a['elapsed_ns'],s['elapsed_ns'])
        self.assertEqual(a['by_kind'],s['by_kind'])
        self.assertGreater(a['counts']['peak_outstanding'],4)
    def test_global_credit_and_return_capacity(self):
        h=self.hub(credit=2,response_bytes=128)
        r=self.workload(h)
        self.assertLessEqual(r['counts']['peak_outstanding'],2)
        self.assertLessEqual(r['counts']['peak_response_bytes'],128)
        self.assertEqual(r['final_pending'],0)
    def test_exact_word_energy(self):
        h=self.hub();r=self.workload(h,owners=1,bytes_each=64)
        c=r['SRAM']['counts']
        self.assertEqual(c['read_words'],4)
        self.assertEqual(c['write_words'],8)
        self.assertAlmostEqual(r['SRAM']['dynamic_mJ'],(4*10.0527+8*13.9599)*1e-9)
    def test_explicit_bypass_removes_only_FIFO_events(self):
        a=self.workload(self.hub(),1,64)
        b=self.workload(self.hub(response_buffered=False),1,64)
        self.assertEqual(a['by_kind'],b['by_kind'])
        self.assertEqual(b['SRAM']['counts'].get('read_words',0),0)
        self.assertEqual(b['SRAM']['counts']['write_words'],4)
        self.assertEqual(b['unpriced_actions']['ingress_elastic_64B_beats'],1)
    def test_bank_parallelism(self):
        def trial(shared):
            h=self.hub();a=h.mem.region('a',4096,[20]);b=h.mem.region('b',4096,[20 if shared else 21])
            def read(r):yield from h.transfer(r,0,64,False,'compute')
            h.execute([read(a),read(b)]);return h.now,h.mem.report(h.now)
        serial,one=trial(True);parallel,two=trial(False)
        self.assertGreater(serial,parallel)
        self.assertEqual(one['dynamic_mJ'],two['dynamic_mJ'])
    def test_future_job_does_not_block_ready_job(self):
        h=self.hub();r=h.mem.region('shared',4096,[20]);ends={}
        def late():
            yield from h.delay(1000)
            yield from h.transfer(r,0,64,False,'late');ends['late']=h.now
        def early():
            yield from h.transfer(r,64,64,False,'early');ends['early']=h.now
        h.execute([late(),early()]);self.assertLess(ends['early'],100)
        self.assertGreater(ends['late'],1000)
    def test_scatter_gather_addresses(self):
        h=self.hub();r=h.mem.region('dest',4096,range(20,36))
        def flow():yield from h.fetch('sg',65536,192,r,0,'sg',spans=[(65536,64),(131072,128)])
        h.execute([flow()]);c=h.report()['by_kind']['sg']
        self.assertEqual(c['issued_bytes'],192)
        self.assertEqual(c['issued_address_sum'],65536+131072+131136)
    def test_capacity_and_period_failures(self):
        h=self.hub()
        with self.assertRaises(ValueError):h.mem.region('too_big',h.mem.capacity+1,[0])
        with self.assertRaises(ValueError):h.mem.region('invalid',64,[512])
        with self.assertRaises(ValueError):self.hub(memory_config={'clock_hz':500000000})
        h.mem.region('bank_full',16384,[200])
        with self.assertRaises(ValueError):h.mem.region('same_bank_overflow',16,[200])
    def test_return_FIFO_banks_change_time_not_event_price(self):
        def run(banks):
            h=SharedMemory(AnalyticDRAM(latency_ns=10),return_banks=banks)
            targets=[h.mem.region('t'+str(j),16384,range(256+j*32,288+j*32)) for j in range(4)]
            def flow(j):yield from h.fetch(str(j),65536+j*16384,16384,targets[j],0,'weights')
            h.execute([flow(j) for j in range(4)]);return h.report()
        a=run(16);b=run(128)
        self.assertLess(b['elapsed_ns'],a['elapsed_ns'])
        self.assertEqual(a['by_kind'],b['by_kind'])
        self.assertAlmostEqual(a['SRAM']['dynamic_mJ'],b['SRAM']['dynamic_mJ'])
    def test_invalid_alignment_rejected(self):
        h=self.hub();r=h.mem.region('r',4096,[20])
        with self.assertRaises(ValueError):h.dma('x',1,64,r,0,'bad',lambda:None)
    def test_DMA_write_reads_source_and_is_bounded(self):
        h=self.hub();r=h.mem.region('source',16384,range(256,384))
        def flow():yield from h.fetch('writer',65536,16384,r,0,'output',write=True)
        h.execute([flow()]);report=h.report()
        self.assertEqual(report['counts']['dram_write_bytes'],16384)
        self.assertEqual(report['SRAM']['by_tag']['output_DMA_source']['read_words'],1024)
        self.assertLessEqual(report['counts']['peak_write_source_slots'],8)
        self.assertEqual(h.free_write_slots,8)


if __name__=='__main__':unittest.main()
