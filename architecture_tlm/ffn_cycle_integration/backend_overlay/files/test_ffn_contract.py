"""Complete small FFNs: independent numerics, observable timing and credits."""
from dataclasses import asdict, replace
import math
import struct
import unittest

from . import ffn
from .ffn_contract import CONTRACT, encode_values
from ..encoding_restore_contract.adapter import Profile
from ..ffn_cycle_integration.active_memory import ActiveMemoryKernel


def config(**overrides):
    values = dict(samples=16, strata=16, output_bf16=False,
                  encoding_restore_contract=CONTRACT,
                  encoding_restore_profile=asdict(Profile()),
                  restore_rounding='rtl_fused0_order')
    values.update(overrides)
    return ffn.FFNConfig(**values)


def fixture(d=65, f=65, o=3):
    def matrix(nr, nc, phase):
        return dict(codes=[[((r*29+c*19+phase)%256)-128 for c in range(nc)]
                           for r in range(nr)],
                    scales=[[.001*(1+(r+c)%3) for c in range(math.ceil(nc/64))]
                            for r in range(math.ceil(nr/64))])
    return dict(x=[math.sin(i*.7)*.2 for i in range(d)],
                residual=[.03*(i-1) for i in range(o)],
                wg=matrix(f,d,0), wu=matrix(f,d,21), wd=matrix(o,f,7))


def execute(data, c, mode='event'):
    kernel = ffn.make_kernel(c, kernel_factory=ActiveMemoryKernel)
    state = ffn.build_ffn(kernel, data, c)
    result = kernel.run(mode)
    return kernel, state, result


