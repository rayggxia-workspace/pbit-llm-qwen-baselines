"""Close the chosen core-subsystem boundary with explicit measured/proxy rows."""
import math

def close(ledger,r,b):
    assert r['clock_MHz']==250 and b['refresh250_version']==1
    rows=ledger['rows'];wall=r['time_ns'];pv=b['PV_backend'];vacc=pv['vacc'];ctrl=pv['controller']
    def add(name,area,gross_pJ,busy_ns,idle_W,instances,basis,kind):
        assert 0<=busy_ns<=instances*wall+1e-3
        inc=gross_pJ-idle_W*busy_ns*1000;resident=idle_W*instances*wall/1e6
        assert inc>=-1e-6
        total=inc/1e9+resident
        assert math.isclose(total,(gross_pJ+idle_W*(instances*wall-busy_ns)*1000)/1e9,rel_tol=1e-12,abs_tol=1e-15)
        rows.append(dict(component=name,instances=instances,area_mm2=area,incremental_activity_mJ=inc/1e9,
            full_residency_idle_mJ=resident,energy_mJ=total,basis=basis,price_kind=kind))
    a=r['actions'];adds=a['PV_ADD'];samples=a['samples'];miss=a['unique_V'];reuse=a['V_fetch_reuse']
    assert miss+reuse==samples and adds==128*samples
    g=vacc['cell_area28_mm2'];fixed=g['register']+g['icg'];ratio=pv['lanes_per_head']/16
    vmode=vacc['modes']['stream'];vidle=vacc['modes']['idle_gated']['power_mW']/1000
    area=pv['heads']*(fixed+g['other_logic']*ratio)
    add('PV_accum_fixedstate_and_ADD_proxy',area,adds*vmode['gross_pJ_per_operation'],
        adds*vmode['cycles_per_operation']*4,vidle,pv['heads'],
        'retain full128FP32 state/register+ICG perhead;only other_logic x2/16;measured16lane perADD energy proxy',
        'STRUCTURAL_WIDTH_PROXY_FROM_MEASURED_VACC16;hold_deferred')
    ci=ctrl['modes']['idle_gated']['power_mW']/1000
    busy=sum(n*ctrl['modes'][mode]['window_cycles']*4/256 for mode,n in [('cold',miss),('reuse',reuse)])
    gross=sum(n*ctrl['modes'][mode]['gross_pJ_per_operation'] for mode,n in [('cold',miss),('reuse',reuse)])
    add('PV_Vcontrol_reference',pv['KV_groups']*ctrl['area28_mm2'],gross,busy,ci,pv['KV_groups'],
        'actual unique_V misses usecold;remaining actual indices usereuse;16bank controller is reference to9bank runtime,not matched compact-top PPA',
        'MEASURED_REFERENCE_CONTROL_PRICE;hold_deferred;cachemode_mixture_proxy')
    platform=b['platform_macro'];storage_KiB=sum(platform['register_allocations_KiB'].values())
    storage_area=storage_KiB*1024*8*platform['register_bit_area_mm2']
    rows.append(dict(component='DMA_FIFO_and_platform_macros',instances=1,
        area_mm2=storage_area+platform['vector_output_area_mm2']+platform['CIM_programming_distribution_area_mm2'],
        incremental_activity_mJ=None,full_residency_idle_mJ=None,
        energy_mJ=platform['total_activity_and_idle_W']*wall/1e6,
        basis='16KiB DMA+8KiB operands+4KiB descriptors DFF-cell area;named vector/output/CIM interface;40mW total power once',
        price_kind='CELL_AREA_EXTRAPOLATION_AND_EXPLICIT_TOTAL_POWER_MACRO',
        area_detail=dict(register_storage_KiB=storage_KiB,register_area_mm2=storage_area,
            vector_output_mm2=platform['vector_output_area_mm2'],CIM_interface_mm2=platform['CIM_programming_distribution_area_mm2'])))
    area=sum(x['area_mm2'] for x in rows);energy=sum(x['energy_mJ'] for x in rows)
    powers=platform['power_sensitivity_W']
    platform_energy=rows[-1]['energy_mJ'];base_energy=energy-platform_energy
    # Alternative activity traces cannot be recovered from action counts. Keep
    # stalled/control sensitivity explicit rather than pretending measured2lane PPA.
    stalled=vacc['modes']['stalled'];vacc_stalled=adds*(stalled['gross_pJ_per_operation']-
        vidle*stalled['cycles_per_operation']*4*1000)/1e9+vidle*pv['heads']*wall/1e6
    ctrl_back=ctrl['modes']['backpressure'];ctrl_back_e=samples*(ctrl_back['gross_pJ_per_operation']-
        ci*ctrl_back['window_cycles']*4/256*1000)/1e9+ci*pv['KV_groups']*wall/1e6
    ledger.update(status='CONDITIONAL28NM250_CORE_SUBSYSTEM_LEDGER_CLOSED',
        conditional_subsystem_area_mm2=area,conditional_subsystem_energy_mJ=energy,
        conditional_subsystem_average_W=energy/(wall/1e6),
        conditional_total_energy_mJ_by_external_pJbit={k:energy+v for k,v in ledger['external_mJ_by_pJbit'].items()},
        platform_power_sensitivity_core_mJ=[base_energy+p*wall/1e6 for p in powers],
        PV_activity_sensitivity=dict(reference_stalled_vacc_mJ=vacc_stalled,reference_backpressure_control_mJ=ctrl_back_e,
            no_actual_stall_trace_price_claim=True),
        unpriced_in_chosen_boundary=[],
        outside_boundary=b['outside_model_boundary']+['externalDRAMdie_area','LPDDR_PHY/pads/CPU/package'],
        explicit_estimates=b['remaining_estimates'],
        full_system_area_mm2=None,full_system_energy_mJ_token=None,full_system_average_W=None,
        scope='core-subsystem measured primitives+declared proxies/macros;external pJbit scenario separate;not wholechip PPA',
        gross_idle_double_counted=False,uniform_placement_reserve=0,
        physical_full_clock_qualified=False,full_token_replay=(r.get('scope')=='full'))
    ledger['unpriced']=[]
    return ledger

