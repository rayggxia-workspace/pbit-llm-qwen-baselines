"""Reprice immutable TLM activity using explicit circuit/library anchors.

This is an energy model, not an execution or PPL run. Core frequency is a
target; reference dynamic energy per edge is held constant, leakage per second.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def state_energy(active, idle, *, seconds, cycles, work, ref_work=1., instances=1., scale=1., idle_dynamic_keep=1., on_cycles=None):
    """Background plus work increment; never add a gross action price twice.

    Anchor powers are uW at 100MHz. work/ref_work is the number of 10ns
    reference active-cycle equivalents, summed over physical lanes.
    """
    values=(seconds,cycles,work,instances,scale,idle_dynamic_keep)
    if any(not math.isfinite(v) or v<0 for v in values) or ref_work<=0 or idle_dynamic_keep>1:
        raise ValueError('nonnegative finite accounting inputs required')
    if work/ref_work>instances*cycles*(1+1e-9):
        raise ValueError('useful operations exceed physical instance-cycle capacity')
    on=work/ref_work if on_cycles is None else on_cycles
    if not math.isfinite(on) or on<work/ref_work-1e-6 or on>instances*cycles*(1+1e-9):
        raise ValueError('invalid clock-on instance cycles')
    leak=idle['leakage_uW']*1e-6*seconds*instances*scale
    idle_edge=max(0.,idle['power_uW']-idle['leakage_uW'])*.01
    idle_clock=idle_edge*(on+idle_dynamic_keep*(cycles*instances-on))*scale*1e-12
    increment=(active['power_uW']-idle['power_uW'])*.01*(work/ref_work)*scale*1e-12
    if increment < -1e-12:
        raise ValueError('negative activity increment')
    return dict(energy_J=leak+idle_clock+increment,leakage_J=leak,
        idle_clock_background_J=idle_clock,work_increment_J=increment,
        instances=instances,shape_scale=scale,idle_dynamic_keep=idle_dynamic_keep,on_instance_cycles=on)


def merged_bitwork(bins,samples,pipe_every=2):
    lw=8+2*(bins-1)
    aw=1+(64*127*samples).bit_length()+2*(bins-1)
    tree=sum((64>>level)*(lw+level) for level in range(1,7))
    regs=sum((64>>level)*(lw+level) for level in range(1,7) if level%pipe_every==0)
    return dict(aw=aw,tree_and_temporal_adder_bits=tree+aw,pipeline_and_state_bits=regs+aw,
        bitwork=tree+regs+2*aw)


def memory_energy(read_bytes,write_bytes,capacity_bytes,anchor,seconds):
    macros=math.ceil(capacity_bytes/4096)
    reads=math.ceil(read_bytes/16);writes=math.ceil(write_bytes/16)
    dynamic=(reads*anchor['Eread_internal_pJ']+writes*anchor['Ewrite_internal_pJ'])*1e-12
    leak=macros*anchor['leakage_ce_off_uW']*1e-6*seconds
    return dict(energy_J=dynamic+leak,internal_dynamic_J=dynamic,leakage_J=leak,
        area_mm2=macros*anchor['area_um2']*1e-6,macros=macros,read_words=reads,write_words=writes)


def estimate(s,a,*,counter_gate=False,digital_gate=False,b7_scale=None):
    c=s['config'];f=c['ffn'];acts=s['actions'];t=s['metrics']['elapsed_ns']*1e-9;cycles=t*c['core_hz']
    if f['mode']!='sc' or f['engines']*64!=2048 or c['attention']['mode']!='screen_pv':
        raise ValueError('this recorded budget is for the 32x64 SC screen_pv candidate')
    scale=b7_scale or a['b7_bitwork_scale']
    rows=[]
    def add(name,v,evidence,**extra):
        if isinstance(v,(int,float)):v={'energy_J':v}
        rows.append(dict(module=name,**v,evidence=evidence,**extra))
    p=a['counter_g2' if counter_gate else 'counter_g0']
    gu=s['FFN_activity']['SC_4bucket_tiles']*64
    down=s['FFN_activity']['SC_7bucket_tiles']*64
    # Gross-vs-idle increment is measured per completed 64-sample frame.
    # Scaling sample work to128 remains an explicit proxy; not a new B7 run.
    ref_cycles=p['modes']['continuous']['window_ns']/p['modes']['continuous']['operations_per_window']/10
    work=ref_cycles*(gu+down*f['nonlinear_samples']/64.)
    v=state_energy(p['modes']['continuous'],p['modes']['idle'],seconds=t,cycles=cycles,work=work,instances=2048,scale=scale)
    v['area_mm2']=2048*p['area_um2']*scale*1e-6
    add('FFN_counter',v,'B4 real PT; B7 structural-width proxy; g2 actual ICG' if counter_gate else 'B4 real PT; B7 structural-width proxy',
        output_frames=gu+down,gu_frames=gu,down_frames=down,includes='weight gating/sign/bin alignment/reduction/time count; no SNG/SRAM')
    # Combined legacy restore remains an explicitly conservative postscale proxy.
    # Do NOT add SC_bucket_shift_reduce, AND weight gates or old seven counters.
    ar=a['legacy_restore'];ratio=a['legacy_restore_b7_ratio']
    active={'power_uW':ar['restore_cadence72']['mean_mW']*1000,'leakage_uW':ar['restore_cadence72']['leakage_mW']*1000}
    idle={'power_uW':ar['restore_idle']['mean_mW']*1000,'leakage_uW':ar['restore_idle']['leakage_mW']*1000}
    inc=(gu+down)*ar['restore_cadence72']['incremental_pJ_per_operation']*ratio*1e-12
    resources=s['clock_gating']['resources'];period=1e9/c['core_hz']
    restore_on=min(t*1e9,sum(resources[k]['busy_ns'] for k in ('ffn_SC_bucket_shift_reduce','ffn_SC_coefficient16_restore')))*f['restore_lanes']/period
    v=state_energy(idle,idle,seconds=t,cycles=cycles,work=0,instances=f['restore_lanes'],scale=ratio,idle_dynamic_keep=.1 if digital_gate else 1.,on_cycles=restore_on)
    v['energy_J']+=inc;v['work_increment_J']=inc
    v['area_mm2']=f['restore_lanes']*a['legacy_restore_b7_area_um2']*1e-6
    add('FFN_postscale_restore_proxy',v,'old combined restore retained as an upper proxy; no separate bucket energy')
    # Activity-increment proxy for wide integer partials. FP32 add is a measured
    # circuit proxy here, not a claim that the intended INT64 adder is floating.
    mac=a['digital_mac']['modes'];fa=a['fp32_add']['modes']
    keep=.1 if digital_gate else 1.
    mac_on=max(acts['bf16_mac'],resources['mac']['busy_ns']/period*c['macs_per_cycle'])
    v=state_energy(mac['continuous'],mac['idle'],seconds=t,cycles=cycles,work=acts['bf16_mac'],instances=c['macs_per_cycle'],idle_dynamic_keep=keep,on_cycles=mac_on)
    v['area_mm2']=c['macs_per_cycle']*a['digital_mac']['area_um2']*1e-6
    add('ordinary_BF16_MACs',v,'measured CE-only MAC; digital ICG scenario removes90% idle dynamic' if digital_gate else 'measured CE-only nonfused MAC, idle included')
    add_count=acts.get('V_selection_add',0)
    vec_on=max(add_count,resources.get('vector',{}).get('busy_ns',0)/period*c['vector_lanes'])
    v=state_energy(fa['continuous'],fa['idle'],seconds=t,cycles=cycles,work=add_count,instances=c['vector_lanes'],idle_dynamic_keep=keep,on_cycles=vec_on)
    v['area_mm2']=c['vector_lanes']*a['fp32_add']['area_um2']*1e-6
    add('PV_vector_adders',v,'FP32 addition representative lanes; other vector functions separate')
    wide_count=acts.get('SC_cross_tile_add64',0)
    adder_inc=(fa['continuous']['power_uW']-fa['idle']['power_uW'])*.01
    add('wide_partial_activity_proxy',wide_count*2*adder_inc*1e-12,'two FP32-add activity increments per INT64 update; pending INT64 power',area_mm2=f['accumulate_lanes']*a['acc64_area_um2']*1e-6)
    sr=s['SRAM'];macro=sr['calibrated_macro']
    add('shared_SRAM',s['energy_J']['SRAM_internal']+s['energy_J']['SRAM_leakage'],'existing calibrated SS E macros; unchanged exact TLM counters',area_mm2=sr['area_mm2'])
    # Separate physical memories: shared SRAM plus one digital operand tile,
    # local SC ping/pong SRAM, DMA response slots. No per-sample weight read.
    mem=a['sram_E_SS'];loc=s['FFN_contract']['local_state']
    v=memory_energy(0,acts['SC_local_weight_program_byte'],loc['weight_hold_bytes'],mem,t)
    add('local_CIM_SRAM_base',v,'ordinary SRAM write/leakage proxy for CIM storage base; full-parallel readout/custom peripheral excluded')
    v=memory_energy(acts['digital_local_operand_read_byte']+acts['digital_local_activation_read_byte'],acts['digital_local_operand_write_byte']+acts['digital_local_activation_write_byte'],s['digital_operand_contract']['operand_capacity_bytes']+s['digital_operand_contract']['activation_peak_bytes'],mem,t)
    add('digital_local_buffers',v,'same calibrated macro for distinct local operand/activation buffers')
    response_read=acts['digital_DMA_response_buffer_read_byte']+acts['SC_DMA_response_buffer_read_byte']
    response_write=acts['digital_DMA_response_buffer_write_byte']+acts['SC_DMA_response_buffer_write_byte']
    add('DMA_response_buffers',memory_energy(response_read,response_write,s['tile_pipeline']['shared_response_capacity_bytes'],mem,t),'SRAM implementation proxy for already counted response slots, not a new capacity')
    # Solve independently counted GU and ten-endpoint NL demands.
    delivered=s['FFN_activity']['SC_accepted_stream_samples'];updates=acts['locality_endpoint_update']
    if (updates-delivered)%9:raise ValueError('inconsistent local endpoint work')
    nl=(updates-delivered)//9;gx=delivered-nl
    if 192*nl!=acts['AND_threeway_comparison'] or gx<0:raise ValueError('nonlinear stream count mismatch')
    a0=a['ffn_frontend'];v=state_energy(a0['active'],a0['idle'],seconds=t,cycles=cycles,work=gx*34/32.,instances=1)
    v['area_mm2']=a0['area_um2']*1e-6
    add('FFN_shared64_input_frontend',v,'measured K32 N64 frontend; K64 small control delta remains proxy; includes local LFSR/comparators/distribution')
    p=a['prng']['bivium'];v=state_energy(p['stream'],p['idle'],seconds=t,cycles=cycles,work=10*nl,instances=10)
    v['area_mm2']=10*p['area_um2']*1e-6
    add('FFN_nonlinear_10_local_PRNG_endpoints',v,'actual Bivium endpoint price including200 native compares, covers192 used compares; not added again',updates=10*nl,capacity_comparisons_per_update=200)
    erows=[]
    for port in s['random_interface']['endpoint_costs']:
        p=a['prng']['lfsr' if port['kind']=='lfsr32' else 'bivium']
        v=state_energy(p['stream'],p['idle'],seconds=t,cycles=cycles,work=port['active_cycles'],instances=1)
        erows.append(v['energy_J'])
    add('Attention_existing_PRNG_endpoints',sum(erows),'existing actual endpoint counts, reference leakage split corrected',area_mm2=s['random_interface']['calibrated_endpoint_area_mm2'])
    lut=a['sigmoid_lut'];lm=lut['modes'];n=acts['SC_sigmoid_ROM9']+acts['rng_sigmoid_lut_lookup']
    v=state_energy(lm['random'],lm['idle'],seconds=t,cycles=cycles,work=n,instances=f['lut_lanes']+c['random']['lut_lanes'])
    v['area_mm2']=(f['lut_lanes']+c['random']['lut_lanes'])*lut['area_um2']*1e-6
    add('FFN_and_selector_sigmoid_tables',v,'new actual signed8 LUT; lookup once per drive, no resampling lookup fee')
    # Preserve low-impact old vector/nonlinear proxies only for residual work.
    residual=max(0,acts['vector_op']-add_count)
    add('other_vector_and_nonlinear_proxy',(residual+10*acts['nonlinear_op'])*1e-12,'legacy1pJ vector/10pJ nonlinear residual, not calibrated full norm/softmax')
    covered=sum(v['energy_J'] for v in rows)
    area=sum(v.get('area_mm2',0) for v in rows)
    external_bytes=acts['dram_read']+acts.get('dram_write',0)
    dram_proxy=external_bytes*64e-12+.05*t
    return dict(elapsed_s=t,elapsed_ms=t*1000,target_hz=c['core_hz'],counter_gate=counter_gate,
        digital_gate_scenario=digital_gate,b7_scale=scale,modules=rows,
        covered_onchip_J=covered,covered_onchip_W=covered/t,covered_area_mm2=area,
        legacy_external_budget_J=dram_proxy,legacy_external_budget_W=dram_proxy/t,
        conditional_budget_with_legacy_external_J=covered+dram_proxy,
        conditional_budget_with_legacy_external_W=(covered+dram_proxy)/t,
        full_calibrated_system_J=None,full_calibrated_system_W=None,
        unpriced_key=['custom full-parallel CIM readout/driver and global SRAM/interconnect/CTS',
            'B7 integrated counter/postscale and digital gated-array500MHz implementation',
            'HBM stack/controller/PHY power: timing-only HBM trace has no current calibration'],
        optional_only='Ising feedback/arbiter not active in screen_pv; its cost does not belong in this result')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('summary',type=Path);p.add_argument('--anchors',type=Path,default=Path(__file__).with_name('ANCHORS.json'))
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    s=read(args.summary);a=read(args.anchors)
    result={'input_sha256':sha(args.summary),'anchors_sha256':sha(args.anchors),'rows':{
        name:estimate(s,a,counter_gate=cg,digital_gate=dg) for name,cg,dg in (
            ('new_counter_CE',False,False),('counter_real_ICG',True,False),('counter_ICG_plus_digital_gate_candidate',True,True))}}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':main()
