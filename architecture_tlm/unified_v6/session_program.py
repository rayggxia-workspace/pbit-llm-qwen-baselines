"""Software-side templates for prefill -> first token -> decode sessions."""
from dataclasses import dataclass, asdict
from math import ceil


@dataclass(frozen=True)
class Model:
    name: str = 'Qwen/Qwen3-4B'
    revision: str = '1cfa9a7208912126459214e8b04321603b3df60c'
    layers: int = 36
    hidden: int = 2560
    ffn: int = 9728
    q_heads: int = 32
    kv_heads: int = 8
    head_dim: int = 128
    vocab: int = 151936
    qk_norm: bool = True
    ffn_type: str = 'SWIGLU'

    def check(self):
        assert self.layers > 0 and self.hidden % 128 == 0 and self.ffn % 64 == 0
        assert self.q_heads % self.kv_heads == 0 and self.head_dim % 64 == 0
        assert self.ffn_type == 'SWIGLU', 'only implemented template accepted'
        assert self.vocab > 0


def layer_program(model):
    """Generic services; the device never parses a Hugging Face model config."""
    model.check()
    ops = ['ATTN_NORM', 'QKV']
    if model.qk_norm:
        ops += ['QK_NORM']
    return ops + ['ROPE', 'KV_APPEND', 'P_ATTENTION', 'O', 'ATTN_RESIDUAL',
                  'FFN_NORM', 'X_ENCODE', 'GU', 'GU_ENCODE', 'WD', 'FFN_RESIDUAL']


def compile_plan(model, hw, prompt, generated, requested_rows=4):
    model.check()
    assert prompt > 0 and generated > 0 and requested_rows > 0
    # All allocations are physical workspace, not unlimited Python tensors.
    # Keep encoded GU rows on chip; all-layer activations and KV have DRAM backing.
    rows = min(requested_rows, prompt, hw['state_slots'], hw['digital_context_values'] // 64)
    def live_bytes(r):
        return (r * (model.ffn // 64) * 288 + r * (model.hidden // 64) * 81
                + r * model.hidden * 3 + hw['state_slots'] * 384
                + 2 * 8192 + 16384 + 4096)
    while rows > 1 and live_bytes(rows) > hw['front_bytes']:
        rows -= 1
    assert live_bytes(rows) <= hw['front_bytes'], 'workspace cannot hold even one row'
    assert 2*(model.ffn//64)*(model.hidden//64)+hw['state_slots']*384 <= 32768, 'scale/state workspace too small'
    return dict(model=asdict(model), prompt=prompt, generated=generated,
                prefill_rows=rows, prefill_blocks=ceil(prompt / rows),
                max_live_front_bytes=live_bytes(rows),
                prefill_pcim_parallel_groups=min(hw['cores'], hw['state_slots'] // rows),
                program=layer_program(model),
                intermediate='FP24_E8_M15', weight='W8_FFN_BF16_QKVO_HEAD',
                activation_backing_bytes=2 * prompt * model.hidden * 3,
                gu_record_bytes_per_row=(model.ffn // 64) * 288,
                kv_layout='layer,token,kv_head,D; K and V separate BF16 arrays',
                model_parser='SOFTWARE', mapping='SOFTWARE',
                runtime='finite per-engine queues and completion dependencies',
                generation='GREEDY_TIMING; token identities supplied by trace',
                attention_addresses='SYNTHETIC_FINITE_TRACE_NOT_MODEL_QUALITY')
