"""Reprice only changed resources from pinned owner summaries, not failed PPA."""
from pathlib import Path
import hashlib,json,math

def evaluate(base,owner,case='combined32'):
    current=owner['areas'][case];control=owner['areas']['control']
    areas=dict(base['central50ms']['areas55_mm2'])
    assert math.isclose(math.fsum(areas.values()),control['covered_chip_budget_mm2'],abs_tol=1e-8)
    areas['ordinary_final_reduction']=current['reduction_mm2']
    areas['Attention_QK_FMA']=current['dedicated_QK_mm2']
    areas['Attention_V_accumulate_control']=current['PV_accumulate_control_staging_mm2']
    total=math.fsum(areas.values());old=base['central50ms']['covered_area55_mm2']
    assert math.isclose(total,current['covered_chip_budget_mm2'],abs_tol=1e-8)
    reductions=dict(PV_and_staging=control['PV_accumulate_control_staging_mm2']-current['PV_accumulate_control_staging_mm2'],
        FP32_final_reduction=control['reduction_mm2']-current['reduction_mm2'],
        dedicated_QK_removed=control['dedicated_QK_mm2']-current['dedicated_QK_mm2'])
    assert math.isclose(math.fsum(reductions.values()),old-total,abs_tol=1e-8)
    groups={
        'FFN计算与随机前端':math.fsum(v for k,v in areas.items() if k.startswith('FFN_')),
        '共享普通数字池与末端归约':math.fsum(v for k,v in areas.items() if k.startswith('ordinary_')),
        'Attention筛选采样与V通路':math.fsum(v for k,v in areas.items() if k.startswith('Attention_')),
        'SRAM宏':areas['shared_SRAM'],
        'DMA入口保持':areas['DMA_24KiB_holding'],
        '格式向量与本地保持代理':areas['format_and_vector_proxy']+areas['digital_holding_proxy']}
    assert math.isclose(math.fsum(groups.values()),total,abs_tol=1e-8)
    return dict(case=case,scope='conditional_component_budget_not_new_PPA_or_die',
        previous_area55_mm2=old,candidate_area55_mm2=total,saved_mm2=old-total,
        saved_percent=(old-total)/old*100,areas55_mm2=areas,groups=groups,
        reductions=reductions,SRAM_KiB=1216,SS100=True,area_scaled_upstream_once=.81,
        new_PV4_failed_DC_area_used=False,
        PV_price_policy='old accepted scalarADD/state/control plus2KiB holding proxy',
        independent_QK_removal_conditional_on_real_supply_integration=True,
        excluded_delta=['QK input reordering/mux/routing','PV changed state selection/clock gating layout'],
        production_default_changed=False,new_energy_estimate=False)

def main():
    p=Path(__file__).parent
    inputs=json.loads((p/'INPUTS.json').read_bytes())
    out=dict(candidate=evaluate(inputs['base_budget'],inputs['owner_summary']),
        reduction_only=evaluate(inputs['base_budget'],inputs['owner_summary'],'reduce32'),
        owner_source_sha256=inputs['source_sha256'],
        timing_evidence=inputs['timing_evidence'])
    (p/'RESULTS.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({k:out['candidate'][k] for k in ('candidate_area55_mm2','saved_mm2','saved_percent')}))

if __name__=='__main__':main()
