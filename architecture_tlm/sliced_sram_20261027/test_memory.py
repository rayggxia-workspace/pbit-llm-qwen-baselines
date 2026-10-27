import copy
import unittest
from architecture_tlm.unified_v6.core import SRAM,Ledger
from architecture_tlm.scheduling_v2_20261027.calendar import ReadyCalendar
from architecture_tlm.scheduling_v2_20261027.test_scheduling import work
from architecture_tlm.scheduling_v2_20261027.model import SchedulingDecode
from architecture_tlm.unified_v6.test_ffn_locality import case
from architecture_tlm.ffn_local_pipeline_20261025.model import LocalPipelineFFN
from .memory import ClusteredSRAM
from .model import SlicedDecode,configure


def fixture(mode='beats'):
    c=dict(clock_hz=80e6,word_bytes=16,capacity_bytes=8192,banks=8,macro_depth=64,
        fabric_GBs=16.,cdc_ns=20.,sliced=dict(mode=mode,clusters=2,credits=2,network_period_ns=2.))
    spec=dict(read_cycle_ns=4.,write_cycle_ns=4.,read_access_ns=2.,write_access_ns=2.,
        read_internal_pJ=10.,write_internal_pJ=14.,ce_off_leakage_W=1e-6,area_mm2=.01)
    s=ReadyCalendar(10000);e=Ledger();return ClusteredSRAM(c,spec,s,e),s,e


def no_overlaps(test,events):
    rs={}
    for e in events:
        test.assertGreaterEqual(e['start_ns']+1e-7,e['ready_ns'])
        for r in e['resources']:
            if e['end_ns']>e['start_ns']:rs.setdefault(r,[]).append((e['start_ns'],e['end_ns']))
    for r,intervals in rs.items():
        intervals.sort()
        for a,b in zip(intervals,intervals[1:]):test.assertLessEqual(a[1],b[0]+1e-7,r)


class PortsAndLinks(unittest.TestCase):
    def test_disjoint_slices_run_together(self):
        m,s,e=fixture();a=m.transfer(0,0,16,False,'a');b=m.transfer(0,4*16,16,False,'b')
        self.assertEqual(a,b)
        old=SRAM(m.c,m.spec,ReadyCalendar(10000),Ledger())
        a=old.transfer(0,0,16,False,'a');b=old.transfer(0,4*16,16,False,'b')
        self.assertGreater(b,a)

    def test_same_bank_is_one_port(self):
        m,s,e=fixture();m.transfer(0,0,16,False,'a');m.transfer(0,8*16,16,True,'b')
        no_overlaps(self,s.events)
        bank=[x for x in s.events if 'sram_bank:0' in x['resources']]
        self.assertEqual(len(bank),2)
        self.assertTrue(all(x['end_ns']-x['start_ns']==12.5 for x in bank))

    def test_shared_read_write_link_is_not_free_full_duplex(self):
        m,s,e=fixture();m.transfer(0,0,64,False,'a');m.transfer(0,128,64,True,'weight_fill')
        links=[x for x in s.events if 'sram_link:0' in x['resources']]
        self.assertEqual(sum(x['bytes'] for x in links),128)
        self.assertGreaterEqual(sum(x['end_ns']-x['start_ns'] for x in links),128/8.)
        no_overlaps(self,s.events)

    def test_finite_credits_allow_earlier_gap(self):
        m,s,e=fixture();late=m.transfer(1000,0,1024,False,'late')
        early=m.transfer(0,16,16,False,'early')
        self.assertLess(early,1000);self.assertGreater(late,1000)
        self.assertEqual(m.report(late)['sliced']['additional_payload_buffer_bytes'],256)
        no_overlaps(self,s.events)

    def test_credits_and_global_payload_byte_conservation(self):
        m,s,e=fixture();t=m.transfer(0,3,2045,False,'a');m.transfer(0,2048,2048,True,'b')
        self.assertEqual(sum(m.link_bytes.values()),4096)
        self.assertEqual(sum(m.bank_ops.values()),256)
        for x in s.events:
            if x['stage']=='sram_payload_credit':self.assertLessEqual(x['bytes'],x['capacity_bytes'])
        no_overlaps(self,s.events)

    def test_same_rounding_and_macro_energy_as_original(self):
        m,s,e=fixture();old=SRAM(m.c,m.spec,ReadyCalendar(),Ledger())
        for address,size,wr in [(15,3,False),(111,99,True),(512,16,False)]:
            m.transfer(0,address,size,wr,'a');old.transfer(0,address,size,wr,'a')
        self.assertEqual(m.traffic,old.traffic);self.assertEqual(m.e.energy,old.e.energy)

    def test_ports_do_not_hold_CDC_latency(self):
        m,s,e=fixture();m.transfer(0,0,16,False,'a')
        bank=next(x for x in s.events if x['stage']=='sram_bank_read')
        self.assertEqual(bank['end_ns']-bank['start_ns'],m.period)
        self.assertNotIn('sram_fabric',{r for x in s.events for r in x['resources']})

    def test_bandwidth_and_bounds_validation(self):
        m,s,e=fixture();self.assertEqual(m.transfer(12,0,0,False,'empty'),12)
        with self.assertRaises(ValueError):m.transfer(0,8191,2,False,'bad')
        c=copy.deepcopy(m.c);c['sliced']['cluster_GBs']=100
        with self.assertRaises(ValueError):ClusteredSRAM(c,m.spec,s,e)


