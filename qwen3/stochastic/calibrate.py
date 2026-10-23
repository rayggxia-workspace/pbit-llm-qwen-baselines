"""TRAIN-only scalar bias fit, frozen temperature=1; report disjoint TRAIN holdout."""
import math
import torch
from transformers.models.qwen3.modeling_qwen3 import apply_rotary_pos_emb
from .vendor.scoring import ids_sha256


def calibrate(model, train_ids, context=2048, fit_examples=16, holdout_examples=16):
    count = fit_examples + holdout_examples
    starts = [round((len(train_ids) - context) * i / (count - 1)) for i in range(count)]
    assert all(b - a >= context for a, b in zip(starts, starts[1:]))
    records = [[] for _ in model.model.layers]
    handles = []
    def hook(a, args, kwargs):
        hidden = kwargs.get('hidden_states', args[0] if args else None)
        shape = (*hidden.shape[:-1], -1, a.head_dim)
        q = a.q_norm(a.q_proj(hidden).view(shape)).transpose(1, 2)
        k = a.k_norm(a.k_proj(hidden).view(shape)).transpose(1, 2)
        q, k = apply_rotary_pos_emb(q, k, *kwargs['position_embeddings'])
        blocks = context // 64
        means = k.float().reshape(1, a.config.num_key_value_heads, blocks, 4, 16, a.head_dim).mean(-2)
        means = means.repeat_interleave(a.num_key_value_groups, 1)
        scores = (q[:, :, -1:].float().unsqueeze(-2) * means).sum(-1).amax(-1) / math.sqrt(a.head_dim)
        free = scores[:, :, 1:-2]
        z = (free - free.mean(-1, keepdim=True)) / free.std(-1, unbiased=False, keepdim=True).clamp_min(.01)
        records[a.layer_idx].append(z[0].cpu())
    try:
        for layer in model.model.layers:
            handles.append(layer.self_attn.register_forward_pre_hook(hook, with_kwargs=True))
        with torch.inference_mode():
            for start in starts:
                model.model(input_ids=train_ids[start:start + context][None].to(next(model.parameters()).device), use_cache=False)
    finally:
        for handle in handles:
            handle.remove()
    # Overall expected raw keep rate=.30, with 3 mandatory out of 32 blocks.
    # This is distinct from fixed quota 8/32 after repair. No test-set tuning.
    blocks = context // 64
    desired_free = (.30 * blocks - 3) / (blocks - 3)
    assert 0 < desired_free < 1
    biases, reports = [], []
    for layer in records:
        values = torch.stack(layer)
        fit, held = values[:fit_examples], values[fit_examples:]
        lo = torch.full((values.shape[1],), -40.)
        hi = -lo
        for _ in range(60):
            mid = (lo + hi) / 2
            rate = torch.sigmoid(fit + mid[None, :, None]).mean((0, 2))
            lo, hi = torch.where(rate < desired_free, mid, lo), torch.where(rate < desired_free, hi, mid)
        bias = (lo + hi) / 2
        biases.append(bias.tolist())
        reports.append(dict(fit_raw_fraction=((torch.sigmoid(fit + bias[None, :, None]).mean((0, 2)) * (blocks - 3) + 3) / blocks).tolist(),
            holdout_raw_fraction=((torch.sigmoid(held + bias[None, :, None]).mean((0, 2)) * (blocks - 3) + 3) / blocks).tolist()))
    return dict(parameter=biases, temperature=torch.ones(len(records), model.config.num_attention_heads).tolist(),
        method='TRAIN-only per-layer/Q-head scalar bias; temperature fixed 1; free-block std floor .01',
        context=context, target_raw_fraction=.30, repaired_budget_blocks=8, fit_examples=fit_examples,
        holdout_examples=holdout_examples, starts=starts, per_layer=reports,
        train_token_ids_sha256_le_int64=ids_sha256(train_ids.tolist()), test_used_for_fit=False,
        limitation='Qwen3-specific scalar calibration, not transplanted Qwen2.5 checkpoint; fixed 2048 fit used across decode lengths')
