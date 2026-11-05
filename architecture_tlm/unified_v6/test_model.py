"""Mechanism checks: counts, dependencies, capacity, replay and address traffic."""
import copy
import math
import random
import unittest
from .core import Scheduler, Arena, Ledger, LocalRandomService
from .config import tiny, load
from .model import FullDecode, bucket_code, bitplane_reference, stratified_thresholds, MODES


class Contracts(unittest.TestCase):
    def test_resource_conflict_and_independent_overlap(self):
        s=Scheduler()
        self.assertEqual(s.reserve('a',0,20,['mac']),20)
        self.assertEqual(s.reserve('b',0,10,['vector']),10)
        self.assertEqual(s.reserve('c',5,5,['mac']),25)
        self.assertEqual(s.wait['c'],15)

    def test_clock_alignment(self):
        s=Scheduler()
        self.assertEqual(s.reserve('a',3,20,['m'],period=10),30)

    def test_capacity_and_no_silent_spill(self):
        a=Arena(128)
        a.allocate('one',80)
        with self.assertRaises(ValueError):a.allocate('two',80)

    def test_unknown_energy_not_zero(self):
        e=Ledger({'a':None,'b':2})
        e.action('a',10,'x');e.action('b',4,'x')
        self.assertEqual(e.missing['a'],10)
        self.assertAlmostEqual(e.energy['x'],8e-12)

    def test_stratum_boundaries_and_full_enumeration(self):
        a=stratified_thresholds(64,16,random.Random(7))
        for k in range(16):self.assertTrue(all(16*k<=x<16*(k+1) for x in a[k*4:(k+1)*4]))
        self.assertEqual(stratified_thresholds(256,256,random.Random(0)),list(range(256)))
        with self.assertRaises(ValueError):stratified_thresholds(32,64,random.Random(0))

    def test_bucket_scale_and_exact_endpoint(self):
        codes=bucket_code([16.,1.,1/16.,-16.,0.],4)
        self.assertEqual([c['scale'] for c in codes],[16.,1.,.25,16.,.25])
        self.assertTrue(codes[0]['one']);self.assertEqual(codes[3]['sign'],-1)
        self.assertFalse(codes[4]['one']);self.assertEqual(codes[4]['q'],0)

    def test_signed_bitplanes_match_direct_random_products(self):
        r=random.Random(83)
        for bins in (1,2,4,8):
            for T,K in ((16,16),(32,8),(64,1),(256,256)):
                x=[r.uniform(-2,2) for _ in range(64)]
                w=[r.randrange(-128,128) for _ in x]
                codes=bucket_code(x,bins);thresholds=stratified_thresholds(T,K,r)
                direct=sum(wi*c['sign']*c['scale']*sum(c['one'] or v<c['q'] for v in thresholds)/T for wi,c in zip(w,codes))
                self.assertAlmostEqual(bitplane_reference(w,codes,thresholds,bins),direct,places=9)

    def test_rng_replay_no_stream_memory(self):
        s,e=Scheduler(),Ledger()
        r=LocalRandomService(dict(startup_cycles=1,frame_cycles=1,restore_cycles=1),s,e,10)
        r.request('ffn',0,32,3,1,'shared64',('x',0))
        r.request('ffn',100,32,3,1,'shared64',('x',0),replay=True)
        a=r.report()
        self.assertEqual(a['random_stream_SRAM_bytes'],0)
        self.assertEqual(a['demands']['uniform_bits'],192)
        self.assertEqual(a['demands']['startup_seed_requests'],1)
        self.assertEqual(a['demands']['replay_restore_requests'],1)


