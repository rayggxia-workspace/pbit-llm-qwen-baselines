"""Llama-only integration; preserve upstream Qwen guards and numerical kernels.

Llama 2 HF 4.45.2 uses the same RoPE, cache, projection and return conventions
as the inherited dispatch. CPU/GPU digital_sdpa equivalence is a release gate.
This experiment uses ising_only, never Qwen-derived screening calibration.
"""
from types import MethodType

from experiments.qwen_joint_stratified_attention_20261019 import joint_evaluate as joint
from experiments.qwen_joint_stratified_attention_20261019.upstream_attention import evaluate as upstream
from experiments.qwen_joint_stratified_attention_20261019.upstream_attention.attention import (
    JointAttentionController as QwenController)

ExecutionAudit = joint.ExecutionAudit  # Hook lengths are derived from supplied layers.


def pack_weight_codes(module):
    """Lossless storage only. Forward uses untouched FP32 decoded weights.

    Historical W8 codes occupy INT16 buffers for software convenience. Packing
    each layer immediately saves one byte per FFN weight before the next layer
    is quantized. Retaining INT16 until every layer is installed can OOM on a
    32GB GPU with another 1.24GiB process, despite a successful idle-card pilot.
    """
    import torch
    for name in ('gu_codes', 'down_codes'):
        original = getattr(module, name)
        packed = original.to(torch.int8)
        if not torch.equal(packed.to(original.dtype), original):
            raise RuntimeError('W8 storage packing would change an integer code')
        setattr(module, name, packed)
    return module


def _install_ffn(model, case):
    if case['ffn'] == 'none':
        return
    from experiments.qwen_multiscale_stratified_20261019.stratified_core import StratifiedFFN
    for index, layer in enumerate(model.model.layers):
        replacement = StratifiedFFN(layer.mlp, mode='sampled', seed=case['seed'],
                                   layer=index, **joint.FFN_CONFIGS[case['ffn']]).eval()
        layer.mlp = pack_weight_codes(replacement)


def _case(case):
    result = upstream._case(case)
    result.setdefault('ffn', 'none')
    if result['mode'] not in ('sdpa', 'digital_sdpa', 'ising_only'):
        raise ValueError('Llama task scope is original SDPA or unscreened CTMC')
    if result['ffn'] not in ('none', 'b4_t32'):
        raise ValueError('Llama task scope is original FFN or B4/T32/K32')
    return result


def check_original(model):
    layers = list(model.model.layers)
    if model.config.model_type != 'llama' or model.training or len(layers) != 32:
        raise ValueError('fresh eval Llama with 32 layers required')
    if model.config.num_hidden_layers != 32:
        raise ValueError('configuration layer count mismatch')
    for i, layer in enumerate(layers):
        a = layer.self_attn
        if type(layer.mlp).__name__ != 'LlamaMLP' or type(a).__name__ != 'LlamaSdpaAttention':
            raise ValueError('original LlamaMLP and LlamaSdpaAttention required')
        if a.layer_idx != i or hasattr(a, '_joint_attention_owner'):
            raise ValueError('ordered unpatched attention required')
        if a.num_heads != a.num_key_value_heads or a.num_key_value_groups != 1:
            raise ValueError('Llama 2 7B MHA required')
        if a.head_dim % 2 or model.config.pretraining_tp != 1:
            raise ValueError('native even-dimensional RoPE and pretraining_tp=1 required')
    return layers


class JointAttentionController(QwenController):
    def install(self, model):
        if self._originals:
            raise RuntimeError('controller already installed')
        layers = check_original(model)
        self._model = model
        for layer in layers:
            a = layer.self_attn
            self._originals.append((a, a.forward))
            a._joint_attention_owner = self
            a.forward = MethodType(self._dispatch, a)
        self.reset()
        return self


class ModelGuard(joint.ModelGuard):
    def __init__(self, model, ffn):
        self.model, self.ffn = model, ffn
        self.layers = list(model.model.layers)
        if model.config.model_type != 'llama' or len(self.layers) != 32 or model.training:
            raise ValueError('32-layer Llama eval model required')
        expected = 'LlamaMLP' if ffn == 'none' else 'StratifiedFFN'
        if any(type(layer.mlp).__name__ != expected for layer in self.layers):
            raise ValueError('unexpected Llama task FFN type')
        self.mlp_ids = [id(layer.mlp) for layer in self.layers]
        self.parameters = self.snapshot_parameters()
        self.weights = self.snapshot_weights()
