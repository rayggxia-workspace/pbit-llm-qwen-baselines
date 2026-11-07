"""Real bank/row capacities, scratch lifetimes and full vocabulary tile shapes."""
from pathlib import Path
import argparse,unittest
from run_sram100 import setup

def create(case='compact1056'):
    from architecture_tlm.module_refresh_20261107.host100 import make_model
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    return make_model(AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606),
        owner_install=OWNER.install,sram_configuration=case,samples={},layers=36,
        include_lm=True,seed=17)

class Layout(unittest.TestCase):
    def test_real_banks_and_unique_rows(self):
        for case,kib,banks,front in [('compact1216',1216,304,176),
                ('compact1184',1184,296,168),('compact1056',1056,264,168),
                ('compact1088bw',1088,272,176)]:
            h,m=create(case);seen=set()
            self.assertEqual((h.mem.capacity,h.mem.nbank,h.return_banks),(kib*1024,banks,front))
            for r in h.mem.regions.values():
                for word in range(r.size//16):
                    b=r.banks[word%len(r.banks)]
                    row=m.sram_bank_row_bases[r.name][b]+word//len(r.banks)
                    self.assertLess(row,256);self.assertNotIn((b,row),seen);seen.add((b,row))
            self.assertEqual(len(seen)*16,h.mem.top)
            self.assertEqual(h.mem.capacity-h.mem.top,32768 if case=='compact1088bw' else 0)
            self.assertEqual(h.response_bytes,16384);self.assertEqual(m.common_cores,6)
            self.assertEqual(h.mem.period,10)
    def test_projection_slots_and_full_head_cover(self):
        h,m=create()
        self.assertEqual([r.size for r in m.weight],[81920,81920])
        for name,nout,nin in [('QKV',6144,2560),('O',2560,4096),('lm_head',151936,2560)]:
            tasks=m.matrix_tasks(0,name,nout,nin)
            self.assertEqual(sum(sum(n for a,n in t[0]) for t in tasks),nout*nin*2)
            self.assertLessEqual(max(sum(n for a,n in t[0]) for t in tasks),81920)
        self.assertIsNone(h.response);self.assertFalse(h.buffered)
    def test_scratch_scores_output_lifetime_and_data(self):
        from architecture_tlm.sram1216_20261106.model import attention_address
        h,m=create();scratch=m.qk_supply_contract['scratch_offset']
        self.assertEqual(scratch,34816)
        memory=bytearray(49152)
        def put(off,size,tag,value):
            dst=attention_address(off,size,tag,49152);memory[dst:dst+size]=bytes([value])*size
        put(32768,32768,'coarse_scores',1) # dead after topK selection
        put(0,32768,'selected_K_fill',2)
        memory[scratch:scratch+1024]=bytes([3])*1024
        self.assertEqual(memory[:32768],bytes([2])*32768)
        put(16384,2048,'selected_scores',4)
        put(65536,32768,'sample_V_fill',5)
        put(122880,1024,'attention_output',6)
        self.assertEqual(memory[32768:34816],bytes([4])*2048)
        self.assertEqual(memory[48128:49152],bytes([6])*1024)
    def test_live_alias_rejection_and_physical_scratch_service(self):
        h,m=create();r=m.att[0]
        h.mem.submit(r,0,256,True,'selected_K_fill',lambda:None)
        with self.assertRaises(AssertionError):
            h.mem.submit(r,65536,256,True,'sample_V_fill',lambda:None)
        h,m=create();r=m.att[0]
        def jobs():
            yield from h.transfer(r,0,32768,True,'selected_K_fill')
            yield from h.transfer(r,34816,1024,True,'qksupply_transpose_store')
            yield from h.transfer(r,34816,1024,False,'qksupply_K_operand')
            yield from h.transfer(r,122880,1024,True,'attention_output')
        h.execute([jobs()]);self.assertFalse(h.mem.queue)
        self.assertLessEqual(h.mem.count['peak_banks_per_cycle'],12)
        self.assertEqual(h.mem.count['logical_write_bytes'],34816)
        self.assertEqual(h.mem.count['logical_read_bytes'],1024)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True)
    args,rest=p.parse_known_args()
    _,OWNER,_=setup(args.project,Path(__file__).resolve().parents[2])
    unittest.main(argv=['test_sram100']+rest)
