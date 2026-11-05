from pathlib import Path
import copy,json,unittest
from contract import validate,guard_values,flashinfer_scale,whole_measurement_class
import math
from types import SimpleNamespace


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

    def test_exploratory_whole_keeps_failed_gate(self):
        gate=guard_values(.07,True)
        self.assertFalse(gate['accepted'])
        self.assertEqual(whole_measurement_class(False,True,True,True),'blocked')
        self.assertEqual(whole_measurement_class(False,True,True,True,True),'exploratory_numerical_gate_failed')
        self.assertFalse(gate['accepted'])

    def test_exploratory_does_not_override_invalid_kernel_or_input(self):
        for args in ((False,True,True),(True,False,True),(True,True,False)):
            self.assertEqual(whole_measurement_class(False,*args,exploratory=True),'blocked')

    def test_default_scale_workaround_is_exact(self):
        for d in (64,128,256):
            self.assertIsNone(flashinfer_scale(1/math.sqrt(d),d))
            self.assertIsNone(flashinfer_scale(d**-.5,d))
            self.assertIsNone(flashinfer_scale(None,d))

    def test_custom_scale_is_not_silently_changed(self):
        with self.assertRaises(ValueError):flashinfer_scale(.1,128)
        with self.assertRaises(ValueError):flashinfer_scale(None,0)

    def test_cuda_and_tensor_call_real_api_contract(self):
        from bench import core
        calls=[]
        def old_api(q,k,v,*,sm_scale,**kw):
            # Reproduce the installed0.2.5 initialization branch.
            if sm_scale is None:head_dim=q.shape[-1]
            calls.append((head_dim,kw))
            return 'ok'
        fi=SimpleNamespace(single_decode_with_kv_cache=old_api)
        q=SimpleNamespace(shape=(32,128))
        copied=[]
        k=SimpleNamespace(contiguous=lambda:copied.append('K') or 'compactK')
        v=SimpleNamespace(contiguous=lambda:copied.append('V') or 'compactV')
        for backend in ('flashinfer_cuda','flashinfer_tensor'):
            self.assertEqual(core(None,fi,backend,q,k,v,128**-.5),'ok')
        self.assertEqual(copied,['K','V'])
        self.assertFalse(calls[0][1]['use_tensor_cores'])
        self.assertTrue(calls[1][1]['use_tensor_cores'])
        self.assertTrue(all(d==128 and kw['kv_layout']=='HND' and kw['pos_encoding_mode']=='NONE' for d,kw in calls))


if __name__=='__main__':unittest.main()
