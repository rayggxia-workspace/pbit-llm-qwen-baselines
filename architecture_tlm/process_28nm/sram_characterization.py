"""Real S0 macro cost binding; physical-bank timing remains in the host TLM."""
import math


def mixed_budget(result,config):
    s=result['SRAM'];ids=s['bank_model_ids'];activity=s['bank_activity'];cards=config['macro_models']
    assert len(ids)==len(activity)==s['physical_banks']==178
    assert sum(cards[k]['bytes'] for k in ids)==s['capacity_bytes']==832*1024
    assert sum(x.get('read',0) for x in activity)==s['counts']['read_words']
    assert sum(x.get('write',0) for x in activity)==s['counts']['write_words']
    wall=result['time_ns'];period=1000/result['clock_MHz']
    dynamic=resident=area=cim=free_on=0.;extra=0
    for k,x in zip(ids,activity):
        c=cards[k];rd=x.get('read',0);wr=x.get('write',0)
        equivalents=x.get('CIM_write',0)-x.get('CIM_read',0);assert equivalents>=0
        dynamic+=rd*c['read_pJ_per16B']+wr*c['write_pJ_per16B']
        resident+=c['idle_W']*wall*1000;area+=c['area_mm2']
        cim+=equivalents*c['read_pJ_per16B'];extra+=equivalents
        free_on+=(c['clock_on_idle_W']-c['idle_W'])*max(0,wall-(rd+wr+equivalents)*period)/1e6
    expected=sum(result['kernel_active'].get(k,0) for k in ('GU_frames','Wd_M128_frames'))*512
    assert sum(x.get('CIM_write',0) for x in activity)==expected
    # The event engine repeatedly adds positive binary64 prices, whereas this
    # audit multiplies exact action counts. Bound accumulation roundoff by N*u.
    events=s['counts']['read_words']+s['counts']['write_words']
    roundoff_bound=max(1e-12,2*events*math.ulp(1.0))
    error=(s['dynamic_mJ']-dynamic/1e9)/(dynamic/1e9) if dynamic else 0.
    assert abs(error)<=roundoff_bound,dict(event_mJ=s['dynamic_mJ'],count_mJ=dynamic/1e9,
        relative_error=error,binary64_bound=roundoff_bound,events=events)
    return dict(area_mm2=area,ordinary_incremental_mJ=dynamic/1e9,
        clock_off_residency_mJ=resident/1e9,ordinary_total_mJ=(dynamic+resident)/1e9,
        CIM_weight_extra_reads=extra,CIM_weight_read_mJ=cim/1e9,
        total_including_CIM_mJ=(dynamic+resident+cim)/1e9,
        ungated_clock_on_additional_mJ=free_on,ordinary_read_words=s['counts']['read_words'],
        ordinary_write_words=s['counts']['write_words'],macro_characterized=False,
        macro_source='S0_PT;S2_library_area_timing_and_clock_delta_energy_estimate',
        mean_idle_W=sum(cards[k]['idle_W'] for k in ids)/len(ids),
        event_vs_count_relative_error=error,binary64_accumulation_error_bound=roundoff_bound,
        area_multiplier=1,baseline='per_physical_macro incremental access + clock-off residency',
        CIM_policy='one read-equivalent per programmed resident weight word;per-bank price;no actual extra port transaction',
        source_sha256=config['characterization_sha256'])


def budget(result, config):
    if any(config.get(k) is None for k in ('read_pJ_per16B', 'write_pJ_per16B',
                                          'leak_W_per4KiB', 'area_mm2_per4KiB')):
        return None
    wall=result['time_ns'];mhz=result['clock_MHz'];period=1000/mhz
    sram=result['SRAM'];counts=sram['counts'];banks=sram['physical_banks']
    assert sram['word_bytes']==config['word_bytes']==16
    if sram.get('bank_model_ids'):return mixed_budget(result,config)
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
