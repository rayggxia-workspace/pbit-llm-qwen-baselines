"""Decode-only Qwen2 adapter for max4 screening and finite-time Ising samples.

Numerical behavior reference, not a sparse CUDA performance implementation.
The fixed policy matches architecture_tlm.screen_ising_tlm_v4.budget_blocks:
mandatory first/last-two blocks, Bernoulli choices, then score quota repair.
An eight-block budget is AT MOST 512 valid tokens because of partial tails.
"""
import math
from types import MethodType

try:
    import torch
    from torch.nn import functional as F
except ImportError:  # Pure policy tests remain runnable in a stdlib environment.
    torch = None
    F = None


MODES = ('screen_ising', 'screen_exact', 'screen_iid', 'digital_exact', 'ising_only',
         'digital_sdpa')
METRICS = ('query_rows', 'query_token_rows', 'possible_candidates', 'selected_candidates',
           'padded_qk_candidates', 'selected_blocks', 'raw_selected_blocks',
           'quota_added', 'quota_removed', 'GQA_union_candidates',
           'GQA_possible_candidates', 'sample_events', 'adjacent_repeats',
           'adjacent_pairs')


def budget_blocks(scores, chosen, budget):
    """Scalar oracle with exactly the existing v4 ordering and tie break."""
    if type(budget) is not int or budget < 1 or not scores:
        raise ValueError('positive integer budget and nonempty scores required')
    n = len(scores)
    forced = {0, n - 1, max(0, n - 2)}
    if min(n, budget) < len(forced):
        raise ValueError('budget cannot hold mandatory blocks')
    chosen = set(chosen)
    ranked = sorted(range(n), key=lambda i: (i in forced, i in chosen,
                                             scores[i], -i), reverse=True)
    return sorted(ranked[:min(n, budget)])


def _fixed_mask(scores, raw, forced, budget):
    if min(scores.shape[-1], budget) < int(forced.sum()):
        raise ValueError('budget cannot hold mandatory blocks')
    # Stable sorts implement lexicographic (forced, raw, score, -index).
    order = torch.argsort(scores, dim=-1, descending=True, stable=True)
    for flags in (raw, forced.expand_as(raw)):
        priority = flags.gather(-1, order).to(torch.int32)
        permutation = torch.argsort(priority, dim=-1, descending=True, stable=True)
        order = order.gather(-1, permutation)
    return torch.zeros_like(raw).scatter_(-1, order[..., :min(budget, scores.shape[-1])], True)


def _rope(q, k, cos, sin):
    # Exact apply_rotary_pos_emb convention in Transformers 4.45.2 Qwen2.
    def rotate_half(x):
        first, second = x.chunk(2, dim=-1)
        return torch.cat((-second, first), dim=-1)
    cos, sin = cos.unsqueeze(1), sin.unsqueeze(1)
    return q * cos + rotate_half(q) * sin, k * cos + rotate_half(k) * sin


def _repeat_kv(hidden_states, n_rep):
    # Same expand/reshape layout as upstream/modeling_qwen2.py:280-289.
    batch, heads, length, dim = hidden_states.shape
    if n_rep == 1:
        return hidden_states
    return hidden_states[:, :, None, :, :].expand(batch, heads, n_rep, length, dim).reshape(
        batch, heads * n_rep, length, dim)


