"""Hardware contracts and bounded event records; no numerical stream replay."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math


def physical_bytes(offset, size, word=16):
    return (math.ceil((offset+size)/word)-offset//word)*word


class Events:
    def __init__(self, hub, period, path=None, limit=100000):
        self.h = hub; self.period = period; self.counts = Counter(); self.bytes = Counter()
        self.wait_ns = Counter(); self.path = Path(path) if path else None
        self.limit = limit; self.written = 0; self.omitted = 0; self.digest = hashlib.sha256()
        self.file = None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.file = self.path.open('xb')
    def emit(self, event, tile=None, core=None, **details):
        self.counts[event] += 1; self.bytes[event] += details.get('bytes', 0)
        if not self.file: return
        if self.written >= self.limit:
            self.omitted += 1; return
        t = self.h.now; c = t/self.period
        r = dict(event=event, ns=t, cycle=round(c) if abs(c-round(c))<1e-6 else None,
            cycle_at_or_after=math.ceil(c-1e-7), core=core)
        if tile:
            r.update(transaction_id=tile['transaction_id'], command=tile['command'],
                layer=tile['layer'], mode=tile['mode'], out_group=tile['out_group'], k=tile['k'])
        r.update(details)
        b = (json.dumps(r, sort_keys=True, separators=(',',':'))+'\n').encode()
        self.file.write(b); self.digest.update(b); self.written += 1
    def wait(self, reason, elapsed): self.wait_ns[reason] += elapsed
    def report(self):
        if self.file: self.file.flush()
        return dict(events=dict(self.counts), event_bytes=dict(self.bytes), wait_ns=dict(self.wait_ns),
            trace_enabled=bool(self.path), trace_records=self.written, trace_omitted=self.omitted,
            trace_complete=not self.omitted if self.path else None,
            trace_sha256=self.digest.hexdigest() if self.path else None)
    def close(self):
        if self.file: self.file.close(); self.file = None


def tile_identity(m, layer, mode, out, k, blocks):
    command = getattr(m, 'alignment_command', 0)
    return dict(command=command, layer=layer, mode=mode, out_group=out, k=k,
        reference_ordinal=out*blocks+k,
        transaction_id='%s/L%d/%s/O%d/K%d' % (command,layer,mode,out,k))


def cycles(m, number, name):
    """Current-clock cycles -> ns ONCE; bypass the legacy10ns argument ABI."""
    ns = number*m.alignment['period_ns']
    m.compute[name] += ns
    yield from m.h.delay(ns)


def transfer(m, region, offset, size, write, tag, tile=None, core=None):
    start = m.h.now; e = m.alignment_events
    words = physical_bytes(offset, size)
    e.emit('memory_request', tile, core, bytes=size, physical_bytes=words,
        resource=region.name, offset=offset, write=write, reason=tag)
    yield from m.h.transfer(region, offset, size, write, tag)
    e.emit('memory_complete', tile, core, bytes=size, physical_bytes=words,
        resource=region.name, offset=offset, write=write, reason=tag)
    e.wait(tag, m.h.now-start)


class ResultSlots:
    def __init__(self, cores, cfg, events):
        self.cfg = cfg; self.events = events
        self.rows = [[None]*cfg['slots_per_core'] for _ in range(cores)]
        self.peak = [0]*cores
    def available(self, core): return any(x is None for x in self.rows[core])
    def reserve(self, core, tile):
        slot = self.rows[core].index(None)
        self.rows[core][slot] = dict(tile=tile, state='reserved')
        self.peak[core] = max(self.peak[core], sum(x is not None for x in self.rows[core]))
        self.events.emit('result_reserve', tile, core, resource='result_slot', slot=slot)
        return slot
    def capture(self, core, slot):
        r = self.rows[core][slot]; assert r['state']=='reserved'; r['state']='captured'
        self.events.emit('result_capture', r['tile'], core, resource='result_slot', slot=slot,
            payload_bits=self.cfg['columns']*self.cfg['stored_count_bits'],
            metadata_bits=self.cfg['metadata_bits'])
    def read(self, core, slot):
        r = self.rows[core][slot]; assert r['state']=='captured'; r['state']='reading'
        return r['tile']
    def release(self, core, slot):
        r = self.rows[core][slot]; assert r['state']=='reading'
        self.events.emit('result_slot_release', r['tile'], core, resource='result_slot', slot=slot)
        self.rows[core][slot] = None
    def report(self):
        n = len(self.rows); c = self.cfg
        return dict(cores=n, slots_per_core=c['slots_per_core'], peak_used_per_core=self.peak,
            live_slots=sum(x is not None for row in self.rows for x in row),
            payload_bits=n*c['slots_per_core']*c['columns']*c['stored_count_bits'],
            metadata_bits=n*c['slots_per_core']*c['metadata_bits'],
            cost_owner=c['storage_cost_owner'], duplicate_storage_charge=False)


class RNGAssignments:
    def __init__(self, m):
        self.m=m; self.free=0.; self.count=0
    def request(self, tile, core):
        from architecture_tlm.unified_v6.shared_memory import Signal
        m=self.m; cfg=m.alignment['rng_assignment']; p=m.alignment['period_ns']; e=m.alignment_events
        start=max(math.ceil(m.h.now/p-1e-7)*p,self.free)
        self.free=start+cfg['issue_II_cycles']*p; done=Signal(); self.count+=1
        token=dict(reference_ordinal=tile['reference_ordinal'],
            stream_count=cfg[tile['mode']+'_streams'],
            start_steps=tile['reference_ordinal']*m.p28_cim_binding['FFN_core']['modes'][tile['mode']]['samples'])
        e.emit('rng_state_request',tile,core,resource='shared_state_provider',**token)
        def ready():
            e.emit('rng_state_ready',tile,core,resource='shared_state_provider',**token);done.set()
        m.h.later(start+cfg['latency_cycles']*p,ready)
        return done


def install(m, contract, trace_path=None, trace_limit=100000):
    c=contract; r=c['result']; state=c['state']; d=c['DMA']
    assert c['period_ns']==m.compute_period_ns==4
    assert state['ports']==m.state_ports and state['lanes']*state['packet_beats']==r['columns']==128
    assert 64*127*max(x['samples'] for x in m.p28_cim_binding['FFN_core']['modes'].values()) < 2**(r['stored_count_bits']-1)
    assert d['shared_payload_bytes']==m.h.response_bytes and d['outstanding_limit']==m.h.credit
    assert 256*d['header_bits_per_beat']//8+d['descriptor_slots']*d['descriptor_bytes']==4096
    m.alignment=c; m.alignment_command=0
    m.alignment_events=Events(m.h,c['period_ns'],trace_path,trace_limit)
    m.result_slots=ResultSlots(m.common_cores,r,m.alignment_events)
    m.rng_assignments=RNGAssignments(m); m.cim_tiles=[None]*m.common_cores; m.cim_rng_ready=[None]*m.common_cores
    h=m.h; original_dma=h.dma
    def dma(*args,**kw):
        if len(h.descriptors)>=d['descriptor_slots']:
            raise RuntimeError('descriptor capacity exceeded;implement producer backpressure before accepting this workload')
        item=original_dma(*args,**kw)
        if item:
            m.alignment_events.emit('dma_descriptor',resource='shared_DMA',descriptor=item.id,
                bytes=item.size,owner=item.owner,target=item.region.name,target_offset=item.offset)
        return item
    h.dma=dma
    if trace_path:
        old_response=h._response
        def response(reply):
            desc,offset=h.pending[reply['id']]
            core=int(desc.region.name[8:]) if desc.region.name.startswith('CIM_core') else None
            tile=m.cim_tiles[core] if core is not None else None
            m.alignment_events.emit('dma_return',tile,core,resource='shared_DMA',descriptor=desc.id,
                bytes=64,target=desc.region.name,target_offset=desc.offset+offset,request_id=reply['id'])
            old_response(reply)
            assert len(h.pending)*64+h.return_occupied<=h.response_bytes
        h._response=response
    if trace_path or d.get('test_block_core') is not None:
        original_submit=h.mem.submit
        def submit(region,offset,size,write,tag,callback):
            if write and tag.endswith('_fill'):
                core=int(region.name[8:]) if region.name.startswith('CIM_core') else None
                tile=m.cim_tiles[core] if core is not None else None
                def complete():
                    m.alignment_events.emit('dma_landed',tile,core,resource=region.name,bytes=size,offset=offset,
                        first_bank=(offset//16)%16 if region.name.startswith('CIM_core') else None,
                        first_row=offset//256 if region.name.startswith('CIM_core') else None)
                    callback()
                if core==d.get('test_block_core') and h.now<d['test_block_until_cycle']*c['period_ns']:
                    def later(): original_submit(region,offset,size,write,tag,complete)
                    h.later(d['test_block_until_cycle']*c['period_ns'],later)
                    m.alignment_events.emit('dma_target_wait',tile,core,resource=region.name,
                        until_ns=d['test_block_until_cycle']*c['period_ns'])
                    return
                return original_submit(region,offset,size,write,tag,complete)
            return original_submit(region,offset,size,write,tag,callback)
        h.mem.submit=submit


def report(m):
    h=m.h; c=m.alignment; r=h.report(); bits=m.common_cores*(640+1024+7+6+8+2)
    assert r['counts']['peak_outstanding']<=256 and r['counts']['peak_response_bytes']<=16384
    assert r['counts']['peak_descriptors']<=c['DMA']['descriptor_slots']
    assert m.result_slots.report()['live_slots']==0
    return dict(contract=c,events=m.alignment_events.report(),results=m.result_slots.report(),
        input_cache_storage_bits=bits,input_cache_cost_owner=c['result']['input_cache_cost_owner'],
        rng_state_assignments=m.rng_assignments.count,
        RNG_numeric_streams_replayed=False,
        DMA=dict(shared_payload_bytes=h.response_bytes,peak_descriptors=r['counts']['peak_descriptors'],
            header_capacity_bytes=2048,descriptor_capacity_bytes=2048,
            metadata_cost_owner=c['DMA']['metadata_cost_owner'],extra_payload_bytes=0))
