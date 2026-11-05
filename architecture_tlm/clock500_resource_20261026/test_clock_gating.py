"""Small deterministic contracts; run with PBIT_TLM_CHECKOUT set to checkout."""
import copy
import os
import sys
import unittest

from architecture_tlm.unified_v6.core import Scheduler
from .clock_gating import ClockGatedScheduler, is_compute_resource


class ClockGateTests(unittest.TestCase):
    def test_disabled_exact_trace_and_totals(self):
        plain = Scheduler(keep=20)
        gated = ClockGatedScheduler(keep=20, enabled=False)
        for scheduler in (plain,gated):
            scheduler.reserve('a',1,6,('sc:0','sc:1'),2,tag=5)
            scheduler.reserve('m',0,25,('sram_bank:0','sram_fabric'),12.5)
            scheduler.reserve('b',101,3,('mac',),2)
            scheduler.reserve('c',10,4,('mac','vector'),2)
            scheduler.reserve('zero',500,0,('sc:0',),2)
        for key in ('free','busy','wait','events','count','by_stage'):
            self.assertEqual(getattr(plain,key),getattr(gated,key),key)
        self.assertEqual(plain.end(),gated.end())
        for r in gated.clock_gating_report()['resources'].values():
            self.assertEqual(r['off_ns'],0)
            self.assertEqual(r['clock_on_ns'],gated.end())

    def test_timeout_wake_and_tail_conservation(self):
        s=ClockGatedScheduler(core_period_ns=2)
        self.assertEqual(s.reserve('a',0,8,('mac',),2),8)
        self.assertEqual(s.reserve('b',40,6,('mac',),2),48)
        r=s.clock_gating_report(100)['resources']['mac']
        self.assertEqual(r['busy_ns'],14)
        self.assertEqual(r['idle_clock_on_ns'],32)
        self.assertEqual(r['wakeup_ns'],2)
        self.assertEqual(r['off_ns'],52)
        self.assertEqual(r['clock_on_ns'],48)
        self.assertEqual(r['wakeups'],1)
        self.assertEqual(s.wait['b'],2)
        self.assertEqual(s.events[-1]['ready_ns'],40)
        self.assertEqual(s.events[-1]['start_ns'],42)

    def test_parallel_wake_not_serial(self):
        s=ClockGatedScheduler()
        rs=tuple('sc:'+str(i) for i in range(32))
        self.assertEqual(s.reserve('sc',100,148,rs,2),250)
        self.assertEqual(s.wait['sc'],2)
        report=s.clock_gating_report()
        self.assertEqual(sum(x['wakeups'] for x in report['resources'].values()),32)
        self.assertTrue(all(x['wakeup_ns']==2 for x in report['resources'].values()))

    def test_dependency_wait_does_not_predict_wake(self):
        s=ClockGatedScheduler()
        s.reserve('mem',0,100,('sram_fabric',),0)
        self.assertEqual(s.reserve('op',1,10,('sram_fabric','mac'),2),112)
        self.assertEqual(s.wait['op'],101)
        self.assertEqual(s.events[-1]['start_ns'],102)

    def test_warm_domain_holds_through_other_wake(self):
        s=ClockGatedScheduler()
        s.reserve('vector',0,26,('vector',),2)
        # vector deadline42; mac is off. At40 request both; vector stays on.
        s.reserve('both',40,4,('vector','mac'),2)
        r=s.clock_gating_report()['resources']
        self.assertEqual(r['mac']['wakeups'],1)
        self.assertEqual(r['vector']['wakeups'],0)
        self.assertEqual(r['vector']['clock_on_ns'],46)

    def test_unselected_paths_unchanged_and_whitelist(self):
        rs=('sampler','sram_fabric','sram_bank:0','dram_dma','rng_control',
            'locality_stream','locality_seed_port','sc_weight_bank:0','sc_local_program_bus')
        a=Scheduler();b=ClockGatedScheduler()
        self.assertEqual(a.reserve('x',100,10,rs,2),b.reserve('x',100,10,rs,2))
        self.assertEqual(a.events,b.events)
        self.assertEqual(b.clock_gating_report()['resources'],{})
        self.assertTrue(is_compute_resource('ffn_SC_coefficient16_restore'))
        self.assertFalse(is_compute_resource('sc_weight_bank:0'))

    def test_zero_duration_is_not_an_active_wake(self):
        s=ClockGatedScheduler()
        self.assertEqual(s.reserve('zero',100,0,('mac',),2),100)
        r=s.clock_gating_report()['resources']['mac']
        self.assertEqual(r['busy_ns'],0)
        self.assertEqual(r['wakeup_ns'],0)
        self.assertEqual(r['clock_on_ns'],16)

    def test_registered_unused_domain_tail_and_readonly_report(self):
        s=ClockGatedScheduler(installed_resources=('sc:0','sc:1'))
        s.reserve('a',0,8,('sc:0',),2)
        x=s.clock_gating_report(101);y=s.clock_gating_report(101)
        self.assertEqual(x,y)
        self.assertEqual(x['lifetime_ns'],102)
        self.assertEqual(x['resources']['sc:1']['clock_on_ns'],16)
        self.assertEqual(x['resources']['sc:1']['off_ns'],86)

    def test_boundary_request_and_truncated_trace(self):
        s=ClockGatedScheduler(keep=0)
        self.assertEqual(s.reserve('x',16,4,('mac',),2),22)
        self.assertEqual(s.events,[])
        self.assertEqual(s.clock_gating_report()['resources']['mac']['wakeups'],1)

    def test_validation(self):
        with self.assertRaises(ValueError): ClockGatedScheduler(core_period_ns=0)
        with self.assertRaises(ValueError): ClockGatedScheduler(idle_threshold_cycles=0)
        with self.assertRaises(ValueError): ClockGatedScheduler(installed_resources=('dram_dma',))
        s=ClockGatedScheduler()
        with self.assertRaises(ValueError):s.reserve('bad',0,2,('mac',),10)
        s.reserve('a',0,2,('mac',),2)
        with self.assertRaises(ValueError):s.clock_gating_report(1)

    def test_local_pipeline_small_model_integration(self):
        from architecture_tlm.unified_v6.test_ffn_locality import case
        from architecture_tlm.unified_v6.model import FullDecode
        from architecture_tlm.ffn_local_pipeline_20261025.model import LocalPipelineFFN
        c,m=case(engines=2,retain=2)
        c['core_hz']=500000000
        c['random']['clock_hz']=500000000
        c['trace_event_limit']=200000
        c['local_pipeline']=dict(overlap=True,weight_bypass=True)
        results=[]
        for scheduler in (Scheduler(200000),
                          ClockGatedScheduler(200000,enabled=False),
                          ClockGatedScheduler(200000,enabled=True)):
            o=FullDecode(copy.deepcopy(c),copy.deepcopy(m),scheduler=scheduler)
            o.ffn_latest=LocalPipelineFFN(o)
            result=o.run()
            results.append((o,result))
        a,b,g=results
        for key in ('free','busy','wait','events','count','by_stage'):
            self.assertEqual(getattr(a[0].s,key),getattr(b[0].s,key),key)
        # Wall-time leakage/idle ledger entries must change with wake latency.
        actual_work=lambda o:{k:v for k,v in o.e.actions.items() if not k.endswith('_ns')}
        self.assertEqual(actual_work(a[0]),actual_work(g[0]))
        self.assertGreaterEqual(g[0].s.end(),a[0].s.end())
        report=g[0].s.clock_gating_report()
        self.assertTrue(any(x['wakeups'] for x in report['resources'].values()))
        for state in report['resources'].values():
            self.assertAlmostEqual(state['clock_on_ns']+state['off_ns'],report['lifetime_ns'])


if __name__=='__main__':unittest.main()
