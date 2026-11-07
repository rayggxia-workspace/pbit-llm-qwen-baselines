from pathlib import Path
import hashlib,importlib.util,json
WD=Path(__file__).resolve().parents[4]
prior=WD/'architecture_tlm/current_handoff_budget_20261106/estimate.py'
spec=importlib.util.spec_from_file_location('prior_budget',prior)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
inputs=json.loads(prior.with_name('INPUTS.json').read_bytes())
folder=WD/'architecture_tlm/sram1216_20261106'
summary=json.loads((folder/'RESULTS.json').read_bytes())
ratio=summary['rows'][2]['simulated_one_layer_ms']/summary['rows'][0]['simulated_one_layer_ms']
def scenario(ms):
    result=mod.evaluate(inputs,ms,304)
    result['Attention_128KiB_per_group_retained']=False
    result['Attention_KiB_per_group']=64
    result['ordinary_weight_slot_KiB']=80
    result['activation_KiB']=128
    return result
out=dict(scope='whole-token conditional repricing; not a full-token timing run',
    central50ms=scenario(50),time_sensitivity=dict(note='apply local synthetic one-layer slowdown to50ms only as sensitivity',
    multiplier=ratio,result=scenario(50*ratio)),local_mechanics_summary=summary['rows'],
    unpriced='new decoder/interconnect PPA',
    SRAM_dynamic_note='no capacity-ratio discount; inherited action rates;135-word one-layer difference not removed',
    source_sha256={p.relative_to(WD).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (prior,prior.with_name('INPUTS.json'),folder/'RESULTS.json')})
(folder/'BUDGET_ESTIMATE.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({k:out['central50ms'][k] for k in ('covered_area55_mm2','onchip_mJ','onchip_average_W','system_mJ_at4pJ')}))
