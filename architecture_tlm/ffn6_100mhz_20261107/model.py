"""Compose the current shared-QK host with six FFN cores and GU16/Wd32.

Sampling/normalization/width fields are hardware contracts, not a numerical
model implementation. No new C19 area discount is inferred from these fields.
"""
from types import MethodType
from architecture_tlm.sampling_latency_20261106.model import make_model as sampled_host
from architecture_tlm.attention_candidate_20261107.integrate import install as attention_install
from architecture_tlm.qk_supply_100mhz_20261107.model import install as supply_install

DEFAULT_CORES=6
GU_SAMPLES=16
WD_SAMPLES=32

def make_model(backend,*,owner_install,cores=DEFAULT_CORES,sram_configuration='compact1216',**kwargs):
    if cores not in (5,6,8,12):raise ValueError('use selected6, fallback8, reference12, or diagnostic5')
    for key in ('gu_samples','wd_samples','mode','ffn'):
        if key in kwargs:raise ValueError('sampling and algorithm fixed by selected candidate')
    h,m=sampled_host(backend,gu_samples=GU_SAMPLES,wd_samples=WD_SAMPLES,
        cores=cores,mode='ising',ffn='sc',sram_configuration=sram_configuration,**kwargs)
    attention_install(m,owner_install,'combined32')
    supply_install(m)
    assert m.common_cores==cores and m.gu==cores and m.nl==cores
    if sram_configuration not in ('compact1216','compact1184','compact1056','compact1088bw'):
        raise ValueError('unsupported current100 SRAM layout')
    expected={'compact1216':1216,'compact1184':1184,'compact1056':1056,'compact1088bw':1088}[sram_configuration]
    assert h.mem.capacity==expected*1024 and h.mem.nbank==expected//4
    assert len(m.cim_weight)==2 and sum(r.size for r in m.cim_weight)==32*8192
    assert m.common_state.size==96*1024 and m.state_ports==2
    m.ffn6_contract=dict(selected_default_cores=6,active_cores=cores,
        clock_MHz=100,GU_samples=16,Wd_samples=32,GU_II_cycles=18,Wd_II_cycles=34,
        GU_strata=16,Wd_grid=[4,2,4],GU_normalization_log2=4,Wd_normalization_log2=5,
        target_accumulator_bits=19,GU_required_bits=18,Wd_required_bits=19,
        external_result_bits=20,crossK_bits=64,actual_new_C19_RTL=False,
        normalization_is_macro_contract_not_numerical_inference=True,
        weight_slots=32,weight_slot_bytes=8192,state_KiB=96,state_ports=2,
        result_credits_per_core=2,SRAM_KiB=expected,SRAM_banks=h.mem.nbank,
        memory_layout_changed=sram_configuration!='compact1216',writer_parallelism_reduced=False,
        random_source_in_core_price=True,area_basis='old measured C20 price per core; no C19 discount',
        current_candidate_selected=True,historical_default_modified=False,
        unknown_interface='32 weight slots to6 compute peripherals routing/mux macro; not integrated CIM PPA')
    m.resource_contract.update(common_FFN_cores=cores,GU_samples=16,NL_Wd_samples=32)
    m.joint_handoff_contract['physical_profile']['actual_FFN_common_cores']=cores
    parent=m.run
    def run(self):
        result=parent()
        result['ffn6_contract']=dict(self.ffn6_contract)
        result['executed_resources']['physical_common_FFN_cores']=self.common_cores
        return result
    m.run=MethodType(run,m)
    return h,m
