"""Bounded request/completion memory service for unified_v6 (Issue227).

DRAM command scheduling remains in DRAMSys. This module models accelerator
DMA arbitration, finite return storage, and beat-level single-port SRAM.
No complete stochastic stream or tile is silently buffered in Python memory.
"""
from collections import Counter, deque
from dataclasses import dataclass
import heapq
import itertools
import json
import math
import subprocess


def align_time(t, period):
    return math.ceil(t/period-1e-9)*period


class Signal:
    """Readiness notification; simulator optimization, no hardware data buffer."""
    def __init__(self):self.ready=False;self.waiters=[]
    def __call__(self):return self.ready
    def set(self):
        if self.ready:return
        self.ready=True;callbacks=self.waiters;self.waiters=[]
        for callback in callbacks:callback()
    def subscribe(self,callback):
        if self.ready:callback()
        else:self.waiters.append(callback)


def when_any(conditions):
    conditions=list(conditions)
    if not all(hasattr(c,'subscribe') for c in conditions):return lambda:any(c() for c in conditions)
    result=Signal()
    for c in conditions:c.subscribe(result.set)
    return result


class AnalyticDRAM:
    """Explicit functional/timing proxy for tests; NOT DRAMSys or DRAMPower."""
    def __init__(self, latency_ns=60., bandwidth_GBs=119.424):
        self.now=0.;self.latency=latency_ns;self.bandwidth=bandwidth_GBs
        self.events=[];self.serial=itertools.count();self.link_free=0.;self.count=Counter()
    def step(self, until, requests=()):
        assert until+1e-6>=self.now
        for r in requests:
            self.link_free=max(self.link_free,self.now)+64/self.bandwidth
            heapq.heappush(self.events,(self.link_free+self.latency,next(self.serial),r['id']))
            self.count['write' if r.get('write') else 'read']+=1
        # Match the asynchronous bridge: stop early at a response, so consumers
        # may schedule causal SRAM work before the requested horizon.
        target=min(until,self.events[0][0]) if self.events else until
        replies=[]
        while self.events and self.events[0][0]<=target+1e-6:
            t,_,ident=heapq.heappop(self.events);replies.append(dict(id=ident,done_ns=t))
        self.now=target
        return dict(accepted=len(requests),now_ns=target,responses=replies)
    def finish(self,end):
        assert not self.events
        return dict(status='finished',backend='analytic_test_proxy',end_ns=end,
                    reads=self.count['read'],writes=self.count['write'],energy_J=None)
    def close(self):pass


