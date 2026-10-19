"""Admission checks: no expensive old cells duplicated and one variable in sweep."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.qwen_joint_stratified_attention_20261019.run_samples import cases

class SamplePlanTest(unittest.TestCase):
    def test_new_suffix_cells_exclude_recorded_budgets(self):
        grid=cases('suffix');self.assertEqual(len(grid),15)
        draws=[r for r in grid if r['mode']=='screen_ising']
        self.assertEqual({r['samples'] for r in draws},{32,64,256,1024})
        self.assertEqual(sum(r['mode']=='screen_exact' for r in grid),3)
        for count in (32,64,256,1024):
            self.assertEqual(sorted(r['seed'] for r in draws if r['samples']==count),[0,1,2])
        constants={(r['ffn'],r['batch'],r['burn'],r['spacing'],r['budget_blocks'],r['protocol']) for r in grid}
        self.assertEqual(constants,{('b4_t32',8,16.,4.,8,'suffix')})

    def test_new_full_cells_reuse_running128(self):
        grid=cases('full');self.assertEqual(len(grid),6)
        self.assertEqual({r['samples'] for r in grid},{256,512})
        self.assertTrue(all(r['protocol']=='full' and r['batch']==32 for r in grid))
        with self.assertRaises(ValueError):cases('old')
        self.assertNotIn('torch',sys.modules)

if __name__=='__main__':unittest.main()
