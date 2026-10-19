"""Explicit 1RW bank lanes, finite blocking descriptors, calibrated macro costs.

A lane may contain multiple capacity macros behind a mux; adding depth does not
add lane bandwidth. Bulk descriptors use a conservative streaming service bound,
not a claim of cycle-accurate RTL or an unbounded word queue.
"""
import math
from collections import defaultdict
from sram_cacti_calibration_v1 import macro_lookup


class BankedSram:
    def __init__(self, calibration, depth, width, corner, capacity_bytes, lanes,
                 clock_hz, fabric_GBs, interleave_bytes=16, cdc_ns=20):
        if width % 8 or lanes<1 or capacity_bytes<1 or fabric_GBs<=0 or clock_hz<=0:
            raise ValueError('invalid SRAM geometry')
        self.spec=macro_lookup(calibration,depth,width,corner,clock_hz)
        if not self.spec['period_only_eligible']:raise ValueError('macro period violation')
        self.word=width//8;self.period=1e9/clock_hz;self.lanes=lanes
        self.macro_bytes=depth*self.word
        self.depth_macros=math.ceil(capacity_bytes/(lanes*self.macro_bytes))
        self.macros=lanes*self.depth_macros;self.capacity=self.macros*self.macro_bytes
        if interleave_bytes%self.word:raise ValueError('interleave not a whole word')
        self.stripe=interleave_bytes//self.word
        self.fabric_rate=fabric_GBs;self.cdc_ns=cdc_ns
        self.free=[0.]*lanes;self.fabric_free=0.;self.counters=defaultdict(float)
        self.events=[];self.keep_events=False

    def counts(self,address,size):
        if address<0 or size<0 or address+size>self.capacity:raise ValueError('SRAM bounds')
        if not size:return [0]*self.lanes
        lo=address//self.word;hi=math.ceil((address+size)/self.word)
        period=self.lanes*self.stripe
        def prefix(n,b):
            return (n//period)*self.stripe+min(self.stripe,max(0,n%period-b*self.stripe))
        return [prefix(hi,b)-prefix(lo,b) for b in range(self.lanes)]

    def transfer(self,ready,address,size,write=False,tag=''):
        return self._reserve(ready,self.counts(address,size),size,write,tag)

    def gather(self,ready,addresses,item_bytes=4,tag='random_read'):
        words=set()
        for address in addresses:
            if address<0 or address+item_bytes>self.capacity:raise ValueError('SRAM gather bounds')
            words.update(range(address//self.word,math.ceil((address+item_bytes)/self.word)))
        counts=[0]*self.lanes
        for word in words:counts[(word//self.stripe)%self.lanes]+=1
        self.counters['gather_logical_items']+=len(addresses)
        self.counters['gather_unique_words']+=len(words)
        return self._reserve(ready,counts,len(addresses)*item_bytes,False,tag)

    def _reserve(self,ready,counts,size,write,tag):
        if ready<0 or not math.isfinite(ready):raise ValueError('invalid ready time')
        active=[i for i,n in enumerate(counts) if n]
        if not active:return ready
        # One blocking descriptor owns all addressed lanes until it drains.
        # Service bound includes every macro word, rounds, bus and one CDC cost.
        bank_ready=max(self.free[i] for i in active)
        start=max(ready,bank_ready,self.fabric_free)
        start=math.ceil(start/self.period-1e-10)*self.period
        nmax=max(counts);words=sum(counts)
        access=self.spec['write_access_ns' if write else 'read_access_ns']
        port_ns=(nmax-1)*self.period+access
        bus_ns=words*self.word/self.fabric_rate
        done=start+max(port_ns,bus_ns)+self.cdc_ns
        # If the output fabric is slower, backpressure paces the word issuer.
        reserved=max(nmax*self.period,done-start)
        for i in active:self.free[i]=start+reserved
        self.fabric_free=done
        kind='write' if write else 'read'
        self.counters[kind+'_words']+=words
        self.counters[kind+'_logical_bytes']+=size
        self.counters[kind+'_physical_bytes']+=words*self.word
        self.counters['requests']+=1
        self.counters['bank_wait_ns']+=max(0,bank_ready-ready)
        self.counters['service_bound_ns']+=done-start
        self.counters['start_wait_ns']+=start-ready
        self.counters['port_work_ns']+=words*self.period
        self.counters['largest_descriptor_bytes']=max(self.counters['largest_descriptor_bytes'],size)
        if self.keep_events:self.events.append(dict(ready=ready,start=start,done=done,counts=counts,write=write,tag=tag))
        return done

    def report(self,end_ns):
        dynamic=(self.counters['read_words']*self.spec['read_internal_pJ']+
                 self.counters['write_words']*self.spec['write_internal_pJ'])*1e-12
        return dict(capacity_bytes=self.capacity,lanes=self.lanes,macros=self.macros,
            macros_per_lane=self.depth_macros,word_bytes=self.word,period_ns=self.period,
            interleave_bytes=self.stripe*self.word,fabric_GBs=self.fabric_rate,
            area_mm2=self.macros*self.spec['area_mm2'],
            dynamic_J=dynamic,leakage_J=self.macros*self.spec['ce_off_leakage_W']*end_ns*1e-9,
            counters=dict(self.counters),macro=self.spec,
            max_inflight_descriptors_per_lane=1,random_replay_bytes=0,
            model='conservative bulk streaming bound; no intra-descriptor reordering',
            limitations=['macro area excludes mux, routing, wrappers and CTS',
                'CDC is a configurable per-descriptor service cost, not a verified circuit',
                'CE-off clock dynamic uncharacterized; not counted as measured zero',
                'no extra area charge for tiny skid/control registers yet'])
