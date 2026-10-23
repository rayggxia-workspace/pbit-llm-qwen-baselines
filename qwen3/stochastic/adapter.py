"""Qwen3-specific plumbing; fixed Issue141 numerical sampler and max4 policy."""
from types import MethodType
import torch
from transformers.models.qwen3.modeling_qwen3 import apply_rotary_pos_emb
from transformers.integrations.sdpa_attention import sdpa_attention_forward
from .vendor.attention import JointAttentionController


class Qwen3Controller(JointAttentionController):
    def __init__(self, *args, sampler='none', **kwargs):
        super().__init__(*args, **kwargs)
        if sampler not in ('none', 'winner', 'rejection'):
            raise ValueError('unregistered sampler')
        if self.mode == 'screen_ising' and sampler == 'none':
            raise ValueError('explicit new sampler required; no silent CTMC fallback')
        self.sampler, self.kernel_activity = sampler, {}
        self.aliases = []

    def install(self, model):
        if self._originals or model.training or model.config.model_type != 'qwen3':
            raise ValueError('fresh eval Qwen3 required')
        if model.config._attn_implementation != 'sdpa':
            raise ValueError('native SDPA prefill required')
        layers = list(model.model.layers)
        assert len(layers) == model.config.num_hidden_layers
        for i, layer in enumerate(layers):
            a = layer.self_attn
            assert type(layer.mlp).__name__ == 'Qwen3MLP'
            assert a.layer_idx == i and a.sliding_window is None
            assert hasattr(a, 'q_norm') and hasattr(a, 'k_norm')
            assert not hasattr(a, '_joint_attention_owner')
            assert a.q_proj.out_features == a.config.num_attention_heads * a.head_dim
            assert a.o_proj.in_features == a.q_proj.out_features
            assert a.config.num_attention_heads % a.config.num_key_value_heads == 0
        self._model = model
        for layer in layers:
            a = layer.self_attn
            for name, value in [('num_heads', a.config.num_attention_heads),
                                ('num_key_value_heads', a.config.num_key_value_heads)]:
                assert not hasattr(a, name)
                setattr(a, name, value)
                self.aliases.append((a, name))
            self._originals.append((a, a.forward))
            a._joint_attention_owner = self
            a.forward = MethodType(self._dispatch, a)
        self.reset()
        return self

    def close(self):
        super().close()
        for a, name in self.aliases:
            delattr(a, name)
        self.aliases.clear()

    def _dispatch(self, a, hidden_states, position_embeddings, attention_mask=None,
                  past_key_value=None, cache_position=None, **kwargs):
        state = self._state[a.layer_idx]
        state['calls'] += 1
        if hidden_states.shape[1] != 1:
            state['prefill_calls'] += 1
            state['summary'] = None
            original = next(f for attn, f in self._originals if attn is a)
            return original(hidden_states, position_embeddings, attention_mask,
                past_key_value=past_key_value, cache_position=cache_position, **kwargs)
        state['decode_calls'] += 1
        if a.training or kwargs.get('output_attentions', False) or attention_mask is not None:
            raise ValueError('only unmasked, unpadded eval single-token decode')
        shape = (*hidden_states.shape[:-1], -1, a.head_dim)
        q = a.q_norm(a.q_proj(hidden_states).view(shape)).transpose(1, 2)
        k = a.k_norm(a.k_proj(hidden_states).view(shape)).transpose(1, 2)
        v = a.v_proj(hidden_states).view(shape).transpose(1, 2)
        cos, sin = position_embeddings
        q, k = apply_rotary_pos_emb(q, k, cos, sin)
        if past_key_value is not None:
            k, v = past_key_value.update(k, v, a.layer_idx,
                {'cos': cos, 'sin': sin, 'cache_position': cache_position})
        out = self._core(a, q, k, v)
        out = out.transpose(1, 2).reshape(*hidden_states.shape[:-1], -1).contiguous()
        assert out.shape[-1] == a.o_proj.in_features
        return a.o_proj(out), None

    def _core(self, a, q, k, v):
        if self.mode != 'digital_sdpa':
            return super()._core(a, q, k, v)
        # Call precisely the same Transformers implementation, including layout
        # and explicit scaling. This is the integration-equivalence control.
        out, _ = sdpa_attention_forward(a, q, k, v, None,
            dropout=0.0, scaling=a.scaling, sliding_window=None)
        chosen, raw = self._select(a, q, k)
        counts = torch.full((q.shape[0] * q.shape[1],), k.shape[-2],
                            device=q.device, dtype=torch.long)
        self._record_core(a, q, k.shape[-2], chosen, raw, counts, k.shape[-2], False, 0)
        return out.transpose(1, 2)

    def _sample_indices(self, logits, layer):
        if self.sampler == 'none':
            raise ValueError('no legacy sampling fallback')
        from .vendor.kernels import sample
        out, activity = sample(logits, self.samples, self.sampler,
            generator=self._generator(layer, logits.device, 'sampler'))
        self.kernel_activity[layer] = self.kernel_activity.get(layer, 0) + activity.sum(0)
        return out, dict(kind=self.sampler, ideal_fp32_response=True)

    def stats(self):
        result = super().stats()
        result.update(actual_sampler=self.sampler,
            kernel_activity={str(k): v.cpu().tolist() for k, v in self.kernel_activity.items()},
            kernel_activity_columns=['proposals_or_updates', 'accepted_or_retained',
                'collisions', 'empty_rejections', 'reference_accepts', 'final_shift_sum'],
            scope='all Qwen3 decode layers; native QK-Norm before RoPE, GQA/cache/QKV/Wo retained',
            limitation='ideal FP32 Philox Bernoulli; not hardware RNG, q/256 sampler or cycle-accurate PPA',
            sampler_parameters=dict(winner_initialization='argmax', winner_burn=0,
                winner_spacing=1, winner_shift=0, rejection_initial_shift=0,
                rejection_max_shift=24, rejection_cap_factor=128, no_second_PV_draw=True))
        return result
