"""Numerical SparQ GQA reference; this is not a fused sparse-memory kernel.

Inputs are post-QK-normalisation/post-RoPE and include the current cached token.
All masks use True=visible. See SOURCE_AUDIT_ZH.md for paper/tag differences.
"""
from dataclasses import dataclass
import math

import torch
from torch import Tensor


@dataclass(frozen=True)
class SparQConfig:
    r: int = 32
    k_total: int = 128
    local_total: int = 32
    reallocation: bool = False
    selection: str = "probability_sum"
    validate_finite: bool = True

    def __post_init__(self):
        for name in ("r", "k_total", "local_total"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        if self.r < 1 or self.k_total < 1 or not 0 <= self.local_total <= self.k_total:
            raise ValueError("require r,k_total>=1 and 0<=local_total<=k_total")
        if self.selection not in ("probability_sum", "raw_score_sum"):
            raise ValueError("unknown selection law")
        if not isinstance(self.reallocation, bool) or not isinstance(self.validate_finite, bool):
            raise ValueError("reallocation and validate_finite must be booleans")


def _checked_inputs(q, k, v, valid_mask, config):
    if q.ndim != 4 or k.ndim != 4 or v.shape != k.shape:
        raise ValueError("require q[B,Hq,1,D] and matching k/v[B,Hkv,N,D]")
    b, hq, query_length, d = q.shape
    if query_length != 1 or min(b, hq, d, k.shape[1], k.shape[2]) < 1:
        raise ValueError("core supports nonempty single-query decode only")
    if k.shape[0] != b or k.shape[-1] != d or hq % k.shape[1]:
        raise ValueError("incompatible batch/head/dimension shapes")
    if config.r > d:
        raise ValueError("r must not exceed head dimension")
    if not q.is_floating_point() or q.dtype not in (torch.float16, torch.bfloat16, torch.float32, torch.float64):
        raise ValueError("require real floating-point tensors")
    if q.device != k.device or q.device != v.device or q.dtype != k.dtype or q.dtype != v.dtype:
        raise ValueError("q/k/v must share device and dtype")
    if valid_mask is None:
        valid_mask = torch.ones((b, k.shape[2]), dtype=torch.bool, device=q.device)
    if valid_mask.shape != (b, k.shape[2]) or valid_mask.dtype != torch.bool or valid_mask.device != q.device:
        raise ValueError("valid_mask must be bool[B,N] on the input device")
    if not bool(valid_mask.any(-1).all()):
        raise ValueError("each batch row needs at least one visible key")
    if config.validate_finite:
        visible = valid_mask[:, None, :, None]
        if not bool(torch.isfinite(q).all()):
            raise ValueError("query contains nonfinite values")
        if not bool((torch.isfinite(k) | ~visible).all()) or not bool((torch.isfinite(v) | ~visible).all()):
            raise ValueError("visible key/value contains nonfinite values")
    return valid_mask


def sparq_attention(q: Tensor, k: Tensor, v: Tensor, *, config: SparQConfig = SparQConfig(),
                    valid_mask: Tensor | None = None, return_diagnostics: bool = False):
    """Return q-shaped output, optionally (output, diagnostics).

    `k_total` and `local_total` INCLUDE the current token. Channels and candidate
    indices are shared per KV group; temperature, softmax and output are per Q.
    `raw_score_sum` with k_total=k_tag+1/local_total=local_tag+1 is a separately
    labelled official-2024-05-tag comparison, not paper-v6 probability selection.

    Float16/BF16/FP32 inputs use FP32 arithmetic; float64 uses float64. Dense
    fallback is a numerical reference, NOT bitwise native BF16 SDPA. No KV is
    evicted. Finite validation scans the full visible KV: disable only explicitly
    after integration validation, and never count this reference as sparse HBM.
    """
    valid = _checked_inputs(q, k, v, valid_mask, config)
    b, hq, _, d = q.shape
    hkv, n = k.shape[1:3]
    g = hq // hkv
    compute_dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    query = q.to(compute_dtype).reshape(b, hkv, g, d)
    visible = valid[:, None, :, None]
    key = torch.where(visible, k.to(compute_dtype), 0)
    value = torch.where(visible, v.to(compute_dtype), 0)
    nv = valid.sum(-1)[:, None].expand(b, hkv)
    full_budget = nv <= config.k_total
    reason = full_budget.to(torch.int64)  # 0=sparse, 1=full budget, 2=zero coverage
    channels = torch.full((b, hkv, config.r), -1, dtype=torch.long, device=q.device)
    count = min(config.k_total, n)
    candidates = torch.full((b, hkv, count), -1, dtype=torch.long, device=q.device)
    alpha = torch.ones((b, hkv, g, 1), dtype=compute_dtype, device=q.device)
    scale = torch.full((b, hkv, g, 1), math.sqrt(d), dtype=compute_dtype, device=q.device)
    mask = valid[:, None, None, :]

    # Static short-cache path avoids routing; no forced singleton candidate claim.
    if n <= config.k_total:
        logits = (query / math.sqrt(d)) @ key.transpose(-1, -2)
        result = logits.masked_fill(~mask, -torch.inf).softmax(-1) @ value
    else:
        channels = query.abs().sum(2).topk(config.r, dim=-1).indices
        q_sub = query.gather(-1, channels[:, :, None, :].expand(b, hkv, g, config.r))
        total_l1 = query.abs().sum(-1, keepdim=True)
        selected_l1 = q_sub.abs().sum(-1, keepdim=True)
        zero = ((total_l1 == 0) | (selected_l1 == 0)).any(2).squeeze(-1)
        reason = torch.where(~full_budget & zero, 2, reason)
        fallback = reason != 0
        # Safe placeholder temperature is never used as an approximation for an
        # affected group: its FINAL result is replaced with full dense attention.
        safe_total = torch.where(total_l1 > 0, total_l1, 1)
        scale = torch.sqrt(d * (selected_l1 / safe_total))
        scale = torch.where(scale > 0, scale, 1)
        k_sub = key.gather(-1, channels[:, :, None, :].expand(b, hkv, n, config.r))
        approx_logits = ((q_sub / scale) @ k_sub.transpose(-1, -2)).masked_fill(~mask, -torch.inf)
        approx_prob = approx_logits.softmax(-1)
        score = (approx_prob if config.selection == "probability_sum" else approx_logits).sum(2)
        score = score.masked_fill(~valid[:, None, :], -torch.inf)
        # Causal order is input cache order. Count only visible positions, so
        # left padding and holes cannot displace the current/recent valid rows.
        rank_from_right = valid.to(torch.int64).flip(-1).cumsum(-1).flip(-1)
        local = valid & (rank_from_right <= config.local_total)
        score = score.masked_fill(local[:, None, :], torch.inf)
        indices = score.topk(count, dim=-1).indices
        ki = indices[:, :, :, None].expand(b, hkv, count, d)
        chosen_key, chosen_value = key.gather(2, ki), value.gather(2, ki)
        chosen_valid = valid[:, None, :].expand(b, hkv, n).gather(-1, indices)
        logits = ((query / math.sqrt(d)) @ chosen_key.transpose(-1, -2)).masked_fill(~chosen_valid[:, :, None, :], -torch.inf)
        result = logits.softmax(-1) @ chosen_value
        if config.reallocation:
            alpha = approx_prob.gather(-1, indices[:, :, None, :].expand(b, hkv, g, count)).sum(-1, keepdim=True)
            mean = value.sum(2) / nv[:, :, None]
            result = alpha * result + (1 - alpha) * mean[:, :, None, :]
        if bool(fallback.any()):
            dense_logits = ((query / math.sqrt(d)) @ key.transpose(-1, -2)).masked_fill(~mask, -torch.inf)
            dense_result = dense_logits.softmax(-1) @ value
            result = torch.where(fallback[:, :, None, None], dense_result, result)
            alpha = torch.where(fallback[:, :, None, None], 1, alpha)
        candidates = indices.masked_fill(fallback[:, :, None], -1)
        channels = channels.masked_fill(fallback[:, :, None], -1)

    output = result.reshape(b, hq, 1, d).to(q.dtype)
    if config.validate_finite and not bool(torch.isfinite(output).all()):
        raise ValueError("attention arithmetic overflow/nonfinite output")
    if not return_diagnostics:
        return output
    sparse = reason == 0
    dense = ~sparse
    sparse_rows = sparse.to(torch.int64) * config.k_total
    dense_rows = dense.to(torch.int64) * nv
    route_rows = sparse.to(torch.int64) * nv
    counts = {
        "query_groups": nv.new_tensor(b * hkv),
        "sparse_groups": sparse.sum(),
        "dense_groups": dense.sum(),
        "full_budget_groups": (reason == 1).sum(),
        "zero_coverage_groups": (reason == 2).sum(),
        "routing_key_elements": route_rows.sum() * config.r,
        "selected_key_elements": sparse_rows.sum() * d,
        "selected_value_elements": sparse_rows.sum() * d,
        "dense_key_elements": dense_rows.sum() * d,
        "dense_value_elements": dense_rows.sum() * d,
        "mean_value_elements": route_rows.sum() * d if config.reallocation else nv.new_zeros(()),
        "routing_qk_macs": route_rows.sum() * g * config.r,
        "selected_qk_macs": sparse_rows.sum() * g * d,
        "selected_pv_macs": sparse_rows.sum() * g * d,
        "dense_qk_macs": dense_rows.sum() * g * d,
        "dense_pv_macs": dense_rows.sum() * g * d,
        "approx_softmax_elements": route_rows.sum() * g,
        "exact_softmax_elements": (sparse_rows + dense_rows).sum() * g,
        "validation_kv_elements": nv.sum() * d * 2 if config.validate_finite else nv.new_zeros(()),
    }
    return output, {
        "candidate_ids": candidates,
        "channel_ids": channels,
        "group_fallback_reason": reason,
        "valid_counts": nv,
        "selected_counts": torch.where(dense, nv, config.k_total),
        "all_groups_full_budget": full_budget.all(),
        "temperature": scale,
        "alpha": alpha,
        "logical_counts": counts,
        "compute_dtype": str(compute_dtype),
        "cost_scope": "ideal_algorithm_elements_not_observed_reference_memory_traffic",
    }
