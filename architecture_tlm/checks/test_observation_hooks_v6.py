"""Issue104: observer-only cycle/attempt accounting, without new algorithms.

The five complete-result digests were produced before editing, at integration
eb317e4f6fb1b0d8844887401f3275f128ef8a83, using config.tiny() and Python3.12.
They cover every legacy output field, including timing, actions and prices.
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


BASELINE_DIGESTS = {
    'exact': '3be3244ec3cef7a22a403f69474f90bdd7abae0843055610163c9a76441f572e',
    'screen_pv': '534bfc5dc14c5758c7fe44202d08ad303aca2c7d917d79ce4214a9bfe02a1368',
    'screen_winner': '5e1dd1f6c150e5fced31c35f288abb376f4c5e0913b50079586fda123b963b69',
    'screen_rejection': '3be6bd7dbe1775d7c8fb6b8744a1bffa0f467ef300c41f54a4e37e5275f0d522',
    'screen_serial_ising': '02f8695ffea312ebb23f6c974da4faa6148d6059a539e0f31f6fc0f8a116f8e7',
}


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
