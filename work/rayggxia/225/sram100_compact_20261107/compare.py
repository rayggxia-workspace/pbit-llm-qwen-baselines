from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())
names=('compact1216','compact1088bw')
runs={n:load(HERE/'v2'/n/'RESULT.json') for n in names};ref=runs['compact1216']
assert ref['time_ns']==1207620, 'reference changed from accepted finite-supply baseline'
assert ref['memory']['SRAM']['capacity_bytes']==1216*1024
results={};artifacts={}
for n,r in runs.items():
    folder=HERE/'v2'/n;b=load(folder/'BUDGET.json');s=load(folder/'SEAL.json')
    assert r['status']==s['status']=='completed'
    assert sha(folder/'RESULT.json')==s['result_sha256']
    assert sha(folder/'BUDGET.json')==s['budget_sha256']
    assert r['source_identity']==ref['source_identity']
    assert r['actions']==ref['actions'], 'logical work changed'
    assert r['kernel_active']==ref['kernel_active']
    assert r['memory']['by_kind']==ref['memory']['by_kind'], 'external bytes/address changed'
    assert not r['memory']['final_pending'] and not r['memory']['final_response_occupied']
    sr=r['SRAM'];regions=r['compact_memory']['regions']
    assert sum(regions.values())+r['compact_memory']['unallocated_bytes']==sr['capacity_bytes']==sr['physical_banks']*4096
    assert sr['counts']['peak_banks_per_cycle']<=sr['physical_banks']
    phases={}
    for p in r['phases']:phases[p['stage']]=phases.get(p['stage'],0)+p['duration_ns']/1000
    results[n]=dict(SRAM_KiB=sr['capacity_bytes']//1024,banks=sr['physical_banks'],
        front_banks=r['compact_memory']['front_banks'],attention_banks=r['compact_memory']['attention_banks'],
        layer_ms=r['simulated_ms'],cycles=r['chip_cycles'],phases_us=phases,
        covered_area55_mm2=b['covered_area55_proxy_mm2'],SRAM_area55_mm2=sr['area55eq_mm2'],
        SRAM_dynamic_mJ=sr['dynamic_mJ'],SRAM_leakage_mJ=sr['leakage_mJ'],SRAM_counts=sr['counts'],
        FFN_core_energy_mJ=b['FFN_core_budget']['total_mJ'],whole_chip_energy_mJ=None,
        scratch_offset=r['qk_supply_contract']['scratch_offset'],
        unallocated_bytes=r['compact_memory']['unallocated_bytes'],
        highwater=r['sram1216_contract']['accessed_highwater_bytes'])
    artifacts[n]={f:dict(path=(folder/f).relative_to(REPO).as_posix(),sha256=sha(folder/f))
                  for f in ('RESULT.json','BUDGET.json','SEAL.json')}
for n,row in results.items():
    row['latency_delta_percent']=(row['layer_ms']/results['compact1216']['layer_ms']-1)*100
    row['area_saved_mm2']=results['compact1216']['covered_area55_mm2']-row['covered_area55_mm2']
pre=load(HERE/'PREFLIGHT.json')
assert all(sha(Path(p))==v for p,v in pre['unchanged_250_sources'].items())
initial={}
for n in ('compact1216','compact1184','compact1056'):
    f=HERE/n;r=load(f/'RESULT.json');b=load(f/'BUDGET.json');s=load(f/'SEAL.json')
    assert sha(f/'RESULT.json')==s['result_sha256'] and sha(f/'BUDGET.json')==s['budget_sha256']
    initial[n]=dict(layer_ms=r['simulated_ms'],covered_area55_mm2=b['covered_area55_proxy_mm2'],
        local_execution_commit=r['source_identity']['local_commit'],
        result_path=(f/'RESULT.json').relative_to(REPO).as_posix(),result_sha256=sha(f/'RESULT.json'),
        budget_sha256=sha(f/'BUDGET.json'),seal_sha256=sha(f/'SEAL.json'))
out=dict(status='passed',selected_default='compact1088bw',clock_MHz=100,cores=6,
    scope=ref['scope'],backend=ref['backend'],seed=17,same_work_external_address_and_input=True,
    current250_unchanged=True,new_PPA=False,new_PPL=False,whole_native_token=False,
    cases=results,artifacts=artifacts,source_identity=ref['source_identity'],initial_round=initial,
    initial_round_policy='separate prior code commit89bb0b9f; all3paired there; no original rewritten')
dest=REPO/'architecture_tlm/module_refresh_20261107/SRAM100_RESULTS.json'
dest.write_bytes((json.dumps(out,indent=2)+'\n').encode())
print(json.dumps({n:{k:r[k] for k in ('SRAM_KiB','layer_ms','covered_area55_mm2','area_saved_mm2','latency_delta_percent')} for n,r in results.items()},indent=2))
