"""New circuit-boundary and schedule checks; no model-quality assertions."""
import copy
import unittest
from .config import tiny,load
from .ffn_latest import defaults,batch_cycles
from .model import FullDecode


def case():
    c,m=tiny();c['ffn'].update(defaults());c['ffn']['engines']=2
    c['attention']['mode']='exact'
    return c,m


class LatestContracts(unittest.TestCase):
    def test_actual_stage_and_no_z_materialization(self):
        c,m=case();r=FullDecode(c,m).run()
        self.assertNotIn('FFN_SwiGLU',r['phase_ns'])
        self.assertIn('FFN_AND_direct_down',r['phase_ns'])
        self.assertNotIn('SwiGLU_z_FP32',r['SRAM']['layout'])
        self.assertNotIn('group_absmax_calls',r['FFN_activity'])
        self.assertEqual(r['FFN_activity']['fixed_gu_encoded_values'],2*m['intermediate_size'])
        self.assertEqual(r['FFN_activity']['SC_64x64_tiles'],3*m['hidden_size']*m['intermediate_size']//4096)
        self.assertAlmostEqual(sum(r['phase_ns'].values()),r['metrics']['elapsed_ns'])
        self.assertIsNone(r['metrics']['full_physical_energy_J'])
        self.assertIn('SC_coefficient16_restore',r['unpriced_actions'])

    def test_independent_joint_demand_and_replay(self):
        c,m=case();c['ffn']['engines']=1;m['hidden_size']=128
        r=FullDecode(c,m).run();n=r['FFN_contract']['nonlinear_random']
        # F/64 input groups, H/64 output groups, only one resident output tile.
        self.assertEqual(n['counts']['save'],2)
        self.assertEqual(n['counts']['restore'],2)
        self.assertEqual(n['counts']['release'],2)
        self.assertEqual(n['counts']['R8_words'],4*64*192)
        self.assertEqual(n['counts']['useful_random_low_bits'],4*64*1216)
        self.assertEqual(n['random_stream_SRAM_bytes'],0)
        self.assertFalse(n['actual_endpoint_executed'])

    def test_T_changes_work_not_resident_weights(self):
        c,m=case();a=FullDecode(c,m).run();c['ffn']['nonlinear_samples']=128;b=FullDecode(c,m).run()
        self.assertEqual(a['DRAM']['traffic']['weights_physical_bytes'],b['DRAM']['traffic']['weights_physical_bytes'])
        self.assertEqual(a['FFN_activity']['SC_4bucket_tiles'],b['FFN_activity']['SC_4bucket_tiles'])
        self.assertEqual(b['FFN_contract']['nonlinear_random']['counts']['R8_words'],2*a['FFN_contract']['nonlinear_random']['counts']['R8_words'])
        self.assertGreater(b['phase_ns']['FFN_AND_direct_down'],a['phase_ns']['FFN_AND_direct_down'])

    def test_finite_random_throughput_stalls(self):
        c,m=case();c['ffn']['rng_nl'].update(seed_word_interval_cycles=1,warmup_cycles=0)
        a=FullDecode(c,m).run();c['ffn']['rng_nl']['words_per_cycle']=20;b=FullDecode(c,m).run()
        self.assertGreater(b['phase_ns']['FFN_AND_direct_down'],a['phase_ns']['FFN_AND_direct_down'])
        self.assertEqual(a['FFN_activity']['SC_product_trials'],b['FFN_activity']['SC_product_trials'])

    def test_hold_and_wide_capacity_reject(self):
        c,m=case();c['ffn']['local_weight_bytes']=4096
        with self.assertRaises(ValueError):FullDecode(c,m)
        c,m=case();c['ffn']['wide_bits']=32
        with self.assertRaises(ValueError):FullDecode(c,m)

    def test_reread_trades_traffic_for_hold(self):
        c,m=case();a=FullDecode(c,m).run();c['ffn'].update(weight_feed='sram_reread',local_weight_bytes=0)
        b=FullDecode(c,m).run()
        self.assertGreater(b['SRAM']['traffic']['read_logical_bytes'],a['SRAM']['traffic']['read_logical_bytes'])
        self.assertGreater(b['metrics']['elapsed_ns'],a['metrics']['elapsed_ns'])
        self.assertEqual(b['FFN_contract']['local_state']['weight_hold_bytes'],0)

    def test_resources_and_retirement(self):
        c,m=case();c['decode_tokens']=2;r=FullDecode(c,m).run();by={}
        for e in r['events']:
            for k in e['resources']:by.setdefault(k,[]).append((e['start_ns'],e['end_ns']))
        for k,events in by.items():
            events.sort()
            for a,b in zip(events,events[1:]):self.assertLessEqual(a[1],b[0]+1e-5,k)
        self.assertAlmostEqual(max(e['end_ns'] for e in r['events']),r['metrics']['elapsed_ns'])

    def test_current_input_random_backend_stays_real(self):
        c,m=case();c['random']['backend']='integrated_service'
        r=FullDecode(c,m).run()
        self.assertTrue(r['random_interface']['actual_backend_executed'])
        self.assertGreater(r['random_interface']['source_counts']['ffn_samples_consumed'],0)
        self.assertEqual(r['FFN_contract']['nonlinear_random']['clock_hz'],c['core_hz'])

    def test_attention_traffic_preserved(self):
        for mode in ('exact','pv','screen_exact','screen_pv','screen_winner','screen_rejection'):
            c,m=tiny();c['attention']['mode']=mode;a=FullDecode(c,m).run()
            c['ffn'].update(defaults());b=FullDecode(c,m).run()
            self.assertEqual(a['attention_activity'],b['attention_activity'],mode)
            self.assertEqual(a['row_receipts'],b['row_receipts'],mode)
            for key,val in a['DRAM']['traffic'].items():
                if key.startswith(('K_','V_','KV_','summary_')):
                    self.assertEqual(val,b['DRAM']['traffic'][key],key)

    def test_head_dim_shape_and_qknorm(self):
        c,m=case();m['head_dim']=64;m['qk_norm']=True
        d=FullDecode(c,m);self.assertEqual(d.matrix_info['L0/qkv']['out'],256)
        self.assertEqual(d.matrix_info['L0/o']['inp'],128)
        r=d.run();self.assertIn('QK_head_norm',r['phase_ns'])

    def test_qwen3_config_and_capacity(self):
        c,m=load('qwen3_4b');d=FullDecode(c,m)
        self.assertEqual((d.d,d.q_width),(128,4096))
        self.assertEqual(d.matrix_info['L0/gu']['bytes']+d.matrix_info['L0/down']['bytes'],74711040)
        self.assertLessEqual(d.arena.peak,c['sram']['capacity_bytes'])
        self.assertLessEqual(d.ffn_latest.report()['down_width_bound'],64)

    def test_batch_tail_not_one_vector_cycle(self):
        self.assertEqual(batch_cycles(512,16,6),37)
        self.assertEqual(batch_cycles(64,16,1),4)

if __name__=='__main__':unittest.main()
