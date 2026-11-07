"""Refresh current100 in place: measured short FFN and finite Attention supply."""
from types import MethodType
from .bindings import bind_attention, core_budget

def make_model(backend, *, owner_install, attention_source=None, **kwargs):
    from architecture_tlm.ffn6_100mhz_20261107.ingress16 import make_model as parent
    identity = bind_attention(attention_source)
    from architecture_tlm.attention_supply_front_20261107.adapter100 import install
    h,m = parent(backend, owner_install=owner_install, **kwargs)
    install(m, credits=8, policy='fair', supply='finite', front=True,
            word_interleaved=True)
    assert h.mem.period == 10 and h.response_bytes == 16384
    assert m.common_cores == 6 and m.mac_lanes == 640
    m.ffn6_contract.update(actual_new_C19_RTL=True,
        area_basis='SS100 shortT/C19 measured complete M128; raw area x0.81 once',
        actual_new_C19_implemented_in_transaction_actor=False,
        hardware_counter_contract_bits=19, production_quantizer_is_macro=True)
    m.ffn6_contract.update(GU_output_quant_cycles=4,Wd_BF16_cycles=3,
        g8_encoding='signed two-complement; G/8 directly drives sigmoid',
        u8_encoding='independent sign plus7bit magnitude',
        GU_input_payload_B=80,Wd_input_payload_B=128,normalization_shifts={'GU':-4,'Wd':-5})
    original = m.run
    def run(self):
        result = original()
        result['FFN_core_budget'] = core_budget(self.kernel_active, h.now, 6, 100)
        result['module_refresh_contract'] = dict(clock_MHz=100,
            external_attention_source=identity, finite_projection_FIFO_KiB=10,
            static_weight_format='[Kblock8][outputRow][8BF16]',
            inference_weight_transpose=False, wide_score_front=True,
            removed_legacy_sampler_front_cycles_per_query=65,
            score_gap='FP32 max-score -> RNE/sat u8F4 -> floor sigmoid LUT -> P8',
            stored_scores_are_FP32=True, FIFO_depth_packets=8,
            old_24KiB_and_250MHz_defaults_changed=False,
            numerical_model_or_new_PPL=False)
        return result
    m.run = MethodType(run,m)
    return h,m
