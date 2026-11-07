"""Real beat/bank/DMA mechanics, not neural-network arithmetic or PPL tests."""
import unittest
from .model import make_model, SLOT_BYTES
from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM


def create(profile, layers=3, include_lm=True):
    return make_model(AnalyticDRAM(latency_ns=80, bandwidth_GBs=136.46),
        profile=profile, mode='ising', ffn='sc', samples={}, layers=layers,
        include_lm=include_lm, cross_prefetch=True)


def norms_only(m):
    m.phase('embedding', [], -1)
    for layer in range(m.model['layers']):
        m.phase('norm', [m.norm(layer,'attention')], layer)
        m.phase('QKV', [m.h.delay(5000)], layer)
        m.phase('RoPE_headnorm', [m.rope()], layer)
        m.phase('ffn_norm', [m.norm(layer,'ffn')], layer)
    if m.include_lm:
        m.phase('final_norm', [m.norm(0,'final')], -1)
    return m.norm_store.report()


class NormContracts(unittest.TestCase):
    def test_current_full_shape_capacity(self):
        h, m = create('stream_2m',36)
        self.assertEqual(h.mem.capacity, 2*1024**2)
        self.assertEqual(sum(h.mem.bank_allocated),2008*1024)
        self.assertEqual(m.norm_weights.size,32768)
        self.assertTrue(all(x<=4096 for x in h.mem.bank_allocated))
        self.assertEqual(len(h.mem.bank_depths),512)
        self.assertEqual(m.common_cores,12)
        self.assertEqual(m.mac_lanes,1024)

    def test_exact_parameter_byte_identity_for_every_consumer(self):
        _, m = create('stream_2m',5)
        c=m.norm_store
        blob=bytes((i*31+i//256)%256 for i in range(c.logical_bytes))
        slots=[bytearray(SLOT_BYTES),bytearray(SLOT_BYTES)]
        # Independent byte-copy oracle; includes all gamma bytes, headnorm and
        # final gamma. No numeric rounding/conversion is allowed in placement.
        for tag in range(c.layers+1):
            offset,size=c.spec(tag);slots[tag%2][:size]=blob[offset:offset+size]
            kinds=('final',) if tag==c.layers else ('attention','ffn','qk')
            for kind in kinds:
                local={'attention':0,'ffn':2*c.d,'qk':4*c.d,'final':0}[kind]
                n=512 if kind=='qk' else 2*c.d
                self.assertEqual(bytes(slots[tag%2][local:local+n]),blob[offset+local:offset+local+n])

    def test_36_layer_stream_once_and_all_consumers(self):
        h,m=create('stream_2m',36)
        r=norms_only(m)
        self.assertEqual(r['streamed_bytes'],392192)
        self.assertEqual(r['load_counts'],{i:1 for i in range(37)})
        self.assertEqual(r['RMS_gamma_read_bytes'],73*5120)
        self.assertEqual(r['QK_headnorm_gamma_read_bytes'],36*512)
        self.assertEqual(h.report()['counts']['dram_read_bytes'],392192)
        for slot in m.norm_store.slots:self.assertTrue(slot['released'].ready)
        self.assertFalse(h.mem.queue)
        self.assertFalse(h.descriptors)

    def test_prefetch_reuse_after_last_consumer(self):
        _,m=create('stream_2m',5)
        r=norms_only(m)
        release={x['tag']:x['ns'] for x in r['events'] if x['event']=='release'}
        starts={x['tag']:x['ns'] for x in r['events'] if x['event']=='load_start'}
        for tag in range(2,6):self.assertGreaterEqual(starts[tag],release[tag-2])
        # Next layer is loaded in a QKV phase, not a separate global drain.
        for tag in range(1,6):
            phase=next(x for x in m.phases if x['stage']=='QKV' and x['layer']==tag-1)
            self.assertGreaterEqual(starts[tag],phase['start_ns'])
            self.assertLessEqual(starts[tag],phase['end_ns'])

    def test_reads_before_ready_or_release_before_use_rejected(self):
        _,m=create('stream_2m')
        with self.assertRaises(RuntimeError):m.norm_store.address(0,'attention')
        m.h.execute([m.norm_store.load(0)])
        with self.assertRaises(RuntimeError):m.norm_store.release(0)
        with self.assertRaises(RuntimeError):m.norm_store.address(2,'attention')

    def test_no_lm_does_not_fetch_final(self):
        _,m=create('stream_2m',3,False)
        r=norms_only(m)
        self.assertEqual(r['streamed_bytes'],3*(4*2560+512))
        self.assertEqual(r['load_counts'],{0:1,1:1,2:1})

    def test_resident_control_keeps_arithmetic_and_gamma_reads(self):
        hr,mr=create('resident_2p5');hs,ms=create('stream_2p5')
        a,b=norms_only(mr),norms_only(ms)
        self.assertEqual(a['RMS_gamma_read_bytes'],b['RMS_gamma_read_bytes'])
        self.assertEqual(a['QK_headnorm_gamma_read_bytes'],b['QK_headnorm_gamma_read_bytes'])
        self.assertEqual(dict(mr.compute),dict(ms.compute))
        self.assertEqual(a['streamed_bytes'],0)
        self.assertEqual(hr.mem.capacity,hs.mem.capacity)
        self.assertEqual(hr.mem.bank_depths,hs.mem.bank_depths)

    def test_constructor_hooks_do_not_leak(self):
        from architecture_tlm.digital_baselines_20261104 import factory
        from architecture_tlm.sram_capacity_20261103.depth_banks import DepthSRAM
        before=factory.common_model,DepthSRAM.region
        create('stream_2m');create('resident_2p5')
        self.assertEqual(before,(factory.common_model,DepthSRAM.region))


if __name__=='__main__':unittest.main()
