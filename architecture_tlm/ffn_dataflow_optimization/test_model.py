import hashlib
import os
from pathlib import Path
import unittest

from .dependencies import load
from .fixtures import build_fixture
from .model import Config, execute


class DataflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        default = Path(__file__).resolve().parents[4]/'outputs/asic_recovery_dataflow_20261023/dependencies'
        cls.deps = load(os.environ.get('FFN_DATAFLOW_DEPS',
                        os.environ.get('FFN_DATAFLOW_DEPENDENCIES', str(default))))
        cls.fixture = build_fixture(cls.deps.restore, groups=2, tiles=1, rows_per_tile=2)

    def config(self, **kwargs):
        return Config(groups=2, tiles=1, rows_per_tile=2, **kwargs)

    def test_cycle_event_every_observable_and_both_numeric_outputs(self):
        for method in ('sc', 'w8'):
            event = execute(self.deps, self.fixture, self.config(), method, 'event')
            cycle = execute(self.deps, self.fixture, self.config(), method, 'cycle')
            self.assertEqual(event['result'].equivalence_payload(), cycle['result'].equivalence_payload())
            self.assertEqual(event['output_words'], self.fixture['expected_'+method])

    def test_paid_counter_copy_before_release_under_backpressure(self):
        profile = dict(restore_latency=30, restore_depth=2, restore_lanes=2, add_ii=5)
        out = execute(self.deps, self.fixture, self.config(weight_slots=2, counter_slots=2,
            staging_packets=1, partial_write_slots=1, profile=profile, sink_start_ps=2000000))
        result = out['result']
        self.assertLessEqual(out['storage']['credit_peak_used']['staging_free'], 1)
        self.assertTrue(any(event['kind'] == 'stall' and 'input_empty' in event.get('reason', '') for event in result.trace))
        for group in range(2):
            release = result.accepted_ps['k%04d.counter_release' % group]
            for row in range(2):
                prefix = 'k%04d.r%05d' % (group, row)
                self.assertGreater(release, result.completion_ps[prefix+'.counter_read'])
                self.assertGreater(result.accepted_ps[prefix+'.add'], result.completion_ps[prefix+'.restore'])

    def test_same_feed_and_storage_interface_for_w8(self):
        sc = execute(self.deps, self.fixture, self.config())
        w8 = execute(self.deps, self.fixture, self.config(), 'w8')
        self.assertEqual(sc['feed_template'], w8['feed_template'])
        for name in ('weight_hold_bytes', 'counter_allocated_bytes', 'staging_allocated_bytes',
                     'output_slots', 'partial_sram_bytes'):
            self.assertEqual(sc['storage'][name], w8['storage'][name])
        self.assertNotIn('complete_b4_restore', w8['result'].actions)
        self.assertEqual(w8['result'].actions['w8_mac'], 2*2*64)
        self.assertEqual(sc['result'].actions['partial_write_physical_bytes'], 2*2*16)
        self.assertEqual(sc['result'].actions['partial_read_physical_bytes'], 2*16)

    def test_feed_offsets_replay_and_partial_fabric_are_exclusive(self):
        out = execute(self.deps, self.fixture, self.config(weight_slots=2, counter_slots=2))
        result = out['result']
        for receipt in out['feed_receipts']:
            self.assertEqual(receipt['offset_ps'] % 50000, 0)
            self.assertEqual(receipt['replay_validation']['samples_completed'], 32)
            self.assertGreater(receipt['consumer_start_ps'], receipt['last_hold_write_ps'])
        intervals = [(result.accepted_ps[name], end, name) for name, end in result.completion_ps.items()
                     if name.endswith(('.feed', '.partial_read', '.partial_write'))]
        contract = out['partial_io_contract']
        self.assertEqual(contract['unrounded_service_ps'], 12500+20000+1000)
        self.assertEqual(contract['service_ps'], 37500)
        self.assertEqual(contract['rounding_guard_ps'], 4000)
        for begin, end, name in intervals:
            if name.endswith(('.partial_read', '.partial_write')):
                self.assertEqual(end-begin, contract['service_ps'])
        for index, (begin, end, name) in enumerate(intervals):
            for other_begin, other_end, other in intervals[index+1:]:
                self.assertTrue(end <= other_begin or other_end <= begin, (name, other))

    def test_zero_and_invalid_resources_fail(self):
        for field in ('weight_slots', 'counter_slots', 'counter_read_ports', 'staging_packets', 'partial_write_slots'):
            with self.assertRaises(ValueError):
                execute(self.deps, self.fixture, self.config(**{field: 0}))
        with self.assertRaises(ValueError):
            execute(self.deps, self.fixture, self.config(counter_read_bytes=32))
        with self.assertRaises(ValueError):
            execute(self.deps, self.fixture, self.config(profile={'restore_lanes': 0}))
        with self.assertRaises(ValueError):
            execute(self.deps, self.fixture, self.config(feed_overrides={'fabric_bytes_per_second': 0}))

    def test_multigroup_multiport_fifo_and_masked_sram_replay(self):
        fixture = build_fixture(self.deps.restore, groups=3, tiles=1, rows_per_tile=9)
        cfg = Config(groups=3, tiles=1, rows_per_tile=9, weight_slots=2, counter_slots=2,
            counter_read_bytes=128, counter_read_ports=2, staging_packets=3,
            partial_write_slots=1, sink_start_ps=2000000,
            profile=dict(restore_latency=7, restore_lanes=2, restore_depth=2, add_ii=5))
        for method in ('sc', 'w8'):
            out = execute(self.deps, fixture, cfg, method)
            cycle = execute(self.deps, fixture, cfg, method, 'cycle')
            self.assertEqual(out['result'].equivalence_payload(), cycle['result'].equivalence_payload())
            self.assertEqual(out['partial_receipts'], cycle['partial_receipts'])
            self.assertEqual(out['output_words'], fixture['expected_'+method])
            layout = out['storage']['sram_layout']
            self.assertEqual(layout['weight_wave_bases'], [0, 576, 1152])
            self.assertEqual(layout['partial_base'], 1728)
            self.assertEqual(out['storage']['partial_sram_bytes'], 48)
            image = bytearray(layout['capacity_bytes'])
            for group, template in enumerate(out['feed_templates']):
                base = layout['weight_wave_bases'][group]
                payload = bytes(value & 255 for row in fixture['inputs'][group]['weights'] for value in row)
                image[base:base+len(payload)] = payload
                self.assertEqual(template['addresses'], list(range(base, base+576, 16)))
                self.assertEqual(out['feed_receipts'][group]['weight_payload_sha256'], hashlib.sha256(payload).hexdigest())
            accumulator = [0]*9
            versions = [0]*9
            for receipt in out['partial_receipts']:
                group, row = receipt['group'], receipt['row']
                address, physical = receipt['address'], receipt['physical_address']
                self.assertEqual(address, layout['partial_base']+row*4)
                self.assertEqual(physical, address//16*16)
                self.assertEqual(receipt['completion_ps'], out['result'].completion_ps[receipt['operation']])
                before = bytes(image[physical:physical+16])
                self.assertEqual(receipt['before_hex'], before.hex())
                self.assertEqual(receipt['byte_enable'], 15 << (address % 16))
                if receipt['kind'] == 'write':
                    self.assertEqual(versions[row], group)
                    accumulator[row] = self.deps.restore.add_words(accumulator[row], fixture[method+'_partials'][group][row])
                    versions[row] += 1
                    self.assertEqual(receipt['word'], accumulator[row])
                    image[address:address+4] = receipt['word'].to_bytes(4, 'little')
                else:
                    self.assertEqual(versions[row], group)
                    self.assertEqual(receipt['word'], int.from_bytes(image[address:address+4], 'little'))
                self.assertEqual(receipt['after_hex'], bytes(image[physical:physical+16]).hex())
            self.assertEqual(versions, [3]*9)
            self.assertEqual(hashlib.sha256(image).hexdigest(), out['final_sram_sha256'])
            self.assertEqual(out['result'].buffer_final,
                             {key: spec.initial for key, spec in out['kernel'].buffer_specs.items()})

    def test_sram_layout_capacity_is_checked_before_feed(self):
        with self.assertRaisesRegex(ValueError, 'immutable weight waves'):
            execute(self.deps, self.fixture, self.config(feed_overrides={'sram_capacity_bytes': 256}))


if __name__ == '__main__':
    unittest.main()
