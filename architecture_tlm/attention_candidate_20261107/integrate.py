"""Opt-in Attention resource candidate; no default or frozen-run mutation."""
from types import MethodType

def install(model, owner_install, case='combined32'):
    if case not in ('control','reduce32','qk_shared','pv128','combined32'):
        raise ValueError('use reviewed100MHz resource candidate')
    if model.h.now:raise ValueError('install before any transaction')
    owner_install(model,case)
    # The owner actor updates its resource_contract, but the inherited whole
    # model still reports the previous independent512QK/512PV/128reduce counts.
    # Keep the physical-resource ledger consistent with the selected scenario.
    parent=model.run
    def run(self):
        result=parent();contract=self.resource_contract
        resources=result.setdefault('executed_resources',{})
        resources.update(ordinary_MAC_lanes=640,
            QK_MAC_lanes=contract['independent_QK_lanes'],
            PV_MAC_lanes=0,PV_sample_ADD_lanes=contract['PV_ADD_lanes'],
            FP32_reduction_adders=contract['FP32_reduction_adders'],
            logical_QK_service_lanes=512)
        result['attention_candidate_integration']=dict(case=case,
            status='conditional_TLM_candidate_not_physical_release',
            physical_input_reordering_validated=False,
            PV4_mapped_gate_validation='failed_X_not_accepted',
            new_PV4_DC_area_used=False,
            price_policy='existingSS100_components;no newPT;no TT250 mixing',
            default_changed=False)
        return result
    model.run=MethodType(run,model)
    return model
