"""Check design correction only; these tests do not validate a hardware forward."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
import scan

HERE = Path(__file__).resolve().parent

class HardwareGate(unittest.TestCase):
    def test_manifest_matches_generator_and_keeps_scan(self):
        data = json.loads((HERE/'SCAN_MANIFEST.json').read_bytes())
        self.assertTrue(scan.check(data)['design_manifest_pass'])
        self.assertEqual(len(data['stage_A_cases']), 57)
        self.assertFalse(data['training_defaults']['hardware_forward_validated'])
        self.assertEqual(data['training_defaults']['initial_ffn_numeric_backend'],
                         'unimplemented_hardware_constrained_forward')
        self.assertIn('hardware_forward_contract_and_sha', data['required_before_launch'])

    def test_missing_hardware_contract_refuses_launch(self):
        result = subprocess.run([sys.executable, str(HERE/'scan.py'), '--require-launch-ready'],
                                capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'hardware forward contract', result.stderr)

    def test_contract_and_receipts_are_explicitly_unresolved(self):
        contract = json.loads((HERE/'HARDWARE_CONTRACT.example.json').read_bytes())
        self.assertFalse(contract['deployment_unquantized_fp32_ffn_allowed'])
        self.assertTrue(all(v is None for v in contract['fields'].values()))
        for name in ('REMOTE_ENV.example.json', 'RUN_RESULT.example.json'):
            hw = json.loads((HERE/name).read_bytes())['hardware_forward']
            self.assertFalse(hw['target_circuit_supported'])
            self.assertIsNone(hw['contract_sha256'])

if __name__ == '__main__':
    unittest.main()