class FullGraph(unittest.TestCase):
    def case(self,ffn='sc',attention='exact'):
        c,m=tiny();c['ffn']['mode']=ffn;c['attention']['mode']=attention
        return c,m

    def test_exact_full_model_MAC_count(self):
        c,m=self.case('bf16','exact');r=FullDecode(c,m).run()
        h,F,H,d,L=m['hidden_size'],m['intermediate_size'],m['num_attention_heads'],32,c['context_tokens']
        fixed=h*(h+2*d)+h*h+3*h*F+h*m['vocab_size']
        self.assertEqual(r['actions']['bf16_mac'],fixed+H*L*d)
        self.assertEqual(r['actions']['fp32_mac'],H*L*d)
        self.assertAlmostEqual(sum(r['phase_ns'].values()),r['metrics']['elapsed_ns'])

    def test_W8_scale_metadata_layout_with_partial_output_tiles(self):
        c,m=self.case('w8','exact');c['weight_chunk_bytes']=2048
        r=FullDecode(c,m).run()
        self.assertGreater(r['DRAM']['traffic']['weight_scales_physical_bytes'],0)
        self.assertEqual(r['actions']['weight_scale_op'],2*m['intermediate_size']*((m['hidden_size']+63)//64)+m['hidden_size']*((m['intermediate_size']+63)//64))

    def test_all_modes_have_all_decoder_phases(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                c,m=self.case(attention=mode);r=FullDecode(c,m).run()
                names={p['name'] for p in r['phases']}
                self.assertTrue({'FFN_gate_up','FFN_SwiGLU','FFN_down','lm_head_and_argmax','attention_core'}<=names)
                self.assertIsNone(r['metrics']['full_physical_energy_J'])
                self.assertTrue(r['unpriced_actions'])

    def test_SC_tile_count_and_shared_gu_encoding(self):
        c,m=self.case();r=FullDecode(c,m).run()
        self.assertEqual(r['FFN_activity']['SC_64x64_tiles'],3*m['hidden_size']*m['intermediate_size']//4096)
        self.assertEqual(r['FFN_activity']['BF16_to_probability8_values'],m['hidden_size'])
        self.assertEqual(r['FFN_activity']['FP32_to_probability8_values'],m['intermediate_size'])
        self.assertEqual(r['random_interface']['random_stream_SRAM_bytes'],0)
        self.assertEqual(r['random_interface']['extra_probability_copy_bytes'],0)

    def test_samples_change_array_work_not_weight_payload(self):
        c,m=self.case();r1=FullDecode(c,m).run()
        c['ffn'].update(samples=64,strata=32);r2=FullDecode(c,m).run()
        self.assertEqual(r2['FFN_activity']['SC_product_trials'],2*r1['FFN_activity']['SC_product_trials'])
        self.assertEqual(r2['DRAM']['traffic']['weights_physical_bytes'],r1['DRAM']['traffic']['weights_physical_bytes'])
        self.assertGreater(r2['metrics']['elapsed_ns'],r1['metrics']['elapsed_ns'])

    def test_sampled_V_read_saving_and_GQA_union(self):
        c,m=self.case(attention='exact');dense=FullDecode(c,m).run()
        c['attention']['mode']='pv';sample=FullDecode(c,m).run()
        self.assertLess(sample['attention_activity']['V_unique_group_positions'],dense['attention_activity']['V_unique_group_positions'])
        self.assertEqual(sample['attention_activity']['V_sample_events'],m['num_attention_heads']*c['attention']['samples'])
        self.assertLessEqual(sample['attention_activity']['V_unique_group_positions'],sample['attention_activity']['V_sample_events'])
        self.assertLess(sample['DRAM']['traffic']['V_sparse_union_physical_bytes'],dense['DRAM']['traffic']['KV_fused_physical_bytes']//2)

    def test_bank_resources_never_overlap(self):
        c,m=self.case();r=FullDecode(c,m).run();by={}
        for event in r['events']:
            for resource in event['resources']:
                by.setdefault(resource,[]).append((event['start_ns'],event['end_ns']))
        for values in by.values():
            values.sort()
            for a,b in zip(values,values[1:]):self.assertLessEqual(a[1],b[0]+1e-6)

    def test_two_tokens_retire_and_update_summary(self):
        c,m=self.case(attention='screen_pv');c['decode_tokens']=2
        r=FullDecode(c,m).run()
        self.assertEqual(len(r['metrics']['token_ms']),2)
        self.assertGreater(r['DRAM']['traffic']['summary_update_physical_bytes'],0)

    def test_seed_reproducible_receipts(self):
        c,m=self.case(attention='screen_rejection')
        a=FullDecode(c,m).run();b=FullDecode(c,m).run()
        self.assertEqual(a['row_receipts'],b['row_receipts'])
        self.assertEqual(a['metrics'],b['metrics'])

    def test_full_geometry_capacity_2k_8k(self):
        for model in ('qwen','llama1','llama2'):
            for L in (2048,8192):
                c,m=load(model);c['context_tokens']=L
                x=FullDecode(c,m)
                self.assertLessEqual(x.arena.peak,c['sram']['capacity_bytes'])
                self.assertEqual(x.mem.physical_capacity,c['sram']['capacity_bytes'])

    def test_bad_macro_clock_rejected(self):
        c,m=self.case();c['sram']['clock_hz']=1000000000
        with self.assertRaises(ValueError):FullDecode(c,m)

    def test_no_live_tensor_alias_or_cross_region_transfer(self):
        c,m=self.case();x=FullDecode(c,m)
        self.assertNotEqual(x.z,x.matrix_output)
        self.assertNotEqual(x.residual,x.activation)
        r=x.arena.regions['live_BF16_residual']
        with self.assertRaises(ValueError):x.mem.transfer(0,r['address'],r['bytes']+16,False,'bad')

    def test_no_silent_missing_trace_row(self):
        c,m=self.case();c['attention']['trace_file']='this_file_does_not_exist.json'
        with self.assertRaises(FileNotFoundError):FullDecode(c,m)


if __name__=='__main__':unittest.main()
