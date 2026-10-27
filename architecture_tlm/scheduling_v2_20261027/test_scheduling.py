"""Mechanism and conservation checks; no model/EDA/DRAMSys required."""
import copy,random,unittest
from architecture_tlm.scheduling_v2_20261027.calendar import ReadyCalendar
from architecture_tlm.scheduling_v2_20261027.model import SchedulingDecode
from architecture_tlm.unified_v6.core import Scheduler
from architecture_tlm.unified_v6.test_ffn_locality import case
from architecture_tlm.ffn_local_pipeline_20261025.model import LocalPipelineFFN

def run(calendar=False,prefill=False,cross=False,*,tile=64,early=False):
    c,m=case(tile=tile,engines=2,retain=2,source_groups=tile//64)
    c['trace_event_limit']=100000;c['local_pipeline']=dict(overlap=True,weight_bypass=True,cross_window_program=cross)
    c['digital_shared_prefill']=prefill;c['early_next_dma']=early;c['local_pipeline']['early_next_dma']=early
    sched=ReadyCalendar(c['trace_event_limit'],core_period_ns=1e9/c['core_hz']) if calendar else Scheduler(c['trace_event_limit'])
    o=SchedulingDecode(c,m,scheduler=sched);o.ffn_latest=LocalPipelineFFN(o);r=o.run()
    return o,r

def work(actions):
    duration={'dram_background_ns','digital_idle_ns','sc_idle_ns','control_interconnect_ns','uncalibrated_HBM_system_ns'}
    return {k:v for k,v in actions.items() if k not in duration}

class CalendarTests(unittest.TestCase):
    def test_early_work_uses_idle_gap(self):
        s=ReadyCalendar();self.assertEqual(s.reserve('late',100,10,['r']),110)
        self.assertEqual(s.reserve('early',0,10,['r']),10);self.assertEqual(s.end(),110)
    def test_multi_resource_intersection(self):
        s=ReadyCalendar();s.reserve('a',10,10,['a']);s.reserve('b',0,15,['b'])
        self.assertEqual(s.reserve('both',0,10,['a','b']),30)
    def test_period_alignment(self):
        s=ReadyCalendar();s.reserve('a',8,4,['r']);self.assertEqual(s.reserve('b',1,4,['r'],4),8)
    def test_fence_discards_only_completed_history(self):
        s=ReadyCalendar();s.reserve('late',100,10,['r']);s.advance(20)
        self.assertEqual(s.reserve('early',21,10,['r']),31);s.advance(110);self.assertEqual(s.calendar['r'],[])
    def test_against_independent_candidate_enumeration(self):
        g=random.Random(186);s=ReadyCalendar(10000);book={'a':[],'b':[],'c':[]}
        for i in range(300):
            ready=g.randrange(100);length=g.randrange(1,9);rs=g.sample(list(book),g.randrange(1,4))
            candidates=sorted({ready}|{e for r in rs for _,e in book[r] if e>=ready})
            start=next(t for t in candidates if all(not(t<b and a<t+length) for r in rs for a,b in book[r]))
            self.assertEqual(s.reserve(str(i),ready,length,rs),start+length)
            for r in rs:book[r].append((start,start+length))

class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs=[run(*x) for x in [(False,False,False),(False,True,False),(False,False,True),(True,False,False),(True,True,True)]]
    def test_no_resource_overlap_or_past_dependency(self):
        for _,r in self.runs:
            self.assertFalse(r['trace_truncated']);resources={}
            for e in r['events']:
                self.assertGreaterEqual(e['start_ns']+1e-7,e['ready_ns'])
                if e['end_ns']>e['start_ns']:
                    for name in e['resources']:resources.setdefault(name,[]).append((e['start_ns'],e['end_ns']))
            for name,events in resources.items():
                q=sorted(events)
                for a,b in zip(q,q[1:]):self.assertLessEqual(a[1],b[0]+1e-6,name)
    def test_identical_work_traffic_and_local_storage(self):
        a=self.runs[0][1]
        for _,b in self.runs[1:]:
            self.assertEqual(work(a['actions']),work(b['actions']))
            self.assertEqual(a['DRAM']['traffic'],b['DRAM']['traffic'])
            self.assertEqual(a['SRAM']['traffic'],b['SRAM']['traffic'])
            self.assertEqual(a['FFN_activity'],b['FFN_activity'])
            self.assertEqual(a['attention_activity'],b['attention_activity'])
            self.assertEqual(a['FFN_contract']['local_state'],b['FFN_contract']['local_state'])
            for field in ['logical_job_order_sha256','logical_frame_order_sha256']:
                self.assertEqual(a['FFN_contract']['local_pipeline'][field],b['FFN_contract']['local_pipeline'][field])
    def test_all_banks_and_tickets_retire(self):
        for o,r in self.runs:
            self.assertEqual(o.ffn_latest.bank_tickets,[None,None]);self.assertIsNone(o.ffn_latest.response_ticket)
            records=r['FFN_contract']['local_pipeline']['records'];prior={}
            for i,t in enumerate(records):
                self.assertLessEqual(t['ready_ns'],t['compute_start_ns']+1e-6)
                if i:self.assertLessEqual(records[i-1]['retire_ns'],t['compute_start_ns']+1e-6)
                if t['bank'] in prior:self.assertLessEqual(prior[t['bank']],t['issue_ns']+1e-6)
                prior[t['bank']]=t['retire_ns']
    def test_new_policies_executed(self):
        r=self.runs[-1][1]
        self.assertGreater(r['FFN_contract']['local_pipeline']['counts']['cross_window_early_programs'],0)
        self.assertGreater(r['tile_pipeline']['digital']['counts']['prefilled'],0)
        self.assertIsInstance(self.runs[-1][0].s,ReadyCalendar)
    def test_earlier_dma_same_capacity_work_and_bytes(self):
        _,a=run(False,False,False);o,b=run(True,True,True,early=True)
        self.assertEqual(work(a['actions']),work(b['actions']))
        self.assertEqual(a['DRAM']['traffic'],b['DRAM']['traffic'])
        self.assertEqual(a['SRAM']['traffic'],b['SRAM']['traffic'])
        self.assertEqual(a['FFN_contract']['local_state'],b['FFN_contract']['local_state'])
        pipe=b['tile_pipeline']['digital'];self.assertEqual(pipe['counts']['max_pending'],1)
        self.assertGreater(pipe['counts']['dma_issue_after_shared_fill'],0)
        self.assertGreater(b['FFN_contract']['local_pipeline']['counts']['early_dma_before_context'],0)
        self.assertLessEqual(b['metrics']['elapsed_ns'],a['metrics']['elapsed_ns'])
        for prev,cur in zip(pipe['records'],pipe['records'][1:]):
            if prev['name']==cur['name']:
                self.assertGreaterEqual(cur['issue_ns']+1e-6,prev['fill_done_ns'])
        resources={}
        for e in b['events']:
            self.assertGreaterEqual(e['start_ns']+1e-6,e['ready_ns'])
            if e['end_ns']>e['start_ns']:
                for r in e['resources']:resources.setdefault(r,[]).append((e['start_ns'],e['end_ns']))
        for name,events in resources.items():
            q=sorted(events)
            for a,b in zip(q,q[1:]):self.assertLessEqual(a[1],b[0]+1e-6,name)

    def test_clock_usage_ungated(self):
        o,r=self.runs[-1];z=o.s.clock_gating_report(r['metrics']['elapsed_ns'])
        self.assertFalse(z['enabled'])
        for v in z['resources'].values():self.assertEqual(v['clock_on_ns'],v['lifetime_ns'])
    def test_128_quadrants_keep_same_work(self):
        _,a=run(tile=128);o,b=run(True,True,True,tile=128)
        self.assertEqual(work(a['actions']),work(b['actions']));self.assertEqual(a['FFN_activity'],b['FFN_activity'])

if __name__=='__main__':unittest.main(verbosity=2)
