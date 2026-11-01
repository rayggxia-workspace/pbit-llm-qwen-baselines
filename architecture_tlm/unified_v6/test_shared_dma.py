import unittest
from .shared_memory import SharedMemory,AnalyticDRAM
from .shared_decode import SharedDecode,spans_tile
from .shared_dma import dma_config

class DMATests(unittest.TestCase):
    def execute(self,profile='legacy',layout='row_major'):
        c=dma_config(profile);h=SharedMemory(AnalyticDRAM(),credit=c['credit'],issue_per_cycle=c['issue'],response_bytes=c['response_bytes'],return_banks=c['return_banks'])
        m=SharedDecode(h,layers=1,context=128,hidden=128,ffn_size=128,q_heads=4,kv_heads=1,vocab=64,gu=2,nl=2,include_lm=False,weight_layout=layout)
        r=m.run();s=h.report();h.backend.finish(h.now);return r,s
    def test_finite_wide_resources_same_work(self):
        a,ma=self.execute();b,mb=self.execute('wide24')
        self.assertEqual(a['actions'],b['actions']);self.assertEqual(ma['by_kind'],mb['by_kind'])
        self.assertEqual(ma['SRAM']['counts']['read_words'],mb['SRAM']['counts']['read_words'])
        self.assertEqual(ma['SRAM']['counts']['write_words'],mb['SRAM']['counts']['write_words'])
        self.assertLessEqual(mb['counts']['peak_outstanding'],256)
        self.assertLessEqual(mb['counts']['peak_response_bytes'],32768)
        self.assertEqual(ma['SRAM']['capacity_bytes'],mb['SRAM']['capacity_bytes'])
    def test_tile_pack_is_bijection_and_correct_values(self):
        # Independent offline packing oracle with unique logical elements.
        for rows,cols,m,k,eb in [(128,128,64,64,1),(32,192,8,64,1),(128,2560,64,1024,2)]:
            matrix=list(range(rows*cols));packed=[]
            for o in range(0,rows,m):
                for start in range(0,cols,k):
                    for i in range(m):packed.extend(matrix[(o+i)*cols+start:(o+i)*cols+min(start+k,cols)])
            self.assertEqual(sorted(packed),matrix)
            for o in range(0,rows,m):
                for start in range(0,cols,k):
                    n=min(k,cols-start);sp=spans_tile(0,o,m,start,cols,n,eb,'tile_packed')
                    self.assertEqual(sp[0][1],m*n*eb)
                    offset=sp[0][0]//eb
                    expected=[matrix[(o+i)*cols+start+j] for i in range(m) for j in range(n)]
                    self.assertEqual(packed[offset:offset+m*n],expected)
    def test_pack_changes_addresses_not_arithmetic_or_bytes(self):
        a,ma=self.execute('wide24','row_major');b,mb=self.execute('wide24','tile_packed')
        self.assertEqual(a['actions'],b['actions']);self.assertEqual(a['kernel_active'],b['kernel_active'])
        for k in ma['by_kind']:
            for f in ['issued_bytes','read_bytes','write_bytes']:self.assertEqual(ma['by_kind'][k].get(f,0),mb['by_kind'][k].get(f,0))
        self.assertEqual(a['work_spec_sha256'],b['work_spec_sha256'])
    def test_full_model_wide_bank_capacity(self):
        c=dma_config('wide24');h=SharedMemory(AnalyticDRAM(),credit=c['credit'],issue_per_cycle=c['issue'],response_bytes=c['response_bytes'],return_banks=c['return_banks'])
        SharedDecode(h,weight_layout='tile_packed')
        self.assertLessEqual(max(h.mem.bank_allocated),h.mem.capacity//h.mem.nbank)
    def test_invalid_profile_limits(self):
        with self.assertRaises(ValueError):dma_config('wide24',response_bytes=1)
        with self.assertRaises(ValueError):dma_config('wide24',return_banks=513)

if __name__=='__main__':unittest.main()
