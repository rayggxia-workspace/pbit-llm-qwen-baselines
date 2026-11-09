"""Real S0 macro cost binding; physical-bank timing remains in the host TLM."""
import math


def budget(result, config):
    if any(config.get(k) is None for k in ('read_pJ_per16B', 'write_pJ_per16B',
                                          'leak_W_per4KiB', 'area_mm2_per4KiB')):
        return None
    wall=result['time_ns'];mhz=result['clock_MHz'];period=1000/mhz
    sram=result['SRAM'];counts=sram['counts'];banks=sram['physical_banks']
    assert sram['word_bytes']==config['word_bytes']==16
    assert banks==config['bank_count'] and banks*4096==sram['capacity_bytes']
    reads=counts.get('read_words',0);writes=counts.get('write_words',0)
    idle=config['leak_W_per4KiB']
    dynamic=(reads*config['read_pJ_per16B']+writes*config['write_pJ_per16B'])/1e9
    resident=banks*idle*wall/1e6
    # Resident CIM data is presented once, reused for all samples in its frame.
    frames=sum(result['kernel_active'].get(k,0) for k in ('GU_frames','Wd_M128_frames'))
    expected=frames*512
    included=sum(sram.get('by_tag',{}).get(k,{}).get('read_words',0) for k in (
        'CIM_weight_presentation_read','GU_weight_presentation_read','Wd_weight_presentation_read'))
    assert 0<=included<=expected
    extra=expected-included
    cim=extra*config['read_pJ_per16B']/1e9
    on=config['clock_on_idle_W_per4KiB']
    free_bank_ns=banks*wall-(reads+writes+extra)*period
    assert free_bank_ns>=-1e-3
    return dict(area_mm2=banks*config['area_mm2_per4KiB'],
        ordinary_incremental_mJ=dynamic,clock_off_residency_mJ=resident,
        ordinary_total_mJ=dynamic+resident,CIM_weight_extra_reads=extra,
        CIM_weight_read_mJ=cim,total_including_CIM_mJ=dynamic+resident+cim,
        ungated_clock_on_additional_mJ=(on-idle)*max(0,free_bank_ns)/1e6,
        ordinary_read_words=reads,ordinary_write_words=writes,
        macro_characterized=True,area_multiplier=1,
        baseline='clock-off incremental access + full physical-bank clock-off power',
        CIM_policy='ordinary SRAM read-equivalent once per resident8KiB frame;writes/area/leakage counted once',
        source_sha256=config['characterization_sha256'])
