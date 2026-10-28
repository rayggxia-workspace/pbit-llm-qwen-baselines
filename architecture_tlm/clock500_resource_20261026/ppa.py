"""Evidence-bounded PPA postprocessor for the 500 MHz TLM sweep.

No circuit is simulated here. Reads a RESULT_SUMMARY.json and explicit per-
instance occupancy counts. Never supplies a fabricated full-chip total.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def nonnegative(value, name):
    value=float(value)
    if not math.isfinite(value) or value<0:
        raise ValueError(name+' must be finite and nonnegative')
    return value


def make_row(name, classification, area, energy, elapsed_s, **extra):
    return dict(module=name,classification=classification,area_mm2=area,
        energy_J=energy,average_power_W=None if energy is None else energy/elapsed_s,**extra)


def clock_account(instances,total_cycles,on_cycles,leak_mW,idle_dyn_pJ,incremental_pJ,
                  elapsed_s,efficiency,area_ratio=1.0):
    """All on_cycles are SUMMED across physical instances, not global makespan.

    leakage runs for wall time; e_idle uses reference idle clock activity; useful
    action increment is relative to same clock-on idle. No gross-energy addition.
    """
    available=instances*total_cycles
    on_cycles=nonnegative(on_cycles,'on_instance_cycles')
    if on_cycles>available*(1+1e-9):
        raise ValueError('on-instance cycles exceed physical instance capacity')
    if not 0<=efficiency<=1:
        raise ValueError('clock gating efficiency must lie in [0,1]')
    off_cycles=max(0.,available-on_cycles)
    leak=instances*leak_mW*1e-3*elapsed_s*area_ratio
    active_idle=on_cycles*idle_dyn_pJ*1e-12*area_ratio
    off_idle=off_cycles*idle_dyn_pJ*1e-12*area_ratio
    increment=incremental_pJ*1e-12
    energy=leak+active_idle+(1-efficiency)*off_idle+increment
    return dict(energy_J=energy,leakage_J=leak,clock_on_idle_background_J=active_idle,
        useful_activity_increment_J=increment,ungated_idle_dynamic_J=off_idle,
        ideal_ICG_saving_upper_bound_J=off_idle,
        selected_clock_gating_saving_J=efficiency*off_idle,
        conditional_no_gating_J=energy+efficiency*off_idle,
        conditional_ideal_gating_J=energy-(1-efficiency)*off_idle,
        instances=instances,on_instance_cycles=on_cycles,off_instance_cycles=off_cycles,
        duty=0. if available==0 else on_cycles/available,
        gating_efficiency=efficiency,
        excluded='ICG/CTS/wakeup/ungated-control/operand-isolation cost not measured')


def usage_from_tlm(summary):
    """Map explicit clock-gating resource accounting; do not infer occupancy.

    A sc:i resource is one N64/M64 array. A restore resource is its lane bank.
    Counts are per OUTPUT dot product (64 per 64x64 tile), never per array.
    """
    c=summary['config'];f=c.get('ffn',{})
    g=summary.get('clock_gating',{})
    resources=g.get('resources',{})
    period=1e9/c['core_hz']
    removal_fraction=g.get('gate_idle_dynamic_removed_fraction',
        c.get('gate_idle_dynamic_removed_fraction',0.8))
    use={'gating_efficiency':float(removal_fraction) if g.get('enabled',False) else 0.0,
         'occupancy_source':'RESULT_SUMMARY.clock_gating.resources; instance-count weighted',
         'clock_gating_implementation':'Explicit removal fraction of clock-on idle dynamic while gated off; unmeasured ICG/CTS and residual input activity excluded'}
    if f.get('mode')!='sc':
        return use
    if not g:
        raise ValueError('SC PPA requires explicit clock_gating resource occupancy; do not guess from elapsed time')
    locality=f.get('locality',{})
    if locality.get('tile',64)!=64:
        raise ValueError('PPA calibration only supports N64/M64 array tiles')
    activity=summary['FFN_activity']
    gu=activity.get('SC_4bucket_tiles',0)*64
    down=activity.get('SC_7bucket_tiles',0)*64
    counter_on=64*sum(float(v['clock_on_ns']) for k,v in resources.items() if k.startswith('sc:'))/period
    expected_restore=gu+down
    actual_restore=summary.get('actions',{}).get('SC_coefficient16_restore',0)
    if actual_restore!=expected_restore:
        raise ValueError('restore counts do not match N64 tile output boundary')
    restore_resource=resources.get('ffn_SC_coefficient16_restore')
    if restore_resource is None and expected_restore:
        raise ValueError('missing explicit restore resource occupancy')
    bucket_resource=resources.get('ffn_SC_bucket_shift_reduce')
    if bucket_resource is None and expected_restore:
        raise ValueError('missing explicit bucket-reduce resource occupancy for combined restore macro')
    lifetime_ns=float(g.get('lifetime_ns',summary['metrics']['elapsed_ns']))
    bucket_on_ns=float(bucket_resource['clock_on_ns']) if bucket_resource else 0.
    coefficient_on_ns=float(restore_resource['clock_on_ns']) if restore_resource else 0.
    # The current two functions execute sequentially. Sum is an upper bound on
    # their union if separate keep-alive / wake intervals overlap; cap lifetime.
    combined_restore_on_ns=min(lifetime_ns,bucket_on_ns+coefficient_on_ns)
    use.update(counter={'output_channels':int(f['engines'])*64,'physical_bins':7,
        'on_instance_cycles':counter_on,
        'frames':[{'bins':4,'samples':f['samples'],'count':gu},
                  {'bins':7,'samples':f['nonlinear_samples'],'count':down}]},
        restore={'lanes':int(f['restore_lanes']),'physical_bins':7,
            'on_instance_cycles':combined_restore_on_ns*f['restore_lanes']/period,
            'activity_mode':'cadence72','actions':[{'bins':4,'count':gu},{'bins':7,'count':down}],
            'combined_macro_mapping':{'bucket_clock_on_ns':bucket_on_ns,
                'coefficient_clock_on_ns':coefficient_on_ns,'combined_clock_on_ns_upper_bound':combined_restore_on_ns,
                'rule':'min(lifetime, bucket_clock_on_ns + coefficient_clock_on_ns)',
                'not_exact_interval_union':True,
                'limit':'Sequential useful work; keep-alive/wakeup interval overlap may overcount. A single physical macro is priced once, and its enable must cover both phases. Lane/provisioning reconciliation remains pending.'}},
        accumulator={'lanes':int(f['accumulate_lanes'])},
        schedule_to_RTL_limit='TLM uses separate bucket-reduce/restore resources. The measured restore already combines both functions; priced once. Combined clock-on uses a capped sum upper bound, not an exact union; pipeline/lane split remains to be reconciled.',
        wakeup_accounting='clock_on_ns includes modeled wake interval; no extra double charge. Actual ICG wake/control energy remains unknown.')
    return use


def estimate(summary,usage,anchors):
    elapsed_s=summary['metrics']['elapsed_ns']*1e-9
    if elapsed_s<=0:
        raise ValueError('positive execution time required')
    core_hz=summary['config']['core_hz']
    total_cycles=elapsed_s*core_hz
    rows=[]
    unknown=[]
    freq_note='Power/action extrapolated at fixed voltage; 500 MHz and new pipeline are not STA/PPA validated.'
    areas=anchors['area_100MHz']
    powers=anchors['power_100MHz']
    eta=float(usage.get('gating_efficiency',0.8))
    for core in ('counter','restore'):
        u=usage.get(core)
        if not u:
            if summary['config'].get('ffn',{}).get('mode')=='sc':
                unknown.append(core+' occupancy not supplied')
            continue
        physical_bins=int(u.get('physical_bins',7))
        if physical_bins not in (4,7):
            raise ValueError('only measured B4 and B7 shapes may select area anchors')
        mode='continuous' if core=='counter' else u.get('activity_mode','cadence72')
        active=powers[core+'_'+mode]
        idle=powers[core+'_idle']
        if core=='counter':
            channels=int(u['output_channels'])
            if channels<0:
                raise ValueError('negative output_channels')
            # M8 measurements already contain eight outputs. Never multiply by64 again.
            groups8=math.ceil(channels/8)
            instances=groups8*8
            area=groups8*areas['counter_b%d_t%d_m8'%(physical_bins,64 if physical_bins==4 else 128)]['area_um2']*1e-6
            a4=areas['counter_b4_t64_m1']['area_um2']
            physical_ratio=areas['counter_b%d_t%d_m1'%(physical_bins,64 if physical_bins==4 else 128)]['area_um2']/a4
            increment=0.
            sample_cycles=0.
            has_proxy=physical_bins!=4
            for g in u.get('frames',[]):
                bins=int(g['bins']);samples=int(g['samples'])
                count=nonnegative(g['count'],'counter output frame count')
                if bins not in (4,7) or bins>physical_bins or samples<1:
                    raise ValueError('invalid frame geometry')
                ratio=areas['counter_b%d_t%d_m1'%(bins,64 if bins==4 else 128)]['area_um2']/a4
                increment+=count*active['incremental_pJ_per_operation']*(samples/64.)*ratio
                sample_cycles+=count*samples
                has_proxy=has_proxy or bins!=4 or samples!=64
            if float(u['on_instance_cycles'])+1e-6<sample_cycles:
                raise ValueError('counter occupancy cannot cover accepted per-output samples')
            boundary='N64 input channels; %d physical output channels; B%d-capable shared GU/Wd counter'%(instances,physical_bins)
        else:
            instances=int(u['lanes'])
            area=instances*areas['restore_b%d_c%d'%(physical_bins,20 if physical_bins==4 else 21)]['area_um2']*1e-6
            a4=areas['restore_b4_c20']['area_um2']
            physical_ratio=areas['restore_b%d_c%d'%(physical_bins,20 if physical_bins==4 else 21)]['area_um2']/a4
            increment=0.
            has_proxy=physical_bins!=4
            count_total=0.
            for g in u.get('actions',[]):
                bins=int(g['bins']); count=nonnegative(g['count'],'restore action count')
                if bins not in (4,7) or bins>physical_bins:
                    raise ValueError('invalid restore geometry')
                ratio=areas['restore_b%d_c%d'%(bins,20 if bins==4 else 21)]['area_um2']/a4
                increment+=count*active['incremental_pJ_per_operation']*ratio
                has_proxy=has_proxy or bins!=4
                count_total+=count
            if float(u['on_instance_cycles'])+1e-6<count_total:
                raise ValueError('restore occupancy cannot cover II1 action count')
            boundary='One lane includes bucket shift/reduction AND coefficient/round/sign recovery; no duplicate bucket energy.'
        account=clock_account(instances,total_cycles,u['on_instance_cycles'],idle['leakage_mW'],
            idle['clock_on_idle_dynamic_pJ_per_cycle'],increment,elapsed_s,
            float(u.get('gating_efficiency',eta)),physical_ratio)
        rows.append(make_row('FFN_'+core,'proxy_from_measured' if has_proxy else 'measured_extrapolation',
            area,account['energy_J'],elapsed_s,accounting=account,boundary=boundary,
            area_source='measured 100 MHz prelayout synthesis, replicated',
            power_source='measured B4/M1 active and clock-on idle, B7 area-ratio proxy' if has_proxy else 'measured B4/M1 active and clock-on idle',
            frequency_limit=freq_note,
            combined_macro_mapping=u.get('combined_macro_mapping')))
    u=usage.get('accumulator')
    if u:
        rows.append(make_row('FFN_wide_local_accumulator','area_only_measured_extrapolation',
            int(u['lanes'])*areas['accumulator64']['area_um2']*1e-6,None,elapsed_s,
            boundary='signed64 saturating update lane; storage banks beyond one state/lane excluded'))
        unknown.append('FFN wide accumulator activity power and multi-entry psum storage')
    sram=summary.get('SRAM')
    if sram:
        a=sram['calibrated_macro']
        s=anchors['SRAM'].get(a['id']+'_'+a['corner'])
        if s is None:
            raise ValueError('SRAM macro is not an included E/F anchor')
        macros=int(sram['macros'])
        traffic=sram['traffic']
        dynamic=(traffic.get('read_words',0)*s['Eread_internal_pJ']+traffic.get('write_words',0)*s['Ewrite_internal_pJ'])*1e-12
        leakage=macros*s['leakage_ce_off_uW']*1e-6*elapsed_s
        rows.append(make_row('shared_SRAM','library_calibrated',macros*s['area_um2']*1e-6,dynamic+leakage,elapsed_s,
            internal_dynamic_J=dynamic,leakage_J=leakage,macro=a['id'],macros=macros,
            physical_bytes=sram.get('physical_bytes'),requested_clock_hz=sram['clock_hz'],
            period_eligible=sram['clock_hz']<=s['max_clock_by_period_hz'],
            boundary=s['boundary'],external_mux_NoC_CTS_energy_J=None))
        unknown.append('SRAM mux/NoC/CTS, clocked-idle macro energy, and custom CIM bitcell/output visibility')
    # Legacy operation prices stay separate from circuit anchors.
    actions=summary.get('actions',{})
    for name,price in anchors['explicit_legacy_proxies_pJ'].items():
        count=nonnegative(actions.get(name,0),name)
        if count:
            rows.append(make_row(name,'legacy_proxy',None,count*price*1e-12,elapsed_s,
                actions=count,pJ_per_action=price,boundary=anchors['proxy_note']))
    r=summary.get('random_interface',{})
    if r.get('calibrated_endpoint_two_state_energy_J') is not None:
        rows.append(make_row('local_PRNG_endpoints','external_calibrated_subtotal',
            r.get('calibrated_endpoint_area_mm2'),r['calibrated_endpoint_two_state_energy_J'],elapsed_s,
            boundary='Imported service endpoint subtotal only; not repriced, not clock-gating remeasured.'))
    unknown += ['BF16 MAC array area / clock-idle power / implemented 500MHz pipeline',
        'HBM PHY/controller/stack state and command energy; bandwidth-only timing is not energy evidence',
        'Nonlinear P8 comparator/AND/drivers, format conversion and selector/softmax control not covered by counter/restore',
        'ICG cells, always-on wake control, CTS, timing repair, physical interconnect and package overhead']
    # Covered action aliases must not be added as extra unknown energy for the
    # same gates, though the proxy/shape limitations remain on their module row.
    covered={'SC_W8_magnitude_AND','SC_product_sign_XOR','SC_weighted_bitplane_compress_bit_work',
             'SC_signed_temporal_accumulate','SC_bucket_route','SC_bucket_shift_reduce',
             'SC_coefficient16_restore'} if usage.get('counter') else set()
    unpriced=summary.get('unpriced_actions',{})
    if isinstance(unpriced,list):
        unpriced={k:1 for k in unpriced}
    for name,count in unpriced.items():
        if count and name not in covered:
            unknown.append('TLM unpriced action: '+name)
    known=sum(r['energy_J'] for r in rows if r['energy_J'] is not None)
    area=sum(r['area_mm2'] for r in rows if r['area_mm2'] is not None)
    counter_restore=[r for r in rows if 'accounting' in r]
    no_gate=sum(r['accounting']['conditional_no_gating_J'] for r in counter_restore)
    ideal_gate=sum(r['accounting']['conditional_ideal_gating_J'] for r in counter_restore)
    selected=sum(r['energy_J'] for r in counter_restore)
    other=known-selected
    sensitivity=[]
    for removed in (0.0,0.5,0.8,1.0):
        value=no_gate-removed*(no_gate-ideal_gate)
        sensitivity.append(dict(idle_dynamic_removed_fraction=removed,counter_restore_J=value,
            priced_subtotal_J=other+value,priced_subtotal_average_W=(other+value)/elapsed_s,
            excludes='Unmeasured ICG/CTS/wakeup/control power; not full-chip energy'))
    return dict(schema_version=1,elapsed_s=elapsed_s,core_hz=core_hz,total_core_cycles=total_cycles,
        modules=rows,priced_subtotal_J=known,priced_subtotal_average_W=known/elapsed_s,
        known_area_subtotal_mm2=area,full_chip_energy_J=None,full_chip_average_W=None,full_chip_area_mm2=None,
        counter_restore_only_clock_gating=dict(no_gating_J=no_gate,ideal_gating_J=ideal_gate,
            selected_J=selected,sensitivity=sensitivity,
            maximum_dynamic_saving_J=no_gate-ideal_gate,
            limitation='Conditional upper-bound savings, not measured ICG/CTS; area/power overhead unpriced.'),
        unpriced=sorted(set(unknown)),input_contract=usage,
        warnings=anchors['limits'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('summary',type=Path)
    p.add_argument('--usage',type=Path,help='Explicit per-instance occupancy JSON; defaults to summary.ppa_usage')
    p.add_argument('--anchors',type=Path,default=Path(__file__).with_name('PPA_ANCHORS.json'))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    summary=read(args.summary)
    usage=read(args.usage) if args.usage else summary.get('ppa_usage') or usage_from_tlm(summary)
    result=estimate(summary,usage,read(args.anchors))
    result['source_sha256']={'RESULT_SUMMARY.json':sha(args.summary),'PPA_ANCHORS.json':sha(args.anchors)}
    if args.usage:
        result['source_sha256']['usage.json']=sha(args.usage)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
