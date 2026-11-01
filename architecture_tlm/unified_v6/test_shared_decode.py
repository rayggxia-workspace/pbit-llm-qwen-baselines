import unittest
from architecture_tlm.unified_v6.shared_memory import SharedMemory,AnalyticDRAM
from architecture_tlm.unified_v6.shared_decode import SharedDecode

class DecodeTests(unittest.TestCase):
    def execute(self,**kwargs):
        h=SharedMemory(AnalyticDRAM());m=SharedDecode(h,layers=1,context=128,hidden=64,ffn_size=64,
            q_heads=4,kv_heads=1,vocab=64,gu=1,nl=1,include_lm=False,**kwargs)
        result=m.run();memory=h.report();h.backend.finish(h.now)
        return result,memory
    def test_single_layer_causal_sc_work(self):
        r,m=self.execute(ffn='sc')
        self.assertEqual(r['kernel_active']['GU_frames'],1)
        self.assertEqual(r['kernel_active']['NL_frames'],8)
        self.assertEqual(r['actions']['digital_BF16_MAC'],64*768+64*512)
        self.assertEqual(r['actions']['samples'],256)
        self.assertEqual(r['actions']['PV_ADD'],256*128)
        self.assertEqual(m['final_pending'],0)
        self.assertEqual(m['final_response_occupied'],0)
    def test_staging_preserves_external_work(self):
        a,ma=self.execute(ffn='sc',staging=False)
        b,mb=self.execute(ffn='sc',staging=True)
        self.assertEqual(a['actions'],b['actions'])
        self.assertEqual(ma['by_kind'],mb['by_kind'])
        self.assertGreater(mb['SRAM']['counts']['read_words'],ma['SRAM']['counts']['read_words'])
        self.assertGreater(mb['SRAM']['dynamic_mJ'],ma['SRAM']['dynamic_mJ'])
    def test_digital_w8_reference_same_shapes(self):
        r,m=self.execute(ffn='w8')
        self.assertEqual(r['actions']['digital_W8_MAC'],3*64*64)
        self.assertNotIn('GU_frames',r['kernel_active'])
        self.assertEqual(r['actions']['samples'],256)
    def test_cross_prefetch_preserves_work_and_addresses(self):
        a,ma=self.execute(ffn='sc',cross_prefetch=True)
        b,mb=self.execute(ffn='sc',cross_prefetch=False)
        keys=set(a['actions'])|set(b['actions'])
        for k in keys-{'ordinary_prefetch_hits','GU_prefetch_hits'}:self.assertEqual(a['actions'].get(k,0),b['actions'].get(k,0),k)
        self.assertEqual(ma['by_kind'],mb['by_kind'])
        self.assertGreater(a['actions']['ordinary_prefetch_hits'],0)
        self.assertGreater(a['actions']['GU_prefetch_hits'],0)
    def test_lm_head_streams_argmax_without_vocab_tensor(self):
        h=SharedMemory(AnalyticDRAM());m=SharedDecode(h,layers=1,context=128,hidden=64,ffn_size=64,
            q_heads=4,kv_heads=1,vocab=320,gu=1,nl=1,include_lm=True)
        r=m.run();sr=h.report()['SRAM']
        self.assertEqual(r['actions']['argmax_compares'],320)
        self.assertNotIn('lm_head_output',sr['by_tag'])
        self.assertEqual(r['unpriced_state_and_actions']['digital_FP32_partial_register_bytes_peak'],256)

if __name__=='__main__':unittest.main()