def split_head(full,body,full_ns,body_ns):
    """Observed phase-prefix accounting on one execution; no second chip area."""
    assert 0<body_ns<full_ns
    assert math.isclose(full['conditional_subsystem_area_mm2'],body['conditional_subsystem_area_mm2'],rel_tol=1e-12)
    m={}
    for label,budget,t in [('including_lm_head',full,full_ns),('without_lm_head_stage',body,body_ns)]:
        m[label]=dict(time_ms=t/1e6,core_energy_mJ=budget['conditional_subsystem_energy_mJ'],
            core_average_W=budget['conditional_subsystem_energy_mJ']/(t/1e6),external_bytes=budget['external_bytes'],
            total_mJ_by_external_pJbit=budget['conditional_total_energy_mJ_by_external_pJbit'])
    m['lm_head_stage']=dict(time_ms=(full_ns-body_ns)/1e6,
        core_energy_mJ=full['conditional_subsystem_energy_mJ']-body['conditional_subsystem_energy_mJ'],
        external_bytes=full['external_bytes']-body['external_bytes'],
        total_mJ_by_external_pJbit={k:full['conditional_total_energy_mJ_by_external_pJbit'][k]-body['conditional_total_energy_mJ_by_external_pJbit'][k]
            for k in full['conditional_total_energy_mJ_by_external_pJbit']})
    for k in ('time_ms','core_energy_mJ','external_bytes'):
        assert math.isclose(m['including_lm_head'][k],m['without_lm_head_stage'][k]+m['lm_head_stage'][k],rel_tol=1e-12,abs_tol=1e-12)
    m['scope']='same execution prefix at final_norm;resident hardware unchanged;not independently restarted nohead run'
    return m
