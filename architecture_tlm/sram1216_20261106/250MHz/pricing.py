"""Action-based calibrated budget; no measured power scaled by frequency.

New small variants keep PV state/control, use arithmetic-only area subtraction,
and expose their unmeasured interfaces. Whole-chip shared supports remain owned
once by the host. All areas in this output already include the0.81 factor.
"""
import json,math
from pathlib import Path
from architecture_tlm.module_refresh_20261107.bindings import core_budget
HERE=Path(__file__).parent/'vendor_attention'
def price(r):
 c=r['resource_contract']['configuration'];a=r['actions'];m=r['memory'];T=r['time_ns'];ms=T/1e6
 cal=json.loads((HERE/'CALIBRATION.json').read_bytes());other=json.loads((HERE/'OTHER_PRICES.json').read_bytes())
 u=cal['TT250_units'];w=cal['new_wrappers'];area={};dynamic={};background={};statuses={}
 def add(label,area55,dyn_pJ,idle_W,status='TT250 calibrated activity; component composition estimate'):
  area[label]=area55;dynamic[label]=dyn_pJ/1e6;background[label]=idle_W*T/1000;statuses[label]=status
 def pair_cost(top,mode,operations):
  z=u[top]['groups'][mode];idle=next(u[top]['groups'][x] for x in ('idle','idle_hold','idle_gated') if x in u[top]['groups'])
  gross=z['gross_pJ_per_operation'];duration_ns=gross/z['total_W']/1000
  return operations*(gross-idle['total_W']*duration_ns*1000),idle['total_W']
 q=w['qk/mixed'];fidle=u['db_fma16_c4']['groups']['idle_hold']['total_W'];frate=q['gross_pJ_per_operation']-fidle*q['window_ns']*1000/q['operations']
 fm_count=a.get('digital_BF16_MAC',0);qk_count=a.get('attention_QK_MAC',0)
 add('shared_FMA_pool',c['lanes']/16*q['area55_mm2'],(fm_count+qk_count)*frate,c['lanes']/16*fidle,'TT250 wrapper active; sameTT FMA16 idle_hold proxy; pool area counted once')
 fpadd=other['fp32_add_incremental_pJ'];fpadd_area=other['fp32_add_area55_mm2']
 add('final_FP32_reduction',c['reduction']*fpadd_area,a.get('digital_FP32_reduce_ADD',0)*fpadd,c['reduction']*other['fp32_add_idle_W'],'SS100 FP32 ADD proxy;250MHz II/latency contract not new STA')
 layers=sum(p['stage']=='attention' for p in r['phases'])
 groups=8*layers if qk_count else 0
 n1,i1=pair_cost('screen_norm16','group',groups);n2,i2=pair_cost('screen_top16','feature',groups);n3,_=pair_cost('screen_top16','token',groups)
 add('SparQ_top_and_norm',c['norm']*(u['screen_norm16']['area55_mm2']+u['screen_top16']['area55_mm2']),n1+n2+n3,c['norm']*(i1+i2))
 n,idle=pair_cost('ab_both','work',a.get('sampler_queries',0));add('Ising_sampler',c['sampler']*u['ab_both']['area55_mm2'],n,c['sampler']*idle)
 # Full4-lane mapped PV includes128FP32 values and2x32B/head. Smaller
 # variants remove only mapped arithmetic lanes, retain every state bit,
 # and carry a selector/control reserve; no blanket division by lane count.
 pv=w['pv/work64'];pa=pv['area55_mm2']-(4-c['pv'])*cal['PV_arithmetic_lane_area55_mm2']
 selector_reserve=0 if c['pv']==4 else .01*pv['area55_mm2'];pa+=selector_reserve
 pidle=u['bf_vacc16']['groups']['idle_gated']['total_W']*pa/u['bf_vacc16']['area55_mm2']
 prate=pv['gross_pJ_per_operation']-pidle*pv['window_ns']*1000/pv['operations']
 add('PV_ADD_state_and_word_buffers',32*pa,a.get('PV_ADD',0)*prate,32*pidle,'PV4 measured; PV2/1 lane-only area subtraction plus1%selector reserve; perADD energy held atPV4 with25%sensitivity')
 unique=a.get('unique_V',0);samples=a.get('samples',0);frac=min(1,max(0,(unique/max(groups,1)-8)/120))
 cold,ci=pair_cost('bf_vctrl4','cold',samples);reuse,_=pair_cost('bf_vctrl4','reuse',samples)
 add('V_address_cache_descriptor_control',8*u['bf_vctrl4']['area55_mm2'],cold*frac+reuse*(1-frac),8*ci)
 # Fixed-function transpose wiring, boundedholding and read selection.
 big=c['transpose']=='big';regbytes=8*(2048 if big else 512)+1024
 mux=8*((2048*7) if big else (1024*3))+8*256*3+8*256
 raw=regbytes*8*7.2+mux*3.96+8*(12 if big else 8)*11.88
 tags=m['SRAM']['by_tag'];read_bytes=lambda names:sum(tags.get(k,{}).get('read_words',0)*16 for k in names)
 held=read_bytes(('selected_K_transpose_read','coarse_K_operand','selected_K_operand'))
 capture=other['capture_pJ_per64B'];hold_idle=other['holding_idle_W_per_byte']
 add('QK_transpose_input_buffers',raw*.81/1e6,2*held/64*capture,regbytes*hold_idle,'cell-count area;2xexisting holding capture energy allowance covers capture+selection, SS100 proxy,0.5x–2x sensitivity')
 add('output_normalize_BF16',other['output_area55_mm2'],a.get('sample_output_BF16',0)*2*other['fp32_to_bf16_pJ'],other['output_idle_W'],'existing SS100 output conversion proxy; no new250 STA')
 # Explicit budget for wide-score max -> difference -> fixed/LUT address.
 # Does not relabel earlier absoluteS12 hardware as this implementation.
 front_area=4*fpadd_area+.008+64*other['holding_area55_per_byte']
 explicit_front=r.get('explicit_front',False)
 front_ops=a.get('wide_score_quantize',0) if explicit_front else a.get('FP32_to_S12',0)
 front_dynamic=front_ops*(2*fpadd+other['fp32_to_bf16_pJ'])+front_ops*4/64*capture
 add('wide_score_front_reserve',c['sampler']*front_area,front_dynamic,c['sampler']*64*hold_idle,'unmeasured wide max/subtract/quantize reserve:4 FP32 add-class lanes pluscompare/convert/control; outside tested numerical trace; latency allowance separately reported')
 activation_bytes=read_bytes(('QKV_activation_to_local','O_activation_to_local','lm_head_activation_to_local'))
 add('ordinary_activation_holding',other['activation_hold_bytes']*other['holding_area55_per_byte'],activation_bytes/64*capture,other['activation_hold_bytes']*hold_idle,'existing holding proxy; actual full-run captures; not extra weight or threshold array')
 # Dedicated512KiB Attention plus shared160KiB ordinary weight slots.
 area_logic=sum(area.values());sram_macros=(512+160)//4
 area['attention512_weight160_SRAM']=sram_macros*.03322622205*.81
 # Whole-run accounting includes FFN state, metadata and prefetch events once.
 sr=sum(v.get('read_words',0) for v in tags.values())
 sw=sum(v.get('write_words',0) for v in tags.values())
 sram_read,sram_write,sram_leak=(12.0293,16.2931,1.9734e-6) if explicit_front else (10.0527,13.9599,7.7544e-6)
 sram_pJ=sr*sram_read+sw*sram_write
 dynamic['SRAM_all_attention_used_events']=sram_pJ/1e6
 background['attention512_weight160_SRAM']=sram_macros*sram_leak*T/1000
 # Correct inputmax extra read has not been issued by the old trace actor.
 if not explicit_front:
  dynamic['wide_score_extra_SRAM_read_reserve']=front_ops*4/16*sram_read/1e6
 # Explicit front emits both SRAM passes already. One finite projection FIFO
 # serves QKV/O/lm_head; charge actual captures and retain unknown control/leak.
 fifo=r.get('ordinary_contract',{}).get('FIFO_payload_bytes',0)
 if fifo:
  add('projection_FIFO_payload',fifo*other['holding_area55_per_byte'],
      a.get('ordinary_FIFO_capture_bytes',0)/64*capture*2,0,
      'register payload area and2xcapture selection proxy; leakage/control unpriced')
 # Shared ingress payload storage is distinct from the existing32KiB
 # SRAM reservation. Allocate once only when estimating standalone ownership.
 ext_bytes=sum(v['issued_bytes'] for v in m['by_kind'].values())
 dynamic['shared_DMA_capture']=ext_bytes/64*capture/1e6
 holding_B=m.get('ingress',{}).get('holding_bytes',24576)
 assert holding_B in (16384,24576)
 holding_scale=holding_B/24576
 holding_name='DMA%dKiB_holding'%(holding_B//1024)
 background['shared_'+holding_name]=other['DMA24_idle_W']*holding_scale*T/1000
 dynamic['RMSNorm_RoPE_vector_proxy']=layers*other['vector_uJ_per_layer']
 dynamic['projection_BF16_rounding']=8704*layers*other['fp32_to_bf16_pJ']/1e6 if fm_count else 0
 shared_area={holding_name:other['DMA24_area55_mm2']*holding_scale,
     'vector128_norm32_DMAreserve32_SRAM':48*.03322622205*.81,
     'vector_codec_RMSNorm_RoPE_reserve':other['format_area55_mm2']}
 background['shared_vector_norm_DMA_SRAM']=48*sram_leak*T/1000
 background['shared_vector_codec_reserve']=other['format_idle_W']*T/1000
 # Complete compact1216 ownership:168 Attention/weight +48 support +88 FFN.
 # All per-event SRAM energy above already covers the entire executed trace.
 area['FFN_CIM256_state96_SRAM']=88*.03322622205*.81
 background['FFN_CIM256_state96_SRAM']=88*sram_leak*T/1000
 cores=r['short_FFN_contract']['physical_cores'];frames=r.get('kernel_active',{})
 # Short-T/C19 has no PPA yet. Retain predecessor C20/T64 *per-frame work*
 # as a separately labelled reference scenario, granting no T/64 energy saving.
 # This is neither measured short-T energy nor a mathematically strict bound.
 ffn_reference_pJ=frames.get('GU_frames',0)*(9926.4-1.288e-3*264*1000)+frames.get('Wd_M128_frames',0)*(5544-1.288e-3*264*1000)
 add('FFN_shared_pool_T64_frame_energy_PROXY',cores*.9694793124,ffn_reference_pJ,cores*1.288e-3,
     'C19/T16-T32 PPA null; C20 area and unchanged measuredT64 incremental work/frame reference, not time-scaled power')
 ffn_label='FFN_shared_pool_T64_frame_energy_PROXY'
 ffn_measured=core_budget(frames,T,cores,250)
 if ffn_measured['total_mJ'] is not None:
  area.pop(ffn_label);dynamic.pop(ffn_label);background.pop(ffn_label);statuses.pop(ffn_label)
  ffn_label='FFN_shared_pool_C19_shortT_measured'
  area[ffn_label]=ffn_measured['area55_mm2']
  dynamic[ffn_label]=ffn_measured['active_gross_mJ']*1000
  background[ffn_label]=ffn_measured['waiting_mJ']*1000
  statuses[ffn_label]='matchingTT250 shortT gross service plus stopped-clock waiting residency'
 vectors=a.get('common_state32_vectors',0)
 add('FFN_crossK_state32_arithmetic',2*.0524072268,
     vectors*(52.0366013072-.1372e-3*4*1000),2*.1372e-3,
     'TT250 measured arithmetic32-update; SRAM read/write separately counted')
 onchip_idle_clock=sum(dynamic.values())+sum(background.values());external={str(x):ext_bytes*8*x/1e6 for x in (4.,6.6,8.)}
 # Module root clocks and inputs are disabled outside service windows. Keep
 # leakage at all times. Existing idle-clock measurements are an explicit
 # upper sensitivity, not silently billed as active dynamic throughout stalls.
 gated_savings={}
 def gate(label,instances,idle,leak,active_ns):
  assert active_ns<=instances*T+1e-3,(label,active_ns,instances*T)
  gated_savings[label]=max(0,idle-leak)*max(0,instances*T-active_ns)/1000
 gate('shared_FMA_pool',c['lanes']/16,fidle,q['leakage_W'],(fm_count+qk_count)*q['window_ns']/q['operations'])
 gate('PV_ADD_state_and_word_buffers',32,pidle,pv['leakage_W']*pa/pv['area55_mm2'],a.get('PV_ADD',0)*pv['window_ns']/pv['operations']*4/c['pv'])
 for top,modes,instances in [('ab_both',[('work',a.get('sampler_queries',0))],c['sampler']),('screen_top16',[('feature',groups),('token',groups)],c['norm']),('screen_norm16',[('group',groups)],c['norm'])]:
  z=u[top]['groups'];idle=z['idle'];active=sum(n*z[mode]['gross_pJ_per_operation']/z[mode]['total_W']/1000 for mode,n in modes)
  gate(top,instances,idle['total_W'],idle['leakage_W'],active)
 vc=u['bf_vctrl4']['groups'];gate('V_address_cache_descriptor_control',8,ci,vc['idle_gated']['leakage_W'],samples*vc['cold']['gross_pJ_per_operation']/vc['cold']['total_W']/1000)
 gate('output_normalize_BF16',512,other['output_idle_W']/512,other['output_leak_W']/512,a.get('sample_output_BF16',0)*2*other['output_ns_per_operation'])
 onchip=onchip_idle_clock-sum(gated_savings.values())
 root_gates=c['lanes']//16+32+2*c['norm']+c['sampler']+8+8+1
 root_area=root_gates*11.88*.81/1e6
 area['additional_root_ICG_count_reserve']=root_area;area_logic+=root_area
 phases={}
 for p in r['phases']:phases[p['stage']]=phases.get(p['stage'],0)+p['duration_ns']/1000
 time_us=T/1000
 bykind=m['by_kind'];projected_BW={k:bykind[k+'_weights']['issued_bytes']/(phases[k]*1000) for k in ('QKV','O') if k in phases}
 totals=dict(attention_plus_pool_logic_mm2=area_logic,attention_pool_plus672KiB_mm2=sum(area.values()),standalone_with_shared_support_mm2=sum(area.values())+sum(shared_area.values()),onchip_uJ=onchip,onchip_average_W=onchip/time_us,external_uJ_by_pJ_per_bit=external,total_uJ_at4pJ=onchip+external['4.0'],total_average_W_at4pJ=(onchip+external['4.0'])/time_us)
 totals=dict(covered_area55_mm2=sum(area.values())+sum(shared_area.values()),
     onchip_mJ_with_FFN_reference_proxy=onchip/1000,
     priced_onchip_mJ_excluding_unknown_short_FFN=(onchip-dynamic[ffn_label]-background[ffn_label])/1000,
     short_FFN_measured_energy_mJ=ffn_measured['total_mJ'],whole_chip_measured_energy_mJ=None,
     proxy_total_mJ_at4pJ=(onchip+external['4.0'])/1000,
     proxy_onchip_average_W=onchip/time_us,proxy_system_average_W_at4pJ=(onchip+external['4.0'])/time_us,
     external_mJ_by_pJ_per_bit={k:v/1000 for k,v in external.items()})
 assert all(v>=0 for v in list(area.values())+list(dynamic.values())+list(background.values()))
 return dict(totals=totals,areas55_mm2=area,shared_support_area55_mm2=shared_area,
     FFN_core_calibration=ffn_measured,
     dynamic_uJ=dynamic,background_uJ_before_root_gating=background,root_gating_savings_uJ=gated_savings,
     price_status=statuses,source_calibration='vendor_attention/CALIBRATION.json; OTHER_PRICES.json; FFN TT250 handoff',
     latency=dict(executed_us=time_us,phases_us=phases,
         explicit_per_head_front=explicit_front,
         wide_score_front_allowance_us_included=phases.get('wide_score_front_allowance',0),
         legacy_front_and_extra_read_reserve_replaced=explicit_front),
     bandwidth=dict(logical_all_GBs=ext_bytes/T,QKV_O_logical_GBs=projected_BW,
         link_peak_GBs=136.4606,ideal_weight_supply_from_FMA_GBs=c['lanes']*.5,external_bytes=ext_bytes),
     sensitivity=dict(no_added_root_gate_onchip_uJ=onchip_idle_clock,
         PV2_unmeasured_energy_plusminus25_uJ=.25*dynamic['PV_ADD_state_and_word_buffers'],
         QK_buffer_energy_half_to_double_uJ=[.5*dynamic['QK_transpose_input_buffers'],2*dynamic['QK_transpose_input_buffers']]),
     limitations=['conditional action budget, not integrated chip PPA',
         'shortT/C19 area and energy unknown; predecessor area/frame energy reference explicitly retained',
         'TT250 arithmetic/sampling/SRAM with legacySS100 vector/reduction/converter/holding proxies',
         'root gating assumed; global CTS/NoC/PHY/pads and physical CIM interface not characterized',
         'score max/difference uses explicit73cycle uncontended macro per head, not new STA or PPL',
         'projection FIFO payload priced, control/selector detail/leakage unpriced; old sampler prep retained as small energy upper bound',
         'three captured Attention layers cycle across36: conditional workload replay, no new PPL',
         'external4/6.6/8pJ/bit sensitivity includes all bytes, not LPDDR measured background model',
         '1216KiB/304 physical4KiB banks, pool/ingress supports counted once'])
