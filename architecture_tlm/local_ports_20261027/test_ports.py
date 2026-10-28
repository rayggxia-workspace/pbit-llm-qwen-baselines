import copy,sys,unittest
from architecture_tlm.sliced_sram_20261027.test_memory import fixture,no_overlaps
from architecture_tlm.sliced_sram_20261027.calendar import FastCalendar
from architecture_tlm.sliced_sram_20261027.run_case import configuration
from architecture_tlm.sliced_sram_20261027.model import SlicedDecode,configure as old_configure
from architecture_tlm.unified_v6.core import Ledger
from architecture_tlm.unified_v6.test_ffn_locality import case
from architecture_tlm.scheduling_v2_20261027.test_scheduling import work
from architecture_tlm.ffn_local_pipeline_20261025.model import LocalPipelineFFN
from .model import configure,configure_exposed,widen_burst_ports,LocalPortsDecode
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
        self.assertFalse(c['sram']['local_ports']['independent_paths'])

    def test_path_byte_accounting(self):
        m,s=memory();m.transfer(0,15,3,False,'weight_consume');m.transfer(0,128,17,True,'weight_fill')
        self.assertEqual(dict(m.path_bytes),dict(matrix_R=32,DMA_W=32))
        self.assertEqual(sum(m.path_bytes.values()),m.traffic['read_physical_bytes']+m.traffic['write_physical_bytes'])
        shared,_=memory(independent=False)
        self.assertEqual(shared.report(200)['local_ports']['endpoint_GBs_per_slice'],dict(matrix=128.,vector=128.,DMA=128.))

    def test_wide_burst_does_not_increase_storage_or_external_bandwidth(self):
        args=dict(scope='one_layer',expanded_compute=True,expanded_sram=True,ffn='sc',attention='screen_pv')
        c,_=configuration(args,sys.executable,'/unused');configure(c);before=copy.deepcopy(c)
        widen_burst_ports(c)
        self.assertEqual(c['dram'],before['dram'])
        self.assertEqual(c['sram']['capacity_bytes'],before['sram']['capacity_bytes'])
        self.assertEqual(c['sram']['sliced'],before['sram']['sliced'])
        self.assertEqual(c['sram']['local_ports']['path_bytes_per_core_cycle'],dict(matrix=1024,vector=1024,DMA=1024))


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c,m=case(engines=2,retain=2)
        c['sram'].update(capacity_bytes=8*1024**2,banks=512,macro_depth=256)
        c['local_pipeline']=dict(overlap=True,weight_bypass=True,cross_window_program=True,early_next_dma=True)
        c['digital_shared_prefill']=True;c['early_next_dma']=True;c['trace_event_limit']=200000
        cls.results=[]
        for mode in ('old','ports200','ports250','exposed'):
            cfg=copy.deepcopy(c);s=FastCalendar(200000,core_period_ns=1e9/cfg['core_hz'])
            if mode=='old':
                cfg['sram'].update(clock_hz=80e6,fabric_GBs=512.);old_configure(cfg);o=SlicedDecode(cfg,m,scheduler=s)
            else:
                if mode=='exposed':configure_exposed(cfg)
                else:configure(cfg,clock_hz=200e6 if mode=='ports200' else 250e6)
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


class PhysicalPartition(unittest.TestCase):
    def setup_memory(self):
        from .partition import PartitionedSRAM
        old,_,_=fixture();c=copy.deepcopy(old.c)
        c.update(banks=2048,capacity_bytes=8*1024**2,macro_depth=256,clock_hz=250e6,fabric_GBs=8192.)
        c['sliced'].update(clusters=4,quantum_words=128,cluster_GBs=512.,endpoint_GBs=512.)
        c['local_ports']=dict(core_hz=500e6,independent_paths=True,weight_slot_bytes=65536,
            path_bytes_per_core_cycle=dict(matrix=1024,vector=64,DMA=128))
        s=FastCalendar(10000);return PartitionedSRAM(c,old.spec,s,Ledger()),s

    def test_mapping_is_injective_and_capacity_not_replicated(self):
        m,s=self.setup_memory()
        words=list(range(8192))+list(range(8192,8192+4*1024**2//16))
        mapped=[m.map_word(w) for w in words]
        self.assertEqual(len(mapped),len(set(mapped)));self.assertLess(max(mapped)*16,m.capacity)
        self.assertEqual(m.macros,2048);self.assertEqual(m.physical_capacity,8*1024**2)

    def test_ping_pong_workspace_have_disjoint_bank_sets(self):
        m,s=self.setup_memory()
        ping={m.map_word(w)%2048 for w in range(4096)}
        pong={m.map_word(w)%2048 for w in range(4096,8192)}
        workspace={m.map_word(w)%2048 for w in range(8192,8192+1024)}
        self.assertEqual((len(ping),len(pong),len(workspace)),(512,512,1024))
        self.assertFalse(ping&pong or ping&workspace or pong&workspace)

    def test_unaligned_word_rounding_and_energy_conserved(self):
        m,s=self.setup_memory();m.transfer(0,15,4098,False,'weight_consume')
        self.assertEqual(m.traffic['read_logical_bytes'],4098)
        self.assertEqual(m.traffic['read_words'],258)
        self.assertEqual(m.traffic['read_physical_bytes'],4128)
        self.assertEqual(sum(m.path_bytes.values()),4128);no_overlaps(self,s.events)

    def test_workspace_limit_enforced_before_alias(self):
        m,s=self.setup_memory()
        with self.assertRaises(ValueError):m.transfer(0,m.workspace_base+4*1024**2,16,False,'bad')
        with self.assertRaises(ValueError):m.transfer(0,65530,16,False,'cross_slot')

    def test_prefetch_and_current_weights_do_not_arbitrate_same_macros(self):
        m,s=self.setup_memory();m.transfer(0,0,8192,False,'weight_consume');m.transfer(0,65536,8192,True,'weight_fill')
        a={r for e in s.events if e.get('tag')=='weight_consume' for r in e['resources'] if r.startswith('sram_bank:')}
        b={r for e in s.events if e.get('tag')=='weight_fill' for r in e['resources'] if r.startswith('sram_bank:')}
        self.assertTrue(a and b);self.assertFalse(a&b);no_overlaps(self,s.events)


if __name__=='__main__':unittest.main()