class DRAMSysAsync:
    """Existing bounded_async_v1 protocol, no added macro-DMA drain barrier."""
    def __init__(self,binary,config,credit=64,log='dramsys.stderr.log'):
        self.log=open(log,'w',encoding='utf-8')
        self.p=subprocess.Popen([str(binary),str(config),str(credit),'64'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1)
        self.ready=self._read();self.now=0.;self.final=None
        if self.ready.get('status')!='ready' or 'bounded_async_v1' not in self.ready.get('features',[]):
            self.close();raise ValueError('bounded_async_v1 DRAMSys bridge required')
    def _read(self):
        while True:
            s=self.p.stdout.readline()
            if not s:raise RuntimeError('DRAMSys exited before response')
            if s.lstrip().startswith('{'):return json.loads(s)
            self.log.write(s)
    def step(self,until,requests=()):
        if until+1e-6<self.now:raise ValueError('DRAM clock moved backwards')
        self.p.stdin.write(json.dumps(dict(op='step',until_ns=until,requests=list(requests)),separators=(',',':'))+'\n')
        self.p.stdin.flush();r=self._read()
        if r['now_ns']+1e-6<self.now:raise ValueError('DRAM returned past time')
        self.now=r['now_ns'];return r
    def finish(self,end):
        self.p.stdin.write(json.dumps(dict(op='finish',end_ns=end))+'\n');self.p.stdin.flush()
        self.final=self._read()
        assert self.final['status']=='finished' and self.p.wait(timeout=30)==0
        self.log.close();return self.final
    def close(self):
        if self.p.poll() is None:self.p.terminate();self.p.wait(timeout=10)
        if not self.log.closed:self.log.close()


@dataclass
class Region:
    name:str
    base:int
    size:int
    banks:tuple


class BeatSRAM:
    """One16B read OR write per physical bank/clock, finite fabric per cycle.

    A long transfer relinquishes ports after every beat. Grants occur only at
    simulated current time; a future vector never reserves all banks in advance.
    Two128-bit banks may implement one256-bit logical Attention bank.
    """
    def __init__(self,hub,capacity=8388608,banks=512,clock_hz=100000000,
                 fabric_GBs=512.,read_pJ=10.0527,write_pJ=13.9599,
                 leakage_macro_W=7.7544e-6,area_raw_macro_mm2=.03322622205,
                 word_bytes=16,access_ns=2.8767,minimum_period_ns=3.468):
        self.hub=hub;self.capacity=capacity;self.nbank=banks;self.period=1e9/clock_hz
        if self.period<minimum_period_ns:raise ValueError('SRAM period below library minimum')
        self.word=word_bytes;self.access_ns=access_ns
        self.fabric_words=max(1,int(fabric_GBs*self.period//word_bytes))
        self.prices={'read':read_pJ,'write':write_pJ};self.leak_W=leakage_macro_W
        self.area_raw=area_raw_macro_mm2;self.regions={};self.top=0
        self.queue=deque();self.scheduled=False;self.last_tick=-1
        self.granted_banks=set();self.granted_words=0;self.count=Counter();self.by_tag={}
        self.energy_pJ=0.;self.job_id=itertools.count();self.bank_allocated=[0]*banks
    def region(self,name,size,banks):
        base=math.ceil(self.top/64)*64
        if name in self.regions or size<=0 or base+size>self.capacity:raise ValueError('invalid SRAM allocation')
        banks=tuple(banks)
        if not banks or min(banks)<0 or max(banks)>=self.nbank or len(set(banks))!=len(banks):raise ValueError('invalid bank map')
        words=math.ceil(size/self.word)
        allocation={bank:(words//len(banks)+(j<words%len(banks)))*self.word for j,bank in enumerate(banks)}
        if any(self.bank_allocated[bank]+n>self.capacity//self.nbank for bank,n in allocation.items()):
            raise ValueError('physical SRAM bank capacity exceeded')
        for bank,n in allocation.items():self.bank_allocated[bank]+=n
        r=Region(name,base,size,banks);self.regions[name]=r;self.top=base+size;return r
    def submit(self,r,offset,size,write,tag,callback):
        if offset<0 or size<=0 or offset+size>r.size:raise ValueError('SRAM transfer outside region')
        first=offset//self.word;last=math.ceil((offset+size)/self.word)
        self.count['logical_write_bytes' if write else 'logical_read_bytes']+=size
        self.queue.append(dict(id=next(self.job_id),r=r,next=first,last=last,write=write,tag=tag,cb=callback))
        self.count['peak_jobs']=max(self.count['peak_jobs'],len(self.queue));self._wake()
    def _wake(self):
        if not self.scheduled and self.queue:
            t=align_time(self.hub.now,self.period)
            if t<=self.last_tick+1e-6:t=self.last_tick+self.period
            self.scheduled=True;self.hub.later(t,self._tick)
    def _tick(self):
        self.scheduled=False;now=self.hub.now
        if now<=self.last_tick+1e-6:raise ValueError('double SRAM tick')
        self.last_tick=now;used=set();budget=self.fabric_words
        # Round robin among transfers; once all currently eligible heads are
        # blocked, wait for the next physical clock instead of locking banks.
        missed=0
        while self.queue and budget and missed<len(self.queue):
            job=self.queue.popleft();r=job['r'];bank=r.banks[job['next']%len(r.banks)]
            if bank in used:
                self.queue.append(job);missed+=1;self.count['bank_head_conflicts']+=1;continue
            missed=0;used.add(bank);budget-=1;job['next']+=1
            kind='write' if job['write'] else 'read';tag=job['tag']
            self.count[kind+'_words']+=1;self.count[kind+'_physical_bytes']+=self.word
            record=self.by_tag.setdefault(tag,Counter());record[kind+'_words']+=1
            self.energy_pJ+=self.prices[kind]
            if job['next']==job['last']:self.hub.later(now+self.access_ns,job['cb'])
            else:self.queue.append(job)
        self.count['cycles_with_grants']+=bool(used)
        self.count['peak_banks_per_cycle']=max(self.count['peak_banks_per_cycle'],len(used))
        self.count['peak_words_per_cycle']=max(self.count['peak_words_per_cycle'],self.fabric_words-budget)
        self._wake()
    def report(self,end):
        macros=math.ceil(self.capacity/4096)
        return dict(capacity_bytes=self.capacity,allocated_bytes=self.top,physical_banks=self.nbank,
            word_bytes=self.word,clock_hz=1e9/self.period,fabric_GBs=self.fabric_words*self.word/self.period,
            counts=dict(self.count),by_tag={k:dict(v) for k,v in self.by_tag.items()},
            dynamic_mJ=self.energy_pJ*1e-9,leakage_mJ=macros*self.leak_W*end*1e-6,
            area_raw_mm2=macros*self.area_raw,area_factor=.81,area55eq_mm2=macros*self.area_raw*.81,
            boundaries='macro internal events and CEoff leakage; no external driver/CTS/PHY',
            regions=[dict(name=r.name,base=r.base,size=r.size,banks=list(r.banks)) for r in self.regions.values()])


class Descriptor:
    def __init__(self,ident,owner,address,size,region,offset,kind,write,callback,spans=None):
        if address%64 or size%64 or offset%16:raise ValueError('DMA64B alignment required')
        self.id=ident;self.owner=owner;self.address=address;self.size=size
        self.region=region;self.offset=offset;self.kind=kind;self.write=write;self.cb=callback
        self.issued=0;self.returned=0;self.filled=0
        self.prepared=0;self.write_ready=set()
        self.spans=spans or [(address,size)];self.span=0;self.span_offset=0
        if sum(n for _,n in self.spans)!=size or any(a%64 or n%64 for a,n in self.spans):raise ValueError('unaligned SG')
    def next_address(self):
        a,n=self.spans[self.span];result=a+self.span_offset;self.span_offset+=64
        if self.span_offset==n:self.span+=1;self.span_offset=0
        return result


class SharedMemory:
    """ONE global credit/return/issue budget across all requester classes."""
    def __init__(self,backend,credit=64,response_bytes=8192,issue_per_cycle=8,
                 issue_period_ns=10.,descriptor_serial=False,response_buffered=True,
                 memory_config=None,owner_quantum=16,return_banks=128):
        if min(credit,response_bytes,issue_per_cycle,issue_period_ns)<=0:raise ValueError('finite positive limits')
        self.backend=backend;self.now=0.;self.events=[];self.serial=itertools.count()
        self.req_id=0;self.desc_id=0;self.queues={};self.owners=[];self.rr=0
        self.active_owners=deque()
        self.owner_quantum=owner_quantum;self.current_owner=None;self.quantum_left=0
        if owner_quantum<1:raise ValueError('positive DMA service quantum')
        self.pending={};self.credit=credit;self.response_bytes=response_bytes
        self.return_occupied=0;self.issue_n=issue_per_cycle;self.issue_period=issue_period_ns;self.issue_at=0.
        self.descriptor_serial=descriptor_serial;self.active_desc=None;self.buffered=response_buffered
        self.count=Counter();self.by_kind={};self.descriptors={};self.completions=[]
        self.mem=BeatSRAM(self,**(memory_config or {}))
        self.return_banks=return_banks
        self.response=self.mem.region('DMA_return_FIFO',response_bytes,range(return_banks));self.free_slots=deque(range(response_bytes//64))
        self.unpriced=Counter();self.write_slots=8;self.free_write_slots=8
    def later(self,t,callback,*args):
        if t+1e-6<self.now:raise ValueError('event before current time')
        t=math.ceil(t*1000-1e-6)/1000
        heapq.heappush(self.events,(t,next(self.serial),callback,args))
    def after(self,ns,callback):self.later(self.now+ns,callback)
    def delay(self,ns):
        done=Signal();self.after(ns,done.set);yield done
    def dma(self,owner,address,size,region,offset,kind,callback,write=False,spans=None):
        if size==0:self.later(self.now,callback);return None
        if owner not in self.queues:self.queues[owner]=deque();self.owners.append(owner)
        self.desc_id+=1;d=Descriptor(self.desc_id,owner,address,size,region,offset,kind,write,callback,spans)
        if not self.queues[owner]:self.active_owners.append(owner)
        self.queues[owner].append(d);self.descriptors[d.id]=d
        self.count['descriptors']+=1
        self.count['peak_descriptors']=max(self.count['peak_descriptors'],len(self.descriptors))
        return d
    def fetch(self,*args,**kw):
        done=Signal();self.dma(*args,callback=done.set,**kw);yield done
    def transfer(self,r,offset,size,write,tag):
        done=Signal();self.mem.submit(r,offset,size,write,tag,done.set);yield done
    def _choose(self):
        for _ in range(len(self.active_owners)):
            owner=self.active_owners[0]
            q=self.queues[owner]
            if not q:raise RuntimeError('stale active DMA owner')
            d=q[0]
            if d.write and d.issued not in d.write_ready:
                self.active_owners.rotate(-1);self.current_owner=None;continue
            if self.descriptor_serial and self.active_desc not in (None,d.id):
                self.active_owners.rotate(-1);self.current_owner=None;continue
            if owner!=self.current_owner or self.quantum_left==0:
                self.current_owner=owner;self.quantum_left=self.owner_quantum
            self.quantum_left-=1
            if self.active_desc is None and self.descriptor_serial:self.active_desc=d.id
            if d.write:d.write_ready.remove(d.issued)
            d.issued+=64
            if d.issued==d.size:q.popleft()
            if not q:
                self.active_owners.popleft();self.current_owner=None;self.quantum_left=0
            elif self.quantum_left==0:
                self.active_owners.rotate(-1);self.current_owner=None
            return d
        return None
    def _prepare_writes(self):
        # Eight explicit64B source holding slots; SRAM data must be ready
        # before a DRAM write is issued. They stay occupied until completion.
        for owner in list(self.active_owners):
            if not self.free_write_slots:return
            if not self.queues[owner]:continue
            d=self.queues[owner][0]
            if not d.write:continue
            while self.free_write_slots and d.prepared<d.size:
                off=d.prepared;d.prepared+=64;self.free_write_slots-=1
                self.mem.submit(d.region,d.offset+off,64,False,d.kind+'_DMA_source',lambda d=d,off=off:d.write_ready.add(off))
                self.count['peak_write_source_slots']=max(self.count['peak_write_source_slots'],self.write_slots-self.free_write_slots)
                self.unpriced['write_source_holding_bytes_peak']=max(self.unpriced['write_source_holding_bytes_peak'],(self.write_slots-self.free_write_slots)*64)
    def _finish_burst(self,d):
        d.filled+=64
        if d.filled==d.size:
            del self.descriptors[d.id]
            self.count['descriptors_completed']+=1
            if len(self.completions)<100:self.completions.append(dict(descriptor=d.id,owner=d.owner,kind=d.kind,done_ns=self.now,bytes=d.size))
            d.cb()
    def _response(self,reply):
        d,offset=self.pending.pop(reply['id']);d.returned+=64
        if self.descriptor_serial and d.returned==d.size:self.active_desc=None
        stats=self.by_kind.setdefault(d.kind,Counter());kind='write' if d.write else 'read'
        self.count['dram_'+kind+'_bytes']+=64;stats[kind+'_bytes']+=64
        if d.write:self.free_write_slots+=1;self._finish_burst(d);return
        self.return_occupied+=64
        self.count['peak_response_bytes']=max(self.count['peak_response_bytes'],self.return_occupied)
        if not self.free_slots:raise RuntimeError('response FIFO overflow')
        slot=self.free_slots.popleft()
        def target_ready():
            self.return_occupied-=64;self.free_slots.append(slot);self._finish_burst(d)
        def target_write():
            self.mem.submit(d.region,d.offset+offset,64,True,d.kind+'_fill',target_ready)
        if self.buffered:
            def written():self.mem.submit(self.response,slot*64,64,False,'DMA_return_read',target_write)
            self.mem.submit(self.response,slot*64,64,True,'DMA_return_write',written)
        else:
            # The payload remains in an explicit64B elastic ingress slot until
            # target SRAM accepts it. This control/register price is UNKNOWN.
            self.unpriced['ingress_elastic_64B_beats']+=1;target_write()
    def run(self,done):
        spins=0
        while True:
            while self.events and self.events[0][0]<=self.now+1e-6:
                _,_,fn,args=heapq.heappop(self.events);fn(*args)
            finished=done()
            if finished and not self.descriptors and not self.pending and not self.mem.queue:return
            self._prepare_writes()
            requests=[];issued=[]
            if self.now+1e-6>=self.issue_at:
                budget=min(self.issue_n,self.credit-len(self.pending),
                           (self.response_bytes-self.return_occupied)//64-len(self.pending))
                for _ in range(max(0,budget)):
                    d=self._choose()
                    if d is None:break
                    offset=d.issued-64;self.req_id+=1
                    address=d.next_address()
                    record=self.by_kind.setdefault(d.kind,Counter())
                    record['issued_bytes']+=64;record['issued_address_sum']+=address
                    record['issued_address_xor']^=address
                    requests.append(dict(id=self.req_id,address=address,write=d.write))
                    issued.append((self.req_id,(d,offset)))
                if requests:self.issue_at=(math.floor(self.now/self.issue_period+1e-9)+1)*self.issue_period
            horizon=self.events[0][0] if self.events else self.now+10000
            remaining_slots=min(self.credit-len(self.pending)-len(issued),
                (self.response_bytes-self.return_occupied)//64-len(self.pending)-len(issued))
            if self.active_owners and remaining_slots>0:
                # If descriptor barrier is waiting for a response, do not spin
                # at the injection clock without an eligible descriptor.
                eligible=any(self.queues[o] and
                    (not self.descriptor_serial or self.active_desc in (None,self.queues[o][0].id)) and
                    (not self.queues[o][0].write or self.queues[o][0].issued in self.queues[o][0].write_ready)
                    for o in self.active_owners)
                if eligible:horizon=min(horizon,max(self.now+.001,self.issue_at))
            response=self.backend.step(max(self.now,horizon),requests)
            if response['accepted']!=len(issued):raise RuntimeError('backend admission mismatch')
            self.pending.update(issued);self.now=response['now_ns']
            self.count['peak_outstanding']=max(self.count['peak_outstanding'],len(self.pending))
            self.count['issue_batches']+=bool(requests)
            for reply in response['responses']:self._response(reply)
            assert len(self.pending)<=self.credit
            assert self.return_occupied+len(self.pending)*64<=self.response_bytes
            spins+=1
            if spins>200000000:raise RuntimeError('event progress limit')
    def execute(self,generators):
        active={};returns=[];ready=deque();queued=set();fallback=set()
        def wake(key):
            if key in active and key not in queued:ready.append(key);queued.add(key)
        for key,gen in enumerate(generators):active[key]=[gen,None];wake(key)
        def advance():
            for key in list(fallback):
                if active[key][1]():wake(key)
            while ready:
                key=ready.popleft();queued.remove(key);fallback.discard(key)
                if key not in active:continue
                gen,_=active[key]
                while True:
                    try:condition=next(gen);active[key][1]=condition
                    except StopIteration as s:
                        del active[key];returns.append(s.value);break
                    if condition():continue
                    if hasattr(condition,'subscribe'):condition.subscribe(lambda key=key:wake(key))
                    else:fallback.add(key)
                    break
            return not active
        self.run(advance);return returns
    def report(self):
        assert self.count['descriptors']==self.count['descriptors_completed']
        return dict(elapsed_ns=self.now,global_credit=self.credit,response_bytes=self.response_bytes,
            issue_peak_GBs=self.issue_n*64/self.issue_period,descriptor_serial=self.descriptor_serial,
            owner_quantum=self.owner_quantum,
            return_banks=self.return_banks,
            response_buffered=self.buffered,counts=dict(self.count),by_kind={k:dict(v) for k,v in self.by_kind.items()},
            SRAM=self.mem.report(self.now),unpriced_actions=dict(self.unpriced),first_completions=self.completions,
            final_pending=len(self.pending),final_response_occupied=self.return_occupied)


def dram_energy(final):
    channels=final.get('power_at_system_end')
    if channels is None:return None
    components=Counter();total=0.
    for value in channels.values():
        total+=value['core_J']
        components.update(value['core_components_J'])
    command=sum(components[k] for k in ('ACT','PRE','RD','WR','RDA','WRA'))
    return dict(core_total_mJ=total*1000,command_component_mJ=command*1000,
        background_refresh_other_mJ=(total-command)*1000,
        components_mJ={k:v*1000 for k,v in components.items()},channels=len(channels),
        boundary='DRAM core only, counted once for global horizon; VDDQ/PHY uncalibrated; negative ACT terms retained')
