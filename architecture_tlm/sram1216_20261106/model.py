"""Actual smaller banks and translated actor addresses, not capacity-only pricing.

The existing actors retain semantic/legacy offsets. This explicit address decoder
maps them BEFORE BeatSRAM's bounds check, arbitration and physical bank service.
No data buffering or free ports are introduced by the decoder. Mapping records
are simulator metadata, not additional on-chip storage. Only the K128/S64
sampled Ising path is supported; dense/long-context paths must not use this map.
"""
from collections import Counter
import hashlib, math
from types import MethodType
from architecture_tlm.ffn_sram_batch_20261106.model import make_model as batch_model
from architecture_tlm.ordinary_mapping_20261106.model import install as ordinary_install

CASES = ('control1952', 'attention1440', 'compact1216', 'compact1184', 'compact1056', 'compact1088bw')

def vector_address(offset, size):
    # Fixed live objects: low activation/codes32KiB; metadata32KiB; residual5KiB;
    # eight independent four-Q snapshots1KiB each. Permanent ranges are disjoint.
    ranges = [(0,32768,0), (65536,98304,65536), (131072,136192,32768)]
    ranges += [(196608+g*6144+5120,196608+(g+1)*6144,49152+g*1024) for g in range(8)]
    for first, end, target in ranges:
        if first <= offset and offset+size <= end:
            return target+offset-first
    raise ValueError('unmapped activation live object: %d+%d' % (offset,size))

def attention_address(offset, size, tag, capacity=65536):
    # Append/transpose scratch and later selectedK/V reuse0..32KiB in sequence.
    if tag.startswith(('K_append','V_append','K_block_for_transpose','K_transpose','K_feature_append')):
        source, target, limit = 114688, 0, 8192
    elif tag.startswith('coarse_K'):
        source, target, limit = 0, 0, 16384
    elif tag.startswith('coarse_score'):
        source, target, limit = 32768, 16384, 32768
    elif tag.startswith('selected_K'):
        source, target, limit = 0, 0, 32768
    elif tag.startswith(('selected_scores','sampler_score_input')):
        source, target, limit = 16384, 32768, 2048
    elif tag.startswith('sample_V'):
        source, target, limit = 65536, 0, 32768
    elif tag.startswith(('attention_output','attention_gather')):
        source, target, limit = 122880, (48128 if capacity==49152 else 61440), 1024
    else:
        raise ValueError('unmapped Attention role '+tag)
    if not source <= offset or offset+size > source+limit:
        raise ValueError('Attention role outside declared span: '+tag)
    dest=target+offset-source
    if dest<0 or dest+size>capacity:raise ValueError('Attention object exceeds physical capacity: '+tag)
    return dest

