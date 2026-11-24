"""Instance-local direct-CIM layout on the existing finite DMA/BeatSRAM TLM."""
from collections import Counter
from types import MethodType
import copy


def packed_byte(i, o):
    if not 0 <= i < 64 or not 0 <= o < 128:
        raise ValueError((i, o))
    return (i // 2) * 256 + (o // 8) * 16 + (i % 2) * 8 + o % 8


def install(m, config, macros, binding, finish_output):
    from architecture_tlm.unified_v6.shared_memory import Region
    from actor import common_stage, prefetch_gu
    h, mem = m.h, m.h.mem
    c = copy.deepcopy(config); n = m.common_cores
    assert c['clock_MHz'] == binding['clock_MHz'] == 250
    assert not h.now and not h.events and not mem.queue and not h.pending
    assert mem.word == 16 and h.response_bytes == c['DMA_holding_KiB'] * 1024
    assert (c['banks_per_core'], c['rows_per_bank'], c['word_bytes']) == (16, 32, 16)
    removed = [r for r in mem.regions.values() if r.name in ('CIM_ping', 'CIM_pong')]
    assert len(removed) == 2 and sum(r.size for r in removed) == 256 * 1024
    for r in removed:
        del mem.regions[r.name]
    ordinary = sorted(mem.regions.values(), key=lambda r: r.base)
    front = [r for r in ordinary if not r.name.startswith('Attention_KVgroup')]
    assert sum(r.size for r in ordinary) == c['ordinary_SRAM_KiB'] * 1024
    assert sum(r.size for r in front) == 288 * 1024
    offset, cursor = {}, 0
    for r in front:
        offset[id(r)] = cursor; cursor += r.size // 16; r.banks = tuple(range(72))
    for g, r in enumerate(m.att):
        r.banks = tuple(range(72 + 9*g, 72 + 9*(g+1)))
    cim = []
    for core in range(n):
        r = Region('CIM_core%d' % core, 0, 8192, tuple(range(144 + core*16, 160 + core*16)))
        mem.regions[r.name] = r; cim.append(r)
    def location(r, word):
        if not 0 <= word < r.size // 16:
            raise ValueError((r.name, word))
        if id(r) in offset:
            row, bank = divmod(offset[id(r)] + word, 72)
            return bank, row
        return r.banks[word % len(r.banks)], word // len(r.banks)
    depths = (4096,)*144 + (512,)*(16*n)
    seen = set(); allocation = [0]*len(depths); base = 0
    for r in sorted(mem.regions.values(), key=lambda r: r.base):
        r.base = base; base += r.size
        for word in range(r.size//16):
            bank, row = location(r, word)
            assert row < depths[bank]//16 and (bank, row) not in seen
            seen.add((bank, row)); allocation[bank] += 16
    assert allocation == list(depths) and base == (576 + 8*n)*1024
    mem.capacity = mem.top = base; mem.nbank = len(depths)
    mem.bank_depths = depths; mem.bank_allocated = allocation
    mem.physical_location = location; mem.physical_bank_resolver = lambda r, w: location(r, w)[0]
    mem.bank_activity = [Counter() for _ in depths]
    s = macros['SRAM']; s0 = copy.deepcopy(s['macro_models']['S0'])
    small = copy.deepcopy(s0); small.update(bytes=512,
        area_mm2=s0['area_mm2']/8*c['CIM_area_factor_vs_capacity_equivalent_S0'],
        idle_W=s0['idle_W']/8*c['CIM_idle_factor_vs_capacity_equivalent_S0'],
        clock_on_idle_W=s0['clock_on_idle_W']/8,
        characterization='512B capacity-scaled S0 storage proxy,not measured custom macro')
    s['macro_models'] = {'S0': s0, 'CIM512_PROXY': small}
    mem.bank_model_ids = ('S0',)*144 + ('CIM512_PROXY',)*(16*n)
    mem.bank_prices = {kind: tuple(s['macro_models'][k][kind+'_pJ_per16B'] for k in mem.bank_model_ids)
                       for kind in ('read', 'write')}
    mem.bank_idle_W = tuple(s['macro_models'][k]['idle_W'] for k in mem.bank_model_ids)
    mem.bank_area_mm2 = tuple(s['macro_models'][k]['area_mm2'] for k in mem.bank_model_ids)
    previous_report = mem.report
    def report(self, end):
        value = previous_report(end)
        value['depth_model'] = '144 ordinary4KiB banks plus %d custom512B CIM banks' % (16*n)
        value['energy_status'] = c['CIM_price_status']
        value['CIM_contract'] = dict(m.cim_contract)
        return value
    mem.report = MethodType(report, mem)
    s.update(capacity_KiB=576+8*n, bank_count=len(depths), macro_characterized=False,
        price_status='144 characterized S0 ordinary macros plus explicit custom-CIM proxy')
    h.return_banks = 72 + 16*n
    m.sram_bank_row_bases = {}
    m.cim_weight = cim; m.cim_stage = []; m.common_prefetched.clear()
    m.cim_states = ['free']*n; m.cim_compute_busy = [False]*n
    m.cim_lifetimes = []; m.cim_contract = c
    m.cim_contract.update(cores=n, capacity_KiB=576+8*n, weight_slots=n,
        ordinary_physical_banks=144, CIM_physical_banks=16*n,
        per_core_write_B_per_cycle=256, per_core_load_cycles=32,
        no_32slot_pool=True, physical_words_verified=len(seen))
    m.candidate_sram_contract = copy.deepcopy(m.cim_contract)
    m.compact_memory.update(capacity_KiB=576+8*n, front_banks=72, attention_banks=72,
        physical_macro_count=len(depths), return_SRAM_reservation_KiB=0)
    m.p28_finish_output = finish_output; m.p28_cim_binding = binding
    m._common_stage = MethodType(common_stage, m); m.prefetch_gu = MethodType(prefetch_gu, m)
    original = mem.submit
    def submit(region, off, size, write, tag, callback):
        if region in cim and write:
            core = cim.index(region)
            assert not m.cim_compute_busy[core], 'weight overwrite during compute'
            assert m.cim_states[core] == 'loading'
        return original(region, off, size, write, tag, callback)
    mem.submit = submit
    return m.cim_contract


def sram_budget(result, config):
    """Count actual physical bank actions; ordinary price and CIM proxy separate."""
    s = result['SRAM']; cards = config['macro_models']; wall = result['time_ns']
    area = idle = dyn = cim = 0.; writes = 0
    for name, a in zip(s['bank_model_ids'], s['bank_activity']):
        c = cards[name]; area += c['area_mm2']; idle += c['idle_W']
        dyn += a.get('read', 0)*c['read_pJ_per16B'] + a.get('write', 0)*c['write_pJ_per16B']
        extra = a.get('CIM_write', 0) - a.get('CIM_read', 0)
        assert extra >= 0
        writes += a.get('CIM_write', 0); cim += extra*c['read_pJ_per16B']
    assert writes == sum(result['kernel_active'].get(k, 0) for k in ('GU_frames','Wd_M128_frames'))*512
    assert abs(s['dynamic_mJ']-dyn/1e9) < max(1e-8, dyn/1e9*1e-5)
    return dict(area_mm2=area, ordinary_incremental_mJ=dyn/1e9,
        mean_idle_W=idle/len(s['bank_model_ids']), clock_off_residency_mJ=idle*wall/1e6,
        CIM_weight_read_mJ=cim/1e9, macro_characterized=False,
        source_sha256=config['characterization_sha256'],
        CIM_policy='ordinary SRAM write actions plus one read-equivalent per tile;custom512B macro proxy')
