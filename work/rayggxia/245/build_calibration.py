"""Extract only small numerical contracts from existing sealed evidence."""
from pathlib import Path
import hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[3]
SPACE=ROOT.parents[1]
OUT=ROOT/'architecture_tlm/model_scaling_20261106'
archive=SPACE/'project_archives/joint_equal_area236_20261105/recovery_ed028cc70e06/cases'
sources={}
def read(path,label):
    raw=path.read_bytes();sources[label]=dict(path=str(path.relative_to(SPACE)).replace('\\','/'),sha256=hashlib.sha256(raw).hexdigest())
    return json.loads(raw)
results=[];budgets=[]
for seed in (17,503,1009):
    p=archive/('sc_ising_s'+str(seed))
    seal=read(p/'SEAL.json','seal_'+str(seed))
    r=read(p/'RESULT.json','result_'+str(seed));b=read(p/'BUDGET.json','budget_'+str(seed))
    assert sources['result_'+str(seed)]['sha256']==seal['result_sha256']
    assert sources['budget_'+str(seed)]['sha256']==seal['budget_sha256']
    assert r['status']=='completed' and r['model']['layers']==36
    results.append(r);budgets.append(b)
p=read(SPACE/'tmp/lpddr-digital-issue236-20261104/work/rayggxia/236/accounting_v1/PRICES.json','prices')
sc=read(SPACE/'architecture_tlm/digital_fair_20261105/LATEST_SC_PRICES.json','SC_prices')
att=read(SPACE/'architecture_tlm/digital_fair_20261105/joint_handoff/ATTENTION_PRICES.json','attention_prices')
def avgdict(rows):
    keys=set().union(*(x.keys() for x in rows))
    return {k:statistics.mean(x.get(k,0) for x in rows) for k in sorted(keys)}
r=results[0]
cal=dict(format='cross-model-analytic-calibration-1',source_issue=236,
    hardware=dict(chip_hz=100000000,ordinary_FMA_lanes=1024,FFN_cores=12,FFN_K=64,FFN_M=128,
        FFN_T=64,FFN_frame_cycles=66,attention_physical_groups=8,attention_QK_lanes_per_group=64,
        V_ADD_lanes_per_head_slot=16,physical_head_slots_per_group=4,context=2048,r=32,K=128,S=64,
        SRAM_bytes=2621440,SRAM_word_bytes=16,nominal_DRAM_GBs=136.46055437100214,
        external_pJ_per_bit=[4,6.6,8],area_scale_already_applied=0.81),
    reference=dict(model=r['model'],time_ms=statistics.mean(x['simulated_ms'] for x in results),
        external_bytes=statistics.mean(x['memory']['counts']['dram_read_bytes']+x['memory']['counts']['dram_write_bytes'] for x in results),
        actions=avgdict([x['actions'] for x in results]),kernel_active=r['kernel_active'],
        onchip_components_mJ=avgdict([x['onchip_components_mJ'] for x in budgets]),
        areas55_mm2=budgets[0]['covered_areas55_mm2'],
        sram_by_tag={tag:avgdict([x['memory']['SRAM']['by_tag'][tag] for x in results]) for tag in r['memory']['SRAM']['by_tag']},
        sram_regions=[dict(name=z['name'],size=z['size'],banks=z['banks']) for z in r['memory']['SRAM']['regions']],
        allocated_bytes=r['memory']['SRAM']['allocated_bytes'],
        bank_depths=r['memory']['SRAM']['bank_depths_bytes'],
        timing_basis='17/503/1009 frozen Qwen native runs; time same, activities averaged'),
    prices=dict(digital=p['digital'],common=p['common'],remaining=p['legacy']['remaining_proxy'],
        ingress=p['legacy']['ingress'],screen=p['legacy']['attention'],online=p['online']['prices_pJ_incremental'],
        sc=sc['profiles'][sc['default_profile']],sampler=att['samplers']['ising'],vpath=att['vpath'],
        output_converter=att['output_converter'],SRAM_read_pJ_per16B=10.0527,
        SRAM_write_pJ_per16B=13.9599,SRAM_idle_W_per4KiB=7.7544e-6),
    sources=sources,new_RTL_PPA=False,new_native_TLM=False,
    limits=['C20 has partial PT windows and area-scaled idle proxy; retained as current anchor',
        'FFN core includes digital RNG and SNG; no second FFN random-source charge',
        'no physical DAC/p-bit implementation cost is introduced',
        'PHY/global interconnect/CTS/CIM interface and some conversion costs remain outside covered boundary'])
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'CALIBRATION.json').write_bytes((json.dumps(cal,indent=2)+'\n').encode())
print(json.dumps(dict(status='PASS',sources=len(sources),reference_time_ms=cal['reference']['time_ms'],
    reference_area55_mm2=sum(cal['reference']['areas55_mm2'].values()),
    reference_effective_GBs=cal['reference']['external_bytes']/cal['reference']['time_ms']/1e6)))
