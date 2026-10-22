"""Independent protocol regressions for the encoding/restoration adapter.

Set ENCODE_CYCLE_BACKEND to a frozen Issue116 source snapshot. This suite checks
software contracts and exact FP32 ordering; it is not RTL, timing or PPA proof.
"""
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from architecture_tlm.encoding_restore_contract.adapter import Adapter, Profile
from architecture_tlm.encoding_restore_contract.arithmetic import add_words
from architecture_tlm.encoding_restore_contract.backend import load
from architecture_tlm.encoding_restore_contract.run_cycle import execute, fixture


def unit_counts(negative=False):
    """A real T32 frame: one active bin0 input, W=1, chosen input sign."""
    counts = [[[0] * 8 for _ in range(2)] for _ in range(4)]
    counts[0][int(negative)][0] = 32
    return tuple(tuple(tuple(planes) for planes in rails) for rails in counts)


def attach_unit_group(adapter, name, *, rows=1, scale=0x3f800000,
                      negative=False, sink=0):
    adapter.add_encode(name, [0xbf800000 if negative else 0x3f800000] + [0] * 63, frac=23)
    counts = unit_counts(negative)
    return adapter.add_restore_tile(
        name, rows=rows, counter_provider=lambda row: counts,
        representation='input_sign_twos_complement', count_width=12,
        samples=32, weight_scale_word=scale, sink_start_ps=sink)


class ReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = Path(os.environ['ENCODE_CYCLE_BACKEND']).resolve()
        cls.api, cls.hashes = load(cls.backend)

    def assert_credit_conservation(self, result, profile, prefix='er'):
        """Replay every transfer, including slots held by downstream adds.

        Individual resource/buffer peaks cannot establish this joint invariant.
        Stage membership here follows public trace transfers, not adapter state.
        """
        stages = {f'{prefix}.restore{lane}':
                  dict(free=profile.restore_depth, restore=0, ready=0, add=0)
                  for lane in range(profile.restore_lanes)}
        add_lane = {}
        seen = dict(restore=False, ready=False, add=False)
        encoded_free, encoded_reserved = 1, 0
        relevant = 0
        for event in result.trace:
            kind, resource = event['kind'], event.get('resource')
            if kind not in ('accept', 'complete'):
                continue
            if resource in stages:
                state = stages[resource]
                if kind == 'accept':
                    self.assertEqual(event['inputs'], {resource + '.free': 1})
                    state['free'] -= 1
                    state['restore'] += 1
                else:
                    self.assertEqual(event['outputs'], {resource + '.ready': 1})
                    state['restore'] -= 1
                    state['ready'] += 1
                relevant += 1
            elif resource == prefix + '.add':
                if kind == 'accept':
                    self.assertEqual(len(event['inputs']), 1)
                    name, amount = next(iter(event['inputs'].items()))
                    self.assertEqual(amount, 1)
                    self.assertTrue(name.endswith('.ready'))
                    lane = name[:-len('.ready')]
                    self.assertIn(lane, stages)
                    self.assertNotIn(event['op'], add_lane)
                    add_lane[event['op']] = lane
                    stages[lane]['ready'] -= 1
                    stages[lane]['add'] += 1
                else:
                    lane = add_lane.pop(event['op'])
                    self.assertEqual(event['outputs'], {lane + '.free': 1})
                    stages[lane]['add'] -= 1
                    stages[lane]['free'] += 1
                relevant += 1
            elif resource == prefix + '.encode' and kind == 'accept':
                self.assertEqual(event['inputs'], {prefix + '.encoded_free': 1})
                encoded_free -= 1
                encoded_reserved += 1
            elif resource == prefix + '.release' and kind == 'complete':
                self.assertEqual(event['outputs'], {prefix + '.encoded_free': 1})
                encoded_reserved -= 1
                encoded_free += 1
            for lane, state in stages.items():
                self.assertEqual(sum(state.values()), profile.restore_depth,
                                 (event, lane, state))
                self.assertTrue(all(0 <= n <= profile.restore_depth for n in state.values()),
                                (event, lane, state))
                for stage in seen:
                    seen[stage] |= state[stage] > 0
            self.assertEqual(encoded_free + encoded_reserved, 1)
            self.assertIn(encoded_free, (0, 1))
            self.assertIn(encoded_reserved, (0, 1))
        self.assertGreater(relevant, 0)
        self.assertTrue(all(seen.values()), seen)
        self.assertFalse(add_lane)
        self.assertEqual((encoded_free, encoded_reserved), (1, 0))
        self.assertEqual(result.buffer_final[prefix + '.encoded_free'], 1)
        for lane, state in stages.items():
            self.assertEqual(state, dict(free=profile.restore_depth, restore=0, ready=0, add=0))
            self.assertEqual(result.buffer_final[lane + '.free'], state['free'])
            self.assertEqual(result.buffer_final[lane + '.ready'], state['ready'])

    def test_credit_conservation_at_every_event_under_backpressure(self):
        profile = Profile(restore_lanes=3, restore_depth=2, restore_latency=3,
                          add_latency=3, add_ii=5, add_capacity=2)
        data = fixture(16, rows=7, groups=3, seed=20261023)
        results = []
        for mode in ('cycle', 'event'):
            result, values, receipts = execute(
                self.api, data, 16, 'input_sign_twos_complement', profile, mode,
                sink_start_ps=400000)
            self.assert_credit_conservation(result, profile)
            self.assertEqual(result.actions['complete_restore_output_b4'], 21)
            self.assertEqual(result.actions['cross_k_fp32_add'], 21)
            results.append((result.equivalence_payload(), values, receipts))
        self.assertEqual(*results)

    def test_reverse_lexical_group_names_with_one_slot_do_not_deadlock(self):
        profile = Profile(restore_depth=1, add_latency=3, add_ii=4, add_capacity=1)
        results = []
        for mode in ('cycle', 'event'):
            resources, buffers = profile.specs(self.api)
            kernel = self.api.Kernel(resources, buffers)
            adapter = Adapter(kernel, self.api, profile)
            attach_unit_group(adapter, 'z', rows=3, sink=300000)
            attach_unit_group(adapter, 'a', rows=3)
            result = kernel.run(mode)
            self.assertEqual(adapter.partial, {row: 0x40000000 for row in range(3)})
            self.assertGreater(result.accepted_ps['er.a.encode'],
                               result.completion_ps['er.z.release'])
            self.assert_credit_conservation(result, profile)
            results.append(result.equivalence_payload())
        self.assertEqual(*results)
        with self.assertRaisesRegex(ValueError, 'encoded_groups must be 1'):
            Profile(encoded_groups=2)

    def test_three_group_fp32_add_order_is_observable(self):
        # (2^24 + 1) rounds to 2^24 before adding -2^24, giving zero.
        # Reordering cancellation first would instead produce exactly one.
        self.assertEqual(add_words(add_words(0x4b800000, 0xcb800000), 0x3f800000),
                         0x3f800000)
        profile = Profile(restore_depth=1)
        for mode in ('cycle', 'event'):
            resources, buffers = profile.specs(self.api)
            kernel = self.api.Kernel(resources, buffers)
            adapter = Adapter(kernel, self.api, profile)
            attach_unit_group(adapter, 'z_large', scale=0x4b800000)
            attach_unit_group(adapter, 'm_one')
            attach_unit_group(adapter, 'a_negative', scale=0x4b800000, negative=True)
            result = kernel.run(mode)
            self.assertEqual([receipt['fp32_word'] for receipt in adapter.receipts],
                             [0x4b800000, 0x3f800000, 0xcb800000])
            self.assertEqual(adapter.partial, {0: 0})
            ids = [f'er.{name}.row000.add' for name in ('z_large', 'm_one', 'a_negative')]
            self.assertLess(result.completion_ps[ids[0]], result.accepted_ps[ids[1]])
            self.assertLess(result.completion_ps[ids[1]], result.accepted_ps[ids[2]])
            self.assert_credit_conservation(result, profile)

    def test_two_adapters_share_kernel_without_state_or_credit_aliasing(self):
        profile = Profile(restore_depth=1, add_latency=2)
        results = []
        for mode in ('cycle', 'event'):
            resources, buffers = [], []
            for prefix in ('left', 'right'):
                r, b = profile.specs(self.api, prefix)
                resources.extend(r)
                buffers.extend(b)
            kernel = self.api.Kernel(resources, buffers)
            left = Adapter(kernel, self.api, profile, 'left')
            right = Adapter(kernel, self.api, profile, 'right')
            attach_unit_group(left, 'same', rows=4, scale=0x40000000, sink=500000)
            attach_unit_group(right, 'same', rows=3, scale=0x40400000, negative=True)
            result = kernel.run(mode)
            self.assertEqual(left.partial, {row: 0x40000000 for row in range(4)})
            self.assertEqual(right.partial, {row: 0xc0400000 for row in range(3)})
            self.assertTrue(all(r['operation'].startswith('left.') for r in left.receipts))
            self.assertTrue(all(r['operation'].startswith('right.') for r in right.receipts))
            self.assertLess(result.completion_ps['right.same.release'],
                            result.accepted_ps['left.same.row000.add'])
            self.assertEqual(result.actions['complete_restore_output_b4'], 7)
            self.assertEqual(result.actions['cross_k_fp32_add'], 7)
            for prefix in ('left', 'right'):
                self.assert_credit_conservation(result, profile, prefix)
            results.append(result.equivalence_payload())
        self.assertEqual(*results)

    def test_loader_cache_changes_when_only_contracts_changes(self):
        # Explicit personal/workspace temporary root also works on shared hosts.
        base = Path(os.environ.get('ENCODE_CYCLE_REVIEW_TMP',
                    str(Path(__file__).resolve().parents[2] / 'outputs/encoding_restore_review_tmp')))
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='contracts_cache_', dir=base) as tmp:
            roots = [Path(tmp) / name for name in ('original', 'changed')]
            for root in roots:
                target = root / 'architecture_tlm/cycle_v1'
                target.mkdir(parents=True)
                for name in ('__init__.py', 'contracts.py', 'kernel.py', 'memory.py'):
                    shutil.copyfile(self.backend / 'architecture_tlm/cycle_v1' / name, target / name)
            changed = roots[1] / 'architecture_tlm/cycle_v1/contracts.py'
            with changed.open('a', encoding='utf-8', newline='\n') as stream:
                stream.write("\nResource.REVIEW_CACHE_MARKER = 'contract-only-change'\n")
            original, first_hashes = load(roots[0])
            repeated, _ = load(roots[0])
            altered, changed_hashes = load(roots[1])
            self.assertIs(original.Resource, repeated.Resource)
            self.assertEqual(first_hashes['kernel.py'], changed_hashes['kernel.py'])
            self.assertNotEqual(first_hashes['contracts.py'], changed_hashes['contracts.py'])
            self.assertIsNot(original.Resource, altered.Resource)
            self.assertFalse(hasattr(original.Resource, 'REVIEW_CACHE_MARKER'))
            self.assertEqual(altered.Resource.REVIEW_CACHE_MARKER, 'contract-only-change')
            self.assertIs(load(roots[0])[0].Resource, original.Resource)


if __name__ == '__main__':
    unittest.main()
