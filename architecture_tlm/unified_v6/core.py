"""Resource reservations, local random-service interface, and bounded storage.

All times are simulated nanoseconds. Reservations are FIFO in submission order;
there is no implicit out-of-order scheduler or free overlap. Unknown energy
prices remain unknown, and a random-service request never allocates SRAM.
"""
import hashlib
import json
import math
from collections import Counter, defaultdict


def ceildiv(a, b):
    return (a + b - 1) // b


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Ledger:
    def __init__(self, prices=None):
        self.prices = prices or {}
        self.actions = Counter()
        self.energy = defaultdict(float)
        self.missing = Counter()
        self.action_energy = defaultdict(Counter)

    def action(self, name, count, category, price=None):
        if count < 0 or not math.isfinite(count):
            raise ValueError('invalid action count: ' + name)
        self.actions[name] += count
        value = self.prices.get(name) if price is None else price
        if count and value is None:
            self.missing[name] += count
        elif count:
            if value < 0 or not math.isfinite(value):
                raise ValueError('invalid energy price: ' + name)
            charge = count * value * 1e-12
            self.energy[category] += charge
            self.action_energy[name][category] += charge


    def replace_action_energy(self, name, energy_J, category):
        if energy_J < 0 or not math.isfinite(energy_J):
            raise ValueError('invalid replacement action energy')
        previous = dict(self.action_energy[name])
        for old_category, amount in previous.items():
            self.energy[old_category] -= amount
            if abs(self.energy[old_category]) < 1e-18:
                self.energy[old_category] = 0.
        self.energy[category] += energy_J
        self.action_energy[name] = Counter({category: energy_J})
        self.missing.pop(name, None)
        return previous


class Scheduler:
    def __init__(self, keep=2000):
        self.free = defaultdict(float)
        self.busy = defaultdict(float)
        self.wait = defaultdict(float)
        self.events = []
        self.keep = keep
        self.count = 0
        self.by_stage = defaultdict(float)

    def reserve(self, stage, ready, duration, resources, period=0., **detail):
        if ready < 0 or duration < 0 or not math.isfinite(ready + duration):
            raise ValueError('invalid time')
        resources = tuple(sorted(set(resources)))
        start = max([ready] + [self.free[r] for r in resources])
        if period:
            start = math.ceil(start / period - 1e-10) * period
        done = start + duration
        for r in resources:
            self.free[r] = done
            self.busy[r] += duration
        self.wait[stage] += start - ready
        self.by_stage[stage] += duration
        self.count += 1
        if len(self.events) < self.keep:
            self.events.append(dict(id=self.count, stage=stage, ready_ns=ready,
                start_ns=start, end_ns=done, resources=resources, **detail))
        return done

    def end(self):
        return max([0.] + list(self.free.values()))


class Arena:
    """Static named regions; ping-pong owners retain slots until consumers finish."""
    def __init__(self, capacity):
        self.capacity = capacity
        self.regions = {}
        self.peak = 0

    def allocate(self, name, size, align=64):
        if name in self.regions or size <= 0:
            raise ValueError('invalid allocation')
        start = ceildiv(self.peak, align) * align
        end = start + size
        if end > self.capacity:
            raise ValueError('SRAM capacity exceeded by ' + name)
        self.regions[name] = dict(address=start, bytes=size)
        self.peak = end
        return start


