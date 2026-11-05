"""Count and native-dispatch checks; CPU, no model weights or GPU."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

from qwen_decode import inventory, make_devices


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shape = json.loads(Path(sys.argv_config).read_text())['shape']

    def test_qwen_shape_and_counts(self):
        x = inventory(self.shape, 2048)
        self.assertEqual(x['dense_mac'], 4022272000)
        self.assertEqual(x['qk_mac'], 301989888)
        self.assertEqual(x['total_mac'], 4626251776)
        self.assertEqual(x['weight_bytes'], 8044544000)
        self.assertIn(('q_proj', 2560, 4096), x['projections'])
        self.assertIn(('k_proj', 2560, 1024), x['projections'])
        self.assertIn(('down_proj', 9728, 2560), x['projections'])

    def test_context_only_changes_attention(self):
        a, b = inventory(self.shape, 2048), inventory(self.shape, 8192)
        self.assertEqual(a['dense_mac'], b['dense_mac'])
        self.assertEqual(4*a['qk_mac'], b['qk_mac'])
        self.assertEqual(4*a['kv_read_bytes'], b['kv_read_bytes'])

    def test_native_gemv_contract(self):
        from software_model.matmul import Matmul
        from software_model.utils import Tensor, data_type_dict
        dt = data_type_dict['fp16']
        for case in ['a100_native','small_native_hbm256','small_native_hbm186','small_fabric32','small_native_ddr']:
            dev, gemv, notes = make_devices(case)
            for k, n in [(2560,4096),(2560,9728),(9728,2560),(2560,151936)]:
                op = Matmul(dt); op(Tensor([1,k],dt),Tensor([k,n],dt))
                t = op.compile_and_simulate(gemv,'heuristic-GPU')
                c = gemv.compute_module
                expected = max(2*k*n/(c.core.vector_unit.total_vector_flops_per_cycle*c.core_count*c.clock_freq),
                               2*(k+k*n+n)/gemv.io_module.bandwidth)
                self.assertAlmostEqual(t,expected,places=14)
                self.assertIsNone(op.best_mapping)

    def test_unmodified_native_gemv_l2_bypass(self):
        from software_model.matmul import Matmul
        from software_model.utils import Tensor, data_type_dict
        dt = data_type_dict['fp16']; dev, gemv, _ = make_devices('a100_native')
        a = Matmul(dt); a(Tensor([1,2560],dt),Tensor([2560,4096],dt))
        t = a.compile_and_simulate(gemv,'heuristic-GPU')
        tiny = copy.deepcopy(gemv); tiny.compute_module.l2_bandwidth_per_cycle=1
        self.assertEqual(t,a.compile_and_simulate(tiny,'heuristic-GPU'))

    def test_small_resource_separation(self):
        for case in ['small_native_hbm186','small_fabric32']:
            dev, gemv, _ = make_devices(case)
            self.assertEqual(dev.compute_module.total_systolic_array_flops/2,51.2e9)
            self.assertEqual(dev.compute_module.total_vector_flops_per_cycle,64)
            self.assertEqual(gemv.compute_module.core.vector_unit.total_vector_flops_per_cycle,1024)
        self.assertEqual(gemv.io_module.bandwidth,32e9)


if __name__ == '__main__':
    sys.argv_config = sys.argv.pop(1)
    sys.path.insert(0,sys.argv.pop(1))
    unittest.main(verbosity=2)
