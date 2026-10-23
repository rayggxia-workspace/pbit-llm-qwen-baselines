"""Issue104: observer-only cycle/attempt accounting, without new algorithms.

The pre-observer digests were independently captured from PR103 commit
b05fb36d8104eb07b33a9af13c747ca2722728cf, before merging these hooks.
They cover every pre-observer output field, including configuration, timing,
actions and prices. Historical eb317e4f archives remain bound in inspector tests.
"""
import hashlib
import json
import random
import unittest

from architecture_tlm.unified_v6.config import tiny
from architecture_tlm.unified_v6.model import FullDecode
from winner_hold_tlm_v5 import WinnerHoldSampler
from corrected_rejection_tlm_v5 import CorrectedRejectionSampler
from parallel_sampler_v5 import SamplingCapError


BASELINE_DIGESTS = {'exact': '16c4fdbb7329191f3746d57952287ffb65917f4fa10a13c7e6a7d32d13e8f0f0', 'screen_pv': '9f67c7a14a27860fc26c37cdbfa39416d4f7d18197a8fd839016daa781fe74e6', 'screen_winner': 'd281d328bfdd358321bcef66bb23654b5aaf78764bb26ddf7d15457493c19f8c', 'screen_rejection': 'e031c0e3ec15142ddbb7c4f50918dfa89d5e28b2347ffc292f8462440b680140', 'screen_serial_ising': '2b66b89eff92f53953b0b8b5d386e44f999cf7ff4467396451d9bebe528a35f5'}

INTEGRATED_DIGESTS = {'exact': 'aae0dc698f10335aeb6f7a7291b604c3b4ed811dbc23bdc8ecc6639eb975ee93', 'pv': 'e4ceb38f1ed5fb7c47d1d8fecac04de596d9cfdcaa5fb9000b6512a28c55c8ed', 'screen_exact': '6bcff10486a6f466c6e26e0a8becdf0a8845977a3328769979080bd0b50e6239', 'screen_pv': 'a5b85381c7fe4a0b56707f60925219dd6cd77b8eacaf88edcd3ec9e9a1dc2b2b', 'screen_winner': '074acef83647722df57d0192afb5f34426e6a3a3515eb260234063b8ddc97fc1', 'screen_rejection': '9dd0ff60844dff2777735c792b80acc8dba670674235a8abbad48e4d875b9f45'}


class AlwaysActive:
    kind = 'deterministic_failure_fixture'

    def draw(self, drives):
        return [True]*len(drives)

    def fair(self, width):
        return 0


