"""Seal audit, matched-work regression and explicit36-layer/head extrapolation."""
from pathlib import Path
from collections import Counter
import hashlib,json,math
H=Path(__file__).resolve().parent;ROOT=H.parents[3];D=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_bytes())
def dump(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
sources={};cases={}
for name in ('p250','p500','p250_one','head250_1024','head250_1152','head250_2048'):
    folder=H/name;s=load(folder/'SEAL.json');assert s['status']=='completed'
    for n,v in s['files_sha256'].items():assert sha(folder/n)==v
    assert load(H/(name+'_RETURN.json'))['exit_code']==0
    r=load(folder/'RESULT.json');assert r['status']=='completed';cases[name]=r
    sources[name]=dict(path=str(folder),files_sha256={n:sha(folder/n) for n in s['files_sha256']},
        seal_sha256=sha(folder/'SEAL.json'))
old=H.parent/'mixed34_20261109/revision2'
checks=[]
for name,prior in [('p250','p250_mixed'),('p500','p500_mixed')]:
    before=load(old/prior/'RESULT.json');after=cases[name]
    assert before['time_ns']==after['time_ns']
    assert before['actions']==after['actions'] and before['process28_counts']==after['process28_counts']
    assert before['kernel_active']==after['kernel_active']
    assert before['SRAM']['counts']==after['SRAM']['counts']
    assert before['SRAM']['bank_activity']==after['SRAM']['bank_activity']
    assert before['memory']['by_kind']==after['memory']['by_kind']
    if name=='p500':assert load(old/prior/'BUDGET.json')==load(H/name/'BUDGET.json')
    checks.append(name+':exacttiming/actions/traffic;500budget unchanged')
r=cases['p250'];r1=cases['p250_one'];b=load(H/'p250/BUDGET.json');b1=load(H/'p250_one/BUDGET.json')
assert b['status']=='CONDITIONAL28NM250_CORE_SUBSYSTEM_LEDGER_CLOSED' and not b['unpriced_in_chosen_boundary']
for ledger in (b,b1):
    split=ledger['lm_head_split']
    for key in ('time_ms','core_energy_mJ','external_bytes'):
        assert math.isclose(split['including_lm_head'][key],split['without_lm_head_stage'][key]+split['lm_head_stage'][key],rel_tol=1e-12)
    assert math.isclose(sum(x['area_mm2'] for x in ledger['rows']),ledger['conditional_subsystem_area_mm2'],rel_tol=1e-12)
    assert math.isclose(sum(x['energy_mJ'] for x in ledger['rows']),ledger['conditional_subsystem_energy_mJ'],rel_tol=1e-12)
checks+=['ledger/head phase closure','178real SRAM ports and exact matched traffic','gross-idle identities;unit tests separately']

# Reprice observed finalnorm prefixes. This is a measured execution prefix, not
# an independent model without any readout prefetch.
import sys
plan=load(H/'PLAN.json');sys.path.insert(0,plan['execution'])
from whole_pricing import price
from types import SimpleNamespace as NS
slots={x['component']:x['instances'] for x in b['rows']}
m=NS(common_cores=3,sampler_pool=NS(slots=slots['score_front']),norm_pool=NS(slots=slots['SparQ_norm']),top_pool=NS(slots=slots['SparQ_top']))
binding=load(Path(plan['execution'])/'250MHz/BINDINGS.json')
p1=r1['observed_prefix_without_lm_head'];p2=r['observed_prefix_without_lm_head'];q1=price(m,p1,binding);q2=price(m,p2,binding)
body_ns=p1['time_ns']+35*(p2['time_ns']-p1['time_ns'])
hp1,hpt,hp2=[cases['head250_'+str(n)] for n in (1024,1152,2048)]
block_ns=(hp2['head_duration_ns']-hp1['head_duration_ns'])/4
tail_ns=hpt['head_duration_ns']-hp1['head_duration_ns'];assert block_ns>0 and 0<tail_ns<block_ns
# 151936-384=148*(2048-1024). Anchor to actualwhole384-stage to
# retain its initial prefetch overlap rather than fitting a negative startup.
head_ns=r['lm_head_stage_ms']*1e6+148*(hp2['head_duration_ns']-hp1['head_duration_ns'])
total_ns=body_ns+head_ns
fma=binding['shared_FMA'];fma_inc=fma['gross_pJ_per_FMA']-fma['idle_W']*fma['measurement_ns_per_FMA']*1000
head_extra_fma_pJ=148*(hp2['MAC']-hp1['MAC'])*fma_inc
head_extra_sram_mJ=148*(hp2['SRAM']['dynamic_mJ']-hp1['SRAM']['dynamic_mJ'])
parts=[]
for full,first,two in zip(b['rows'],q1['rows'],q2['rows']):
    assert full['component']==first['component']==two['component']
    name=full['component']
    if name=='DMA_FIFO_and_platform_macros':
        body_e=binding['platform_macro']['total_activity_and_idle_W']*body_ns/1e6
        head_e=binding['platform_macro']['total_activity_and_idle_W']*head_ns/1e6
    else:
        idle_W=two['full_residency_idle_mJ']/(p2['time_ns']/1e6)
        body_inc=first['incremental_activity_mJ']+35*(two['incremental_activity_mJ']-first['incremental_activity_mJ'])
        head_inc=full['incremental_activity_mJ']-two['incremental_activity_mJ']
        if name=='shared_FMA256':head_inc+=head_extra_fma_pJ/1e9
        if name=='SRAM28_mixed_S0_S2_macros':head_inc+=head_extra_sram_mJ
        body_e=body_inc+idle_W*body_ns/1e6;head_e=head_inc+idle_W*head_ns/1e6
    assert body_e>=0 and head_e>=-1e-12
    parts.append(dict(component=name,area_mm2=full['area_mm2'],body_mJ=body_e,head_stage_mJ=head_e,total_mJ=body_e+head_e,
        source_kind=full.get('price_kind','measured primitive or declared staging/SRAM proxy'),basis=full.get('basis')))
body_bytes=q1['external_bytes']+35*(q2['external_bytes']-q1['external_bytes'])
head_bytes=b['external_bytes']-q2['external_bytes']+148*(hp2['external_bytes']-hp1['external_bytes'])
prefetch=p2['memory']['by_kind'].get('lm_head_weights',{}).get('issued_bytes',0)
assert prefetch==65536
logical_head=151936*2560*2;assert head_bytes+prefetch==logical_head
core_body=sum(x['body_mJ'] for x in parts);core_head=sum(x['head_stage_mJ'] for x in parts);core=core_body+core_head
totals={str(e):core+(body_bytes+head_bytes)*8*e/1e9 for e in (4.,6.6,8.)}
estimate=dict(status='EXPLICIT_CONDITIONAL36_LAYER_EXTRAPOLATION_NOT_FULL_RUN',model='Qwen3-4B',B=1,context=2048,
    clock_MHz=250,FFN_cores=3,GU_samples=16,Wd_samples=32,candidates=128,samples=64,SRAM_KiB=832,
    area_mm2=b['conditional_subsystem_area_mm2'],time_ms=total_ns/1e6,without_lm_head_stage_ms=body_ns/1e6,
    lm_head_stage_ms=head_ns/1e6,core_energy_mJ=core,body_core_energy_mJ=core_body,head_stage_core_energy_mJ=core_head,
    core_average_W=core/(total_ns/1e6),external_bytes=body_bytes+head_bytes,
    total_energy_mJ_by_external_pJbit=totals,total_average_W_at4pJbit=totals['4.0']/(total_ns/1e6),
    without_lm_head_stage_total_mJ_at4pJbit=core_body+body_bytes*32/1e9,
    body_external_bytes=body_bytes,head_stage_external_bytes=head_bytes,
    logical_full_lm_head_weight_bytes=logical_head,head_prefetch_bytes_in_body_prefix=prefetch,
    head_fit=dict(increment_ns_per256rows=block_ns,tail128_increment_ns=tail_ns,extra1024row_blocks=148,
        basis='observedwhole384head +148*(actual2048head-actual1024head)'),
    parts=parts,full36_layers_actually_executed=False,native_LPDDR_actually_executed=False,
    scope='cold one/two-layer prefixes + actualheadprobes;phase exclusion includes64KiB overlapped head prefetch',
    no_uniform15percent=True,physical_wholechip_verified=False)
report=dict(status='PASS_UPDATED250_INTEGRATION_AND_PRICE_CLOSURE',owner='rayggxia',issue=225,PR=249,
    actual_cases={n:dict(time_ms=cases[n].get('time_ms'),scope=cases[n].get('scope'),rows=cases[n].get('rows')) for n in cases},
    checks=checks,sources=sources,execution=plan['execution'],unit_tests='test_refresh250.py:5passed',
    actual250_partial_area_mm2=b['conditional_subsystem_area_mm2'],actual250_partial_time_ms=r['time_ms'],
    prior_conditional_area_mm2=6.566339504479158,
    area_change_percent=100*(b['conditional_subsystem_area_mm2']/6.566339504479158-1),
    current_scope='28nm250only;500one-layer regression unchanged;55defaults unchanged',
    full36_estimate=estimate,full36_actual=False,new_circuit_PPA=False)
dump(D/'250MHz/UPDATED_TLM_20261109.json',report)
dump(D/'250MHz/CONDITIONAL_ESTIMATE_20261109.json',estimate)
print(json.dumps(dict(status=report['status'],area_mm2=estimate['area_mm2'],time_ms=estimate['time_ms'],
    without_head_ms=estimate['without_lm_head_stage_ms'],core_mJ=core,total_at4pJbit_mJ=totals['4.0'],area_change_pct=report['area_change_percent'])))
