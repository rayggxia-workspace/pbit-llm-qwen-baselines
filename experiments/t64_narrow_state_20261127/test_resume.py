import copy,math,unittest
from resume_full import checked_rows,merge_rows

class Tests(unittest.TestCase):
    def setUp(self):
        self.rows=[dict(window=i,start=i*10,end=i*10+10,first_scored=i*10+1,targets=9,
                        target_token_sha256=str(i),nll_sum=9*(i+1)) for i in range(4)]
    def test_disjoint_reuse_equals_uninterrupted(self):
        rows,z=merge_rows(self.rows[:2],self.rows[2:],self.rows)
        self.assertEqual(rows,self.rows);self.assertEqual(z['targets'],36)
        self.assertAlmostEqual(z['ppl'],math.exp(2.5))
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):merge_rows(self.rows,self.rows[:1],self.rows)
    def test_missing_rejected(self):
        with self.assertRaises(ValueError):merge_rows(self.rows[:2],[],self.rows)
    def test_changed_targets_rejected(self):
        bad=copy.deepcopy(self.rows);bad[1]['target_token_sha256']='changed'
        with self.assertRaises(ValueError):checked_rows(bad,self.rows)
    def test_nonfinite_rejected(self):
        bad=copy.deepcopy(self.rows);bad[1]['nll_sum']=float('nan')
        with self.assertRaises(ValueError):checked_rows(bad,self.rows)

if __name__=='__main__':unittest.main()
