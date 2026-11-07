import unittest
from .model import make_model, vector_address, attention_address
from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM

def create(case='compact1216'):
    return make_model(AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606),
        configuration=case,mode='ising',ffn='sc',samples={},layers=36,include_lm=True)

class Layout(unittest.TestCase):
    def test_three_real_capacities_and_ports(self):
        for case,kib,banks in [('control1952',1952,488),('attention1440',1440,360),('compact1216',1216,304)]:
            h,m=create(case)
            self.assertEqual((h.mem.capacity,h.mem.nbank),(kib*1024,banks))
            self.assertEqual(sum(h.mem.bank_allocated),h.mem.capacity)
            self.assertEqual(h.response_bytes,24576)
            self.assertEqual(m.common_cores,12)
            self.assertEqual(m.common_state.size,96*1024)
            self.assertEqual(m.mac_lanes,640)
            self.assertEqual(sum(r.size for r in m.cim_weight),256*1024)
            self.assertEqual(len(m.att[0].banks),32 if case=='control1952' else 16)
    def test_physical_word_locations_unique(self):
        h,m=create();seen=set()
        for r in h.mem.regions.values():
            for word in range(r.size//16):
                b=r.banks[word%len(r.banks)]
                row=m.sram_bank_row_bases[r.name][b]+word//len(r.banks)
                self.assertLess(row,256);self.assertNotIn((b,row),seen);seen.add((b,row))
        self.assertEqual(len(seen)*16,h.mem.capacity)
    def test_ordinary_tile_fits_smaller_pingpong(self):
        h,m=create()
        for name,nout,nin in [('QKV',6144,2560),('O',2560,4096),('lm_head',151936,2560)]:
            tasks=m.matrix_tasks(0,name,nout,nin)
            self.assertEqual(sum(sum(n for a,n in t[0]) for t in tasks),nout*nin*2)
            self.assertLessEqual(max(sum(n for a,n in t[0]) for t in tasks),81920)
        self.assertEqual([r.size for r in m.weight],[81920,81920])
    def test_activation_objects_byte_identity_and_disjointness(self):
        old=[(0,32768),(65536,32768),(131072,5120)]
        old += [(196608+g*6144+5120,1024) for g in range(8)]
        seen=set();memory=bytearray(131072)
        for index,(start,size) in enumerate(old):
            dest=vector_address(start,size)
            self.assertFalse(seen.intersection(range(dest,dest+size)))
            seen.update(range(dest,dest+size))
            data=bytes((index*31+j)%256 for j in range(size));memory[dest:dest+size]=data
            self.assertEqual(memory[dest:dest+size],data)
        with self.assertRaises(ValueError):vector_address(196608,1024)
    def test_attention_role_layout_and_unmapped_rejection(self):
        cases=[(114688,8192,'K_transpose_read',0),(32768,16384,'coarse_scores',16384),
            (0,32768,'selected_K_fill',0),(16384,2048,'selected_scores',32768),
            (65536,32768,'sample_V_fill',0),(122880,1024,'attention_gather_read',61440)]
        for offset,size,tag,want in cases:self.assertEqual(attention_address(offset,size,tag),want)
        with self.assertRaises(ValueError):attention_address(0,16,'unknown')
        with self.assertRaises(ValueError):attention_address(65536,32784,'sample_V_fill')
    def test_overlapping_pending_alias_is_rejected(self):
        h,m=create();r=m.att[0]
        h.mem.submit(r,0,256,True,'selected_K_fill',lambda:None)
        with self.assertRaises(AssertionError):
            h.mem.submit(r,65536,256,True,'sample_V_fill',lambda:None)
    def test_actual_translated_memory_service_and_reuse(self):
        h,m=create();r=m.att[0]
        def jobs():
            yield from h.transfer(r,114688,8192,True,'K_transpose_write')
            yield from h.transfer(r,0,32768,True,'selected_K_fill')
            yield from h.transfer(r,0,32768,False,'selected_K_operand')
            yield from h.transfer(r,16384,2048,True,'selected_scores')
            yield from h.transfer(r,16384,2048,False,'sampler_score_input')
            yield from h.transfer(r,65536,32768,True,'sample_V_fill')
            yield from h.transfer(r,65536,32768,False,'sample_V_operand')
            yield from h.transfer(r,122880,1024,True,'attention_output')
        h.execute([jobs()])
        self.assertFalse(h.mem.queue)
        self.assertEqual(h.mem.count['logical_write_bytes'],8192+32768+2048+32768+1024)
        self.assertEqual(h.mem.count['logical_read_bytes'],32768+2048+32768)
        self.assertLessEqual(h.mem.count['peak_banks_per_cycle'],16)
    def test_no_global_actor_mutation(self):
        from architecture_tlm.unified_v6.shared_memory import BeatSRAM
        original=BeatSRAM.submit
        create();self.assertIs(BeatSRAM.submit,original)

if __name__=='__main__':unittest.main()
