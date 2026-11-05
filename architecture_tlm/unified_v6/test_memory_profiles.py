import copy,json,unittest
from pathlib import Path
from .config import tiny,load
from .memory_profiles import apply,DRAM_CONFIG
from .ffn_latest import defaults
from .model import FullDecode

class ProfileContracts(unittest.TestCase):
    def test_fixed_capacity_and_macro_count(self):
        for model in ('qwen','qwen3_4b','llama1','llama2'):
            c,m=load(model);c=apply(c,'sram64');d=FullDecode(c,m)
            self.assertEqual(d.mem.physical_capacity,8*1024**2)
            self.assertEqual(d.mem.macros,128)
    def test_no_missing_backend_fallback(self):
        c,m=tiny()
        with self.assertRaises(ValueError):apply(c,'ddr4','/no/such/bridge','/tmp/no-run')
    def test_standard_ddr4_geometry(self):
        d=json.loads(DRAM_CONFIG.read_text())['simulation']['memspec']
        a=d['memarchitecturespec'];self.assertEqual((a['nbrOfChannels'],a['nbrOfRanks']),(2,2))
        self.assertEqual(d['memoryId'],'MICRON_4Gb_DDR4-1866_8bit_A')
        self.assertAlmostEqual(2*8*2/(d['memtimingspec']['tCK']*1e9),29.8507462686567)
        self.assertEqual(d['mempowerspec']['vddq'],0.) # explicit unknown I/O boundary
    def test_digital_chunk_independent_of_sc_staging_size(self):
        c,m=tiny();m.update(hidden_size=192,intermediate_size=320,vocab_size=384)
        c['attention']['mode']='exact';c['ffn'].update(defaults());c['ffn']['engines']=2
        c['digital_weight_chunk_bytes']=32768
        def run(chunk):
            cfg=copy.deepcopy(c);cfg['weight_chunk_bytes']=chunk;d=FullDecode(cfg,m)
            d.matrix(0.,'L0/qkv')
            return [(e['stage'],e.get('bytes'),e.get('macs')) for e in d.s.events if e['stage'].startswith(('dram_weights','matrix_','qkv'))]
        self.assertEqual(run(32768),run(131072))
if __name__=='__main__':unittest.main()