def repack(hub, model, front_banks=None):
    mem = hub.mem
    assert not hub.now and not hub.events and not hub.descriptors and not mem.queue
    rows = sorted(mem.regions.values(),key=lambda r:r.base)
    front = [r for r in rows if not r.name.startswith('Attention_KVgroup')]
    att = model.att
    minimum_front = math.ceil(sum(r.size for r in front)/4096)
    front_count = minimum_front if front_banks is None else front_banks
    assert front_count>=minimum_front
    total = front_count+sum(r.size//4096 for r in att)
    allocation, physical, cursor = [0]*total, {}, 0
    for r in front:
        words = r.size//16
        r.banks = tuple((cursor+j)%front_count for j in range(front_count))
        physical[r.name] = {}
        for j,b in enumerate(r.banks):
            physical[r.name][b] = allocation[b]//16
            allocation[b] += (words//front_count+(j<words%front_count))*16
        cursor = (cursor+words)%front_count
    next_bank = front_count
    for r in att:
        count = r.size//4096
        r.banks = tuple(range(next_bank,next_bank+count))
        physical[r.name] = {b:0 for b in r.banks}
        for b in r.banks: allocation[b] = 4096
        next_bank += count
    top = 0
    for r in rows: r.base,top = top,top+r.size
    assert sum(allocation)==top and all(n<=4096 for n in allocation)
    capacity=total*4096
    mem.capacity,mem.nbank,mem.top = capacity,total,top
    mem.bank_depths,mem.bank_allocated = (4096,)*total,allocation
    hub.return_banks = front_count
    model.sram_bank_row_bases = physical
    return dict(capacity_KiB=capacity//1024,physical_4KiB_banks=total,
        front_banks=front_count,attention_banks=total-front_count,
        bank_word_bytes=16,bank_clock_MHz=100,ports='1RW',unallocated_bytes=capacity-top,
        macro_area55_mm2=total*.03322622205*.81,
        regions={r.name:r.size for r in rows})

def make_model(backend, configuration='compact1216', **kwargs):
    if configuration not in CASES: raise ValueError(configuration)
    if kwargs.get('mode') != 'ising' or kwargs.get('ffn') != 'sc':
        raise ValueError('K128/S64 sampled Attention + common SC FFN only')
    h,m = batch_model(backend,configuration='b96s96',**kwargs)
    if m.N!=2048 or m.model['hidden']!=2560 or m.model['kv_heads']!=8:
        raise ValueError('this candidate is scoped to Qwen3-4B B1/2K')
    ordinary_install(m,lanes=640,k_parallel=8,early_refill=True)
    compact_att = configuration != 'control1952'
    compact_vec = configuration in ('compact1216','compact1184','compact1056','compact1088bw')
    if compact_att:
        for r in m.att: r.size = 49152 if configuration in ('compact1056','compact1088bw') else 65536
    if compact_vec:
        for r in m.weight: r.size = 81920
        m.vector.size = 131072
    reclaim_dma=configuration in ('compact1184','compact1056','compact1088bw')
    if reclaim_dma:
        assert not h.buffered and h.response is h.mem.regions['DMA_return_FIFO']
        assert h.response.size==32768
        del h.mem.regions['DMA_return_FIFO'];h.response=None
    memory = repack(h,m,front_banks=176 if configuration=='compact1088bw' else None)
    expected = {'control1952':1952,'attention1440':1440,'compact1216':1216,
                'compact1184':1184,'compact1056':1056,'compact1088bw':1088}[configuration]
    assert memory['capacity_KiB'] == expected
    memory.update(return_SRAM_reservation_KiB=0 if reclaim_dma else 32,
                  attention_group_KiB=m.att[0].size//1024,
                  ordinary_weight_slot_KiB=m.weight[0].size//1024)
    m.ordinary_pool_contract['weight_slot_capacity_bytes'] = m.weight[0].size
    # Translating submit covers direct queued reads, h.transfer and DMA fill/
    # source beats. A wrapper around h.transfer alone would miss direct reads.
    original = h.mem.submit
    counts,high,active = Counter(),{},{}
    digest = hashlib.sha256()
    def submit(region, offset, size, write, tag, callback):
        legacy = offset
        if compact_vec and region is m.vector: offset=vector_address(offset,size)
        if compact_att and region in m.att: offset=attention_address(offset,size,tag,region.size)
        if offset<0 or offset+size>region.size: raise ValueError('physical bounds '+tag)
        high[region.name]=max(high.get(region.name,0),offset+size)
        counts[tag]+=1
        digest.update(('%s|%d|%d|%d|%s\n'%(region.name,legacy,offset,size,tag)).encode())
        # Detect address reuse while an older conflicting transaction is live.
        ident = (id(region),len(active.get(id(region),{})))
        pending = active.setdefault(id(region),{})
        key = object()
        if compact_att and region in m.att:
            for a,b,w,t in pending.values():
                if max(a,offset)<min(b,offset+size) and (write or w):
                    raise AssertionError('live Attention alias: '+t+' / '+tag)
        pending[key]=(offset,offset+size,write,tag)
        def done():
            del pending[key]
            callback()
        original(region,offset,size,write,tag,done)
    h.mem.submit = submit
    parent = m.run
    def run(self):
        result=parent()
        assert not any(active.values()), 'undrained mapped transactions'
        result['sram1216_contract']=dict(configuration=configuration,memory=memory,
            compact_attention=compact_att,compact_activation=compact_vec,
            address_decoder='fixed base additions and semantic mode selects; not a data buffer',
            accessed_highwater_bytes=high,submit_counts=dict(counts),address_trace_sha256=digest.hexdigest(),
            Attention_V_cache_entries_per_group=128,coarse_score_bytes=16384,
            return_SRAM_reclaimed=reclaim_dma,
            output_offset_bytes=48128 if configuration in ('compact1056','compact1088bw') else 61440,
            coarse_score_contract='same old16KiB transactions;32KiB address space reserved',
            timing='actual reduced-bank beat service; no retained phantom ports',
            PPA_delta='decoder and interconnect not separately characterized',
            numeric='same existing actors and input indices; no new PPL')
        return result
    m.run=MethodType(run,m)
    m.compact_memory=memory
    return h,m
