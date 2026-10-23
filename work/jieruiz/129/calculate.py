"""Recalculate saved byte/energy ledgers, not a new simulator run."""
import subprocess,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'architecture_tlm/memory_savings_20261023'
BASE='e8705765ed3286b225e042378d57e5d010e221ee'
idx=[]
def read(path,commit=BASE):
    raw=subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
    idx.append(dict(path=path,commit=commit,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    return raw
rows=[]
for L,modes in [(2048,['bf16_exact','sc_exact','sc_pv','sc_screen_exact','sc_screen_pv']),(8192,['bf16_exact','sc_pv','sc_screen_pv'])]:
    for mode in modes:
        path=f'architecture_tlm/unified_v6/results/integrated_rng_20261022_v3/qwen/qwen_L{L}_seed0_{mode}_integrated_service.json'
        x=json.loads(read(path)); a=x['actions'];s=x['SRAM'];t=x['DRAM']['traffic']
        assert x['config']['dram']['backend']=='link'
        assert x['config']['ffn']['samples']==32
        assert x['metrics']['full_physical_energy_J'] is None
        assert s['configured_bytes']==2**20
        dram=a['dram_read']+a['dram_write']; sr=sum(s['traffic'][k] for k in ['read_physical_bytes','write_physical_bytes'])
        if 'KV_fused_physical_bytes' in t:k=v=t['KV_fused_physical_bytes']//2
        else:k=t['K_selected_physical_bytes'];v=t['V_sparse_union_physical_bytes']
        summary=sum(t.get(f'summary_{z}_physical_bytes',0) for z in ['read','update'])
        en=sum(v for k,v in x['energy_J'].items() if k.startswith(('DRAM','SRAM')))*1000
        # Internal SRAM price from each actual macro access, and fixed Link pricing.
        spec=s['calibrated_macro']
        assert math.isclose(x['energy_J']['SRAM_internal'],(s['traffic']['read_words']*spec['read_internal_pJ']+s['traffic']['write_words']*spec['write_internal_pJ'])*1e-12,rel_tol=1e-8)
        assert math.isclose(x['energy_J']['DRAM_dynamic'],dram*64e-12,rel_tol=1e-8)
        assert math.isclose(x['energy_J']['DRAM_background'],x['metrics']['elapsed_ns']*50e-12,rel_tol=1e-8)
        r=dict(context=L,mode=mode,dram_B=dram,sram_B=sr,dram_MiB=dram/2**20,sram_MiB=sr/2**20,
            sram_reserved_KiB=s['reserved_peak_bytes']/1024,configured_sram_MiB=1,K_MiB=k/2**20,V_MiB=v/2**20,
            summary_MiB=summary/2**20,attention_traffic_saving_pct=100*(1-(k+v+summary)/(24*L*2*64*2*2)),
            conditional_storage_mJ=en,config_sha256=x['config_sha256'],execution_commit=x['execution_commit'])
        if mode=='bf16_exact':base=r
        r.update(dram_saving_vs_bf16_pct=100*(1-dram/base['dram_B']),sram_saving_vs_bf16_pct=100*(1-sr/base['sram_B']),conditional_storage_energy_saving_pct=100*(1-en/base['conditional_storage_mJ']))
        rows.append(r)
models={}
for name in ['qwen','llama2']:
    m=json.loads(read(f'architecture_tlm/unified_v6/configs/model_{name}.json'))
    # The released shape wrapper retains the original model config.
    if 'hidden_size' not in m:m=m['shape']
    d,h,n=m['hidden_size'],m['intermediate_size'],m['num_hidden_layers']
    hd=m.get('head_dim',d//m['num_attention_heads']);kv=m['num_key_value_heads']
    models[name]=dict(single_ffn_w8_MiB=3*d*h/2**20,total_ffn_w8_MiB=n*3*d*h/2**20,
        KV_BF16_MiB={str(L):n*L*kv*hd*2*2/2**20 for L in [2048,8192]})
for p in ['architecture_tlm/unified_v6/core.py','architecture_tlm/unified_v6/model.py','architecture_tlm/unified_v6/RNG_INTEGRATION_RESULTS_ZH.md','architecture_tlm/DRAM_POWER_AND_DS_CIM_WEIGHT_REVIEW_ZH_20261017.md','architecture_tlm/SCREEN_K_TRAFFIC_ANALYSIS_ZH_20261017.md','architecture_tlm/digital_attention_reference/README_ZH.md','architecture_tlm/SRAM_CACTI_CALIBRATION_V1_RESULTS_ZH_20261016.txt']:
    read(p)
external=[('120','ecb0f5efb19be8ad72bf7ef0ee0109a3decd5ca5','architecture_tlm/ffn_storage_contract/README_ZH.md'),('127','7fe9c05f68dc16767ab7828eb144943d171a85d0','architecture_tlm/ffn_dataflow_optimization/README_ZH.md'),('119','62591df15b1dbcc2d489b605fbabf65eec6b6b67','architecture_tlm/resource_optimization_v1/RESULTS_ZH.md')]
for number,commit,p in external:
    cache=Path(__file__).parent/'evidence'/f'pr{number}.md'
    raw=cache.read_bytes()
    idx.append(dict(path=p,commit=commit,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),status='open_unmerged_at_read',verification='GitHub content API exact fixed head'))
out=dict(scope='arithmetic recalculation of archived TLM and explicit capacity formulas; no new simulation',rows=rows,models=models,
    local_counter=dict(before_KiB=48,after_KiB=5,reduction_pct=100*(1-5/48)),
    partial_sum=dict(physical_KiB=56,logical_KiB=14,max_payload_reduction_pct=75),
    dram_state_example=dict(pd_reduction_pct=100*(1-.3480/.4824),sref_reduction_pct=100*(1-.2520/.4824)))
assert round(rows[4]['dram_saving_vs_bf16_pct'],2)==31.95
assert round(rows[7]['dram_saving_vs_bf16_pct'],2)==35.52
for name,obj in [('CALCULATIONS.json',out),('SOURCE_INDEX.json',dict(base=BASE,sources=idx))]:
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(cases=len(rows),source_files=len(idx),models=models),ensure_ascii=False))
