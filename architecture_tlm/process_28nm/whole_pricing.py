"""28nm known-component ledger. Missing costs are null, never silently55nm."""
import math
from sram_characterization import budget as sram_budget

def price(m,r,binding):
    wall=r['time_ns'];mhz=binding['clock_MHz'];period=1000/mhz;counts=r['process28_counts'];rows=[]
    def row(name,area,incremental_pJ,idle_W,instances,basis):
        rows.append(dict(component=name,instances=instances,area_mm2=area,
            incremental_activity_mJ=None if incremental_pJ is None else incremental_pJ/1e9,
            full_residency_idle_mJ=None if idle_W is None else idle_W*instances*wall/1e6,
            energy_mJ=None if incremental_pJ is None or idle_W is None else
                incremental_pJ/1e9+idle_W*instances*wall/1e6,basis=basis))
    core=binding['FFN_core'];busy=sum(r['kernel_active'].get(k,0)*core['modes'][n]['frame_ns']
        for n,k in [('GU','GU_frames'),('Wd','Wd_M128_frames')])
    active=sum(r['kernel_active'].get(k,0)*core['modes'][n]['gross_pJ_per_frame']
        for n,k in [('GU','GU_frames'),('Wd','Wd_M128_frames')])
    assert busy<=m.common_cores*wall+1e-5
    row('FFN_shared_GU_Wd',m.common_cores*core['area_mm2'],active-core['waiting_power_W']*busy*1000,
        core['waiting_power_W'],m.common_cores,'measured gross frames minus active idle + full residency;no extra SNG/nonlinearity')
    for name,instances,mode,number in [('state',2,'state_cont',r['actions']['common_state32_vectors']),
        ('scale',1,'scale_cont',counts.get('scale64_groups',0))]:
        c=binding['FFN_shared_aux'][name]
        row('FFN_'+name,c['area_mm2']*instances,c['modes'][mode]['incremental_pJ_per_unit']*number,c['idle_W'],instances,'qualified32lane/64element primitive;external SRAM separate')
    c=binding['FFN_shared_aux']['codec'];energy=sum(counts.get('codec_'+n,0)*c['modes'][n]['incremental_pJ_per_unit'] for n in ('g8','u8','bf16'))
    row('FFN_codec',16*c['area_mm2'],energy,c['idle_W'],16,'16scalar replicas;shared formats,not16lane mapped wrapper')
    c=binding['FFN_staging_proxy']
    row('FFN_1KiB_staging',c['area_mm2_proxy'],counts.get('staging_groups',0)*c['incremental_pJ_per_group_proxy'],c['idle_W_proxy'],1,'cell-composition proxy;one finite credit')
    cards=binding['attention_cards'];sampler_instances=m.sampler_pool.slots
    for name,key,number,instances,mode in [('score_front','front_s12buf',counts.get('front_queries',0),sampler_instances,'work'),
        ('gap_sampler','gap_sampler',counts.get('sampler_queries',0),sampler_instances,'work')]:
        c=cards[key+'_'+str(mhz)];work=c['modes'][mode];idle=c['modes'].get('gated_idle',c['modes'].get('idle'))['power_mW']/1000
        ns=work['window_service_cycles_per_query']*period
        assert number*ns<=instances*wall+1e-6
        row(name,c['area28_mm2']*instances,number*(work['gross_query_nJ']*1000-idle*ns*1000),idle,instances,
            'qualified standalone query gross;32load handshakes overlap only in time;no additional legacyab_both')
    for name,key,operations in [('SparQ_norm','screen_norm16',[('group',counts.get('norm_groups',0))]),
        ('SparQ_top','screen_top16',[('feature',counts.get('top_feature',0)),('token',counts.get('top_token',0))])]:
        c=cards[key+'_'+str(mhz)];idle=c['modes']['idle']['power_mW']/1000
        inc=sum(n*(c['modes'][mode]['window_gross_nJ_mean']*1000-idle*c['modes'][mode]['window_cycles_mean']*period*1000) for mode,n in operations)
        slots=m.norm_pool.slots if name=='SparQ_norm' else m.top_pool.slots
        row(name,c['area28_mm2']*slots,inc,idle,slots,'norm group=4heads;feature=1head;token=1KVgroup')
    sram=sram_budget(r,r.get('macro_config',{}).get('SRAM',{}))
    if sram is not None:
        cfg=r['macro_config']['SRAM'];banks=r['SRAM']['physical_banks']
        mixed=bool(r['SRAM'].get('bank_model_ids'))
        row('SRAM28_mixed_S0_S2_macros' if mixed else 'SRAM28_real_S0_macros',sram['area_mm2'],sram['ordinary_incremental_mJ']*1e9,
            sram.get('mean_idle_W',cfg['leak_W_per4KiB']),banks,
            'S0 measured;S2 lib area/timing plus CLK-delta energy estimate' if mixed else 'real28HPC+ S0 TT;clock-off baseline increments + one full residency')
        row('CIM_weight_presentation_SRAM_proxy',0,sram['CIM_weight_read_mJ']*1e9,0,1,
            'user-selected ordinary SRAM read per resident tile;no added per-sample reread or physical port')
    fma=binding['shared_FMA'];ops=r['actions']['digital_BF16_MAC']+r['actions']['attention_QK_MAC'];n=16
    if mhz==250 and fma.get('gross_pJ_per_FMA') is not None:
        # Continuous characterization4096FMA/1052ns;idle per physical FMA16.
        idle=fma['idle_W'];inc=ops*(fma['gross_pJ_per_FMA']-idle*1052/4096*1000)
        row('shared_FMA256',n*fma['area_mm2'],inc,idle,n,'qualified older FMA16/C4;4cycle timing retained explicit')
    else:row('shared_FMA256',None,None,None,n,'500MHz pipeline/price macro pending;4contexts/II1/latency4 assumption')
    missing=[dict(component='PV_ADD_fixedstate_Vcontrol_and_output',scalar_ADDs=r['actions']['PV_ADD'],area_mm2=None,energy_mJ=None),
        dict(component='DMA_FIFOs_vectors_RMSNorm_RoPE_residual_reduction',area_mm2=None,energy_mJ=None),
        dict(component='CTS_PHY_NoC_TIE_and_remaining_control',area_mm2=None,energy_mJ=None)]
    if sram is None:missing.insert(0,dict(component='SRAM28',action_counts=r['SRAM']['counts'],area_mm2=None,energy_mJ=None))
    external=r['memory']['by_kind'];bytes_=sum(x.get('issued_bytes',0) for x in external.values())
    known_area=sum(x['area_mm2'] for x in rows if x['area_mm2'] is not None)
    known_energy=sum(x['energy_mJ'] for x in rows if x['energy_mJ'] is not None)
    return dict(status='PARTIAL28NM_COMPONENT_LEDGER_WITH_EXPLICIT_UNPRICED_ACTIONS',rows=rows,unpriced=missing,SRAM_calibration=sram,
        covered_component_area_mm2=known_area,covered_component_energy_mJ=known_energy,
        external_bytes=bytes_,external_mJ_by_pJbit={str(e):bytes_*8*e/1e9 for e in (4.,6.6,8.)},
        full_system_area_mm2=None,full_system_energy_mJ_token=None,full_system_average_W=None,
        scope='measured28 components + explicitstagingproxy;partial sum,not full chip or lowerbound under all input distributions',
        area_multiplier=1,used55nm_prices=False,gross_idle_double_counted=False)
