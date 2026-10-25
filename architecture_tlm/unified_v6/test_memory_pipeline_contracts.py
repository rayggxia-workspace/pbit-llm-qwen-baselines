"""Issue182 independently authored memory-pipeline acceptance checks.

This suite targets the agreed minimum implementation: prefetch the next wave's
DRAM DMA during the current SC wave; defer SRAM fill and coefficient handling
until the current restore completes. It does not require an interval scheduler
or claim a fully overlapped SRAM-fill pipeline.

Run after implementation, with the intended checkout explicitly selected::

    $env:PBIT_TLM_CHECKOUT = 'C:/absolute/path/to/issue182-checkout'
    python -B test_memory_pipeline_contracts.py -v

Alternatively copy this file into architecture_tlm/unified_v6 and invoke it
with unittest. The tests use existing public configuration and event names.
They spy on DRAM tensor calls, so individual 32-burst Link windows are not
mistaken for independent SC waves. No models, weights, network, or files are
created by the tests. Full shape/performance/DRAMSys integration runs belong
to the parent task, with immutable manifests and actual-backend evidence.

The focused geometry has 15 GU waves (3 input groups x 5 output waves),
including repeated ping/pong reuse. Full decode also has 10 down waves and a
one-engine tail. This is conditional timing/ownership validation, not PPL,
RTL, STA, or evidence for the physical local-weight holding macro.
"""

import copy
import os
from pathlib import Path
import sys
import unittest
from functools import lru_cache
from unittest.mock import patch


CHECKOUT = os.environ.get('PBIT_TLM_CHECKOUT')
if CHECKOUT:
    selected = Path(CHECKOUT).resolve()
    if not (selected / 'architecture_tlm' / 'unified_v6' / 'model.py').is_file():
        raise RuntimeError('PBIT_TLM_CHECKOUT is not the intended TLM checkout')
    sys.path.insert(0, str(selected))

from architecture_tlm.unified_v6.config import tiny
from architecture_tlm.unified_v6.ffn_latest import defaults
from architecture_tlm.unified_v6.model import FullDecode


EPS = 1e-5
ARRAY_STAGES = {'SC_gate_up', 'SC_AND_direct_Wd'}
TIME_ACTIONS = {
    'dram_background_ns', 'digital_idle_ns', 'sc_idle_ns',
    'control_interconnect_ns',
}


def case(double_buffer=True, long_array=False, decode_tokens=1):
    cfg, shape = tiny()
    cfg['ffn'].update(defaults())
    cfg['ffn'].update(engines=2, local_weight_load_bytes_per_cycle=1024,
                      weight_schedule='dma_prefetch')
    if long_array:
        cfg['ffn']['sample_II_cycles'] = 32
    cfg.update(double_buffer=double_buffer, decode_tokens=decode_tokens,
               trace_event_limit=200000, weight_chunk_bytes=32768)
    cfg['random']['backend'] = 'local_prng_interface'
    cfg['attention']['mode'] = 'exact'
    cfg['sram'].update(capacity_bytes=8 * 1024**2, banks=64,
                       word_bytes=16, macro_depth=4096, clock_hz=80000000,
                       fabric_GBs=64.)
    cfg['dram']['backend'] = 'link'
    shape.update(hidden_size=192, intermediate_size=320,
                 num_hidden_layers=1, vocab_size=128)
    return cfg, shape


