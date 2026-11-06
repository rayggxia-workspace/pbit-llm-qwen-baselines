import copy,importlib.util,math,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('time_audit',Path(__file__).with_name('time_audit.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class AuditTests(unittest.TestCase):
    def audit(self,residual=0):
        a=dict(zip(module.FIELDS,(710.,130.1,19360.,20.2,3440.)))
        a['elapsed_ns']=math.fsum(a.values())+residual
        return a
    def test_exact(self):
        self.assertEqual(module.check_exclusive_time(self.audit())['time_ledger_residual_ns'],0)
    def test_actual_native_failure(self):
        a=dict(zip(module.FIELDS,(530.,3009.9999999998836,188690.00000000012,6649.999999999884,8810.)))
        a['elapsed_ns']=207690.
        self.assertNotEqual(sum(a[k] for k in module.FIELDS),a['elapsed_ns'])
        before=copy.deepcopy(a);module.check_exclusive_time(a)
        for key in (*module.FIELDS,'elapsed_ns'):self.assertEqual(a[key],before[key])
    def test_roundoff_is_recorded(self):
        for residual in (-1e-9,1e-9,-1e-7,1e-7):
            a=self.audit(residual);before=copy.deepcopy(a)
            module.check_exclusive_time(a)
            self.assertNotEqual(a['time_ledger_residual_ns'],0)
            for key in (*module.FIELDS,'elapsed_ns'):self.assertEqual(a[key],before[key])
    def test_one_ps_real_omission_fails(self):
        for residual in (-.001,.001):
            with self.assertRaises(AssertionError):module.check_exclusive_time(self.audit(residual))
    def test_whole_cycle_omission_fails(self):
        for residual in (-10.,10.):
            with self.assertRaises(AssertionError):module.check_exclusive_time(self.audit(residual))
    def test_nonfinite_fails(self):
        for value in (math.nan,math.inf,-math.inf):
            a=self.audit();a['elapsed_ns']=value
            with self.assertRaises(AssertionError):module.check_exclusive_time(a)

if __name__=='__main__':unittest.main()
