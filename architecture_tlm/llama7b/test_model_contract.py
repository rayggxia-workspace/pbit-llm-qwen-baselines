"""Architecture checks that catch Qwen assumptions leaking into LLaMA runs."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('llama_runner', ROOT / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from dramsys_backend import AddressSpace
from pv_stream_v6 import context_samples


class ModelContract(unittest.TestCase):
    def test_full_parameter_allocation_and_untied_embedding(self):
        cfg, _, shape, _, _ = runner.build(2048, 0)
        layout = AddressSpace(shape, 'digital_bf16', 2048, 1)
        non_kv = sum(r['logical_bytes'] for name, r in layout.regions.items() if not name.endswith('/KV'))
        self.assertEqual(non_kv, 6738415616 * 2)
        self.assertNotEqual(layout.regions['embedding']['base'], layout.regions['lm_head']['base'])
        self.assertEqual(layout.regions['L0/norms']['logical_bytes'], 4096 * 4)
        self.assertLess(layout.total_bytes, 16 * 2**30)
        self.assertFalse(shape['attention_bias'])

    def test_native_context_and_proportional_budget(self):
        cfg, _, shape, _, _ = runner.build(2048, 0)
        self.assertEqual(shape['num_attention_heads'], shape['num_key_value_heads'])
        for length, samples in [(512, 32), (1024, 64), (2048, 128)]:
            self.assertEqual(context_samples(length, cfg['pv_stream_v6']), samples)
        with self.assertRaises(ValueError):
            runner.build(2048, 0, tokens=2)
        with self.assertRaises(ValueError):
            runner.build(8192, 0)

    def test_no_qwen_calibration_or_replay(self):
        cfg, _, _, plan, _ = runner.build(1024, 1)
        self.assertIsNone(cfg['attention_v3']['calibration_file'])
        self.assertEqual(cfg['rng']['input_bits_per_decision'], 8)
        self.assertEqual(cfg['local_shared_input']['share_group'], 64)
        self.assertEqual(plan['unified_bytes'], 8 * 2**20)
        self.assertEqual(cfg['weight_macro']['per_weight_validity_bits'], 0)


if __name__ == '__main__':
    unittest.main()
