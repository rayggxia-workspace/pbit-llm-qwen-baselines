"""Coalesced resource adapters using unified_v6's existing event executor.

Transactions are addressed ranges. SRAM service is bank-calendar/burst-level;
DRAM is a bounded bandwidth/latency macro, not Ramulator command scheduling.
These adapters permit fast controller integration without calling them native
DRAM or beat-exact SRAM results. Native service adapters can replace them.
"""
from collections import Counter, deque
from math import ceil


class Pool:
    def __init__(self, sim, count, name):
        self.sim, self.count, self.name = sim, count, name
        self.free = deque(range(count)); self.waiters = deque()
        self.peak = self.used = 0; self.wait_ns = 0.

    def acquire(self):
        if self.free:
            item = self.free.popleft()
        else:
            ticket = self.sim.signal(); box = []; start = self.sim.now
            self.waiters.append((ticket, box)); yield ticket
            self.wait_ns += self.sim.now - start; item = box[0]
        self.used += 1; self.peak = max(self.peak, self.used)
        return item

    def release(self, item):
        assert self.used > 0
        self.used -= 1
        if self.waiters:
            ticket, box = self.waiters.popleft(); box.append(item); ticket.set()
        else:
            self.free.append(item)


class SRAM:
    def __init__(self, sim, hw):
        self.sim, self.hw = sim, hw
        self.bank_free = [0.] * (144 + 16 * hw['cores'])
        self.count = Counter(); self.by_tag = {}
        self.beat = None; self.regions = {}
        if hw.get('sram_backend') == 'beat':
            n=len(self.bank_free)
            self.beat=sim.core.BeatSRAM(sim.h,capacity=n*4096,banks=n,
                clock_hz=hw['clock_MHz']*1e6,fabric_GBs=n*16/sim.period,
                read_pJ=hw['sram_read_pJ'],write_pJ=hw['sram_write_pJ'],access_ns=sim.period)
            self.regions['front']=self.beat.region('front',hw['front_bytes'],range(72))
            self.regions['attention']=self.beat.region('attention',hw['attention_bytes'],range(72,144))
            for group in range(8):
                capacity=hw['attention_bytes']//8
                self.regions['attention:'+str(group)]=sim.core.Region('attention:'+str(group),
                    self.regions['attention'].base+group*capacity,capacity,tuple(range(72+9*group,81+9*group)))
            for core in range(hw['cores']):
                self.regions['cim:'+str(core)]=self.beat.region('cim'+str(core),8192,range(144+16*core,160+16*core))
            sim.h.mem=self.beat

    def transfer(self, region, offset, size, write, tag):
        assert offset >= 0 and size > 0
        if region == 'front':
            banks, capacity = list(range(72)), self.hw['front_bytes']
        elif region == 'attention':
            banks, capacity = list(range(72, 144)), self.hw['attention_bytes']
        elif region.startswith('attention:'):
            group=int(region.split(':')[1])
            banks, capacity = list(range(72+9*group,81+9*group)), self.hw['attention_bytes']//8
        else:
            core = int(region.split(':')[1]); assert 0 <= core < self.hw['cores']
            banks, capacity = list(range(144+16*core, 160+16*core)), 8192
        assert offset + size <= capacity, (region, offset, size, capacity)
        first, last = offset // 16, ceil((offset + size) / 16)
        n = last - first; period = self.sim.period
        if self.beat is not None:
            done=self.sim.signal()
            if region.startswith('attention:') and region not in self.regions:
                group=int(region.split(':')[1])
                self.regions[region]=self.sim.core.Region(region,self.regions['attention'].base+group*capacity,capacity,tuple(banks))
            self.beat.submit(self.regions[region],offset,size,write,tag,done.set)
            yield done
            kind='write' if write else 'read'
            row=self.by_tag.setdefault(tag,Counter())
            row[kind+'_bytes']+=size;row[kind+'_words']+=n
            self.count[kind+'_bytes']+=size;self.count[kind+'_words']+=n
            return
        end = self.sim.now; kind = 'write' if write else 'read'
        for j, bank in enumerate(banks):
            # Contiguous addresses striped over the declared bank set.
            residue = (j - first) % len(banks)
            words = max(0, (n - 1 - residue) // len(banks) + 1)
            if not words:
                continue
            start = self.sim.edge(max(self.sim.now, self.bank_free[bank]))
            self.bank_free[bank] = start + words * period
            end = max(end, self.bank_free[bank])
        row = self.by_tag.setdefault(tag, Counter())
        row[kind+'_bytes'] += size; row[kind+'_words'] += n
        self.count[kind+'_bytes'] += size; self.count[kind+'_words'] += n
        yield from self.sim.delay(end - self.sim.now)


class DMA:
    """Two8KiB in-flight buffers; full credit retained through target landing.

    One range may represent many64B beats. Its return latency and bus occupancy
    remain finite. This intentionally exposes transaction-boundary sensitivity.
    """
    def __init__(self, sim, sram, hw):
        self.sim, self.sram, self.hw = sim, sram, hw
        self.slots = Pool(sim, hw['dma_bytes']//8192, 'DMA_8KiB_credit')
        self.bus_free = 0.; self.count = Counter(); self.by_tag = {}
        self.address_digest = 0

    def transfer(self, address, size, region, offset, write, tag, spans=None):
        assert address >= 0 and size > 0
        if spans is not None:
            assert len(spans) <= self.hw['sg_segments'] and sum(n for _,n in spans) == size and size <= 8192
        done = 0
        while done < size:
            n = min(8192, size-done)
            physical = sum(ceil(z/64)*64 for _,z in spans) if spans else ceil(n/64)*64
            native=self.hw.get('dma_backend')=='beat_analytic'
            if native:
                assert self.sram.beat is not None
                yield from self.sim.h.fetch(tag,address+done,physical,self.sram.regions[region],
                    offset+done,tag,write=write,spans=spans)
            else:
                slot = yield from self.slots.acquire()
                if write:
                    yield from self.sram.transfer(region, offset+done, n, False, tag+'_source')
                start = max(self.sim.now, self.bus_free)
                self.bus_free = start + physical/self.hw['dram_GBs']
                # B/GBps is ns. Initial latency is per coalesced transaction.
                end = self.bus_free + self.hw['dram_latency_ns']
                yield from self.sim.delay(end-self.sim.now)
                if not write:
                    yield from self.sram.transfer(region, offset+done, n, True, tag+'_land')
            kind = 'write' if write else 'read'
            row = self.by_tag.setdefault(tag, Counter())
            row[kind+'_logical_bytes'] += n; row[kind+'_physical_bytes'] += physical
            self.count[kind+'_logical_bytes'] += n
            self.count[kind+'_physical_bytes'] += physical
            self.count['scatter_segments'] += len(spans) if spans else 1
            self.count['ranges'] += 1
            for a,z in (spans or [(address+done,n)]):
                self.address_digest = (self.address_digest*1000003 + a + z) % (1<<64)
            if not native:
                self.slots.release(slot)
            done += n


class Engine:
    def __init__(self, sim, name, units):
        self.sim, self.name = sim, name
        self.pool = Pool(sim, units, name); self.busy_ns = 0.; self.actions = Counter()

    def execute(self, cycles, action, count=1):
        ident = yield from self.pool.acquire()
        duration = ceil(cycles)*self.sim.period
        yield from self.sim.delay(duration)
        self.busy_ns += duration; self.actions[action] += count
        self.pool.release(ident)


def parallel(sim, generators):
    pending = [len(generators)]; done = sim.signal()
    if not pending[0]:
        return
    def wrap(gen):
        yield from gen
        pending[0] -= 1
        if not pending[0]:
            done.set()
    for gen in generators:
        sim.spawn(wrap(gen))
    yield done
