"""Small derived price/evidence snapshot; do not republish owner raw handoffs."""
from pathlib import Path
import hashlib,importlib.util,json,math
ROOT=Path('C:/Users/86134/Documents/a_P_BIT')
REPO=Path(__file__).resolve().parents[4]
OUT=REPO/'architecture_tlm/current_handoff_budget_20261106'


def load(rel):return json.loads((ROOT/rel).read_bytes())
def identity(rel):
    p=ROOT/rel
    return dict(path=rel,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)


def main():
    calrel='architecture_tlm/model_scaling_20261106/CALIBRATION.json'
    c=load(calrel);ref=c['reference'];t=ref['time_ms']
    source='architecture_tlm/model_scaling_20261106/estimate.py'
    spec=importlib.util.spec_from_file_location('ppa_reference',ROOT/source)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    configrel='architecture_tlm/model_scaling_20261106/evidence/qwen3_4b_config.json'
    r=m.model_from_config('qwen3_4b',load(configrel))
    unique=ref['actions']['unique_V']/(r['layers']*r['kv_heads'])
    x=m.quantities(r,c,unique)
    e0=m.energy_budget(x,c,dict(time_ms=t))['onchip_components_mJ']
    e1=m.energy_budget(x,c,dict(time_ms=t+1))['onchip_components_mJ']
    for k,v in ref['onchip_components_mJ'].items():assert abs(v-e0[k])<1e-8
    curves={k:dict(activity_mJ=e0[k]-(e1[k]-e0[k])*t,idle_W=e1[k]-e0[k]) for k in e0}
    profile=load('architecture_tlm/module_handoff/ordinary_mapping_20261106/PROFILE.json')
    primary=profile['primary']
    assert primary['lanes']==640 and primary['k_parallel']==8 and primary['early_refill']
    assert primary['FP32_reduction_adders']==128 and profile['independent_QK_retained']
    candidate=load('architecture_tlm/module_handoff/ffn_sram_batch96_20261106/profile_candidate.json')
    assert candidate['shared_SRAM_KiB']==1952 and candidate['physical_4KiB_banks']==488 and candidate['T']==64
    pilot=load('architecture_tlm/ffn_sram_batch_20261106/results/PILOT_SUMMARY.json')
    chosen=next(y for y in pilot['rows'] if y['configuration']=='b96s96')
    assert chosen['passes'] and all(chosen['equal_work_checks'].values())
    delta=sum(v['candidate'].get('read_words',0)-v['control'].get('read_words',0) for v in chosen['SRAM_event_differences'].values())
    p=c['prices'];fma=p['digital']['fma16_c4']
    prices=dict(FMA16_area55_mm2=fma['area55_mm2'],FMA16_idle_W=fma['idle_W'],FMA_incremental_pJ=fma['incremental_pJ'],
        FP32_ADD_incremental_pJ=p['online']['fpadd'],FP32_ADD_idle_W=17.52e-6,
        SRAM_macro_area55_mm2=ref['areas55_mm2']['shared_SRAM']/640,
        SRAM_macro_idle_W=p['SRAM_idle_W_per4KiB'],SRAM_read_pJ_per16B=p['SRAM_read_pJ_per16B'],
        SRAM_write_pJ_per16B=p['SRAM_write_pJ_per16B'],DMA_capture_pJ_per64B=p['ingress']['capture_pJ_per64B'])
    sources=[identity(y) for y in [calrel,source,configrel,
        'architecture_tlm/module_handoff/ordinary_mapping_20261106/HANDOFF_ZH.md',
        'architecture_tlm/module_handoff/ordinary_mapping_20261106/PROFILE.json',
        'architecture_tlm/ordinary_mapping_20261106/model.py',
        'architecture_tlm/ordinary_mapping_20261106/RESULTS.json',
        'architecture_tlm/module_handoff/ffn_sram_batch96_20261106/HANDOFF_ZH.md',
        'architecture_tlm/module_handoff/ffn_sram_batch96_20261106/profile_candidate.json',
        'architecture_tlm/ffn_sram_batch_20261106/results/PILOT_SUMMARY.json',
        'architecture_tlm/ffn_sram_batch_20261106/results/CONFIRM_B96S96_SUMMARY.json',
        'architecture_tlm/module_handoff/attention_buffer_compaction_20261106/SRAM64_PLAN_ZH.md']]
    result=dict(format='current_handoff_conditional_budget1',model=dict(id='Qwen/Qwen3-4B',revision='1cfa9a7208912126459214e8b04321603b3df60c',
        layers=36,hidden=2560,FFN=9728,B=1,N=2048,clock_MHz=100,ordinary_output_elements=36*(6144+2560)+151936),
        reference=dict(time_ms=t,actions=ref['actions'],areas55_mm2=ref['areas55_mm2'],
            covered_area55_mm2=math.fsum(ref['areas55_mm2'].values()),external_bytes=ref['external_bytes'],
            onchip_components_mJ=e0,energy_curves_mJ_plus_W_times_ms=curves,
            summary=dict(time_ms=t,onchip_mJ=math.fsum(e0.values()),total_mJ=math.fsum(e0.values())+ref['external_bytes']*32e-9,area55_mm2=math.fsum(ref['areas55_mm2'].values()))),
        prices=prices,norm_stream_bytes=392192,FFN96_observed_extra_read_words_per_layer=delta/2,
        FFN96_extra_read_scope='two-layer seed17 activity extrapolated; combined schedule not observed',
        ordinary_profile_selected=primary,
        FFN96_candidate={k:candidate[k] for k in ('status','GU_state_KiB','shared_SRAM_KiB','physical_4KiB_banks','crossK_state_bits','kernel_count','T','weight_slots')},
        not_deducted=['Attention64KiB_plan_only','QK_shared_pool_not_implemented','activation128KiB_not_implemented','CIM24slots_not_implemented','fused_DOT8_not_implemented'],
        sources=sources,new_native_jobs_submitted=False,new_RTL_PPA=False,new_PPL=False)
    OUT.mkdir(exist_ok=True,parents=True)
    (OUT/'INPUTS.json').write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+'\n').encode())
    print('reference16components reproduced;'+str(len(sources))+' source identities captured;no new jobs')


if __name__=='__main__':main()
