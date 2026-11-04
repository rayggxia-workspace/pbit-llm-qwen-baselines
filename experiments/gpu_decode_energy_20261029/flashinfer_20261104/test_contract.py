from pathlib import Path
import copy,json,unittest
from contract import validate,guard_values


class Tests(unittest.TestCase):
    def test_fixed_conditions(self):
        c=json.loads(Path(__file__).with_name('CONFIG.json').read_bytes());validate(c)
        for key,value in [('batch',16),('dtype','float16'),('logit_relative_L2_max',.02),('native_steps',512)]:
            d=copy.deepcopy(c);d[key]=value
            with self.assertRaises(AssertionError):validate(d)

    def test_failed_gqa_is_not_silently_accepted(self):
        self.assertFalse(guard_values(.0142698,True)['accepted'])
        self.assertFalse(guard_values(.001,False)['accepted'])
        self.assertTrue(guard_values(.009,True)['accepted'])


if __name__=='__main__':unittest.main()
