"""Check sealed layer runs; preserve originals and publish only small summaries."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())
names=('reference1216','compact1088','compact960')
runs={name:load(HERE/name/'RESULT.json') for name in names}
ref=runs[names[0]]
evidence={};rows={}
for name,r in runs.items():
    folder=HERE/name;budget=load(folder/'BUDGET.json');seal=load(folder/'SEAL.json')
    assert r['status']=='completed' and seal['status']=='completed'
    assert sha(folder/'RESULT.json')==seal['result_sha256']
    assert sha(folder/'BUDGET.json')==seal['budget_sha256']
    assert r['source_identity']==ref['source_identity']
    assert r['seed']==ref['seed']==17 and r['scope']=='layer'
    assert r['actions']==ref['actions'], 'arithmetic/sampling/cache action drift'
    assert r['kernel_active']==ref['kernel_active']
    assert r['memory']['by_kind']==ref['memory']['by_kind'], 'external address/byte drift'
    assert not r['memory']['final_pending'] and not r['memory']['final_response_occupied']
    mem=r['compact_memory'];sram=r['memory']['SRAM']
    assert sum(mem['regions'].values())==mem['capacity_KiB']*1024
    assert sram['physical_banks']==mem['physical_4KiB_banks']
    assert sram['counts']['peak_banks_per_cycle']<=sram['physical_banks']
    rows[name]=dict(SRAM_KiB=mem['capacity_KiB'],banks=mem['physical_4KiB_banks'],
        front_banks=mem['front_banks'],attention_banks=mem['attention_banks'],
        layer_ms=r['simulated_ms'],cycles=r['simulated_chip_cycles'],
        phases_ms=r['phase_totals_ms'],area55_mm2=budget['totals']['covered_area55_mm2'],
        SRAM_area55_mm2=sram['area55eq_mm2'],
        onchip_mJ_reference=budget['totals']['onchip_mJ_with_FFN_reference_proxy'],
        total_mJ_at4pJ_reference=budget['totals']['proxy_total_mJ_at4pJ'],
        external_bytes=budget['bandwidth']['external_bytes'],
        SRAM_counts=sram['counts'],SRAM_dynamic_mJ=sram['dynamic_mJ'],
        SRAM_leakage_mJ=sram['leakage_mJ'],
        highwater_bytes=r['sram_capacity_contract']['accessed_highwater_bytes'],
        reference_FFN_status=budget['totals']['FFN_target_clock_implementation_status'])
    evidence[name]={filename:dict(path=(folder/filename).relative_to(HERE.parents[3]).as_posix(),
                                sha256=sha(folder/filename))
                    for filename in ('RESULT.json','BUDGET.json','SEAL.json')}
for name,row in rows.items():
    row['latency_delta_percent']=(row['layer_ms']/rows[names[0]]['layer_ms']-1)*100
    row['area_saved_mm2']=rows[names[0]]['area55_mm2']-row['area55_mm2']
summary=dict(status='passed',selected_default='compact960',clock_MHz=250,cores=3,
    scope='complete cold layer0 incl embedding, no lm_head;36-layer address allocation',
    backend='analytic136.4606GB/s30ns; real bank/queue/credit schedule',seed=17,
    same_source_input_action_kernel_external_address_checks=True,
    new_numeric_PPL=False,new_RTL_PPA=False,full_native_token=False,
    FFN_TT250_shortT_setup_slack_ns=-.421007,
    conditional_4ns_schedule_not_clock_signoff=True,
    cases=rows,artifacts=evidence,source_identity=ref['source_identity'])
dest=HERE.parents[3]/'architecture_tlm/sram1216_20261106/250MHz/SRAM_COMPACT_RESULTS.json'
dest.write_bytes((json.dumps(summary,indent=2,ensure_ascii=False)+'\n').encode())
print(json.dumps({k:{a:v for a,v in row.items() if a in ('SRAM_KiB','layer_ms','area55_mm2','area_saved_mm2','latency_delta_percent','total_mJ_at4pJ_reference')} for k,row in rows.items()},indent=2))