class ContractFFNTests(unittest.TestCase):
    def assert_oracle(self, data, c, kernel, state, result):
        ref = ffn.reference_ffn_tiled(ffn.replay_fixture(data,state),c)
        for name in ('gate','up','z','projected','output'):
            pack=lambda values:struct.pack('<'+'f'*len(values),*values)
            self.assertEqual(pack(state[name]),pack(ref[name]),name)
        self.assertEqual(result.buffer_final,{n:b.initial for n,b in kernel.buffer_specs.items()})
        for name in ('encoded','counters','resident_weights','restore_intermediates'):
            self.assertFalse(state[name],name)
        self.assertFalse(state['encoding_restore']['results'])
        self.assertFalse(state['encoding_restore']['top_exp'])

    def test_complete_multik_multiwave_tails_and_full_trace(self):
        data = fixture()
        c = config(weight_slots=1,engines=1)
        event = execute(data,c)
        cycle = execute(data,c,'cycle')
        self.assertEqual(event[2].equivalence_payload(),cycle[2].equivalence_payload())
        self.assert_oracle(data,c,*event)
        actions = event[2].actions
        self.assertEqual(actions['complete_encode_group64'],4)
        self.assertEqual(actions['complete_restore_output_b4'],266)
        self.assertEqual(actions['cross_k_fp32_add'],266)
        self.assertNotIn('activation_encode_values',actions)
        self.assertNotIn('restore_values',actions)
        # Every output tile/k owns counters through the last scalar add; packed
        # pending write storage stays reserved until that actual write completes.
        for ident, op in event[0].operations.items():
            if ident.endswith('.partial_write'):
                self.assertEqual(op.outputs,{'ffn.restore':op.memory.size_bytes*3})

    def test_finite_depth_one_slow_consumer_preserves_identity(self):
        data = fixture(d=7,f=9,o=3)
        fast = config()
        slow = config(encoding_restore_profile=asdict(Profile(restore_lanes=2,
                      restore_depth=1,add_latency=5,add_ii=5,add_capacity=1)))
        fk,fs,fr = execute(data,fast)
        sk,ss,sr = execute(data,slow)
        self.assert_oracle(data,slow,sk,ss,sr)
        self.assertEqual(fs['output'],ss['output'])
        self.assertGreater(sr.finish_ps,fr.finish_ps)
        self.assertLessEqual(ss['encoding_restore']['peak_live_results'],2)
        # At every observable event, each lane conserves exactly its one slot:
        # free + restore flight + ready + add flight = depth.
        for lane in range(2):
            name=f'ffn.er.restore{lane}'
            free=1; ready=flight=adding=0
            for event in sr.trace:
                if event['kind'] not in ('accept','complete'): continue
                op=sk.operations[event['op']]
                if event['kind']=='accept':
                    if op.resource==name: free-=1; flight+=1
                    if name+'.ready' in op.inputs: ready-=1; adding+=1
                else:
                    if op.resource==name: flight-=1; ready+=1
                    if name+'.free' in op.outputs: adding-=1; free+=1
                self.assertEqual(free+ready+flight+adding,1)
                self.assertGreaterEqual(min(free,ready,flight,adding),0)

    def test_legacy_default_remains_original_numeric_and_resources(self):
        data=fixture(d=5,f=3,o=2)
        default=ffn.FFNConfig(samples=16,strata=16,output_bf16=False)
        explicit=replace(default,encoding_restore_contract='legacy')
        a=execute(data,default); b=execute(data,explicit)
        self.assertEqual(a[2].equivalence_payload(),b[2].equivalence_payload())
        ref=ffn.reference_ffn_tiled(ffn.replay_fixture(data,a[1]),default)
        self.assertEqual(a[1]['output'],ref['output'])
        self.assertNotIn('encoding_restore',a[1])
        self.assertIn('encode',a[0].resources)
        self.assertNotIn('ffn.er.encode',a[0].resources)

    def test_subnormal_encoder_and_separate_restore_rounding(self):
        tiny=2.0**-149
        data=dict(x=[tiny],residual=[0.],
                  wg=dict(codes=[[1]],scales=[[1.]]),
                  wu=dict(codes=[[1]],scales=[[1.]]),
                  wd=dict(codes=[[1]],scales=[[1.]]))
        c=config(samples=32,strata=32)
        k,s,r=execute(data,c)
        self.assert_oracle(data,c,k,s,r)
        self.assertEqual(s['gate'],[tiny])
        self.assertEqual(encode_values([tiny])[0][0]['q'],255)
        self.assertTrue(encode_values([tiny])[0][0]['full_one'])
        legacy=execute(data,ffn.FFNConfig(output_bf16=False))[1]
        self.assertEqual(legacy['gate'],[0.])
        # Raw valid counter boundary diagnostic, independently of reachability
        # under this fixture's selected stratified thresholds.
        bits=lambda x:struct.unpack('<I',struct.pack('<f',x))[0]
        self.assertEqual(bits(ffn.restore_bin_value(3,2.0**-145,1.5,32,'host_order')),2)
        self.assertEqual(bits(ffn.restore_bin_value(3,2.0**-145,1.5,32,'rtl_fused0_order')),3)

    def test_profile_is_explicit_and_incompatible_modes_rejected(self):
        for overrides in (dict(encoding_restore_profile={}),dict(bins=2),
                          dict(counter_layout='signed_bin'),dict(restore_rounding='host_order')):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                config(**overrides).validate()

    def test_negative_w8_endpoint_all_supported_samples(self):
        data=dict(x=[-1.]*64,residual=[0.],
                  wg=dict(codes=[[-128]*64],scales=[[1.]]),
                  wu=dict(codes=[[0]*64],scales=[[1.]]),
                  wd=dict(codes=[[1]],scales=[[1.]]))
        for samples in (16,32,64):
            with self.subTest(samples=samples):
                c=config(samples=samples,strata=samples)
                k,s,r=execute(data,c)
                self.assert_oracle(data,c,k,s,r)
                self.assertEqual(s['gate'],[8192.])
                self.assertEqual(max(x['counter_peak'] for x in s['tile_receipts']),64*samples)
                self.assertEqual(max(x['integer_equivalent_peak'] for x in s['tile_receipts']),8192*samples)


if __name__=='__main__':
    unittest.main()
