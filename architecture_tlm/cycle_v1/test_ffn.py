import dataclasses
import math
import random
import struct
import unittest

from .ffn import FFNConfig, build_ffn, encode_group, make_kernel, matrix_spec, reference_ffn, reference_ffn_tiled


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

    def test_tails_samples_and_cycle_event_equivalence(self):
        data=fixture()
        for t in (16,32,64):
            with self.subTest(T=t):
                c=FFNConfig(samples=t,strata=t,output_bf16=False)
                a,ar,_=execute(data,c,'cycle')
                b,br,_=execute(data,c,'event')
                self.assertEqual(ar.equivalence_payload(),br.equivalence_payload())
                self.assertEqual(a['output'],b['output'])
                reference=reference_ffn(data,c)
                tiled=reference_ffn_tiled(data,c)
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
        data['thresholds']={'x':[[0]*32,[0]*32]}
        with self.assertRaisesRegex(ValueError,'stratified'): execute(data)

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


if __name__=='__main__': unittest.main()
