import copy,sys,unittest
from architecture_tlm.sliced_sram_20261027.test_memory import fixture,no_overlaps
from architecture_tlm.sliced_sram_20261027.calendar import FastCalendar
from architecture_tlm.sliced_sram_20261027.run_case import configuration
from architecture_tlm.sliced_sram_20261027.model import SlicedDecode,configure as old_configure
from architecture_tlm.unified_v6.core import Ledger
from architecture_tlm.unified_v6.test_ffn_locality import case
from architecture_tlm.scheduling_v2_20261027.test_scheduling import work
from architecture_tlm.ffn_local_pipeline_20261025.model import LocalPipelineFFN
from .model import configure,LocalPortsDecode
from .memory import LocalPortSRAM


def memory(independent=True):
    old,_,_=fixture();c=copy.deepcopy(old.c)
    c['clock_hz']=250e6;c['fabric_GBs']=1024.
    c['sliced'].update(cluster_GBs=128.,endpoint_GBs=128.)
    c['local_ports']=dict(core_hz=500e6,independent_paths=independent,
        path_bytes_per_core_cycle=dict(matrix=256,vector=64,DMA=256))
    s=FastCalendar(10000);m=LocalPortSRAM(c,old.spec,s,Ledger());return m,s


class LocalPorts(unittest.TestCase):
    def test_no_global_link_but_same_bank_conflict(self):
        m,s=memory();m.transfer(0,0,16,False,'weight_consume');m.transfer(0,128,16,True,'weight_fill')
        no_overlaps(self,s.events)
        bank=[x for x in s.events if 'sram_bank:0' in x['resources']]
        self.assertEqual(len(bank),2);self.assertEqual(bank[0]['end_ns']-bank[0]['start_ns'],4.)
        self.assertNotIn('sram_fabric',{r for x in s.events for r in x['resources']})
        self.assertFalse(any(r.startswith('sram_link:') for x in s.events for r in x['resources']))

    def test_endpoint_width_really_limits_wire(self):
        m,s=memory();m.c['local_ports']['path_bytes_per_core_cycle']['vector']=1
        m.transfer(0,0,64,False,'a')
        x=next(x for x in s.events if x['stage']=='sram_link_read')
        self.assertEqual(x['end_ns']-x['start_ns'],128.)
        self.assertEqual(x['bytes'],64);no_overlaps(self,s.events)

    def test_independent_trunks_with_same_single_port_banks(self):
        m,s=memory();m.paths['matrix']=2;m.paths['DMA']=2
        m.transfer(0,0,32,False,'weight_consume');m.transfer(0,32,32,True,'weight_fill')
        links=[x for x in s.events if x['stage'].startswith('sram_link_')]
        a,b=links;self.assertLess(max(a['start_ns'],b['start_ns']),min(a['end_ns'],b['end_ns']))
        self.assertEqual(m.report(200)['sliced']['additional_payload_buffer_bytes'],256)
        no_overlaps(self,s.events)

    def test_macro_clock_rejection(self):
        m,s=memory();c=copy.deepcopy(m.c);c['clock_hz']=500e6
        with self.assertRaises(ValueError):LocalPortSRAM(c,m.spec,s,Ledger())

    def test_config_ports_derived_from_consumers(self):
        args=dict(scope='one_layer',expanded_compute=True,expanded_sram=True,
            nonlinear_samples=128,ffn='sc',attention='screen_pv')
        c,_=configuration(args,sys.executable,'/unused');configure(c)
        self.assertEqual(c['sram']['capacity_bytes'],8*1024**2)
        self.assertEqual(c['sram']['local_ports']['path_bytes_per_core_cycle'],dict(matrix=1024,vector=64,DMA=128))
        self.assertEqual(c['sram']['fabric_GBs'],2048.)
        self.assertEqual(c['sram']['sliced']['cluster_GBs'],512.)
        self.assertEqual(c['sram']['clock_hz'],250e6)

    def test_path_byte_accounting(self):
        m,s=memory();m.transfer(0,15,3,False,'weight_consume');m.transfer(0,128,17,True,'weight_fill')
        self.assertEqual(dict(m.path_bytes),dict(matrix_R=32,DMA_W=32))
        self.assertEqual(sum(m.path_bytes.values()),m.traffic['read_physical_bytes']+m.traffic['write_physical_bytes'])


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c,m=case(engines=2,retain=2)
        c['sram'].update(capacity_bytes=8*1024**2,banks=512,macro_depth=256)
        c['local_pipeline']=dict(overlap=True,weight_bypass=True,cross_window_program=True,early_next_dma=True)
        c['digital_shared_prefill']=True;c['early_next_dma']=True;c['trace_event_limit']=200000
        cls.results=[]
        for mode in ('old','ports200','ports250'):
            cfg=copy.deepcopy(c);s=FastCalendar(200000,core_period_ns=1e9/cfg['core_hz'])
            if mode=='old':
                cfg['sram'].update(clock_hz=80e6,fabric_GBs=512.);old_configure(cfg);o=SlicedDecode(cfg,m,scheduler=s)
            else:
                configure(cfg,clock_hz=200e6 if mode=='ports200' else 250e6)
                o=LocalPortsDecode(cfg,m,scheduler=s)
            o.ffn_latest=LocalPipelineFFN(o);cls.results.append(o.run())

    def test_identical_work_and_physical_bytes(self):
        old=self.results[0]
        for r in self.results[1:]:
            self.assertEqual(work(old['actions']),work(r['actions']))
            self.assertEqual(old['SRAM']['traffic'],r['SRAM']['traffic'])
            self.assertEqual(old['DRAM']['traffic'],r['DRAM']['traffic'])
            self.assertEqual(old['FFN_activity'],r['FFN_activity'])
            self.assertEqual(old['attention_activity'],r['attention_activity'])
            for k in ('logical_job_order_sha256','logical_frame_order_sha256'):
                self.assertEqual(old['FFN_contract']['local_pipeline'][k],r['FFN_contract']['local_pipeline'][k])

    def test_same_capacity_cell_area_and_no_resource_overlaps(self):
        for r in self.results:
            self.assertFalse(r['trace_truncated']);no_overlaps(self,r['events'])
            self.assertEqual(r['SRAM']['configured_bytes'],8*1024**2)
            self.assertEqual(r['SRAM']['macros'],2048)
            self.assertEqual(self.results[0]['SRAM']['area_mm2'],r['SRAM']['area_mm2'])


if __name__=='__main__':unittest.main()