class LocalRandomService:
    """Backend contract only: no random-word array, probability copy or RNG FIFO.

Replay restores a local stream/checkpoint, not a stored sequence. The backend
must eventually prove this contract (Issue95); statistical independence and
PRNG period/seed quality are not established by this timing interface.
"""
    def __init__(self, cfg, scheduler, ledger, period):
        self.cfg, self.s, self.e, self.period = cfg, scheduler, ledger, period
        self.requests = Counter()
        self.demands = Counter()
        self.seeded = set()
        self.last_frame = {}
        self.max_parallel = Counter()

    def request(self, site, ready, words, width, parallel_lanes, semantic,
                frame, replay=False, repeat=1):
        if min(words, width, parallel_lanes, repeat) < 0 or not parallel_lanes:
            raise ValueError('invalid random request')
        self.requests[semantic] += repeat
        bits = words * width * parallel_lanes * repeat
        self.demands['uniform_bits'] += bits
        self.demands['uniform_words'] += words * parallel_lanes * repeat
        self.max_parallel[site] = max(self.max_parallel[site], parallel_lanes)
        setup = 0
        if site not in self.seeded:
            self.seeded.add(site)
            self.demands['startup_seed_requests'] += 1
            self.e.action('rng_seed', 1, 'random')
            setup += self.cfg['startup_cycles']
        if self.last_frame.get(site) != frame:
            self.last_frame[site] = frame
            self.demands['new_frame_requests'] += repeat
            self.e.action('rng_frame', repeat, 'random')
            setup += self.cfg['frame_cycles']
        if replay:
            self.demands['replay_restore_requests'] += repeat
            self.e.action('rng_restore', repeat, 'random')
            setup += self.cfg['restore_cycles']
        self.e.action('rng_uniform_bit', bits, 'random')
        # Sources are adjacent and provisioned for the requested lane count.
        # Streaming production is paced with the consumer; only setup is here.
        return self.s.reserve('rng_setup', ready, setup*self.period,
            ('rng_control:' + site,), self.period, site=site, semantic=semantic,
            random_stream_storage_bytes=0)

    def embedded(self, site, actions, source_cycles):
        """Sampling FSM owns these cycles; do not charge a second timed service."""
        biased = actions.get('biased_bit_draws', 0)
        fair = actions.get('fair_bit_draws', 0)
        self.demands['biased_response_bits'] += biased
        self.demands['fair_bits'] += fair
        self.demands['embedded_source_cycles'] += source_cycles
        self.e.action('rng_biased_response', biased, 'random')
        self.e.action('rng_uniform_bit', fair, 'random')
        self.requests['embedded_independent_biased_response'] += 1

    def report(self):
        return dict(backend='local_prng_interface', random_stream_SRAM_bytes=0,
            extra_probability_copy_bytes=0, extra_random_FIFO_bytes=0,
            source_timing='provisioned local lanes; configured startup/frame/restore, no global distribution',
            demands=dict(self.demands), requests=dict(self.requests),
            max_parallel_lanes=dict(self.max_parallel),
            seed_policy='one startup request/site; new logical frame IDs; replay restores same frame; backend reseed policy reserved',
            deferred=['PRNG/seed architecture and actual state area', 'finite source rate and backpressure',
                'independence, correlation and finite-resolution probability response',
                'local PRNG+probability conversion/comparison or later physical p-bit implementation'],
            independence='FFN one word shared by 64 inputs; Attention biased candidates require separate fresh responses')


