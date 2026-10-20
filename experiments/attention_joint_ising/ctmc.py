"""Finite-time hard-one-hot heat-bath CTMC, not target-distribution IID.

This follows the event-compressed reference at 03f0031, in
experiments/pbit_softmax_router/sampling.py.  The maximum-logit category is
represented by the empty state.  Other categories have birth rate sigmoid(delta)
and death rate 1 - sigmoid(delta), with unit-rate clocks for individual sites.
Only empty/active dwell times are compressed; burn-in and sample correlations
remain.  These dimensionless times do not specify a physical device frequency,
finite inhibition penalty, feedback delay, or bias quantization.

Fixed event blocks and a fixed draw order make sample-budget sweeps share a
prefix for the same logits, generator seed, and event cap.  Coverage extensions
append events; neither completed trajectories nor output rows are discarded.
"""
from __future__ import annotations

import math

import torch


EVENT_BLOCK = 256


class CTMCEventLimitError(RuntimeError):
    """The caller must record failure rather than substitute IID samples."""

    def __init__(self, stats: dict):
        self.stats = stats
        super().__init__(
            "CTMC event cap reached before every observation was covered; "
            "no samples returned, no rows dropped, and no IID fallback: "
            f"{stats}"
        )


def _positive_int(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


@torch.no_grad()
def ct_mc_indices(
    logits: torch.Tensor,
    samples: int,
    burn: float,
    spacing: float,
    *,
    generator: torch.Generator | None = None,
    max_events: int = 32768,
) -> tuple[torch.Tensor, dict]:
    """Return local category indices ``[rows, samples]`` and service diagnostics.

    ``logits`` is a nonempty floating tensor ``[rows, candidates]``.  Negative
    infinity denotes an invalid padded category; every row needs a finite
    category.  NaN and positive infinity are errors.  All trajectories start in
    their maximum-logit/empty state, and are observed at ``burn + spacing*k``
    for k = 1..samples.  The caller should give routing a separate RNG domain.

    A supplied generator must be on the logits device.  Fixed-size event blocks
    are drawn before testing coverage, so changing only the sample count keeps
    the ordered output prefix for identical input and initial generator state.
    ``max_events`` caps event pairs per nondegenerate row, not the output count.
    Hitting it raises CTMCEventLimitError with diagnostics and no partial result.
    """
    _positive_int(samples, "samples")
    _positive_int(max_events, "max_events")
    if not isinstance(logits, torch.Tensor) or logits.ndim != 2:
        raise ValueError("logits must be a [rows, candidates] tensor")
    if not logits.is_floating_point() or min(logits.shape) < 1:
        raise ValueError("logits must have nonempty floating rows and candidates")
    if isinstance(burn, bool) or isinstance(spacing, bool):
        raise ValueError("burn and spacing must be real finite time values")
    try:
        burn, spacing = float(burn), float(spacing)
    except (TypeError, ValueError) as exc:
        raise ValueError("burn and spacing must be real finite time values") from exc
    horizon = burn + spacing * samples
    if not math.isfinite(burn) or burn < 0:
        raise ValueError("burn must be finite and nonnegative")
    if not math.isfinite(spacing) or spacing <= 0 or not math.isfinite(horizon):
        raise ValueError("spacing and observation horizon must be finite and positive")
    if generator is not None:
        source_device, target_device = torch.device(generator.device), logits.device
        if source_device.type != target_device.type or (
            source_device.index is not None
            and target_device.index is not None
            and source_device.index != target_device.index
        ):
            raise ValueError("generator and logits must be on the same device")

    # Preserve float64 inputs for small-state generator checks; BF16/FP16
    # logits use FP32 rates and time, as in the historical behavior reference.
    dtype = torch.float64 if logits.dtype == torch.float64 else torch.float32
    z = logits.to(dtype=dtype)
    valid = torch.isfinite(z)
    if bool((torch.isnan(z) | torch.isposinf(z)).any()) or not bool(valid.any(-1).all()):
        raise ValueError("each row needs a finite logit; only -inf padding is allowed")
    if horizon > torch.finfo(dtype).max:
        raise ValueError("observation horizon exceeds the sampler time format")

    rows, candidates = z.shape
    ref = z.argmax(-1, keepdim=True)
    birth = torch.sigmoid(z - z.gather(1, ref)).scatter(1, ref, 0.0)
    total = birth.sum(-1)
    live = total > 0
    live_rows = live.nonzero(as_tuple=True)[0]
    live_count = live_rows.numel()
    output = ref.expand(rows, samples).clone()
    stats = {
        "kind": "finite_time_hard_onehot_heat_bath_ctmc",
        "rows": rows,
        "candidates": candidates,
        "samples": samples,
        "burn": burn,
        "spacing": spacing,
        "horizon": horizon,
        "initial_state": "maximum-logit category represented by empty state",
        "time_unit": "unit-rate per-site Poisson clock; not physical ns",
        "time_dtype": str(dtype),
        "event_block": EVENT_BLOCK,
        "event_cap": max_events,
        "event_columns_generated": 0,
        "event_pairs_generated": 0,
        "active_rows": live_count,
        "zero_birth_rows": rows - live_count,
        "coverage_appends": 0,
        "event_cap_reached": False,
        "dropped_rows": 0,
        "dropped_events": 0,
        "iid_fallback": False,
        "valid_categories": int(valid.sum().item()),
        "padding_categories": int((~valid).sum().item()),
        "birth_sum_min": float(total.min().item()),
        "birth_sum_max": float(total.max().item()),
    }
    if live_count:
        proposal = birth.index_select(0, live_rows)
        rate = total.index_select(0, live_rows)[:, None]
        last_end = torch.zeros(live_count, device=z.device, dtype=dtype)
        chosen_parts, start_parts, end_parts = [], [], []
        generated = 0
        while True:
            count = min(EVENT_BLOCK, max_events - generated)
            if count == 0:
                stats.update(
                    event_cap_reached=True,
                    uncovered_rows=int((last_end <= horizon).sum().item()),
                )
                raise CTMCEventLimitError(stats)
            # These are unnormalized BIRTH event rates, not Softmax target
            # probabilities.  The waiting times supply the CTMC occupation law.
            chosen = torch.multinomial(proposal, count, replacement=True, generator=generator)
            uniform = torch.rand(
                (live_count, count, 2), device=z.device, dtype=dtype, generator=generator
            )
            waits = -uniform.clamp_min(torch.finfo(dtype).tiny).log()
            empty_dwell = waits[:, :, 0] / rate
            active_dwell = waits[:, :, 1] / (1.0 - proposal.gather(1, chosen))
            end = last_end[:, None] + (empty_dwell + active_dwell).cumsum(-1)
            start = end - active_dwell
            chosen_parts.append(chosen)
            start_parts.append(start)
            end_parts.append(end)
            last_end = end[:, -1]
            generated += count
            stats.update(
                event_columns_generated=generated,
                event_pairs_generated=live_count * generated,
                coverage_appends=len(end_parts) - 1,
            )
            # Strict coverage supports right-continuous boundary semantics.
            if bool((last_end > horizon).all()):
                break

        end = torch.cat(end_parts, -1).contiguous()
        start = torch.cat(start_parts, -1)
        chosen = torch.cat(chosen_parts, -1)
        times = burn + spacing * torch.arange(1, samples + 1, device=z.device, dtype=dtype)
        times = times.expand(live_count, -1).contiguous()
        at = torch.searchsorted(end, times, right=True)
        if bool((at >= generated).any()):
            raise RuntimeError("CTMC observation escaped covered events; no truncation allowed")
        live_ref = ref.index_select(0, live_rows)
        local = torch.where(times >= start.gather(1, at), chosen.gather(1, at), live_ref)
        output.index_copy_(0, live_rows, local)

    if not bool(valid.gather(1, output).all()):
        raise RuntimeError("CTMC selected invalid padding; no invalid categories may be dropped")
    stats["adjacent_repeat_fraction"] = (
        float((output[:, 1:] == output[:, :-1]).float().mean().item()) if samples > 1 else None
    )
    return output, stats