class Integration(unittest.TestCase):
    def test_runner_configuration_supports_bf16_and_preserves_SC(self):
        import sys
        from .run_case import configuration
        from architecture_tlm.scheduling_v2_20261027.profiles import configuration as old
        args=dict(scope='one_layer',expanded_compute=True,expanded_sram=True,nonlinear_samples=128,
            clock_gating=False,ffn='sc',attention='screen_pv',early_next_dma=True,calendar=True,
            digital_prefill=True,cross_window_program=True,seed=0)
        # Configuration validates path existence but does not execute this file.
        self.assertEqual(configuration(args,sys.executable,'/unused/output'),old(args,sys.executable,'/unused/output'))
        args['ffn']='bf16';c,m=configuration(args,sys.executable,'/unused/output')
        self.assertEqual(c['ffn']['mode'],'bf16');self.assertTrue(c['digital_shared_prefill'])
        self.assertNotIn('local_pipeline',c)

    @classmethod
    def setUpClass(cls):
        c,m=case(engines=2,retain=2)
        c['local_pipeline']=dict(overlap=True,weight_bypass=True,cross_window_program=True,early_next_dma=True)
        c['digital_shared_prefill']=True;c['early_next_dma']=True;c['trace_event_limit']=200000
        cls.results=[]
        for mode in ('legacy','descriptor','beats'):
            cfg=copy.deepcopy(c);sched=ReadyCalendar(cfg['trace_event_limit'],core_period_ns=1e9/cfg['core_hz'])
            if mode=='legacy':o=SchedulingDecode(cfg,m,scheduler=sched)
            else:configure(cfg,mode=mode);o=SlicedDecode(cfg,m,scheduler=sched)
            o.ffn_latest=LocalPipelineFFN(o);cls.results.append(o.run())

    def test_identical_arithmetic_memory_and_event_stream_work(self):
        first=self.results[0]
        for r in self.results[1:]:
            self.assertEqual(work(first['actions']),work(r['actions']))
            self.assertEqual(first['SRAM']['traffic'],r['SRAM']['traffic'])
            self.assertEqual(first['DRAM']['traffic'],r['DRAM']['traffic'])
            self.assertEqual(first['FFN_activity'],r['FFN_activity'])
            self.assertEqual(first['FFN_contract']['local_state'],r['FFN_contract']['local_state'])
            self.assertEqual(first['attention_activity'],r['attention_activity'])

    def test_complete_trace_and_resource_exclusivity(self):
        for r in self.results:
            self.assertFalse(r['trace_truncated']);no_overlaps(self,r['events'])


if __name__=='__main__':unittest.main()
