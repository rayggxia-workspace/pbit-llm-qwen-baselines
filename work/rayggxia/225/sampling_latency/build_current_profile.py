"""Current1216KiB prefix extrapolation, explicitly retaining an lm_head proxy."""
from pathlib import Path
import hashlib,json
WD=Path(__file__).resolve().parents[4]
folder=WD/'architecture_tlm/sampling_latency_20261106';here=Path(__file__).parent
collection=json.loads((here/'COLLECTION.json').read_bytes())
rows={x['case']:x for x in collection['sealed'] if x['kind']=='prefix'}
assert set(rows)=={'T64_64','T8_32'}
a,b=rows['T64_64'],rows['T8_32']
same_actions=['digital_BF16_MAC','digital_FP32_reduce_ADD','attention_QK_MAC','PV_ADD',
    'samples','sampler_queries','SC_equivalent_MAC','crossK_updates']
for k in same_actions:assert a['actions'][k]==b['actions'][k],k
for k in ('dram_read_bytes','dram_write_bytes'):
    assert a['memory_counts'][k]==b['memory_counts'][k],k
assert b['actions']['GU_logical_R8_ports']*8==a['actions']['GU_logical_R8_ports']
assert b['actions']['NL_logical_R8_ports']*2==a['actions']['NL_logical_R8_ports']
assert a['memory']['capacity_KiB']==b['memory']['capacity_KiB']==1216
old=json.loads((folder/'REFERENCE_PROFILE.json').read_bytes())
# Two captured layers are extrapolated uniformly; the third captured Attention
# layer and actual full-token head are NOT measured by this shortcut.
phase={k:v*18 for k,v in a['phases_ms'].items() if k not in ('embedding','lm_head','final_norm')}
phase['embedding']=a['phases_ms']['embedding'];phase['final_norm']=old['phase_totals_ms']['final_norm']
phase['lm_head']=old['lm_head_stage_ms']
profile=dict(old,configuration='1216KiB_640FMA_prefix2_extrapolated_lm_head_proxy',
    phase_totals_ms=phase,including_lm_head_ms=sum(phase.values()),reference_completed_native=False,
    source_result=a['remote_result'],source_result_sha256=a['result_sha256'],
    source_seal_sha256=None,lm_head_stage_ms=old['lm_head_stage_ms'],
    use_scope='current two-layer native prefix extrapolation; head uses old1024FMA6.95415ms proxy, not measured640 head',
    extrapolated_layers=36,prefix_native_layers=2,old_lm_head_proxy_configuration=old['configuration'])
(folder/'CURRENT_PREFIX_PROFILE.json').write_bytes((json.dumps(profile,ensure_ascii=False,indent=2)+'\n').encode())
summary=dict(scope='completed native2-layer comparison, not full token',rows=[dict(
    case=x['case'],GU_samples=x['samples']['GU_samples'],NL_Wd_samples=x['samples']['NL_Wd_samples'],
    simulated_prefix2_ms=x['timing']['including_lm_head'],phases_ms=x['phases_ms'],
    GU_plus_Wd_ms=x['phases_ms']['GU']+x['phases_ms']['NL_Wd'],
    result_sha256=x['result_sha256'],DRAM_bytes=x['memory_counts']['dram_read_bytes']+x['memory_counts']['dram_write_bytes']) for x in (a,b)],
    total_change_percent=(b['timing']['including_lm_head']/a['timing']['including_lm_head']-1)*100,
    verified_same_actions=same_actions,DRAM_bytes_equal=True,R8_counts_scaled_correctly=True,
    source_collection_sha256=hashlib.sha256((here/'COLLECTION.json').read_bytes()).hexdigest(),
    current_T64_extrapolation=dict(including_lm_head_ms=sum(phase.values()),excluding_lm_head_stage_ms=sum(phase.values())-phase['lm_head'],lm_head_proxy_ms=phase['lm_head']))
(folder/'NATIVE_PREFIX_RESULTS.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(summary,ensure_ascii=True))
