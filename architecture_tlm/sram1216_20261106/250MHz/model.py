"""Compose the native banked Attention model and GU16/Wd32 shared FFN."""
from types import MethodType
from collections import deque
from architecture_tlm.sram1216_20261106.model import make_model as compact_model
from architecture_tlm.attention_supply_front_20261107.model import install as attention_install
from .ffn_actor import common_stage

ATTENTION='m256_v2_s4_n4_tmicro4_r16'

def make_model(backend,cores=3,front_allowance=False,ingress_kib=16,**kwargs):
    if cores not in (2,3):raise ValueError('evaluate recommended3 or sensitivity2 shared cores')
    if front_allowance:raise ValueError('Explicit score front replaces old5.2us allowance')
    if ingress_kib not in (16,24):raise ValueError('current16 or reference24KiB ingress')
    h,m=compact_model(backend,configuration='compact1216',**kwargs)
    assert not h.now and not h.events and not h.pending and not h.return_occupied
    assert h.response_bytes==24576 and len(h.free_slots)==384
    h.response_bytes=ingress_kib*1024
    h.free_slots=deque(range(h.response_bytes//64))
    attention_install(m,ATTENTION,credits=8,policy='fair',supply='finite',
                      front=True,word_interleaved=True)
    from .clock_bridge import install as install_clock_bridge
    install_clock_bridge(m)
    assert h.mem.period==h.issue_period==h.common_period_ns==4
    assert m.state_ports==2 and m.common_state.size==96*1024
    m.common_cores=cores;m._common_stage=MethodType(common_stage,m)
    m.digital_contract.update(nonlinear='SC mode: fixed8 g/u amplitude codes, sigmoid P8 and three-wayAND directly into fixedWd',
        attention_QK_lanes_per_KVgroup=64,attention_PV_lanes_per_KVgroup=8,
        active_PV_groups=8,active_QK_groups=4)
    m.attention_adapter_contract.update(scope='integrated whole overlay',physical_instances=4,
        score_input='FP32 max/gap -> RNE/sat u8F4 -> floor sigmoid LUT -> P8; no new PPL')
    m.resource_contract.update(whole_token=True,FFN_shared_cores=cores,GU_samples=16,Wd_samples=32)
    m.resource_contract['ingress_holding_KiB']=ingress_kib
    m.ingress_capacity_contract=dict(clock_MHz=250,holding_KiB=ingress_kib,
        slots64B=len(h.free_slots),max_pending_requests=h.credit,
        return_lanes_per_channel=h.per_channel,
        reservation='pending64B+returned_not_landed<=holding_bytes',
        SRAM_KiB=1216,SRAM_banks=304,return_SRAM_reservation_KiB=32,
        unused_return_SRAM_reclaimed=False,physical_data_storage='existing gated-register proxy')
    m.short_FFN_contract=dict(GU_samples=16,Wd_samples=32,GU_frame_cycles=18,Wd_frame_cycles=34,
        GU_frame_ns=72,Wd_frame_ns=136,common_count_bits=19,external_count_bits=20,
        normalize_shifts=dict(GU=-4,Wd=-5),physical_cores=cores,weight_slots=32,
        programming_parallelism=32,result_credits_per_core=2,state_ports32=2,
        state32_II_cycles=1,state32_updates_per_frame=4,crossK_bits=64,
        exact_weighted_tree=True,OR=False,new_short_T_PPA=False,
        GU_output_quant_cycles=4,Wd_BF16_cycles=3,conversion_latency_is_macro=True,
        GU_input_bits=10,GU_input_payload_B=80,
        g8_encoding='signed two-complement; G/8 directly drives sigmoid',
        u8_encoding='independent sign plus7bit magnitude',
        Wd_input_payload_B=128,GU_normalization_shift=-4,Wd_normalization_shift=-5,
        RNG='local GF64 inside measured predecessor core; no extra threshold SRAM',
        scope='transactional contracts, not numerical Qwen or physical signoff')
    # Explicit per-head score preparation replaces both old65cycles and the
    # additional5.2us/layer allowance; no independent front delay is installed.
    m.unified_clock_contract.update(whole_model_enabled=True,GU_samples=16,Wd_samples=32,
        SRAM_access_is_macro_not_new_STA=True)
    old_run=m.run
    def run(self):
        r=old_run()
        r['ingress_capacity_contract']=dict(self.ingress_capacity_contract)
        r['executed_resources'].update(FP32_reduction_adders=16,QK_MAC_lanes=256,
            independent_QK_MAC_lanes=0,PV_sample_ADD_lanes=64,Ising_sampler_cores=4,
            SparQ_top_cores=4,SparQ_norm_cores=4)
        if 'joint_handoff_contract' in r:
            old=r['joint_handoff_contract'].pop('physical_profile',None)
            r['joint_handoff_contract']['historical_pre_overlay_profile']=old
            r['joint_handoff_contract']['active_profile']=self.resource_contract
        if 'ffn_sram_batch_contract' in r:r['ffn_sram_batch_contract']['memory']=self.compact_memory
        r['common_FFN'].update(weight_policy='32x8KiB slots; GU16/Wd32 resident samples; no per-sample ordinary SRAM weight read',
            count_bits=19,interface_count_bits=20)
        return r
    m.run=MethodType(run,m)
    return h,m
