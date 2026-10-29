import copy
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .model import DEFAULT_PROFILE, PROFILES, anchors, estimate
from ..unified_v6.config import tiny, load
from ..unified_v6.core import Ledger
from ..unified_v6.model import FullDecode


class DigitalEnergyContracts(unittest.TestCase):
    def test_replacement_preserves_other_actions_and_does_not_double_charge(self):
        e = Ledger({'bf16_mac': 2., 'vector_op': 3., 'fp32_mac': None})
        e.action('bf16_mac', 10, 'shared')
        e.action('bf16_mac', 20, 'other')
        e.action('vector_op', 11, 'shared')
        e.action('fp32_mac', 7, 'shared')
        old = e.replace_action_energy('bf16_mac', 1e-9, 'digital_MAC_calibrated')
        self.assertAlmostEqual(sum(old.values()), 60e-12)
        self.assertAlmostEqual(sum(e.energy.values()), 1e-9 + 33e-12)
        self.assertEqual(e.missing['fp32_mac'], 7)
        e.replace_action_energy('bf16_mac', 2e-9, 'digital_MAC_calibrated')
        self.assertAlmostEqual(sum(e.energy.values()), 2e-9 + 33e-12)

    def test_measured_gross_is_recovered_at_reference_full_utilization(self):
        c = {'core_hz': 100000000, 'macs_per_cycle': 1,
             'digital_power': {'profile': 'fma2', 'idle_dynamic_keep': 1.}}
        q = estimate(c, {'bf16_mac': 1024}, {'mac': 10360}, 10360)
        measured = anchors()['units']['fma2']['normal']['total_W'] * 10360e-9
        self.assertAlmostEqual(q['energy_J'], measured, delta=1e-14)
        self.assertAlmostEqual(q['components'][0]['work_increment_pJ_per_operation'], 3.6000325520833325)

    def test_leakage_not_scaled_by_frequency_and_area_scaled_once(self):
        c = {'core_hz': 100000000, 'macs_per_cycle': 4,
             'digital_power': {'profile': 'nonfused_pair', 'idle_dynamic_keep': .1}}
        a = estimate(c, {'bf16_mac': 64}, {'mac': 200}, 1000)
        c['core_hz'] = 500000000
        b = estimate(c, {'bf16_mac': 64}, {'mac': 200}, 1000)
        self.assertEqual(a['leakage_J'], b['leakage_J'])
        self.assertEqual(a['raw_area_mm2'], b['raw_area_mm2'])
        self.assertAlmostEqual(a['area_55eq_mm2'], .81 * a['raw_area_mm2'])
        self.assertGreater(b['background_dynamic_J'], a['background_dynamic_J'])

    def test_ungated_reference_and_zero_idle_keep_retain_busy_activity(self):
        c = {'core_hz': 100000000, 'macs_per_cycle': 1,
             'digital_power': {'profile': 'fma2', 'idle_dynamic_keep': 0.}}
        a = estimate(c, {'bf16_mac': 10}, {'mac': 200}, 1000)
        c['digital_power']['idle_dynamic_keep'] = 1.
        b = estimate(c, {'bf16_mac': 10}, {'mac': 200}, 1000)
        self.assertEqual(a['work_increment_J'], b['work_increment_J'])
        self.assertEqual(a['leakage_J'], b['leakage_J'])
        self.assertGreater(a['background_dynamic_J'], 0)
        self.assertGreater(b['energy_J'], a['energy_J'])

    def test_unsupported_dot64_and_impossible_work_are_rejected(self):
        c = {'core_hz': 100000000, 'macs_per_cycle': 1}
        with self.assertRaises(ValueError): estimate(c, {}, {}, 100, profile='dot64_4')
        with self.assertRaises(ValueError): estimate(c, {'bf16_mac': 100}, {}, 100)

    def test_live_decode_reprices_without_changing_work_or_schedule(self):
        for mode, profile in product(['exact', 'screen_pv'], PROFILES):
            c, shape = tiny()
            c['attention']['mode'] = mode
            baseline = FullDecode(c, shape).run()
            c['digital_power'] = {'profile': profile, 'idle_dynamic_keep': .1}
            updated = FullDecode(c, shape).run()
            for key in ['actions', 'resource_busy_ns', 'stage_busy_ns', 'phase_ns', 'attention_activity', 'FFN_activity']:
                self.assertEqual(baseline[key], updated[key], key)
            self.assertEqual(baseline['metrics']['TPOT_ms'], updated['metrics']['TPOT_ms'])
            q = updated['digital_power']
            self.assertEqual(q['profile'], profile)
            removed = sum(q['replaced_legacy_charges_J'].values())
            self.assertAlmostEqual(sum(updated['energy_J'].values()),
                sum(baseline['energy_J'].values()) - removed + q['energy_J'])
            self.assertIsNone(updated['metrics']['full_physical_energy_J'])

    def test_latest_FFN_keeps_random_memory_and_timing(self):
        from ..unified_v6.ffn_latest import defaults
        c, shape = tiny()
        c['ffn'].update(defaults())
        c['ffn']['engines'] = 2
        c['attention']['mode'] = 'screen_pv'
        old = FullDecode(c, shape).run()
        c['digital_power'] = dict(profile='nonfused_pair', idle_dynamic_keep=.1)
        new = FullDecode(c, shape).run()
        for k in ['actions', 'resource_busy_ns', 'stage_busy_ns', 'attention_activity', 'FFN_activity', 'SRAM', 'DRAM', 'random_interface']:
            self.assertEqual(old[k], new[k], k)

    def test_cli_dispatch_outputs_calibrated_price(self):
        from ..unified_v6 import run
        c, shape = tiny()
        with tempfile.TemporaryDirectory(prefix='pbit_digital210_') as tmp:
            self.assertEqual(Path(tmp).resolve().parent, Path(tempfile.gettempdir()).resolve())
            out = Path(tmp) / 'run'
            with patch.object(run, 'source_record', return_value={'commit': 'UNIT_TEST_ONLY'}), patch.object(run, 'load', return_value=(c, shape)):
                rows = run.main(['--model','qwen','--ffn','bf16','--attention','exact',
                    '--ffn-profile','legacy','--memory-profile','legacy','--rng-backend','local_prng_interface',
                    '--digital-energy-profile','nonfused_pair','--digital-idle-keep','.1','--output',str(out)])
            self.assertEqual(rows[0]['digital_MAC_profile'], 'nonfused_pair')
            self.assertGreater(rows[0]['digital_MAC_mJ_per_token'], 0)
            self.assertIsNone(rows[0]['physical_energy_J'])
            self.assertTrue(json.loads((out/'ARTIFACT_MANIFEST.json').read_text()))

    def test_opt_in_without_profile_uses_fma_and_legacy_without_policy_stays_unchanged(self):
        c, shape = tiny()
        legacy = FullDecode(c, shape).run()
        self.assertNotIn('digital_power', legacy)
        c['digital_power'] = {'idle_dynamic_keep': .1}
        fused = FullDecode(c, shape).run()
        self.assertEqual(fused['digital_power']['profile'], DEFAULT_PROFILE)
        self.assertEqual([x['unit'] for x in fused['digital_power']['components']], ['fma2'])
        self.assertEqual(legacy['actions'], fused['actions'])
        self.assertEqual(legacy['metrics']['TPOT_ms'], fused['metrics']['TPOT_ms'])

    def test_cli_default_and_legacy_idle_override_use_fma(self):
        from ..unified_v6 import run
        for policy_present in (False, True):
            c, shape = tiny()
            if policy_present:
                c['digital_power'] = copy.deepcopy(load('qwen3_4b')[0]['digital_power'])
            with tempfile.TemporaryDirectory(prefix='pbit_fma210_') as tmp:
                out = Path(tmp) / 'run'
                with patch.object(run, 'source_record', return_value={'commit': 'UNIT_TEST_ONLY'}), patch.object(run, 'load', return_value=(c, shape)):
                    rows = run.main(['--model','qwen','--ffn','bf16','--attention','exact',
                        '--ffn-profile','legacy','--memory-profile','legacy','--rng-backend','local_prng_interface',
                        '--digital-idle-keep','.1','--output',str(out)])
                self.assertEqual(rows[0]['digital_MAC_profile'], 'fma2')

    def test_current_config_defaults_and_legacy_fixture(self):
        for model in ['qwen', 'qwen3_4b', 'llama1', 'llama2']:
            self.assertEqual(load(model)[0]['digital_power']['profile'], 'fma2')
            self.assertNotIn('digital_power', load(model, legacy=True)[0])
        self.assertNotIn('digital_power', tiny()[0])


if __name__ == '__main__':
    unittest.main()