class ObserverContracts(unittest.TestCase):
    def test_stage_totals_exist_without_detailed_events(self):
        for sampler in (WinnerHoldSampler, CorrectedRejectionSampler):
            with self.subTest(sampler=sampler.__name__):
                _, r = sampler(dict(record_events=False), 4).request(
                    3., [0., -.5, -1., -2.], 8, random.Random(19),
                    (0, 0, 0), [0, 1, 2, 3], output_ns_per_index=31.)
                self.assertEqual(r['events'], [])
                self.assertEqual(sum(r['stage_cycles'].values()), r['elapsed_cycles'])
                self.assertEqual(r['stage_calls']['parallel_source_read'],
                                 r['actions']['proposal_frames'])
                self.assertEqual(r['stage_calls']['output_transfer'], r['samples'])
                self.assertEqual(r['stage_cycles']['output_transfer'], 4*r['samples'])

    def test_event_recording_does_not_change_compact_observation(self):
        for sampler in (WinnerHoldSampler, CorrectedRejectionSampler):
            records = []
            for record in (False, True):
                _, r = sampler(dict(record_events=record), 4).request(
                    0., [0., -.5, -1., -2.], 12, random.Random(23),
                    (0, 0, 0), [0, 1, 2, 3])
                r.pop('events'); r.pop('frames')
                records.append(r)
            self.assertEqual(records[0], records[1])

    def test_failed_proposals_retain_stage_totals(self):
        m = CorrectedRejectionSampler(dict(max_proposals_per_sample=1), 4)
        with self.assertRaises(SamplingCapError) as failed:
            m.request(0., [0., -.5, -1., -2.], 2, random.Random(0),
                      (0, 0, 0), [0, 1, 2, 3], source=AlwaysActive())
        r = failed.exception.receipt
        self.assertEqual(r['status'], 'failed_cap')
        self.assertEqual(r['actions']['rejected_multi'], 2)
        self.assertEqual(sum(r['stage_cycles'].values()), r['elapsed_cycles'])

    def test_full_results_preserve_every_legacy_field(self):
        for mode, expected in BASELINE_DIGESTS.items():
            with self.subTest(mode=mode):
                c, m = tiny(); c['attention']['mode'] = mode
                r = FullDecode(c, m).run()
                r.pop('stage_busy_ns'); r.pop('sampler_audit')
                raw = json.dumps(r, sort_keys=True, separators=(',', ':'),
                                 allow_nan=False).encode()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)

    def test_integrated_outputs_equal_frozen_pre_observer_backend(self):
        for mode, expected in INTEGRATED_DIGESTS.items():
            with self.subTest(mode=mode):
                c, m = tiny()
                c['random'].update(backend='integrated_service',
                                   seed_word_interval_cycles=2, seed_startup_cycles=3)
                c['attention']['mode'] = mode
                r = FullDecode(c, m).run()
                for a in r['sampler_audit']:
                    self.assertEqual(sum(a['stage_cycles'].values()), a['elapsed_cycles'])
                r.pop('stage_busy_ns'); r.pop('sampler_audit')
                raw = json.dumps(r, sort_keys=True, separators=(',', ':'),
                                 allow_nan=False).encode()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)

    def test_every_sampler_head_is_retained_and_reconciles(self):
        for mode in ('screen_winner', 'screen_rejection', 'screen_serial_ising'):
            with self.subTest(mode=mode):
                c, m = tiny(); c['attention']['mode'] = mode
                c['decode_tokens'] = 2; m['num_hidden_layers'] = 2
                c['trace_event_limit'] = 1; c['row_receipt_limit'] = 1
                r = FullDecode(c, m).run()
                rows = r['sampler_audit']
                self.assertTrue(r['trace_truncated'])
                self.assertEqual(len(r['row_receipts']), 1)
                self.assertEqual(len(rows), 2*2*m['num_attention_heads'])
                self.assertEqual(len({(a['token'], a['layer'], a['head']) for a in rows}), len(rows))
                self.assertAlmostEqual(sum(a['end_ns']-a['start_ns'] for a in rows),
                                       r['resource_busy_ns']['sampler'])
                self.assertEqual(sum(a['outputs'] for a in rows),
                                 r['attention_activity']['V_sample_events'])
                for a in rows:
                    self.assertEqual(sum(a['stage_cycles'].values()), a['elapsed_cycles'])
                    self.assertAlmostEqual(a['elapsed_cycles']*a['clock_ns'],
                                           a['end_ns']-a['start_ns'])
                    self.assertNotIn('local_indices', a)
                    self.assertNotIn('bits', a)
                    if mode == 'screen_rejection':
                        self.assertEqual(a['proposal_frames'], a['outputs']+
                                         a['rejected_multi']+a['rejected_empty'])
                    elif mode == 'screen_winner':
                        self.assertEqual(a['proposal_frames'], a['algorithm_updates'])
                if mode != 'screen_serial_ising':
                    self.assertEqual(sum(a['elapsed_cycles'] for a in rows),
                                     r['actions']['sampler_macro_active_cycles'])
                    self.assertEqual(sum(a['proposal_frames'] for a in rows),
                                     r['attention_activity']['sampler_proposal_frames'])
                    self.assertEqual(sum(a['source_lane_work']['source_slot_cycles'] for a in rows),
                                     r['random_interface']['demands']['embedded_source_cycles'])
                else:
                    self.assertEqual(sum(a['attempts'] for a in rows),
                                     r['attention_activity']['serial_attempts'])

    def test_stage_totals_are_busy_time_not_a_serial_sum(self):
        c, m = tiny(); c['trace_event_limit'] = 20000
        r = FullDecode(c, m).run()
        stages = {}
        self.assertFalse(r['trace_truncated'])
        for event in r['events']:
            name = event['stage']
            stages[name] = stages.get(name, 0.) + event['end_ns']-event['start_ns']
        self.assertEqual(set(stages), set(r['stage_busy_ns']))
        for name, duration in stages.items():
            self.assertAlmostEqual(duration, r['stage_busy_ns'][name])


if __name__ == '__main__':
    unittest.main()
