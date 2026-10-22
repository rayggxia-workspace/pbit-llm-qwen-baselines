import dataclasses
import math
import random
import struct
import unittest

from .ffn import FFNConfig, build_ffn, encode_group, make_kernel, matrix_spec, reference_ffn, reference_ffn_tiled, replay_fixture


def fixture(d=65,f=3,o=2):
    rng=random.Random(78)
    return dict(x=[rng.uniform(-1,1) for _ in range(d)],
        residual=[rng.uniform(-.1,.1) for _ in range(o)],
        wg=[[rng.uniform(-.3,.3) for _ in range(d)] for _ in range(f)],
        wu=[[rng.uniform(-.3,.3) for _ in range(d)] for _ in range(f)],
        wd=[[rng.uniform(-.3,.3) for _ in range(f)] for _ in range(o)])


def execute(data,c=None,mode='event',latency=4):
    c=c or FFNConfig(output_bf16=False)
    kernel=make_kernel(c,memory_latency=latency)
    state=build_ffn(kernel,data,c)
    result=kernel.run(mode=mode)
    return state,result,kernel


class FFNTests(unittest.TestCase):
    def assertClose(self,a,b,tol=2e-5):
        self.assertEqual(len(a),len(b))
        for x,y in zip(a,b): self.assertLessEqual(abs(x-y),tol*max(1,abs(y)))

    def test_encoding_bins_and_endpoints(self):
        encoded=encode_group([-1.,.25,-.0625,.015625,0.,255/256])
        self.assertEqual([v['bin'] for v in encoded],[0,1,2,3,3,0])
        self.assertTrue(all(v['full_one'] for v in encoded[:4]))
        self.assertEqual(encoded[-1]['q'],255)
        self.assertFalse(encoded[-1]['full_one'])
        self.assertEqual(encoded[4]['sign'],0)

    def test_encoding_tiny_subnormal_and_explicit_upper_domain(self):
        for vector in ([1e-38,-1e-39,0.0],[2.0**-149,-2.0**-148,0.0],[0.0],[2.0**127]):
            encoded=encode_group(vector)
            for raw,item in zip(vector,encoded):
                actual=struct.unpack('<f',struct.pack('<f',raw))[0]
                self.assertEqual(item['q'],min(255,round(abs(actual)/item['scale']*256)))
                self.assertTrue(math.isfinite(item['scale']))
        with self.assertRaisesRegex(ValueError,'ceil-PoT'):
            encode_group([struct.unpack('<f',struct.pack('<I',0x7f7fffff))[0]])
        with self.assertRaisesRegex(ValueError,'FP32 encoder domain'):
            encode_group([2.0**128])

    def test_tails_samples_and_cycle_event_equivalence(self):
        data=fixture()
        for t in (16,32,64):
            with self.subTest(T=t):
                c=FFNConfig(samples=t,strata=t,output_bf16=False)
                a,ar,_=execute(data,c,'cycle')
                b,br,_=execute(data,c,'event')
                self.assertEqual(ar.equivalence_payload(),br.equivalence_payload())
                self.assertEqual(a['output'],b['output'])
                observed=replay_fixture(data,a)
                reference=reference_ffn(observed,c)
                tiled=reference_ffn_tiled(observed,c)
                for field in ('gate','up','z','projected','output'):
                    self.assertClose(a[field],reference[field])
                    self.assertEqual(a[field],tiled[field])
                self.assertEqual(a['counters'],{})
                self.assertEqual(a['resident_weights'],{})
                self.assertEqual(a['encoded'],{})
                self.assertTrue(all(ar.buffer_final[k]==v for k,v in ar.buffer_peak.items()))

    def test_nonlinear_waits_for_all_input_tiles(self):
        data=dict(x=[1.]*65,residual=[0.],
            wg={'codes':[[1]*64+[-64]],'scales':[[1.,1.]]},
            wu={'codes':[[1]*65],'scales':[[1.,1.]]},
            wd={'codes':[[1]],'scales':[[1.]]})
        state,result,_=execute(data)
        self.assertEqual(state['gate'],[0.])
        self.assertEqual(state['up'],[65.])
        self.assertEqual(state['z'],[0.])
        self.assertEqual(state['output'],[0.])
        last=max(time for op,time in result.completion_ps.items() if op.startswith(('ffn.wg','ffn.wu')))
        self.assertGreater(result.accepted_ps['ffn.swiglu'],last)

    def test_positive_signed_counter_endpoint(self):
        data=dict(x=[-1.]*64,residual=[0.],
            wg={'codes':[[-128]*64],'scales':[[1.]]},
            wu={'codes':[[0]*64],'scales':[[1.]]},
            wd={'codes':[[1]],'scales':[[1.]]})
        state,_,_=execute(data)
        self.assertEqual(state['gate'],[8192.])
        self.assertEqual(max(r['counter_peak'] for r in state['tile_receipts']),2048)
        self.assertEqual(max(r['integer_equivalent_peak'] for r in state['tile_receipts']),262144)
        with self.assertRaises(ValueError): execute(data,FFNConfig(counter_layout='signed_bin',count_bits=19))
        with self.assertRaises(ValueError): execute(data,FFNConfig(count_bits=11))

    def test_backpressure_changes_timing_not_numeric(self):
        data=fixture(d=130,f=70,o=3)
        fast,fr,_=execute(data)
        slow,sr,_=execute(data,FFNConfig(weight_slots=1,output_bf16=False),latency=17)
        self.assertEqual(fast['output'],slow['output'])
        self.assertGreater(sr.finish_ps,fr.finish_ps)

    def test_weight_bytes_are_consumed_and_checked(self):
        data=fixture()
        kernel=make_kernel()
        build_ffn(kernel,data)
        kernel.load_memory('dram',0x10000000,b'\x7f')
        with self.assertRaisesRegex(AssertionError,'weight bytes'):
            kernel.run()

    def test_input_bytes_are_consumed_and_checked(self):
        data=fixture()
        kernel=make_kernel()
        build_ffn(kernel,data)
        kernel.load_memory('sram',0x40000000,bytes(4))
        with self.assertRaisesRegex(AssertionError,'activation data'):
            kernel.run()

    def test_capacity_and_replay_fail_explicitly(self):
        data=fixture()
        with self.assertRaises(ValueError): execute(data,FFNConfig(partial_capacity_bytes=1))
        with self.assertRaises(ValueError): execute(data,FFNConfig(weight_slot_bytes=8))
        with self.assertRaisesRegex(ValueError,'encoded group'):
            execute(data,FFNConfig(encoded_capacity_bytes=196))
        with self.assertRaisesRegex(ValueError,'restore scratch'):
            execute(data,FFNConfig(restore_capacity_bytes=1))
        data['thresholds']={'x':[[0]*32,[0]*32]}
        with self.assertRaisesRegex(ValueError,'stratified'): execute(data,FFNConfig(random_backend='replay'))

    def test_output_bytes_match_interface(self):
        for narrow in (False,True):
            state,result,kernel=execute(fixture(),FFNConfig(output_bf16=narrow))
            payload=struct.pack('<'+'f'*len(state['output']),*state['output'])
            if narrow: payload=b''.join(payload[i+2:i+4] for i in range(0,len(payload),4))
            self.assertEqual(kernel.read_memory('sram',state['output_address'],state['output_bytes']),payload)
            self.assertEqual(state['complete_ps'],result.finish_ps)

    def test_original_bitplane_capacity_and_signed_alternative(self):
        c=FFNConfig()
        self.assertEqual(c.weight_slots*c.weight_slot_bytes,32768)
        self.assertEqual(c.weight_scale_capacity_bytes,32)
        self.assertEqual(c.counter_capacity_bytes,49152)
        self.assertEqual(64*c.bins*2*8*c.counter_width//8,6144)
        data=fixture(d=130,f=70,o=3)
        bitplanes,_,_=execute(data,c)
        signed,_,_=execute(data,dataclasses.replace(c,counter_layout='signed_bin'))
        for field in ('gate','up','z','projected','output'):
            self.assertEqual(bitplanes[field],signed[field])

    def test_original_signed_weight_planes_and_native_multiwave_replay(self):
        simple=dict(x=[1.],wg={'codes':[[-1]],'scales':[[1.]]},
            wu={'codes':[[1]],'scales':[[1.]]},wd={'codes':[[1]],'scales':[[1.]]})
        state,_,_=execute(simple)
        gate=next(x for x in state['tile_receipts'] if x['tile']=='wg.r0.k0')
        self.assertEqual(gate['nonzero_counter_slots'],8)
        self.assertEqual(state['gate'],[-1.])
        data=fixture(d=3,f=257,o=2)
        c=FFNConfig(seed_word_interval=1,seed_startup=0)
        state,_,_=execute(data,c)
        oracle=reference_ffn_tiled(replay_fixture(data,state),c)
        self.assertEqual(state['output'],oracle['output'])
        source=state['native_random']['ports']['ffn']['counts']
        self.assertEqual(source['restore_bits_loaded'],32)
        self.assertEqual(source['checkpoint_bits_written'],6*32)
        self.assertEqual(source['frames_generated'],7*32)

    def test_restore_work_is_bounded_by_lanes(self):
        data=fixture(d=3,f=64,o=2)
        fast=FFNConfig(random_backend='behavioral',vector_lanes=16)
        a,ar,_=execute(data,fast)
        b,br,_=execute(data,dataclasses.replace(fast,vector_lanes=4))
        self.assertEqual(a['output'],b['output'])
        self.assertGreater(br.finish_ps,ar.finish_ps)
        tile_rows=64+64+2
        self.assertEqual(ar.actions['restore_counter_reads'],tile_rows*4*16)
        self.assertEqual(ar.actions['restore_signed_rail_subtract'],tile_rows*4*8)
        self.assertEqual(ar.actions['restore_integer_plane_add'],tile_rows*4*7)
        self.assertEqual(ar.actions['restore_integer_scale_fp32'],tile_rows*4)
        self.assertEqual(ar.actions['restore_ordered_bin_fp32_add'],tile_rows*4)
        rail='ffn.wg.r0.k0.restore_rails'
        cycles=(ar.completion_ps[rail]-ar.accepted_ps[rail])//10000
        self.assertEqual(cycles,fast.restore_latency+math.ceil(64*4*8/16)-1)
        self.assertEqual(a['restore_intermediates'],{})


if __name__=='__main__': unittest.main()
