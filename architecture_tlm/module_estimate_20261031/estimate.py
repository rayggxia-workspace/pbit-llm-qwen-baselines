"""Initial local replacement model; does not execute unified_v6 or DRAMSys."""
from pathlib import Path
import argparse,json,math,csv,hashlib

def estimate(i,nl_instances=256,attention_lanes=8):
    b=i['baseline'];n=i['ffn'];a=i['attention'];m=i['model']
    layers=m['num_hidden_layers'];D=m['hidden_size'];F=m['intermediate_size']
    frames=layers*(F//n['N'])*(D//n['M'])
    waves=layers*(F//n['N'])*math.ceil((D//n['M'])/nl_instances)
    frame_s=n['frame_cycles']/n['clock_hz'];new_down_s=waves*frame_s
    old_s=b['fma']['TPOT_ms']/1000
    attention_old_s=b['phase_ns']['attention_core']*1e-9
    other_s=old_s-attention_old_s
    # This is an explicit envelope, not a confidence interval or cycle simulation.
    # Lower: 64 add lanes finish the S64 useful work, all V already available.
    # Upper: retain the complete measured S128 PV stage as a service allowance.
    pv_lower_us=a['S64_PV_ADD_count']/a['arithmetic_lanes_per_group']/a['clock_hz']*1e6
    group_lower_us=a['pre_PV_us']+pv_lower_us
    group_upper_us=a['old_S128_group_us']
    batches=layers*math.ceil(a['kv_heads_per_layer']/attention_lanes)
    new_att_lower=batches*group_lower_us*1e-6
    new_att_upper=batches*group_upper_us*1e-6
    exposed_increase=max(0,new_down_s-b['down_busy_ns']*1e-9)
    old_down_stage_s=b['phase_ns']['FFN_AND_direct_down']*1e-9
    # Even complete overlap cannot make a whole down stage shorter than its compute.
    unavoidable_increase=max(0,new_down_s-old_down_stage_s)
    tlo=other_s+new_att_lower+unavoidable_increase
    thi=other_s+new_att_upper+exposed_increase
    # If new compute is faster, do not delete old memory/restore stalls speculatively.
    assert thi>=tlo>0
    total_activity_s=frames*frame_s
    active_J=frames*n['frame_pJ']*1e-12
    old_m=b['modules'];counter_old=old_m['FFN_counter'];old_gu=b['gu_tiles']
    old_down=b['down_tiles'];down_work_fraction=(old_down*2)/(old_gu+old_down*2)
    restore_down_fraction=old_down/(old_gu+old_down)
    def energy(t,hold_W):
        out={}
        for name,v in old_m.items():
            bg=(v.get('leakage_J') or 0)+(v.get('idle_clock_background_J') or 0)
            out[name]=v['energy_mJ_per_token']*1e-3-bg+bg*t/old_s
        out['FFN_counter']-=counter_old['work_increment_J']*down_work_fraction
        out['FFN_postscale_restore_proxy']-=old_m['FFN_postscale_restore_proxy']['work_increment_J']*restore_down_fraction
        # Keep GU physical pool/background. The new down kernel is separate.
        out['NL_Wd_active']=active_J
        inactive_instance_s=max(0,nl_instances*t-total_activity_s)
        out['NL_Wd_inactive_scenario']=inactive_instance_s*hold_W
        # Preserve old combined NL source as an explicit budget reserve only.
        # It is not a new source-only measurement; comparator overlap is disclosed.
        out['FFN_external_RNG_reserved_old_endpoint_budget']=out.pop('FFN_nonlinear_10_local_PRNG_endpoints')
        out.pop('Attention_existing_PRNG_endpoints')
        out['Attention_complete_sampler_S128_reserved_for_S64']=a['groups_per_token']*4*a['sampler_nJ_per_head_reserved_S128']*1e-9
        out['Attention_SparQ_logic']=a['groups_per_token']*a['screen_nJ']*1e-9
        adds=a['groups_per_token']*a['S64_PV_ADD_count'];lanes=attention_lanes*64
        active_lane_s=adds*a['PV_ADD_reference_ns_per_op']*1e-9
        out['PV_vector_adders']=adds*a['PV_ADD_pJ']*1e-12+max(0,lanes*t-active_lane_s)*a['PV_ADD_idle_W']
        # QK operation count is unchanged in this particular mapping:
        # old 75,497,472 selected +18,874,368 summary = new 75,497,472 coarse +18,874,368 selected.
        # Do not add an additional standalone QK price to the shared FMA row.
        known=sum(out.values())
        new_att_bytes=a['groups_per_token']*a['S64_KV_KiB']*1024
        new_bytes=b['dram_bytes']-b['old_attention_bytes']+new_att_bytes
        ext=new_bytes*64e-12+.05*t
        return dict(time_ms=t*1000,onchip_mJ=known*1000,onchip_W=known/t,
            external_proxy_mJ=ext*1000,with_external_proxy_mJ=(known+ext)*1000,
            with_external_proxy_W=(known+ext)/t,modules_mJ={k:v*1000 for k,v in out.items()},
            new_external_bytes=new_bytes,NL_inactive_instance_s=inactive_instance_s)
    corners=[dict(hold=state,**energy(t,power)) for t in (tlo,thi) for state,power in
             [('leakage_only_floor',n['leakage_proxy_W']),('measured_toggling_R_idle_diagnostic',n['idle_diagnostic_W'])]]
    ext_bytes=corners[0]['new_external_bytes'];peak=a['DDR4_channels']*a['DDR4_MT_s']*1e6*a['bus_bytes_per_channel']
    return dict(nl_instances=nl_instances,attention_parallel_KV_groups=attention_lanes,
        NL_frames=frames,NL_waves=waves,NL_output_utilization=frames/(waves*nl_instances),
        NL_compute_ms=new_down_s*1000,old_NL_compute_ms=b['down_busy_ns']*1e-6,
        exposed_NL_increase_allowance_ms=exposed_increase*1000,NL_active_mJ=active_J*1000,
        unavoidable_NL_increase_ms=unavoidable_increase*1000,
        NL_kernel_area55_mm2=nl_instances*n['area55_mm2'],
        attention_group_service_us=[group_lower_us,group_upper_us],attention_ms=[new_att_lower*1000,new_att_upper*1000],
        estimated_TPOT_ms=[tlo*1000,thi*1000],onchip_mJ=[min(x['onchip_mJ'] for x in corners),max(x['onchip_mJ'] for x in corners)],
        onchip_W=[min(x['onchip_W'] for x in corners),max(x['onchip_W'] for x in corners)],
        with_external_proxy_mJ=[min(x['with_external_proxy_mJ'] for x in corners),max(x['with_external_proxy_mJ'] for x in corners)],
        with_external_proxy_W=[min(x['with_external_proxy_W'] for x in corners),max(x['with_external_proxy_W'] for x in corners)],
        physical_storage=dict(NL_weight_bytes_per_bank=nl_instances*512,NL_weight_double_bank_bytes=nl_instances*1024,
            Attention_local_SRAM_reserved_bytes=attention_lanes*a['SRAM_per_lane_bytes'],old_shared_SRAM_bytes=b['shared_SRAM_bytes'],
            within_old_NL_bank=nl_instances*512<=b['local_weight_bank_bytes'],attention_reservation_within_old_shared=attention_lanes*a['SRAM_per_lane_bytes']<=b['shared_SRAM_bytes']),
        DDR4_bandwidth_floor_only=dict(peak_GBs=peak/1e9,ideal_ms=ext_bytes/peak*1000,
            at85percent_ms=ext_bytes/(peak*.85)*1000,at70percent_ms=ext_bytes/(peak*.7)*1000,
            actual_DDR4_TPOT_ms=None,explanation='data movement floor only; not full DDR4 runtime or DRAMPower energy'),corners=corners)

def run(path,out):
    raw=path.read_bytes();i=json.loads(raw);out.mkdir(parents=True,exist_ok=True)
    b=i['baseline']['fma'];assert math.isclose(b['covered_onchip_mJ_per_token']/b['TPOT_ms'],b['covered_onchip_average_W'],rel_tol=1e-12)
    assert i['baseline']['gu_tiles']==2*i['baseline']['down_tiles']
    cases=[estimate(i,n,a) for n,a in [(256,8),(128,8),(32,8),(256,4),(256,1)]]
    assert cases[0]['NL_frames']==1751040
    assert math.isclose(cases[0]['NL_active_mJ'],1.4704183296)
    assert cases[0]['physical_storage']['within_old_NL_bank']
    assert cases[2]['NL_compute_ms']>cases[1]['NL_compute_ms']>cases[0]['NL_compute_ms']
    assert cases[-1]['estimated_TPOT_ms'][0]>cases[0]['estimated_TPOT_ms'][0]
    for c in cases:
        for r in c['corners']:
            assert math.isclose(sum(r['modules_mJ'].values()),r['onchip_mJ'],rel_tol=1e-12)
            assert math.isclose(r['onchip_mJ']/r['time_ms'],r['onchip_W'],rel_tol=1e-12)
    result=dict(scope=i['scope'],input_sha256=hashlib.sha256(raw).hexdigest(),baseline=i['baseline']['fma'],cases=cases,
        complete_chip_energy_or_power=None,full_unified_TLM_or_DRAMSys_rerun=False,model_quality_verified=False,
        remaining=['S64 actual continuous stream and backpressure/memory contention','FFN external RNG source-only price, inactive/stop-source mode and stable input holding','GU restoration and cross-K/BF16 interfaces, 500MHz ordinary array and clock-domain integration','external HBM/DDR4 actual command/background/PHY energy; old64pJ/B is only a proxy'])
    (out/'RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    with (out/'COMPARISON.csv').open('w',encoding='utf-8-sig',newline='') as f:
        cols=['nl_instances','attention_parallel_KV_groups','estimated_TPOT_ms','onchip_mJ','onchip_W','with_external_proxy_mJ','with_external_proxy_W','NL_compute_ms','NL_kernel_area55_mm2']
        w=csv.DictWriter(f,fieldnames=cols,lineterminator='\n');w.writeheader();w.writerows({k:c[k] for k in cols} for c in cases)
    print(json.dumps(dict(status='passed',baseline_ms=b['TPOT_ms'],baseline_mJ=b['covered_onchip_mJ_per_token'],cases=[{k:c[k] for k in ['nl_instances','attention_parallel_KV_groups','estimated_TPOT_ms','onchip_mJ','onchip_W','with_external_proxy_mJ']} for c in cases],DDR4_floor=cases[0]['DDR4_bandwidth_floor_only']),ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,default=Path(__file__).with_name('INPUTS.json'));p.add_argument('--out',type=Path,default=Path(__file__).with_name('results'));a=p.parse_args();run(a.inputs,a.out)
