"""Single-token SparQ at the native Qwen3 post-RoPE attention boundary.

The dense control calls Transformers' own SDPA helper, with its original layout,
dtype and scaling. SparQ's FP32 arithmetic is a separate numerical experiment.
"""
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from types import MethodType

import torch


class SparQController:
    def __init__(self, mode='sparq', config=None):
        if mode not in ('dense', 'sparq'):
            raise ValueError('mode must be dense or sparq')
        self.mode, self.config = mode, config
        self._originals, self.layers = [], {}
        self._prefill = False

    def install(self, model):
        if self._originals or model.training or model.config.model_type != 'qwen3':
            raise ValueError('fresh eval Qwen3 required')
        if model.config._attn_implementation != 'sdpa':
            raise ValueError('native SDPA implementation required')
        layers = list(model.model.layers)
        if len(layers) != model.config.num_hidden_layers or not layers:
            raise ValueError('configured layers are missing')
        for i, layer in enumerate(layers):
            a = layer.self_attn
            if (a.layer_idx != i or a.sliding_window is not None
                    or not hasattr(a, 'q_norm') or not hasattr(a, 'k_norm')
                    or hasattr(a, '_sparq_owner') or hasattr(a, '_joint_attention_owner')
                    or a.q_proj.out_features != a.config.num_attention_heads * a.head_dim
                    or a.o_proj.in_features != a.q_proj.out_features
                    or a.config.num_attention_heads % a.config.num_key_value_heads):
                raise ValueError('unsupported or already patched Qwen3 attention')
        if self.mode == 'sparq':
            from .core import SparQConfig
            if self.config is None:
                self.config = SparQConfig()
            elif isinstance(self.config, dict):
                self.config = SparQConfig(**self.config)
        for layer in layers:
            a = layer.self_attn
            self._originals.append((a, a.forward))
            self.layers[a.layer_idx] = dict(prefill_calls=0, decode_calls=0,
                prefill_query_tokens=0, decode_query_tokens=0, head_rows=0,
                kv_tokens_per_group=0, diagnostics={})
            a._sparq_owner = self
            a.forward = MethodType(self._dispatch, a)
        return self

    @contextmanager
    def prefill(self):
        """Even a one-token unscored prefix uses the native control path."""
        previous, self._prefill = self._prefill, True
        try:
            yield
        finally:
            self._prefill = previous

    def _dispatch(self, a, hidden_states, position_embeddings, attention_mask=None,
                  past_key_value=None, cache_position=None, **kwargs):
        state = self.layers[a.layer_idx]
        batch, length = hidden_states.shape[:2]
        if self._prefill or length != 1:
            state['prefill_calls'] += 1
            state['prefill_query_tokens'] += batch * length
            original = next(f for module, f in self._originals if module is a)
            return original(hidden_states, position_embeddings, attention_mask,
                past_key_value=past_key_value, cache_position=cache_position, **kwargs)
        if a.training or attention_mask is not None or kwargs.get('output_attentions', False):
            raise ValueError('only unmasked unpadded eval single-token decode is supported')
        from transformers.models.qwen3.modeling_qwen3 import apply_rotary_pos_emb
        shape = (*hidden_states.shape[:-1], -1, a.head_dim)
        q = a.q_norm(a.q_proj(hidden_states).view(shape)).transpose(1, 2)
        k = a.k_norm(a.k_proj(hidden_states).view(shape)).transpose(1, 2)
        v = a.v_proj(hidden_states).view(shape).transpose(1, 2)
        cos, sin = position_embeddings
        q, k = apply_rotary_pos_emb(q, k, cos, sin)
        if past_key_value is not None:
            k, v = past_key_value.update(k, v, a.layer_idx,
                {'cos': cos, 'sin': sin, 'cache_position': cache_position})
        state['decode_calls'] += 1
        state['decode_query_tokens'] += batch
        state['head_rows'] += batch * q.shape[1]
        state['kv_tokens_per_group'] += batch * k.shape[1] * k.shape[-2]
        if self.mode == 'dense':
            from transformers.integrations.sdpa_attention import sdpa_attention_forward
            out, _ = sdpa_attention_forward(a, q, k, v, None, dropout=0.0,
                                            scaling=a.scaling, sliding_window=None)
        else:
            from .core import sparq_attention
            out, diagnostics = sparq_attention(q, k, v, config=self.config,
                                                return_diagnostics=True)
            out = out.transpose(1, 2)
            self._record(state, diagnostics)
        out = out.reshape(*hidden_states.shape[:-1], -1).contiguous()
        if out.shape[-1] != a.o_proj.in_features:
            raise RuntimeError('Qwen3 attention output projection width changed')
        return a.o_proj(out.to(hidden_states.dtype)), None

    @staticmethod
    def _record(state, diagnostics):
        # Aggregate scalar counters on their device; never retain token-level
        # candidates or copy the full candidate set to the host per query. One
        # vector add avoids a separate CUDA launch for every diagnostic field.
        counts = diagnostics['logical_counts']
        names = tuple(counts)
        values = list(counts.values())
        if not values or any(not isinstance(v, torch.Tensor) or v.numel() != 1
                             or v.dtype != torch.int64 for v in values):
            raise RuntimeError('core logical counters must be int64 scalar tensors')
        vector = torch.stack([v.detach().reshape(()) for v in values])
        if '_counter_names' not in state:
            state['_counter_names'], state['_counter_totals'] = names, vector
        else:
            if state['_counter_names'] != names:
                raise RuntimeError('core logical counter schema changed during scoring')
            state['_counter_totals'].add_(vector)

    def stats(self):
        def plain(value):
            if isinstance(value, torch.Tensor):
                return value.detach().cpu().item()
            if isinstance(value, dict):
                return {str(k): plain(v) for k, v in value.items()}
            return value
        layers = {}
        for index, state in self.layers.items():
            row = {key: value for key, value in state.items() if not key.startswith('_')}
            if '_counter_totals' in state:
                numbers = state['_counter_totals'].detach().cpu().tolist()
                row['diagnostics'] = {'logical_counts.' + key: value
                                      for key, value in zip(state['_counter_names'], numbers)}
            layers[str(index)] = row
        return dict(mode=self.mode, config=asdict(self.config) if is_dataclass(self.config) else self.config,
                    installed_layers=len(self.layers), layers=plain(layers),
                    scope='all scored single-token queries; native QKV/QK-Norm/RoPE/cache/output projection; native dense prefill',
                    physical_PPA=None)

    def close(self):
        for a, original in self._originals:
            a.forward = original
            delattr(a, '_sparq_owner')
        self._originals.clear()

