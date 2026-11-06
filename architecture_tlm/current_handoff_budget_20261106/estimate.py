"""Reprice current handoffs. Conditional energy/power, not a merged schedule."""
from pathlib import Path
import json,math
HERE=Path(__file__).resolve().parent


def evaluate(inputs,time_ms=50.,sram_banks=488,state96=True):
    ref=inputs['reference'];p=inputs['prices'];a=dict(ref['areas55_mm2'])
    a['ordinary_BF16_FMA']=40*p['FMA16_area55_mm2']
    a['shared_SRAM']=sram_banks*p['SRAM_macro_area55_mm2']
    curves=ref['energy_curves_mJ_plus_W_times_ms']
    energy={k:v['activity_mJ']+v['idle_W']*time_ms for k,v in curves.items()}
    mac=ref['actions']['digital_BF16_MAC']
    reductions=inputs['model']['ordinary_output_elements']*7
    energy['ordinary_BF16_FMA']=mac*p['FMA_incremental_pJ']*1e-9+40*p['FMA16_idle_W']*time_ms
    energy['ordinary_final_reduction']=reductions*p['FP32_ADD_incremental_pJ']*1e-9+128*p['FP32_ADD_idle_W']*time_ms
    norm=inputs['norm_stream_bytes']
    extra_words=inputs['FFN96_observed_extra_read_words_per_layer']*36 if state96 else 0
    # Same physical4KiB macro event price, no proportional dynamic discount.
    energy['shared_SRAM']=(curves['shared_SRAM']['activity_mJ']
        +norm/16*p['SRAM_write_pJ_per16B']*1e-9
        +(36*512/16+extra_words)*p['SRAM_read_pJ_per16B']*1e-9
        +sram_banks*p['SRAM_macro_idle_W']*time_ms)
    energy['DMA_24KiB_holding']+=norm/64*p['DMA_capture_pJ_per64B']*1e-9
    external_bytes=ref['external_bytes']+norm
    onchip=math.fsum(energy.values());area=math.fsum(a.values())
    externals={str(z):external_bytes*8*z*1e-9 for z in (4,6.6,8)}
    groups={}
    for name,predicate in (
        ('FFN计算、随机前端和跨K响应',lambda k:k.startswith('FFN_')),
        ('普通数字FMA与末端归约',lambda k:k.startswith('ordinary_')),
        ('共享SRAM',lambda k:k=='shared_SRAM'),
        ('Attention核心、筛选、采样和V累加',lambda k:k.startswith('Attention_')),
        ('DMA24KiB入口保持',lambda k:k=='DMA_24KiB_holding'),
        ('格式、向量及数字本地保持代理',lambda k:k in ('format_and_vector_proxy','digital_holding_proxy'))):
        groups[name]=dict(area55_mm2=math.fsum(v for k,v in a.items() if predicate(k)),
            energy_mJ=math.fsum(v for k,v in energy.items() if predicate(k)))
        groups[name]['average_W']=groups[name]['energy_mJ']/time_ms
    return dict(scope='conditional_action_repricing_not_combined_native_TLM',
        assumed_time_ms=time_ms,ordinary_lanes=640,K_parallel=8,early_refill=True,
        FFN_state_KiB=96 if state96 else 152,SRAM_KiB=sram_banks*4,SRAM_banks=sram_banks,
        areas55_mm2=a,covered_area55_mm2=area,components_mJ=energy,onchip_mJ=onchip,
        onchip_average_W=onchip/time_ms,external_bytes=external_bytes,
        external_mJ_at_pJ_per_bit=externals,system_mJ_at4pJ=onchip+externals['4'],
        system_average_W_at4pJ=(onchip+externals['4'])/time_ms,groups=groups,
        activity_counts=dict(ordinary_BF16_MAC=mac,ordinary_final_FP32_ADD=reductions),
        area_change_vs_original_percent=(area/ref['covered_area55_mm2']-1)*100,
        independent_QK_retained=True,Attention_128KiB_per_group_retained=True,
        FFN_T64_price=True,FFN_RNG_already_inside_core=True,
        new_owner_routing_control_PPA_missing=True)


def main():
    inputs=json.loads((HERE/'INPUTS.json').read_bytes())
    result=dict(central=evaluate(inputs),time_sensitivity=[evaluate(inputs,t) for t in (45.,55.)],
        state152_control=evaluate(inputs,50.,502,False),
        original_reference=inputs['reference']['summary'],
        timing_note='50ms is an accounting window;45/55ms are scenarios,not measured bounds',
        source_evidence=inputs['sources'])
    (HERE/'RESULTS.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
    print(json.dumps({k:result['central'][k] for k in ('covered_area55_mm2','onchip_mJ','onchip_average_W','system_mJ_at4pJ','system_average_W_at4pJ')}))


if __name__=='__main__':main()