class SRAM:
    """Bank-word accounting and conservative descriptor reservations.

One descriptor reserves the addressed banks and common fabric until drained.
This retains conflicts but does not implement an optimized bank arbiter.
"""
    def __init__(self, cfg, spec, scheduler, ledger):
        self.c, self.spec, self.s, self.e = cfg, spec, scheduler, ledger
        self.period = 1e9 / cfg['clock_hz']
        self.word = cfg['word_bytes']
        self.capacity = cfg['capacity_bytes']
        self.traffic = Counter()
        self.regions = None
        macro_bytes = cfg['macro_depth'] * self.word
        self.macros = ceildiv(self.capacity, cfg['banks']*macro_bytes)*cfg['banks']
        self.physical_capacity = self.macros * macro_bytes
        if self.period < max(spec['read_cycle_ns'], spec['write_cycle_ns']):
            raise ValueError('SRAM clock violates calibrated macro minimum period')

    def transfer(self, ready, address, size, write, tag):
        if size == 0:
            return ready
        if address < 0 or address + size > self.capacity:
            raise ValueError('SRAM request outside configured capacity')
        if self.regions is not None and not any(r['address']<=address and address+size<=r['address']+r['bytes'] for r in self.regions.values()):
            raise ValueError('SRAM transfer crosses a live tensor region: '+tag)
        lo, hi = address//self.word, ceildiv(address+size, self.word)
        counts = [0]*self.c['banks']
        # Prefix residues count words without iterating through a large tensor.
        for b in range(self.c['banks']):
            counts[b] = (hi + self.c['banks']-1-b)//self.c['banks'] - (lo + self.c['banks']-1-b)//self.c['banks']
        active = ['sram_bank:'+str(b) for b, n in enumerate(counts) if n]
        nwords = sum(counts)
        access = self.spec['write_access_ns' if write else 'read_access_ns']
        port = (max(counts)-1)*self.period + access
        duration = max(port, nwords*self.word/self.c['fabric_GBs']) + self.c['cdc_ns']
        done = self.s.reserve('sram_'+tag, ready, duration,
            active+['sram_fabric'], self.period, write=write, bytes=size,
            physical_bytes=nwords*self.word, bank_words=counts)
        kind = 'write' if write else 'read'
        self.traffic[kind+'_logical_bytes'] += size
        self.traffic[kind+'_physical_bytes'] += nwords*self.word
        self.traffic[kind+'_words'] += nwords
        self.e.action('sram_'+kind, nwords, 'SRAM_internal',
            self.spec[kind+'_internal_pJ'])
        return done

    def report(self, end_ns):
        leak = self.macros*self.spec['ce_off_leakage_W']*end_ns*1e-9
        self.e.energy['SRAM_leakage'] += leak
        return dict(traffic=dict(self.traffic), calibrated_macro=self.spec,
            banks=self.c['banks'], macros=self.macros, configured_bytes=self.capacity,
            word_bytes=self.word,clock_hz=self.c['clock_hz'],
            bank_peak_GBs=self.c['banks']*self.word*self.c['clock_hz']/1e9,
            fabric_combined_read_write_GBs=self.c['fabric_GBs'],
            macros_per_bank=self.macros//self.c['banks'],
            physical_bytes=self.physical_capacity, area_mm2=self.macros*self.spec['area_mm2'],
            leakage_J=leak, scheduling='blocking descriptor per addressed banks + shared fabric',
            exclusions=['wrapper/mux/CTS', 'verified CDC implementation', 'optimized bank interleaving'])

    def serial_histogram(self, ready, base, indices, core_period):
        """Dependency-safe RMW per address; collapse its deterministic schedule.

        No optimistic simultaneous reads of a repeatedly updated counter.
        Detailed pipeline forwarding/merging is a possible later optimization.
        """
        if not indices:
            return ready
        addresses = [base+i*4 for i in indices]
        if min(addresses)<0 or max(addresses)+4>self.capacity:
            raise ValueError('histogram bounds')
        banks = sorted(set((a//self.word)%self.c['banks'] for a in addresses))
        per_update = (2*self.period+self.spec['read_access_ns']+
            self.spec['write_access_ns']+2*self.c['cdc_ns']+core_period)
        done = self.s.reserve('histogram_serial_RMW', ready, len(indices)*per_update,
            ['sram_bank:'+str(b) for b in banks]+['sram_fabric','vector'],self.period,
            updates=len(indices), implementation='one dependency-safe RMW/update')
        for kind in ('read','write'):
            self.traffic[kind+'_logical_bytes'] += len(indices)*4
            self.traffic[kind+'_physical_bytes'] += len(indices)*self.word
            self.traffic[kind+'_words'] += len(indices)
            self.e.action('sram_'+kind,len(indices),'SRAM_internal',self.spec[kind+'_internal_pJ'])
        self.e.action('vector_op',len(indices),'digital')
        return done


class AddressMap:
    def __init__(self):
        self.regions, self.total_bytes = {}, 65536

    def allocate(self, name, size):
        base = ceildiv(self.total_bytes, 4096)*4096
        allocated = ceildiv(size, 4096)*4096
        self.regions[name] = dict(base=base, logical_bytes=size, allocated_bytes=allocated)
        self.total_bytes = base + allocated

    def address(self, name, offset, size):
        r = self.regions[name]
        if offset < 0 or size < 0 or offset+size > r['logical_bytes']:
            raise ValueError('DRAM tensor bounds: '+name)
        return r['base']+offset


class DRAM:
    def __init__(self, cfg, layout, scheduler, ledger):
        self.c, self.layout, self.s, self.e = cfg, layout, scheduler, ledger
        self.traffic = Counter()
        self.bridge = None
        self.sg = bool(cfg.get('scatter_gather',False))
        self.sg_max_spans = cfg.get('sg_max_spans',256)
        if not 1 <= self.sg_max_spans <= 256:raise ValueError('invalid SG capacity')
        if cfg.get('descriptor_span_ns',0) < 0:raise ValueError('negative descriptor delay')
        self.bridge_energy, self.bridge_traffic = defaultdict(float), defaultdict(int)
        if cfg['backend'] == 'dramsys':
            from dramsys_backend import DRAMSysExternal
            self.bridge = DRAMSysExternal(cfg, self.bridge_energy, self.bridge_traffic, layout)
        elif cfg['backend'] != 'link':
            raise ValueError('unknown DRAM backend')

    def ranges(self, ready, ranges, write, kind):
        burst = self.c['burst_bytes']
        aligned = set()
        logical = 0
        for address, size in ranges:
            if address < 0 or size <= 0:
                raise ValueError('invalid DRAM range')
            logical += size
            aligned.update(range(address//burst*burst, ceildiv(address+size, burst)*burst, burst))
        addresses = sorted(aligned)
        self.traffic[kind+'_logical_bytes'] += logical
        self.traffic[kind+'_physical_bytes'] += len(addresses)*burst
        self.traffic[kind+'_bursts'] += len(addresses)
        self.traffic['DMA_descriptors'] += 1
        self.e.action('dram_write' if write else 'dram_read', len(addresses)*burst,
            'DRAM_dynamic', 0 if self.bridge else None)
        t = ready
        # Finite bursts per window, each window drains; batching is explicit.
        # In DRAMSys mode contiguous runs use the bridge's bounded DMA queue.
        if self.bridge:
            runs = []
            for a in addresses:
                if runs and a == runs[-1][0]+runs[-1][1]:
                    runs[-1][1] += burst
                else:
                    runs.append([a, burst])
            self.traffic['DRAMSys_address_spans'] += len(runs)
            self.e.action('DMA_descriptor_span',len(runs),'DMA_controller')
            # Same descriptor-generation cost on digital and SC paths. New
            # policy defaults to one core cycle/span; legacy defaults remain 0.
            t = self.s.reserve('dma_descriptor',t,len(runs)*self.c.get('descriptor_span_ns',0),
                               ('dma_descriptor',),spans=len(runs))
            groups = [runs[i:i+self.sg_max_spans] for i in range(0,len(runs),self.sg_max_spans)] if self.sg else [[r] for r in runs]
            for group in groups:
                issued = max(t, self.s.free['dram_dma'])
                size = sum(n for _,n in group)
                if self.sg:
                    self.traffic['DRAMSys_scatter_requests'] += 1
                    self.traffic['SG_max_live_spans'] = max(self.traffic['SG_max_live_spans'],len(group))
                    self.e.action('DMA_descriptor_batch',1,'DMA_controller')
                    done = self.bridge.access_sg(issued,group,kind,write)
                else:
                    self.traffic['DRAMSys_contiguous_requests'] += 1
                    done = self.bridge.access(issued,size,kind,write,address=group[0][0])
                t = self.s.reserve('dram_'+kind,issued,done-issued,('dram_dma',),bytes=size,spans=len(group),scatter_gather=self.sg)
        else:
            for start in range(0, len(addresses), self.c['max_pending']):
                self.traffic['legacy_link_drain_windows'] += 1
                n = min(self.c['max_pending'], len(addresses)-start)
                issued = max(t, self.s.free['dram_dma'])
                duration = self.c['latency_ns'] + n*burst/self.c['bandwidth_GBs']
                t = self.s.reserve('dram_'+kind, issued, duration, ('dram_dma',),
                    bytes=n*burst, pending_bursts=n, write=write)
        return t

    def tensor(self, ready, name, offset, size, write=False, kind='weights'):
        return self.ranges(ready, [(self.layout.address(name, offset, size), size)], write, kind)

    def finish(self, end):
        if self.bridge:
            result = self.bridge.finish(end)
            for k, v in self.bridge_energy.items():
                self.e.energy[k] += v
            return dict(backend='dramsys', traffic=dict(self.traffic), details=result,
                scatter_gather=self.sg,sg_max_spans=self.sg_max_spans,
                descriptor_storage_bytes=self.sg_max_spans*16 if self.sg else 16,
                descriptor_span_ns=self.c.get('descriptor_span_ns',0),
                controller_PPA='unknown; descriptor generation/fetch and storage are not free',
                scheduling='one macro DMA actor; bounded rolling credit within descriptor; no async cross-descriptor claim')
        self.e.action('dram_background_ns', end, 'DRAM_background')
        return dict(backend='link_estimate_NOT_DRAMSys', traffic=dict(self.traffic),
            max_pending=self.c['max_pending'], queue_policy='bounded windows; DMA barriers',
            energy_status='configured pJ/byte + background; not a new DRAMPower run')