def expected_waves(cfg, shape, which):
    h, f = shape['hidden_size'], shape['intermediate_size']
    engines = cfg['ffn']['engines']
    inp, groups = (h, 2 * f // 64) if which == 'gu' else (f, h // 64)
    return (inp // 64) * ((groups + engines - 1) // engines)


def only(events, stage):
    return [event for event in events if event['stage'] == stage]


@lru_cache(maxsize=8)
def run_gu(double_buffer=True, long_array=False):
    """Capture whole-wave DMA calls separately from Link request windows."""
    cfg, shape = case(double_buffer, long_array)
    decode = FullDecode(cfg, shape)
    calls = []
    original = decode.dram.tensor

    def tensor(ready, name, offset, size, write=False, kind='weights'):
        before = len(decode.s.events)
        done = original(ready, name, offset, size, write=write, kind=kind)
        if name == 'L0/gu' and kind in ('weights', 'weight_scales'):
            emitted = decode.s.events[before:]
            stages = [e for e in emitted if e['stage'] == 'dram_' + kind]
            if not stages:
                raise AssertionError('expected untruncated DRAM event evidence')
            calls.append(dict(kind=kind, offset=offset, bytes=size,
                              ready_ns=ready,
                              start_ns=min(e['start_ns'] for e in stages),
                              end_ns=done, window_count=len(stages)))
        return done

    with patch.object(decode.dram, 'tensor', side_effect=tensor):
        end = decode.ffn_latest.gate_up(0., 0)
    if decode.s.count != len(decode.s.events):
        raise AssertionError('focused lifecycle evidence must not be truncated')
    return dict(config=cfg, shape=shape, events=copy.deepcopy(decode.s.events),
                calls=calls, end_ns=end, slots=list(decode.slots),
                slot_free=list(decode.slot_free),
                activity=dict(decode.metadata), actions=dict(decode.e.actions),
                dram_traffic=dict(decode.dram.traffic),
                sram_traffic=dict(decode.mem.traffic))


@lru_cache(maxsize=4)
def run_full(double_buffer=True, decode_tokens=1):
    cfg, shape = case(double_buffer, decode_tokens=decode_tokens)
    result = FullDecode(cfg, shape).run()
    if result['trace_truncated']:
        raise AssertionError('full small-shape evidence must not be truncated')
    return result


class WeightLifecycle(unittest.TestCase):
    def assert_before(self, first, second, message):
        self.assertLessEqual(first['end_ns'], second['start_ns'] + EPS,
                             message)

    def test_at_least_three_waves_program_before_array_without_overwrite(self):
        run = run_gu(True, True)
        events = run['events']
        programs = only(events, 'SC_local_weight_program')
        arrays = only(events, 'SC_gate_up')
        count = expected_waves(run['config'], run['shape'], 'gu')
        self.assertEqual(count, 15)
        self.assertGreaterEqual(count, 3)
        self.assertEqual(len(programs), count)
        self.assertEqual(len(arrays), count)
        for i, (program, array) in enumerate(zip(programs, arrays)):
            self.assert_before(program, array, 'wave must be programmed first')
            self.assertEqual(program['bytes'], array['tiles'] * 4096)
            if i:
                self.assert_before(arrays[i - 1], program,
                                   'single local weight macro cannot be overwritten')
        self.assertEqual(sum(p['bytes'] for p in programs),
                         2 * run['shape']['hidden_size'] *
                         run['shape']['intermediate_size'])

    def test_dma_fill_program_chain_and_deferred_fill(self):
        run = run_gu(True, True)
        events = run['events']
        dmas = [c for c in run['calls'] if c['kind'] == 'weights']
        coefficients = [c for c in run['calls'] if c['kind'] == 'weight_scales']
        fills = only(events, 'sram_weight_fill')
        programs = only(events, 'SC_local_weight_program')
        restored = [e for e in only(events, 'sram_SC_wide_partial')
                    if e['write']]
        count = expected_waves(run['config'], run['shape'], 'gu')
        for evidence in (dmas, coefficients, fills, programs, restored):
            self.assertEqual(len(evidence), count)
        for i in range(count):
            self.assert_before(dmas[i], fills[i], 'fill before DMA completion')
            self.assert_before(fills[i], programs[i], 'program before fill')
            self.assertEqual(dmas[i]['bytes'], fills[i]['bytes'])
            self.assertEqual(fills[i]['bytes'], programs[i]['bytes'])
            if i:
                self.assert_before(restored[i - 1], fills[i],
                                   'minimum implementation defers next fill')
                self.assert_before(restored[i - 1], coefficients[i],
                                   'coefficient scratch still belongs to restore')

    def test_dma_really_overlaps_array_but_single_buffer_does_not(self):
        pipelined = run_gu(True, True)
        serial = run_gu(False, True)
        arrays = only(pipelined['events'], 'SC_gate_up')
        dmas = [c for c in pipelined['calls'] if c['kind'] == 'weights']
        self.assertLess(dmas[1]['start_ns'], arrays[0]['end_ns'],
                        'double_buffer must prefetch during the current wave')
        self.assertGreaterEqual(dmas[1]['start_ns'] + EPS,
                                arrays[0]['start_ns'])
        serial_dmas = [c for c in serial['calls'] if c['kind'] == 'weights']
        serial_restores = [e for e in only(serial['events'],
                                         'sram_SC_wide_partial') if e['write']]
        for previous, current in zip(serial_restores, serial_dmas[1:]):
            self.assert_before(previous, current,
                               'disabled buffering must not prefetch the next wave')
        self.assertLess(pipelined['end_ns'], serial['end_ns'])

    def test_wave_payload_covered_once_and_bursts_audited_separately(self):
        run = run_gu(True, True)
        dmas = [c for c in run['calls'] if c['kind'] == 'weights']
        cursor = 0
        for dma in dmas:
            self.assertEqual(dma['offset'], cursor)
            cursor += dma['bytes']
        self.assertEqual(cursor, 2 * run['shape']['hidden_size'] *
                         run['shape']['intermediate_size'])
        self.assertEqual(len(dmas), 15)
        self.assertEqual(run['dram_traffic']['weights_bursts'], cursor // 64)
        self.assertGreaterEqual(sum(d['window_count'] for d in dmas), len(dmas))


class ConservationAndResources(unittest.TestCase):
    def test_single_double_buffer_conserve_work_and_traffic(self):
        serial, pipelined = run_full(False), run_full(True)
        for key in ('FFN_activity', 'attention_activity', 'row_receipts'):
            self.assertEqual(serial[key], pipelined[key], key)
        for key in ('DRAM', 'SRAM'):
            self.assertEqual(serial[key]['traffic'], pipelined[key]['traffic'], key)
        # Asynchronous DMA buffering may have additional real storage actions;
        # compare existing compute work, while DRAM/SRAM traffic is exact above.
        work = lambda r: {k: v for k, v in r['actions'].items()
                          if k not in TIME_ACTIONS and not k.startswith('DMA_')
                          and 'prefetch_buffer' not in k.lower()}
        self.assertEqual(work(serial), work(pipelined))
        self.assertEqual(serial['random_interface'], pipelined['random_interface'])
        self.assertIsNone(pipelined['metrics']['full_physical_energy_J'])
        self.assertIsNone(pipelined['metrics']['full_physical_area_mm2'])
        self.assertEqual(pipelined['FFN_activity']['SC_64x64_tiles'], 45)
        self.assertEqual(len(only(pipelined['events'], 'SC_local_weight_program')),
                         25)
        down = only(pipelined['events'], 'SC_AND_direct_Wd')
        self.assertEqual(len(down), 10)
        self.assertIn(1, {e['tiles'] for e in down}, 'exercise a partial engine wave')

    def test_every_shared_resource_excludes_overlap(self):
        result = run_full(True)
        by_resource = {}
        for event in result['events']:
            for resource in event['resources']:
                by_resource.setdefault(resource, []).append(event)
        self.assertIn('sram_fabric', by_resource)
        self.assertEqual(len([r for r in by_resource if r.startswith('sram_bank:')]),
                         64)
        for resource, events in by_resource.items():
            events.sort(key=lambda e: (e['start_ns'], e['end_ns']))
            for previous, current in zip(events, events[1:]):
                self.assertLessEqual(previous['end_ns'], current['start_ns'] + EPS,
                                     resource)
        fills = only(result['events'], 'sram_weight_fill')
        for fill in fills:
            if fill['bytes'] >= 64 * 16:
                self.assertEqual(len([r for r in fill['resources']
                                      if r.startswith('sram_bank:')]), 64)
                self.assertIn('sram_fabric', fill['resources'])

    def test_two_tokens_retire_all_scheduled_resources(self):
        result = run_full(True, 2)
        self.assertEqual(len(result['metrics']['token_ms']), 2)
        self.assertEqual(result['FFN_activity']['SC_64x64_tiles'], 90)
        self.assertAlmostEqual(max(e['end_ns'] for e in result['events']),
                               result['metrics']['elapsed_ns'], places=5)
        self.assertAlmostEqual(sum(result['phase_ns'].values()),
                               result['metrics']['elapsed_ns'], places=5)

    def test_64_banks_keep_capacity_and_charge_response_elasticity(self):
        cfg, shape = case()
        wide = FullDecode(cfg, shape)
        cfg['sram'].update(banks=16, fabric_GBs=16.)
        narrow = FullDecode(cfg, shape)
        self.assertEqual(wide.mem.physical_capacity, 8 * 1024**2)
        self.assertEqual(wide.mem.physical_capacity, narrow.mem.physical_capacity)
        self.assertEqual(wide.mem.macros, 128)
        self.assertEqual(wide.mem.macros, narrow.mem.macros)
        self.assertLessEqual(wide.arena.peak, wide.arena.capacity)
        local = wide.ffn_latest.report()['local_state']
        self.assertEqual(local['weight_hold_bytes'], cfg['ffn']['local_weight_bytes'])
        self.assertEqual(local['weight_response_buffer_bytes'], 2048)
        self.assertGreaterEqual(local['dma_prefetch_buffer_bytes'],
                                cfg['ffn']['engines'] * 4096)


class InvalidConfigurations(unittest.TestCase):
    def test_local_hold_smaller_than_wave_rejected(self):
        cfg, shape = case()
        cfg['ffn']['local_weight_bytes'] = 2 * 4096 - 1
        with self.assertRaises(ValueError):
            FullDecode(cfg, shape)

    def test_ping_pong_slot_smaller_than_wave_rejected(self):
        cfg, shape = case()
        cfg['weight_chunk_bytes'] = 2 * 4096 - 1
        with self.assertRaises(ValueError):
            FullDecode(cfg, shape)

    def test_25p6_GBs_receiver_cannot_accept_64_GBs_without_throttling(self):
        cfg, shape = case()
        cfg['ffn']['local_weight_load_bytes_per_cycle'] = 256
        with self.assertRaises(ValueError):
            decode = FullDecode(cfg, shape)
            decode.ffn_latest.gate_up(0., 0)

    def test_live_regions_exceeding_sram_capacity_rejected(self):
        cfg, shape = case()
        cfg['sram']['capacity_bytes'] = 65536
        with self.assertRaises(ValueError):
            FullDecode(cfg, shape)

    def test_sram_clock_above_calibrated_macro_limit_rejected(self):
        cfg, shape = case()
        cfg['sram']['clock_hz'] = 1000000000
        with self.assertRaises(ValueError):
            FullDecode(cfg, shape)


class CrossInputGroupPrefetch(unittest.TestCase):
    def test_single_output_wave_still_prefetches_next_input_group(self):
        c,m=tiny();m.update(hidden_size=192,intermediate_size=320,vocab_size=384)
        c['attention']['mode']='exact';c['ffn'].update(defaults());c['ffn'].update(engines=16,local_weight_bytes=65536,weight_schedule='dma_prefetch')
        c['weight_chunk_bytes']=65536
        a=FullDecode(c,m).run();c['ffn']['prefetch_across_input_groups']=True;b=FullDecode(c,m).run()
        self.assertLess(b['metrics']['elapsed_ns'],a['metrics']['elapsed_ns'])
        self.assertEqual(a['DRAM']['traffic'],b['DRAM']['traffic'])
        self.assertEqual(a['FFN_activity'],b['FFN_activity'])
        self.assertEqual(a['SRAM']['traffic'],b['SRAM']['traffic'])
        self.assertEqual(b['FFN_contract']['weight_pipeline']['counts']['cross_input_group_prefetches'],6)
        self.assertFalse(b['FFN_contract']['weight_pipeline']['pending'])
        rec=b['FFN_contract']['weight_pipeline']['records']
        for x,y in zip(rec,rec[1:]):
            self.assertGreaterEqual(y['program_start_ns'],x['restore_done_ns'])
            if x['name']==y['name']:self.assertLess(y['issue_ns'],x['array_done_ns'])
    def test_no_cross_group_prefetch_when_single_buffer(self):
        c,m=tiny();m.update(hidden_size=192,intermediate_size=320,vocab_size=384)
        c['double_buffer']=False;c['attention']['mode']='exact';c['ffn'].update(defaults())
        c['ffn'].update(engines=2,weight_schedule='dma_prefetch',prefetch_across_input_groups=True)
        r=FullDecode(c,m).run()
        self.assertEqual(r['FFN_contract']['weight_pipeline']['counts'].get('cross_input_group_prefetches',0),0)
        self.assertFalse(r['FFN_contract']['weight_pipeline']['pending'])

if __name__ == '__main__':
    unittest.main()
