"""Read-only oldseals + latestbindings;reprice,never mutate execution records."""
from pathlib import Path
from types import SimpleNamespace
import hashlib,importlib.util,json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];OUT=ROOT/'architecture_tlm/process_28nm'
load=lambda p:json.loads(p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
v=load(OUT/'WHOLE_VALIDATION.json');snapshot=Path(v['execution']['root'])
spec=importlib.util.spec_from_file_location('latest28price',OUT/'whole_pricing.py')
price=importlib.util.module_from_spec(spec);spec.loader.exec_module(price)
rows=[]
for case in v['cases']:
    folder=Path(case['original_result_path']);folder=folder if folder.is_absolute() else ROOT/folder
    seal=load(folder/'SEAL.json')
    for name,digest in seal['files_sha256'].items():assert sha(folder/name)==digest
    result=load(folder/'RESULT.json');old=load(folder/'BUDGET.json');n=str(result['clock_MHz'])
    prior=load(snapshot/(n+'MHz')/'BINDINGS.json');current=load(OUT/(n+'MHz')/'BINDINGS.json')
    host=SimpleNamespace(common_cores=result['FFN_cores'],sampler_pool=SimpleNamespace(slots=4),
        norm_pool=SimpleNamespace(slots=4),top_pool=SimpleNamespace(slots=4))
    assert price.price(host,result,prior)==old,'reprice must reproduce oldexactbudget'
    updated=price.price(host,result,current);assert updated==old,'activepricechange requires newresult'
    for key in ('FFN_core','FFN_shared_services','front_sampler_link'):assert current[key]==prior[key],key
    rows.append(dict(case=case['case'],time_ms=result['time_ms'],old_budget_sha256=sha(folder/'BUDGET.json'),
        new_binding_sha256=sha(OUT/(n+'MHz')/'BINDINGS.json'),active_budget_equal=True,active_service_contract_equal=True,
        covered_component_area_mm2=updated['covered_component_area_mm2'],covered_component_energy_mJ=updated['covered_component_energy_mJ']))
new={n:load(OUT/(n+'MHz')/'BINDINGS.json') for n in ('250','500')}
report=dict(status='LATEST_HANDOFF_REGISTERED_ACTIVE_SC_PRICE_AND_SERVICE_UNCHANGED',cases=rows,
    added_available_cards={'500MHz':['bf_explut_500'],'250MHz':['nl_code8_250','w8_wd_250']},
    already_available=['integer_gu_250','randomGU_Wd28','state32','codec','scale64','SparQ','S12front','gap_sampler'],
    registered_not_current_SC_dispatch=['integer_gu_250','nl_code8_250','w8_wd_250','bf_explut_500'],
    conditional_hold_only={n:list(b['conditional_attention_hold_cards']) for n,b in new.items()},
    PV_diagnostic_not_selected={n:[dict(top=c['top'],setup_ns=c['slacks_ns']['setup'],area_mm2=c['area28_mm2'])
        for c in b['diagnostic_PV_cards']] for n,b in new.items()},
    strict_SC500_area_mm2=new['500']['FFN_core']['area_mm2'],optimized_SC500_not_accepted_setup_ns=-.009314,
    shared_FMA500='NO_QUALIFIED_FMA500_PRICE',owner_handoff_state=new['500']['owner_handoff_status'],
    no_new_scheduler_RTL_PT_or_Slurm_run=True,new_binding_tests=6,old_frozen_results_modified=False,
    note='bindingavailability doesnotmeannewcards areexecuted;SCexcludesdigitalSoftmax/digitalFFN',
    source_sha256=new['500']['source_sha256'])
raw=(json.dumps(report,indent=2)+'\n').encode()
(OUT/'LATEST_INTAKE_20261109.json').write_bytes(raw);(HERE/'VALIDATION.json').write_bytes(raw)
print(json.dumps(dict(status=report['status'],reprice_cases=len(rows),conditional_hold_cards=report['conditional_hold_only'])))
