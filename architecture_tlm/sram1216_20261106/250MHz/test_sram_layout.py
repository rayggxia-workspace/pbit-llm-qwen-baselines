"""Small-shape address/data/port checks; full layer replay is separate."""
import argparse
from pathlib import Path
import unittest
from bootstrap import bootstrap

def create(profile='compact960'):
    from whole250.model import make_model
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    return make_model(AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606),
        sram_profile=profile,mode='ising',ffn='sc',samples={},layers=36,
        include_lm=True,seed=17)

class Layout(unittest.TestCase):
    def test_unique_physical_words_and_real_ports(self):
        for profile,kib,banks,front,per_group in [
                ('reference1216',1216,304,176,16),
                ('compact1088',1088,272,144,16),
                ('compact960',960,240,144,12)]:
            h,m=create(profile)
            self.assertEqual((h.mem.capacity,h.mem.nbank,h.return_banks),
                             (kib*1024,banks,front))
            self.assertEqual(len(m.att[0].banks),per_group)
            seen=set()
            for r in h.mem.regions.values():
                for word in range(r.size//16):
                    b=r.banks[word%len(r.banks)]
                    row=m.sram_bank_row_bases[r.name][b]+word//len(r.banks)
                    self.assertLess(row,256)
                    self.assertNotIn((b,row),seen)
                    seen.add((b,row))
            self.assertEqual(len(seen)*16,h.mem.capacity)
            self.assertEqual(h.response_bytes,16384)
            self.assertFalse(h.buffered)

    def test_full_projection_shapes_fit_and_cover(self):
        h,m=create()
        for name,nout,nin in [('QKV',6144,2560),('O',2560,4096),
                              ('lm_head',151936,2560)]:
            tasks=m.matrix_tasks(0,name,nout,nin)
            self.assertEqual(sum(sum(n for a,n in t[0]) for t in tasks),nout*nin*2)
            self.assertLessEqual(max(sum(n for a,n in t[0]) for t in tasks),32768)
        self.assertEqual([r.size for r in m.weight],[32768,32768])
        self.assertIsNone(h.response)

    def test_lifetime_data_identity(self):
        from whole250.sram_layout import attention_address
        memory=bytearray(49152)
        def put(off,size,tag,value):
            dst=attention_address(off,size,tag,49152)
            memory[dst:dst+size]=bytes([value])*size
        def check(off,size,tag,value):
            dst=attention_address(off,size,tag,49152)
            self.assertEqual(memory[dst:dst+size],bytes([value])*size)
        # Coarse and selectedK/V deliberately reuse memory after consumption.
        put(0,16384,'coarse_K_operand',1)
        put(32768,32768,'coarse_scores',2)
        check(0,16384,'coarse_K_operand',1)
        check(32768,32768,'coarse_scores',2)
        put(0,32768,'selected_K_fill',3)
        check(0,32768,'selected_K_operand',3)
        put(16384,2048,'selected_scores',4)
        put(65536,32768,'sample_V_fill',5)
        put(122880,1024,'attention_output',6)
        check(16384,2048,'sampler_score_input',4)
        check(65536,32768,'sample_V_operand',5)
        check(122880,1024,'attention_gather_read',6)
        with self.assertRaises(ValueError):
            attention_address(65536,32784,'sample_V_fill',49152)

    def test_live_alias_rejected_and_real_service(self):
        h,m=create();r=m.att[0]
        h.mem.submit(r,0,256,True,'selected_K_fill',lambda:None)
        with self.assertRaises(AssertionError):
            h.mem.submit(r,65536,256,True,'sample_V_fill',lambda:None)
        h,m=create();r=m.att[0]
        def jobs():
            for off,size,write,tag in [(0,32768,True,'selected_K_fill'),
                    (0,32768,False,'selected_K_operand'),
                    (16384,2048,True,'selected_scores'),
                    (16384,2048,False,'sampler_score_input'),
                    (65536,32768,True,'sample_V_fill'),
                    (65536,32768,False,'sample_V_operand'),
                    (122880,1024,True,'attention_output'),
                    (122880,1024,False,'attention_gather_read')]:
                yield from h.transfer(r,off,size,write,tag)
        h.execute([jobs()])
        self.assertFalse(h.mem.queue)
        self.assertLessEqual(h.mem.count['peak_banks_per_cycle'],12)
        self.assertEqual(h.mem.count['logical_write_bytes'],68608)
        self.assertEqual(h.mem.count['logical_read_bytes'],68608)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--dependencies',type=Path,required=True)
    args,rest=p.parse_known_args()
    bootstrap(args.runtime,args.dependencies)
    unittest.main(argv=['test_sram_layout']+rest)
