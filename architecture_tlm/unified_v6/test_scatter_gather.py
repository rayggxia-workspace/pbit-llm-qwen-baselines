"""SG mechanism checks use a deterministic memory stub, not DRAM timing evidence."""
import copy,io,json,unittest
from collections import Counter
from types import SimpleNamespace
from architecture_tlm.dramsys_backend import DRAMSysExternal
from .core import DRAM,AddressMap,Scheduler,Ledger

class Stub:
    def __init__(self):self.calls=[]
    def access(self,t,size,kind,write,address=None):
        self.calls.append((t,[(address,size)],kind,write));return t+80+size/16
    def access_sg(self,t,ranges,kind,write):
        self.calls.append((t,list(ranges),kind,write));return t+80+sum(n for _,n in ranges)/16

def core(sg,limit=256,span_ns=10):
    c=dict(backend='link',burst_bytes=64,max_pending=32,bandwidth_GBs=16,latency_ns=80,
           scatter_gather=sg,sg_max_spans=limit,descriptor_span_ns=span_ns)
    d=DRAM(c,AddressMap(),Scheduler(),Ledger());d.bridge=Stub();return d

def wrapper(features=('scatter_gather_v1',)):
    b=DRAMSysExternal.__new__(DRAMSysExternal)
    b.cfg={'sg_max_spans':256,'strict_time_order':True};b.features=set(features)
    b.capacity=1024**2;b.counter=0;b.last_done_ns=0;b.traffic=Counter()
    b.service_ns=0;b.max_service_ns=0;b.trace=io.StringIO()
    b.process=SimpleNamespace(stdin=io.StringIO())
    def reply():
        r=json.loads(b.process.stdin.getvalue().splitlines()[-1])
        n=r.get('bytes',sum(x['bytes'] for x in r.get('ranges',[])))
        return dict(id=r['id'],done_ns=r['ready_ns']+100,burst_count=n//64)
    b._read=reply;return b

class ScatterContracts(unittest.TestCase):
    def test_address_and_byte_conservation(self):
        ranges=[(128*i+3,40) for i in range(1000)]
        old,new=core(False),core(True)
        t0=old.ranges(0,ranges,False,'K');t1=new.ranges(0,ranges,False,'K')
        self.assertEqual(len(old.bridge.calls),1000);self.assertEqual(len(new.bridge.calls),4)
        flatten=lambda d:[(a,n) for _,rs,_,_ in d.bridge.calls for a,n in rs]
        self.assertEqual(flatten(old),flatten(new));self.assertLess(t1,t0)
        for k in ('K_logical_bytes','K_physical_bytes','K_bursts'):
            self.assertEqual(old.traffic[k],new.traffic[k])
        self.assertEqual(new.traffic['SG_max_live_spans'],256)
        self.assertEqual(new.s.busy['dma_descriptor'],10000)
    def test_overlapping_ranges_read_once(self):
        d=core(True);d.ranges(0,[(63,2),(64,1),(70,1)],False,'V')
        self.assertEqual([tuple(x) for x in d.bridge.calls[0][1]],[(0,128)])
        self.assertEqual(d.traffic['V_physical_bytes'],128)
        self.assertEqual(d.traffic['V_logical_bytes'],4)
    def test_writes_and_order(self):
        d=core(True,2)
        d.ranges(500,[(128*i,64) for i in range(5)],True,'append')
        self.assertEqual([len(x[1]) for x in d.bridge.calls],[2,2,1])
        self.assertTrue(all(x[3] for x in d.bridge.calls))
        self.assertEqual(sorted(x[0] for x in d.bridge.calls),[x[0] for x in d.bridge.calls])
        self.assertEqual(d.e.actions['DMA_descriptor_batch'],3)
    def test_capacity_and_descriptor_cost_negative(self):
        for n in (0,257):
            with self.assertRaises(ValueError):core(True,n)
        with self.assertRaises(ValueError):core(True,256,-1)
    def test_single_span_equivalence(self):
        old,new=core(False),core(True)
        self.assertEqual(old.ranges(0,[(128,1024)],False,'weights'),new.ranges(0,[(128,1024)],False,'weights'))
    def test_wrapper_wire_format(self):
        b=wrapper();done=b.access_sg(10,[(0,64),(256,128)],'V',False)
        self.assertEqual(done,110)
        r=json.loads(b.process.stdin.getvalue())
        self.assertEqual(r['op'],'access_sg');self.assertEqual(r['ranges'],[{'address':0,'bytes':64},{'address':256,'bytes':128}])
        self.assertEqual(b.traffic['external_V_read_burst_bytes'],192)
    def test_wrapper_no_unsupported_fallback(self):
        b=wrapper(())
        with self.assertRaises(ValueError):b.access_sg(0,[(0,64)],'V',False)
        self.assertEqual(b.counter,0)
    def test_wrapper_invalid_spans(self):
        for ranges in ([],[(0,64)]*257,[(1,64)],[(0,0)],[(0,65)],[(64,128),(128,64)],[(128,64),(0,64)],[(1024**2,64)]):
            with self.subTest(ranges=ranges[:2]):
                with self.assertRaises(ValueError):wrapper().access_sg(0,ranges,'V',False)
    def test_wrapper_time_causality(self):
        b=wrapper();b.access_sg(100,[(0,64)],'V',False)
        with self.assertRaises(ValueError):b.access_sg(199,[(128,64)],'V',False)
        self.assertEqual(b.access_sg(200,[(128,64)],'V',False),300)
    def test_wrapper_burst_count_guard(self):
        b=wrapper();b._read=lambda:dict(id=1,done_ns=100,burst_count=999)
        with self.assertRaises(RuntimeError):b.access_sg(0,[(0,64)],'V',False)

if __name__=='__main__':unittest.main()
