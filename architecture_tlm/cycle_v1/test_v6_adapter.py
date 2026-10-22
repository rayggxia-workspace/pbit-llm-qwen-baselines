import unittest

from .v6_adapter import UnsupportedMapping, map_config, smoke_input


class V6MappingTests(unittest.TestCase):
    def test_shared_ffn_parameters_and_explicit_non_equivalence(self):
        cfg, shape, fixture = smoke_input('ffn')
        result, boundary = map_config('ffn', cfg, shape, fixture)
        self.assertEqual((result.bins, result.samples, result.strata, result.engines), (4, 32, 32, 8))
        self.assertEqual(result.vector_lanes, cfg['vector_lanes'])
        self.assertEqual(result.seed_word_interval, cfg['random']['seed_word_interval_cycles'])
        self.assertTrue(boundary['v6_only_contracts'])
        self.assertTrue(boundary['no_direct_equivalence'])

    def test_cropped_output_is_rejected_before_running(self):
        cfg, shape, fixture = smoke_input('ffn')
        fixture['wd'] = fixture['wd'][:16]
        with self.assertRaisesRegex(UnsupportedMapping, 'cropped FFN'):
            map_config('ffn', cfg, shape, fixture)

    def test_latency_ii_conversion_is_not_invented(self):
        cfg, shape, fixture = smoke_input('ffn')
        cfg['ffn']['sample_II_cycles'] = 2
        with self.assertRaisesRegex(UnsupportedMapping, 'latency/II'):
            map_config('ffn', cfg, shape, fixture)

    def test_winner_budget_is_mapped_to_retained_count(self):
        cfg, shape, fixture = smoke_input('attention', 'winner')
        cfg['attention']['winner_update_multiplier'] = 3
        result, boundary = map_config('attention', cfg, shape, fixture)
        self.assertEqual((result.mode, result.samples), ('winner', 12))
        self.assertIn('after projection/RoPE and candidate screening', boundary['scope'])

    def test_gqa_and_unscreened_cropping_are_rejected(self):
        cfg, shape, fixture = smoke_input('attention')
        shape['num_attention_heads'] = 2
        with self.assertRaisesRegex(UnsupportedMapping, 'GQA'):
            map_config('attention', cfg, shape, fixture)
        shape['num_attention_heads'] = 1
        fixture['candidate_ids'] = [0, 3]
        with self.assertRaisesRegex(UnsupportedMapping, 'all physical context'):
            map_config('attention', cfg, shape, fixture)

    def test_unsupported_backend_and_clock_fail_closed(self):
        cfg, shape, fixture = smoke_input('ffn')
        cfg['dram']['backend'] = 'dramsys'
        with self.assertRaisesRegex(UnsupportedMapping, 'DRAMSys'):
            map_config('ffn', cfg, shape, fixture)
        cfg['dram']['backend'] = 'link'
        cfg['core_hz'] = 80_000_000
        with self.assertRaisesRegex(UnsupportedMapping, '100MHz'):
            map_config('ffn', cfg, shape, fixture)


if __name__ == '__main__':
    unittest.main()
