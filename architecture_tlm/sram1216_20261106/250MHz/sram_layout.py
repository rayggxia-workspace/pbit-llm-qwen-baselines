"""Instance-local SRAM capacity, physical-bank and live-object decoder.

Profiles change real banks/ports before any transaction, not only area prices.
The 48KiB Attention profile reuses dead coarse-score storage for final output;
selected scores at32..34KiB remain disjoint from V0..32KiB and output47..48KiB.
"""
from collections import Counter
from types import MethodType
import hashlib
from architecture_tlm.sram1216_20261106.model import (
    batch_model, ordinary_install, repack, vector_address,
    attention_address as legacy_attention_address)

PROFILES = {
    'reference1216': (80, 64, True, 1216),
    'compact1088': (32, 64, False, 1088),
    'compact960': (32, 48, False, 960),
}

def attention_address(offset, size, tag, capacity):
    if capacity not in (49152, 65536):
        raise ValueError('unsupported Attention capacity')
    dest = legacy_attention_address(offset, size, tag)
    if capacity == 49152 and tag.startswith(('attention_output', 'attention_gather')):
        dest -= 61440 - 48128
    if dest < 0 or dest + size > capacity:
        raise ValueError('Attention live object exceeds real capacity: '+tag)
    return dest

def make_model(backend, profile='compact960', **kwargs):
    if profile not in PROFILES:
        raise ValueError(profile)
    if kwargs.get('mode') != 'ising' or kwargs.get('ffn') != 'sc':
        raise ValueError('layout is only validated for sampled K128/S64 plus SC FFN')
    weight_kib, attention_kib, keep_dma, expected = PROFILES[profile]
    h,m = batch_model(backend, configuration='b96s96', **kwargs)
    if m.N != 2048 or m.model['hidden'] != 2560 or m.model['kv_heads'] != 8:
        raise ValueError('layout is scoped to Qwen3-4B B1/N2048')
    ordinary_install(m, lanes=640, k_parallel=8, early_refill=True)
    for r in m.att: r.size = attention_kib*1024
    for r in m.weight: r.size = weight_kib*1024
    m.vector.size = 131072
    # DMA currently captures returned data directly in the finite register
    # holding slots; it never stages through this historical SRAM region.
    if not keep_dma:
        assert not h.buffered and h.response is h.mem.regions['DMA_return_FIFO']
        assert h.response.size == 32768
        del h.mem.regions['DMA_return_FIFO']
        h.response = None
    memory = repack(h,m)
    assert memory['capacity_KiB'] == expected
    memory.update(profile=profile, bank_clock_MHz=250,
                  return_SRAM_reservation_KiB=32 if keep_dma else 0,
                  ordinary_weight_slot_KiB=weight_kib,
                  attention_group_KiB=attention_kib)
    m.ordinary_pool_contract['weight_slot_capacity_bytes'] = m.weight[0].size
    original = h.mem.submit
    counts, high, active = Counter(), {}, {}
    digest = hashlib.sha256()
    def submit(region, offset, size, write, tag, callback):
        legacy = offset
        if region is m.vector: offset = vector_address(offset,size)
        if region in m.att: offset = attention_address(offset,size,tag,region.size)
        if offset < 0 or offset+size > region.size:
            raise ValueError('physical SRAM bounds: '+tag)
        high[region.name] = max(high.get(region.name,0),offset+size)
        counts[tag] += 1
        digest.update(('%s|%d|%d|%d|%s\n' % (region.name,legacy,offset,size,tag)).encode())
        pending = active.setdefault(id(region),{})
        if region in m.att:
            for a,b,w,t in pending.values():
                if max(a,offset) < min(b,offset+size) and (write or w):
                    raise AssertionError('live Attention alias: '+t+' / '+tag)
        key = object()
        pending[key] = (offset,offset+size,write,tag)
        def done():
            del pending[key]
            callback()
        original(region,offset,size,write,tag,done)
    h.mem.submit = submit
    parent = m.run
    def run(self):
        result = parent()
        assert not any(active.values()), 'undrained SRAM requests'
        result['sram_capacity_contract'] = dict(profile=profile,memory=memory,
            accessed_highwater_bytes=high,submit_counts=dict(counts),
            address_trace_sha256=digest.hexdigest(),
            decoder='fixed role base additions before real bounds/bank arbitration',
            Attention_V_cache_entries_per_group=128,
            lifetimes='append -> coarse K+score -> selected K+score -> score+V -> output; output retained until O gather',
            coarse_score_reserved_bytes=32768,selected_score_bytes=2048,
            output_offset_bytes=48128 if attention_kib==48 else 61440,
            numeric='unchanged actors and captured sample addresses; no model PPL',
            PPA='actual macro count; new decoder/interconnect not characterized')
        # Old result consumers can still find the current memory under this
        # historical field; the explicit profile above is authoritative.
        result['sram1216_contract'] = result['sram_capacity_contract']
        return result
    m.run = MethodType(run,m)
    m.compact_memory = memory
    return h,m