class JointAttentionController:
    def __init__(self, mode='screen_ising', samples=512, burn=16., spacing=4.,
                 seed=0, budget_blocks=8, selection='fixed', target_fraction=.30,
                 calibration=None):
        if mode not in MODES or selection not in ('fixed', 'variable'):
            raise ValueError('unknown attention mode or selection policy')
        if type(seed) is not int:
            raise ValueError('integer seed required')
        if type(samples) is not int or samples < 1:
            raise ValueError('positive integer samples required')
        if type(budget_blocks) is not int or budget_blocks < 3:
            raise ValueError('budget_blocks must hold first and last two blocks')
        if not math.isfinite(burn) or burn < 0 or not math.isfinite(spacing) or spacing <= 0:
            raise ValueError('finite burn>=0 and spacing>0 required')
        if not math.isfinite(target_fraction) or not 0 < target_fraction <= 1:
            raise ValueError('target_fraction must be in (0,1]')
        if torch is None:
            raise ImportError('Torch is required for the Qwen behavior adapter')
        self.mode, self.samples, self.burn, self.spacing = mode, samples, burn, spacing
        self.seed, self.budget, self.selection = seed, budget_blocks, selection
        self.target_fraction, self.calibration = target_fraction, calibration
        self._originals, self._state, self._rng = [], {}, {}
        self._model = None

    def install(self, model):
        if self._originals:
            raise RuntimeError('controller already installed')
        if model.training:
            raise ValueError('evaluation mode required')
        layers = list(model.model.layers)
        if len(layers) != getattr(model.config, 'num_hidden_layers', len(layers)):
            raise ValueError('decoder layer count differs from model configuration')
        for i, layer in enumerate(layers):
            a = layer.self_attn
            if type(layer.mlp).__name__ != 'Qwen2MLP':
                raise ValueError('original Qwen2MLP required in every layer')
            if getattr(a, 'layer_idx', None) != i:
                raise ValueError('ordered unique decoder layer indices required')
            if hasattr(a, '_joint_attention_owner'):
                raise RuntimeError('attention already patched')
            if a.num_heads % a.num_key_value_heads or a.head_dim % 2:
                raise ValueError('invalid GQA or RoPE head dimensions')
        self._model = model
        for layer in layers:
            a = layer.self_attn
            self._originals.append((a, a.forward))
            a._joint_attention_owner = self
            a.forward = MethodType(self._dispatch, a)
        self.reset()
        return self

    def reset(self):
        """Reset one complete evaluation, including RNG, counters and summaries.

        Do not call between batches when cumulative statistics are wanted.
        A multi-token prefill clears its layer summary automatically.
        """
        self._rng.clear()
        self._state = {a.layer_idx: dict(calls=0, prefill_calls=0, decode_calls=0,
            summary_builds=0, summary_updates=0, sampler_calls=0, summary=None,
            metrics=None, candidate_min=None, candidate_max=None,
            last_sampler_stats=None) for a, _ in self._originals}

    def close(self):
        for a, original in self._originals:
            if getattr(a, '_joint_attention_owner', None) is not self:
                raise RuntimeError('attention patch ownership changed')
            a.forward = original
            del a._joint_attention_owner
        self._originals.clear()
        self._model = None

    def _generator(self, layer, device, role):
        key = (layer, str(device), role)
        if key not in self._rng:
            offset = 2100 if role == 'selector' else 5100
            self._rng[key] = torch.Generator(device=device).manual_seed(self.seed * 10000 + layer + offset)
        return self._rng[key]

    def _summaries(self, a, k):
        state = self._state[a.layer_idx]
        old = state['summary']
        length, dim = k.shape[-2:]
        if old is None or old[0] != length - 1 or old[1].shape[:2] != k.shape[:2]:
            packed = F.pad(k.float(), (0, 0, 0, (-length) % 64))
            sums = packed.reshape(*k.shape[:2], -1, 4, 16, dim).sum(-2)
            state['summary_builds'] += 1
        else:
            sums = old[1]
            if (length - 1) % 64 == 0:
                sums = torch.cat((sums, torch.zeros_like(sums[:, :, :1])), dim=2)
            sums[:, :, -1, ((length - 1) % 64) // 16] += k[:, :, -1].float()
            state['summary_updates'] += 1
        state['summary'] = (length, sums)
        return sums

    def _calibration(self, length, layer, heads, device):
        params = self.calibration
        if params is None:
            return torch.zeros((1, heads, 1), device=device), torch.ones((1, heads, 1), device=device)
        if 'parameter' not in params:
            choices = [(int(key.split('_')[0]), key) for key in params
                       if key.endswith(f'_{self.target_fraction}_max4')]
            if not choices:
                raise ValueError('calibration lacks context/fraction/max4 parameters')
            eligible = [x for x in choices if x[0] <= length]
            params = params[max(eligible or choices)[1]]
        bias = torch.as_tensor(params['parameter'], device=device, dtype=torch.float32)[layer]
        temp = torch.as_tensor(params['temperature'], device=device, dtype=torch.float32)[layer]
        if bias.numel() != heads or temp.numel() != heads:
            raise ValueError('calibration head count mismatch')
        if not bool(torch.isfinite(bias).all() and torch.isfinite(temp).all() and (temp > 0).all()):
            raise ValueError('finite bias and positive finite temperature required')
        return bias.reshape(1, heads, 1), temp.reshape(1, heads, 1)

    def _select(self, a, q, k):
        length, dim = k.shape[-2:]
        blocks = math.ceil(length / 64)
        if not self.mode.startswith('screen_'):
            ones = torch.ones((*q.shape[:2], blocks), device=q.device, dtype=torch.bool)
            return ones, ones
        sums = self._summaries(a, k)
        ns = (length - torch.arange(blocks * 4, device=q.device) * 16).clamp(0, 16).reshape(blocks, 4)
        means = (sums / ns.clamp_min(1)[..., None]).repeat_interleave(a.num_key_value_groups, dim=1)
        values = (q.float().squeeze(-2)[:, :, None, None] * means).sum(-1) / math.sqrt(dim)
        scores = values.masked_fill(ns == 0, -torch.inf).amax(-1)
        forced = (torch.arange(blocks, device=q.device) == 0) | (torch.arange(blocks, device=q.device) >= blocks - 2)
        free = (~forced).float()
        mean = (scores * free).sum(-1, keepdim=True) / free.sum().clamp_min(1)
        std = (((scores - mean).square() * free).sum(-1, keepdim=True) / free.sum().clamp_min(1)).sqrt().clamp_min(.01)
        bias, temp = self._calibration(length, a.layer_idx, q.shape[1], q.device)
        pi = (((scores - mean) / std + bias) / temp).sigmoid().masked_fill(forced, 1.)
        raw = torch.rand(pi.shape, device=q.device,
                         generator=self._generator(a.layer_idx, q.device, 'selector')) < pi
        chosen = _fixed_mask(scores, raw, forced, self.budget) if self.selection == 'fixed' else raw
        return chosen, raw

    def _sample_indices(self, logits, layer):
        generator = self._generator(layer, logits.device, 'sampler')
        if self.mode == 'screen_iid':
            return torch.multinomial(logits.softmax(-1), self.samples, True, generator=generator), {'kind': 'iid_softmax_control'}
        from .ctmc import ct_mc_indices
        return ct_mc_indices(logits, self.samples, self.burn, self.spacing,
                             generator=generator, max_events=32768)

    def _core(self, a, q, k, v):
        batch_size, heads, _, dim = q.shape
        length = k.shape[-2]
        chosen, raw = self._select(a, q, k)
        if self.mode == 'digital_sdpa':
            # Wrapper diagnostic: preserve input dtype and the exact original
            # Qwen SDPA invocation. Do not materialize FP32 scores/softmax here.
            out = F.scaled_dot_product_attention(
                q, _repeat_kv(k, a.num_key_value_groups),
                _repeat_kv(v, a.num_key_value_groups),
                attn_mask=None, dropout_p=0.0, is_causal=False)
            counts = torch.full((batch_size * heads,), length, device=q.device, dtype=torch.long)
            self._record_core(a, q, length, chosen, raw, counts, length, False, 0)
            return out
        tokens = chosen.repeat_interleave(64, dim=-1)[..., :length].reshape(-1, length)
        counts = tokens.sum(-1)
        if not bool((counts > 0).all()):
            raise RuntimeError('empty attention candidate row')
        width = int(counts.max())
        row, address = tokens.nonzero(as_tuple=True)
        slot = tokens.long().cumsum(-1)[row, address] - 1
        index = torch.zeros((batch_size * heads, width), device=q.device, dtype=torch.long)
        index[row, slot] = address
        valid = torch.arange(width, device=q.device)[None, :] < counts[:, None]
        rows = torch.arange(batch_size * heads, device=q.device)
        batch, kvhead = rows // heads, (rows % heads) // a.num_key_value_groups
        keys = k[batch[:, None], kvhead[:, None], index].float()
        logits = torch.bmm(q.reshape(-1, 1, dim).float(), keys.transpose(1, 2)).squeeze(1) / math.sqrt(dim)
        logits = logits.masked_fill(~valid, -torch.inf)
        if not bool(torch.isfinite(logits[valid]).all()):
            raise RuntimeError('nonfinite valid candidate logits')
        state = self._state[a.layer_idx]
        sampled = self.mode in ('screen_ising', 'screen_iid', 'ising_only')
        adjacent = logits.new_tensor(0.)
        if sampled:
            local, sampler_stats = self._sample_indices(logits, a.layer_idx)
            if local.shape != (batch_size * heads, self.samples) or local.dtype != torch.long:
                raise RuntimeError('sampler index shape/dtype contract violated')
            if not bool(((local >= 0) & (local < counts[:, None])).all()):
                raise RuntimeError('sampler returned padding or out-of-range index')
            addresses = index.gather(1, local)
            out = v[batch[:, None], kvhead[:, None], addresses].float().mean(1)
            adjacent = (local[:, 1:] == local[:, :-1]).sum()
            state['sampler_calls'] += 1
            state['last_sampler_stats'] = sampler_stats
        else:
            values = v[batch[:, None], kvhead[:, None], index].float()
            out = torch.bmm(logits.softmax(-1).unsqueeze(1), values).squeeze(1)
        self._record_core(a, q, length, chosen, raw, counts, width, sampled, adjacent)
        return out.reshape(batch_size, heads, 1, dim).to(q.dtype)

    def _record_core(self, a, q, length, chosen, raw, counts, width, sampled, adjacent):
        batch_size, heads = q.shape[:2]
        state = self._state[a.layer_idx]
        sizes = (length - torch.arange(chosen.shape[-1], device=q.device) * 64).clamp(1, 64)
        union = chosen.reshape(batch_size, a.num_key_value_heads, a.num_key_value_groups, -1).any(2)
        items = (batch_size * heads, batch_size, batch_size * heads * length, counts.sum(),
                 batch_size * heads * width, chosen.sum(), raw.sum(),
                 (chosen & ~raw).sum(), (raw & ~chosen).sum(),
                 (union * sizes).sum(), batch_size * a.num_key_value_heads * length,
                 batch_size * heads * self.samples if sampled else 0,
                 adjacent, batch_size * heads * max(self.samples - 1, 0) if sampled else 0)
        values = torch.stack([torch.as_tensor(x, device=q.device, dtype=torch.float64) for x in items])
        state['metrics'] = values if state['metrics'] is None else state['metrics'] + values
        state['candidate_min'] = counts.min() if state['candidate_min'] is None else torch.minimum(state['candidate_min'], counts.min())
        state['candidate_max'] = counts.max() if state['candidate_max'] is None else torch.maximum(state['candidate_max'], counts.max())

    def _dispatch(self, a, hidden_states, attention_mask=None, position_ids=None,
                  past_key_value=None, output_attentions=False, use_cache=False,
                  cache_position=None, position_embeddings=None):
        state = self._state[a.layer_idx]
        state['calls'] += 1
        if hidden_states.shape[1] != 1:
            state['prefill_calls'] += 1
            state['summary'] = None
            original = next(original for attn, original in self._originals if attn is a)
            return original(hidden_states, attention_mask=attention_mask, position_ids=position_ids,
                            past_key_value=past_key_value, output_attentions=output_attentions,
                            use_cache=use_cache, cache_position=cache_position,
                            position_embeddings=position_embeddings)
        state['decode_calls'] += 1
        if a.training or output_attentions or attention_mask is not None:
            raise ValueError('supports eval, unpadded, unmasked single-token cached decode only')
        b, n, _ = hidden_states.shape
        q = a.q_proj(hidden_states).view(b, n, a.num_heads, a.head_dim).transpose(1, 2)
        k = a.k_proj(hidden_states).view(b, n, a.num_key_value_heads, a.head_dim).transpose(1, 2)
        v = a.v_proj(hidden_states).view(b, n, a.num_key_value_heads, a.head_dim).transpose(1, 2)
        cos, sin = a.rotary_emb(v, position_ids) if position_embeddings is None else position_embeddings
        q, k = _rope(q, k, cos, sin)
        if past_key_value is not None:
            k, v = past_key_value.update(k, v, a.layer_idx,
                                        {'sin': sin, 'cos': cos, 'cache_position': cache_position})
        if k.shape[-2] != v.shape[-2] or k.shape[1] != a.num_key_value_heads:
            raise ValueError('unexpected dynamic K/V cache layout')
        out = self._core(a, q, k, v)
        out = out.transpose(1, 2).contiguous().reshape(b, n, a.hidden_size)
        return a.o_proj(out), None, past_key_value

    def stats(self):
        layers, total = {}, dict.fromkeys(METRICS, 0.)
        for i, state in sorted(self._state.items()):
            metrics = dict(zip(METRICS, state['metrics'].tolist())) if state['metrics'] is not None else dict.fromkeys(METRICS, 0.)
            for key, value in metrics.items():
                total[key] += value
            layers[str(i)] = {k: state[k] for k in ('calls', 'prefill_calls', 'decode_calls', 'summary_builds', 'summary_updates', 'sampler_calls')}
            layers[str(i)].update(metrics, candidate_min=int(state['candidate_min']) if state['candidate_min'] is not None else None,
                                  candidate_max=int(state['candidate_max']) if state['candidate_max'] is not None else None,
                                  last_sampler_stats=state['last_sampler_stats'])
        total['selected_fraction'] = total['selected_candidates'] / max(total['possible_candidates'], 1)
        total['GQA_union_fraction'] = total['GQA_union_candidates'] / max(total['GQA_possible_candidates'], 1)
        total['adjacent_repeat_fraction'] = total['adjacent_repeats'] / max(total['adjacent_pairs'], 1)
        return dict(mode=self.mode, samples=self.samples, burn=self.burn, spacing=self.spacing,
                    seed=self.seed, selection=self.selection, budget_blocks=self.budget,
                    target_fraction=self.target_fraction,
                    calibration=('provided' if self.calibration is not None else 'UNCALIBRATED_bias0_temperature1') if self.mode.startswith('screen_') else 'not_used',
                    installed_layers=len(self._originals), layers=layers, totals=total,
                    core_precision='model_dtype_SDPA_wrapper_diagnostic' if self.mode == 'digital_sdpa' else 'FP32_QK_and_exact_Softmax_PV_or_sampled_V_mean',
                    metric_units={'query_rows': 'batch-times-Q-heads per decode call',
                                  'query_token_rows': 'batch tokens per decode call'},
                    rng_scope='independent per-layer selector/sampler streams; seed excludes S/backend; paired only for fixed batch and step ordering',
                    scope='all installed decode layers; original QKV/RoPE/cache/Wo and FFN; original multi-token prefill',
                    limitation='behavior only; hard-constraint CTMC process time is not hardware cycles; fixed blocks allow partial-tail candidate counts')
