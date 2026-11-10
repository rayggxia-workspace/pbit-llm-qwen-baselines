"""One physical-resource ledger:28nm measured primitives + named macros."""
from collections import Counter
from pathlib import Path
import json,math
from sram_characterization import budget as sram_budget

def price(m,r,b):
    wall=r['time_ns'];rows=[];a=r['actions'];fa=Counter();aa=Counter()
    for x in m.cross_digital_results:fa.update(x['actions'])
    for x in m.cross_attention_results:aa.update(x['actions'])
    def row(name,area,incremental_pJ,idle_W,instances,basis,kind='MEASURED28_PRIMITIVE'):
        rows.append(dict(component=name,instances=instances,area_mm2=area,
            incremental_activity_mJ=incremental_pJ/1e9,full_residency_idle_mJ=idle_W*instances*wall/1e6,
            energy_mJ=incremental_pJ/1e9+idle_W*instances*wall/1e6,basis=basis,price_kind=kind))
    fp=m.cross_digital_results[0]['profile'] if m.cross_digital_results else None
    path='BF16' if r['scheme']=='BF16_dense' else 'W8';slices=m.cross_allocation['slices']
    fma=b['shared_FMA'] if path=='BF16' else b['digital_reference_cards']['fma16_dual_28_250']
    nbf=a.get('digital_BF16_MAC',0)+sum(aa.get(k,0) for k in ('coarse_QK_MAC','exact_QK_MAC','PV_MAC'))+fa.get('BF16_FMA',0)
    nw=fa.get('W8_BF16_FMA',0)
    if path=='BF16':bf=fma['gross_pJ_per_FMA'];wf=0;idle=fma['idle_W']
    else:
        bf=fma['modes']['bf16_continuous']['gross_pJ_per_unit']/64
        wf=fma['modes']['w8_continuous']['gross_pJ_per_unit']/64
        idle=max(fma['modes'][k]['mean_whole_module_mW'] for k in ('bf16_idle_hold','w8_idle_hold'))/1000
    inc=nbf*(bf-idle*.2568359375*1000)+nw*(wf-idle*.2568359375*1000)
    row('shared_BF16_W8_FMA_pool',slices*fma['area_mm2'],inc,idle,slices,
        'one shared FMA16/C4 pool for projections,FFN readout,QK/PV/head;mode-specific measured action;full residency once')
    ref=json.loads((Path(__file__).parent/'FFN_SOURCE_PROFILE.json').read_bytes())['accepted_reused_components']
    for key,count,instances in [('integer_gu_250',fa['A9W8_DOT64'],16 if path=='W8' else 0),('nl_bf16_250',fa['SwiGLU'],4)]:
        c=ref[key];row(key,c['area_mm2']*instances,count*c['modes']['continuous']['incremental_pJ_per_unit'],c['idle_W'],instances,c['boundary'])
    # Physical reduction32 plus perAttention slot8ADD; separate from internal
    # FMA feedback. Conversion uses existing measured scalar codec as proxy.
    red=b['digital_reference_cards']['fpadd_28_250'];ri=red['modes']['idle_hold']['mean_whole_module_mW']/1000
    rn=a.get('digital_FP32_reduce_ADD',0)+fa['FP32_reduce_ADD']
    row('shared_final_FP32_reduction',32*red['area_mm2'],rn*(red['modes']['continuous']['gross_pJ_per_unit']-ri*4*1000),ri,32,
        'external4partial tree only;internal FMA accumulation already included')
    cards=b['attention_cards']
    for k,ninst in [('fpadd',8*8),('fpmul',8),('explut',4*8),('recseed',8)]:
        c=cards['bf_'+k+'_250'];idle=c['modes']['idle_hold']['power_mW']/1000
        work=c['modes']['stream'];count=aa[k]
        inc=count*(work['gross_pJ_per_operation']-idle*(work['window_cycles_mean']*4/1024)*1000)
        row('Attention_'+k,ninst*c['area28_mm2'],inc,idle,ninst,'online scalar actions,merge/rescale/normalization;current finite macros')
    codec=b['FFN_shared_aux']['codec'];nc=aa['output_BF16']+aa['coarse_BF16']+aa['weight_BF16']
    row('Attention_BF16_RNE_proxy',8*codec['area_mm2'],nc*codec['modes']['bf16']['incremental_pJ_per_unit'],codec['idle_W'],8,
        'FP32->BF16 output/coarse/exp weights;qualified codec primitive proxy,not new wrapper PPA','CODEC_PROXY')
    if path=='W8':
        scale=b['FFN_shared_aux']['scale'];L=r['layers']
        row('FFN_input_scale',scale['area_mm2'],L*40*scale['modes']['scale_cont']['incremental_pJ_per_unit'],scale['idle_W'],1,'x64PoT max/RNE scale primitive;not free conversion')
        row('FFN_input_codec',32*codec['area_mm2'],L*2560*codec['modes']['g8']['incremental_pJ_per_unit'],codec['idle_W'],32,'x fixed8 encode uses measured scalar codec proxy','CODEC_PROXY')
    if r['scheme']=='W8_screen':
        for name,events in [('screen_top16',[('feature',aa['feature_select_groups']),('token',aa['normalize_select_groups'])]),('screen_norm16',[('group',aa['normalize_select_groups'])])]:
            c=cards[name+'_250'];idle=c['modes']['idle']['power_mW']/1000
            inc=sum(n*(c['modes'][mode]['window_gross_nJ_mean']*1000-idle*c['modes'][mode]['window_cycles_mean']*4*1000) for mode,n in events)
            row(name,c['area28_mm2'],inc,idle,1,'one shared selector with actual finite lease;temperature arithmetic separately macro-priced')
        # L1/temperature frontend already represented by128cycles per group.
        temp=aa['temperature_groups']*(512*cards['bf_fpadd_250']['modes']['stream']['gross_pJ_per_operation']+
            160*cards['bf_fpmul_250']['modes']['stream']['gross_pJ_per_operation']+8*cards['bf_recseed_250']['modes']['stream']['gross_pJ_per_operation'])
        row('SparQ_temperature_action_proxy',0,temp,0,1,'existing scalar pool;extra temperature work within reserved frontend cycles','EXPLICIT_ACTION_PROXY')
    ac=m.cross_allocation['components'];byte_area=8*b['platform_macro']['register_bit_area_mm2']
    captured=aa['input_capture_bytes']+aa['transpose_capture_bytes']+aa['tile_partial_capture_bytes']+aa['stats_update']*4+aa['completed_groups']*1024+aa['PV_MAC']//(4*32*128)*256
    # Existing codec/holding primitive is an activity proxy for capture only.
    capture_unit=codec['modes']['bf16']['incremental_pJ_per_unit']
    holding_area=ac['digital_attention_QK_staging'];hold_idle=8*2176*codec['idle_W']/64
    row('Attention_holding',holding_area,captured/2*capture_unit,hold_idle,1,
        '2176B/slot finiteQ/transpose/stat capture;cell area28,codec capture activity proxy','CELL_AND_CAPTURE_PROXY')
    scalar_area=ac['digital_attention_scalar_pool'];control=ac['digital_attention_control_reserve']
    scalar_energy=sum(x['incremental_activity_mJ'] for x in rows if x['component'].startswith(('Attention_','screen_')))*1e9
    row('Attention_control_reserve',control,.1*scalar_energy,0,1,'10%scalar activity;explicit allocated control area,not global15%reserve','EXPLICIT_CONTROL_PROXY')
    s=sram_budget(r,r['macro_config']['SRAM']);assert s['CIM_weight_extra_reads']==0
    row('SRAM28_mixed',s['area_mm2'],s['ordinary_incremental_mJ']*1e9,s['mean_idle_W'],178,
        'same30x8KiB+148x4KiB;digital ports82front+96Attention;noSCpresentationread')
    platform=b['platform_macro'];fifo=m.cross_allocation['projection_FIFO_payload_bytes']
    row('DMA_vectors_operand_FIFO_macro',(20*1024+fifo)*byte_area+platform['vector_output_area_mm2']+platform['CIM_programming_distribution_area_mm2'],
        platform['total_activity_and_idle_W']*wall*1000,0,1,
        '16KiBDMA+4KiBdescriptors+allocated operandFIFO;vector/norm/RoPE/residual/distribution40mW total once','CELL_AREA_AND_TOTAL_POWER_MACRO')
    # Area is independently enumerated by the allocator; require agreement.
    area=sum(x['area_mm2'] for x in rows);target=m.cross_allocation['area55_mm2']
    assert math.isclose(area,target,abs_tol=1e-10),(area,target,rows)
    energy=sum(x['energy_mJ'] for x in rows);external=sum(x.get('issued_bytes',0) for x in r['memory']['by_kind'].values())
    return dict(status='CONDITIONAL28_DIGITAL_LEDGER_CLOSED',rows=rows,
        conditional_subsystem_area_mm2=area,conditional_subsystem_energy_mJ=energy,
        conditional_subsystem_average_W=energy/(wall/1e6),external_bytes=external,
        external_mJ_by_pJbit={str(e):external*8*e/1e9 for e in (4.,6.6,8.)},
        conditional_total_energy_mJ_by_external_pJbit={str(e):energy+external*8*e/1e9 for e in (4.,6.6,8.)},
        FFN_actions=dict(fa),Attention_actions=dict(aa),SRAM_calibration=s,
        area_multiplier=1,used55nm_prices=False,gross_idle_double_counted=False,
        unpriced_in_chosen_boundary=[],full_system_area_mm2=None,
        scope='same conditional core-subsystem boundary asSC;not physical fullchip or new modelquality',
        outside_boundary=b['outside_model_boundary'],
        remaining_estimates=['finite onlineSoftmax macro timing','DFFcapture activity','vector/DMA40mW','codec conversion proxies','synthetic max-rescale metadata'])
