"""Reconcile existing component tariffs, residence states and external bytes.

This checks the modeled boundary; it does not turn an uncharacterized PHY,
CIM interface or post-layout clock tree into zero-cost measured hardware.
"""
import math

GATE_OWNER={'ab_both':'Ising_sampler','screen_top16':'SparQ_top_and_norm',
            'screen_norm16':'SparQ_top_and_norm'}

def reconcile(*,area,shared_area,service_uJ,resident_uJ,gating_uJ,status,
              time_ns,external_bytes,external_tariffs,expected_onchip_uJ,ffn_label,ffn):
    if set(area)&set(shared_area):raise ValueError('area resource charged by host and module')
    if time_ns<=0:raise ValueError('positive execution window required')
    reductions={}
    for key,value in gating_uJ.items():
        target=GATE_OWNER.get(key,key);reductions[target]=reductions.get(target,0)+value
    names=set(area)|set(shared_area)|set(service_uJ)|set(resident_uJ)|set(reductions)
    rows=[]
    for name in sorted(names):
        active=service_uJ.get(name,0);before=resident_uJ.get(name,0);saved=reductions.get(name,0)
        if min(active,before,saved)<0 or saved>before+1e-7:raise ValueError('invalid energy states '+name)
        row=dict(resource_id=name,area55_mm2=area.get(name,shared_area.get(name,0)),
            activity_or_service_uJ=active,residence_before_root_gating_uJ=before,
            root_gating_savings_uJ=saved,residence_after_root_gating_uJ=max(0,before-saved),
            total_uJ=active+before-saved,basis=status.get(name,'existing host/memory action or state tariff'))
        row['billing']='incremental activity + resident state, with explicit root clock gating'
        if name==ffn_label:
            row['billing']='active gross + waiting only on remaining physical core-time'
            row['active_core_ns']=ffn['active_core_ns'];row['waiting_core_ns']=ffn['waiting_core_ns']
            row['equivalent_incremental_plus_idle_uJ']=ffn['equivalent_incremental_plus_idle_mJ']*1000
            row['background_already_in_active_gross_uJ']=ffn['idle_already_inside_active_gross_mJ']*1000
            if not math.isclose(row['total_uJ'],row['equivalent_incremental_plus_idle_uJ'],rel_tol=1e-10,abs_tol=1e-7):
                raise ValueError('FFN gross/idle formulations disagree')
        rows.append(row)
    onchip=math.fsum(x['total_uJ'] for x in rows)
    if not math.isclose(onchip,expected_onchip_uJ,rel_tol=1e-10,abs_tol=1e-7):raise ValueError('onchip sum mismatch')
    total_area=math.fsum(x['area55_mm2'] for x in rows)
    systems={}
    for rate in external_tariffs:
        ext=external_bytes*8*rate/1e6;energy=onchip+ext
        systems[str(rate)]=dict(external_uJ=ext,modeled_system_uJ=energy,
            modeled_system_mJ=energy/1000,average_W=energy/(time_ns/1000))
    return dict(status='CLOSED_WITHIN_DECLARED_MODEL_BOUNDARY',numerical_sum_closed=True,
        unique_resource_ids=len(rows)==len({x['resource_id'] for x in rows}),
        silicon_complete=False,all_components_measured=False,time_ns=time_ns,
        covered_area55_mm2=total_area,onchip_uJ=onchip,onchip_mJ=onchip/1000,
        onchip_average_W=onchip/(time_ns/1000),components=rows,
        external_bytes=external_bytes,external_pJ_per_bit_scenarios=systems,
        gross_idle_double_count_detected=False,
        gross_idle_check='FFN gross+remaining-idle equals incremental+whole-idle; other root gating reductions attributed once',
        declared_proxies=['legacySS100 vector/format/reduction/holding at250; module reserve composition',
          'PV2 arithmetic composition and QK transpose/holding','projection FIFO payload capture/selection allowance',
          'external4/6.6/8pJ per bit covers modeled transfer boundary; no native LPDDR power model'],
        outside_priced_boundary=['custom CIM readout/programming interface delta beyond ordinary SRAM macro proxy',
          'full physical NoC/CTS/routing/pads and separately characterized LPDDR controller/PHY',
          'new projection FIFO arbitration/control/leakage beyond the recorded payload/host allowance'],
        boundary='existing modeled compute, physical SRAM capacity, DMA holding/vector allowances, plus all external bytes; unknown physical deltas explicitly outside,not silently zero')
