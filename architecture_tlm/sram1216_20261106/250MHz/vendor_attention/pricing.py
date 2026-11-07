"""Action-based calibrated budget; no measured power scaled by frequency.

New small variants keep PV state/control, use arithmetic-only area subtraction,
and expose their unmeasured interfaces. Whole-chip shared supports remain owned
once by the host. All areas in this output already include the0.81 factor.
"""
import json,math
from pathlib import Path
HERE=Path(__file__).parent
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
 groups=8 if qk_count else 0
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
 front_ops=a.get('FP32_to_S12',0)
 front_dynamic=front_ops*(2*fpadd+other['fp32_to_bf16_pJ'])+front_ops*4/64*capture
 add('wide_score_front_reserve',c['sampler']*front_area,front_dynamic,c['sampler']*64*hold_idle,'unmeasured wide max/subtract/quantize reserve:4 FP32 add-class lanes pluscompare/convert/control; outside tested numerical trace; latency allowance separately reported')
 add('ordinary_activation_holding',other['activation_hold_bytes']*other['holding_area55_per_byte'],(5120+8192)/64*capture,other['activation_hold_bytes']*hold_idle,'existing holding proxy; not extra weight or threshold array')
 # Dedicated512KiB Attention plus shared160KiB ordinary weight slots.
 area_logic=sum(area.values());sram_macros=(512+160)//4
 area['attention512_weight160_SRAM']=sram_macros*.03322622205*.81
 # All actually accessed SRAM words, minus the unrelated GU prefetch.
 excluded={k:v for k,v in tags.items() if k.startswith('GU_')}
 sr=sum(v.get('read_words',0) for k,v in tags.items() if k not in excluded)
 sw=sum(v.get('write_words',0) for k,v in tags.items() if k not in excluded)
 sram_pJ=sr*10.0527+sw*13.9599
 dynamic['SRAM_all_attention_used_events']=sram_pJ/1e6
 background['attention512_weight160_SRAM']=sram_macros*7.7544e-6*T/1000
 # Correct inputmax extra read has not been issued by the old trace actor.
 dynamic['wide_score_extra_SRAM_read_reserve']=front_ops*4/16*10.0527/1e6
 # Shared ingress payload storage24KiB is distinct from the existing32KiB
 # SRAM reservation. Allocate once only when estimating standalone ownership.
 ext_bytes=sum(v['issued_bytes'] for k,v in m['by_kind'].items() if not k.startswith('GU_'))
 dynamic['shared_DMA_capture']=ext_bytes/64*capture/1e6
 background['shared_DMA24KiB']=other['DMA24_idle_W']*T/1000
 dynamic['RMSNorm_RoPE_vector_proxy']=other['vector_uJ_per_layer']
 dynamic['projection_BF16_rounding']=8704*other['fp32_to_bf16_pJ']/1e6 if fm_count else 0
 shared_area=dict(DMA24KiB_holding=other['DMA24_area55_mm2'],vector128_norm32_DMAreserve32_SRAM=48*.03322622205*.81,vector_codec_RMSNorm_RoPE_reserve=other['format_area55_mm2'])
 background['shared_vector_norm_DMA_SRAM']=48*7.7544e-6*T/1000
 background['shared_vector_codec_reserve']=other['format_idle_W']*T/1000
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
 phases={p['stage']:p['duration_ns']/1000 for p in r['phases']};time_us=T/1000
 bykind=m['by_kind'];projected_BW={k:bykind[k+'_weights']['issued_bytes']/(phases[k]*1000) for k in ('QKV','O') if k in phases}
 totals=dict(attention_plus_pool_logic_mm2=area_logic,attention_pool_plus672KiB_mm2=sum(area.values()),standalone_with_shared_support_mm2=sum(area.values())+sum(shared_area.values()),onchip_uJ=onchip,onchip_average_W=onchip/time_us,external_uJ_by_pJ_per_bit=external,total_uJ_at4pJ=onchip+external['4.0'],total_average_W_at4pJ=(onchip+external['4.0'])/time_us)
 assert all(v>=0 for v in list(area.values())+list(dynamic.values())+list(background.values()))
 return dict(totals=totals,areas55_mm2=area,shared_support_area55_mm2=shared_area,dynamic_uJ=dynamic,background_uJ_before_root_gating=background,root_gating_savings_uJ=gated_savings,price_status=statuses,source_calibration='CALIBRATION.json; OTHER_PRICES.json',latency=dict(native_prefix_us=time_us,phases_us=phases,wide_score_front_extra_us_allowance=2.6*math.ceil(8/c['sampler']),front_allowance_not_native=True),bandwidth=dict(logical_all_attention_GBs=ext_bytes/T,QKV_O_logical_GBs=projected_BW,link_peak_GBs=136.4606,ideal_weight_supply_from_FMA_GBs=c['lanes']*.5,external_bytes_excluding_GU_prefetch=ext_bytes),sensitivity=dict(no_added_root_gate_onchip_uJ=onchip_idle_clock,PV2_or1_unmeasured_energy_plusminus25_uJ=.25*dynamic['PV_ADD_state_and_word_buffers'] if c['pv']!=4 else 0,QK_buffer_energy_half_to_double_uJ=[.5*dynamic['QK_transpose_input_buffers'],2*dynamic['QK_transpose_input_buffers']],front_reserve_area55_mm2=area['wide_score_front_reserve']),limitations=['conditional activity-derived module budget, not integrated chip PPA','TT250 arithmetic/sampling mixed with explicitly marked legacy proxies and 250MHz SRAM with existing per-event library prices; not new250 activity measurement','root-clock-off plus input isolation assumed for inactive service windows; ICG cell area reserved but CTS unmeasured','input front max/difference budget does not claim numerical equivalence of historicalS12 traces','shared support counted once; remove standalone support if host already owns it','no global interconnect/PHY/CTS/pads/CDC physical implementation','no DRAM background/refresh power beyond4/6.6/8pJ-per-bit sensitivity','finite memory/native timing does not prove final placed routed250MHz'])
