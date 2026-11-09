"""Physical layouts;28nm defaults832KiB, with960KiB retained as a reference.

Repack actual physical banks before any request. This does not retain deleted
ports, reduce V entries, change sampling, or alter a submitted frozen runtime.
"""
import sys


def install(model, config):
    profile=config.get('layout_profile','compact960')
    expected={'compact960':(960,240,128,48),'activation96':(928,232,96,48),
              'activation96_attention36':(832,208,96,36)}
    if profile not in expected:raise ValueError('unknown smaller SRAM layout')
    capacity,banks,vector_kib,attention_kib=expected[profile]
    assert (config['capacity_KiB'],config['bank_count'])==(capacity,banks)
    if profile=='compact960':
        model.candidate_sram_contract=dict(profile=profile,active=False,capacity_KiB=capacity,bank_count=banks)
        return
    h=model.h
    assert h.now==0 and not h.events and not h.pending and not h.mem.queue
    assert model.vector.size==128*1024 and all(r.size==48*1024 for r in model.att)
    model.vector.size=vector_kib*1024
    for region in model.att:region.size=attention_kib*1024
    layout=sys.modules['whole250.sram_layout']
    original=layout.attention_address
    if attention_kib==36:
        def smaller_address(offset,size,tag,capacity):
            assert capacity==36*1024
            dest=original(offset,size,tag,48*1024)
            if tag.startswith(('attention_output','attention_gather')):dest-=13*1024
            if not 0<=dest or dest+size>capacity:
                raise ValueError(('smaller Attention bounds',tag,offset,size,dest,capacity))
            return dest
        layout.attention_address=smaller_address
    repack=layout.repack
    memory=repack(h,model)
    assert memory['capacity_KiB']==capacity and memory['physical_4KiB_banks']==banks
    memory.update(profile=profile,bank_clock_MHz=config.get('clock_MHz'),
        return_SRAM_reservation_KiB=0,ordinary_weight_slot_KiB=32,attention_group_KiB=attention_kib)
    model.compact_memory=memory
    model.candidate_sram_contract=dict(profile=profile,active=True,capacity_KiB=capacity,
        bank_count=banks,front_banks=memory['front_banks'],attention_banks=memory['attention_banks'],
        activation_KiB=vector_kib,attention_group_KiB=attention_kib,
        output_offset_bytes=(34 if attention_kib==36 else 47)*1024,
        weight_slots=32,FFN_state_KiB=96,V_cache_entries=128,
        samples=64,candidates=128,no_extra_ports=True,no_sampler_change=True)
