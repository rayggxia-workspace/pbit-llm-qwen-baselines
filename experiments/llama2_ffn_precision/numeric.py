"""Numerical contracts for Issue 19; these functions are not hardware kernels.

The single-sided matrix uses fixed signed INT8 weights and activation probability
q/256, with a separate sign. Shared-64 streams are represented by their *exact*
temporal counts. This is valid across a linear readout with fixed weights; it
does not claim that a physical p-bit, its tanh transfer, or native PRNG is modeled.
The PyTorch generator supplies ideal uniform 8-bit thresholds, not an LFSR model.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

try:
    import torch
except ImportError:  # The scalar oracle and manifest can be inspected without it.
    torch = None


GROUP = 64
LEVELS = 256
_RNG_BATCH_GROUPS = 8192
_LUT_VALUES = json.loads(
    (Path(__file__).parent / "vendor_q10/sigmoid_lut_q16.json").read_text(encoding="utf-8")
)["values"]


def _require_torch():
    if torch is None:
        raise RuntimeError("This numerical operation requires PyTorch")


def quantize_weight(weight, group=GROUP):
    """Return (INT8 codes, FP32 tile LSB scales), matching legacy quantize_int8.

    Scale has shape [out_features/group, in_features/group]. No decoded duplicate
    weight is retained by this stateless function. Rounding is nearest, ties even.
    """
    _require_torch()
    if weight.ndim != 2 or group <= 0:
        raise ValueError("weight must be a matrix and group must be positive")
    rows, cols = weight.shape
    if rows % group or cols % group:
        raise ValueError("both weight dimensions must be divisible by group")
    tiles = weight.float().reshape(rows // group, group, cols // group, group).permute(0, 2, 1, 3)
    if not bool(torch.isfinite(tiles).all()):
        raise ValueError("weight must be finite")
    scales = tiles.abs().amax((-1, -2)).clamp_min(1e-20) / 127.0
    codes = (tiles / scales[:, :, None, None]).round().clamp(-127, 127).to(torch.int8)
    codes = codes.permute(0, 2, 1, 3).reshape(rows, cols).contiguous()
    return codes, scales.contiguous()


def dequantize_weight(codes, tile_scales, group=GROUP):
    """Decode one INT8 weight matrix; caller controls the lifetime of this copy."""
    _require_torch()
    if group <= 0 or codes.ndim != 2 or tile_scales.shape != (codes.shape[0] // group, codes.shape[1] // group):
        raise ValueError("codes and tile scales have incompatible shapes")
    if codes.shape[0] % group or codes.shape[1] % group:
        raise ValueError("weight dimensions must be divisible by group")
    scales = tile_scales.float().repeat_interleave(group, 0).repeat_interleave(group, 1)
    return (codes.float() * scales).contiguous()


def encode_fixed(value, scale):
    """Return (q:int16, sign:int8, decoded:FP32), probability exactly q/256.

    ``scale`` may be scalar, per-channel, or one value per contiguous 64 channels.
    There is no data-dependent maximum or scale change in this operation.
    """
    _require_torch()
    if value.ndim < 1:
        raise ValueError("value must have a final feature dimension")
    value = value.float()
    scale = torch.as_tensor(scale, dtype=torch.float32, device=value.device)
    if scale.ndim == 1 and scale.numel() != value.shape[-1] and scale.numel() * GROUP == value.shape[-1]:
        scale = scale.repeat_interleave(GROUP)
    if not bool(torch.isfinite(scale).all()) or not bool((scale > 0).all()):
        raise ValueError("scale must be positive and finite")
    if not bool(torch.isfinite(value).all()):
        raise ValueError("activation must be finite")
    q = (value.abs() * (LEVELS / scale)).round().clamp(0, LEVELS - 1).to(torch.int16)
    sign = value.sign().to(torch.int8)
    decoded = sign.float() * scale * (q.float() / LEVELS)
    return q, sign, decoded


def sample_counts(q, T, method="iid", share64=True, generator=None, chunk_groups=8192):
    """Count events ``uniform_8bit < q`` without a [tokens, features, T] array.

    For share64=True every token / contiguous 64-feature group uses one common
    threshold sequence; different token/groups receive separate generator draws.
    False uses one independent sequence per feature. A partial last group works.

    iid: exact joint count law of T draws with replacement, compressed by
    conditional multinomial splits (not explicit T draws). stratified: one
    uniformly jittered threshold
    in each of T equal strata; T must divide 256. enumerate256: every threshold
    once, requires T=256. midpoint: deterministic thresholds k*(256/T)+128/T;
    T must divide 256 and be <=128, and this deliberately measures short-sequence
    quantization bias rather than an unbiased random estimator. For the random
    schemes the mean count is T*q/256. Stratified
    T=256 and enumerate256 return q exactly and do not consume generator state.

    RNG draw batches are fixed independently of chunk_groups, so changing the
    histogram lookup chunk preserves seeded output. PyTorch CPU and CUDA random
    sequences are not claimed to be identical. Counts are exact for the sampled
    thresholds, including shared-stream correlations, rather than independent
    per-feature Binomial surrogates.
    """
    _require_torch()
    if q.ndim < 1 or T <= 0 or T > 32767 or chunk_groups <= 0:
        raise ValueError("invalid shape, sample count, or chunk size")
    if method not in ("iid", "stratified", "enumerate256", "midpoint"):
        raise ValueError(f"unknown sampling method: {method}")
    if q.dtype not in (torch.uint8, torch.int8, torch.int16, torch.int32, torch.int64):
        raise ValueError("q must contain integer probability codes")
    if bool(((q < 0) | (q > 255)).any()):
        raise ValueError("probability code must be in [0,255]")
    if method == "enumerate256" and T != 256:
        raise ValueError("enumerate256 requires T=256")
    if method == "stratified" and (T > 256 or 256 % T):
        raise ValueError("stratified T must divide 256")
    if method == "midpoint" and (T > 128 or 256 % T):
        raise ValueError("midpoint T must divide 256 and be <=128")
    if method == "enumerate256" or (method == "stratified" and T == 256):
        return q.to(torch.int16).clone()
    if method == "midpoint":
        width = 256 // T
        # Number of k with k*width + width//2 < q. Strict comparator matters
        # exactly at a midpoint; it must not be replaced by ties-even rounding.
        return torch.div(q.to(torch.int64) + width - 1 - width // 2,
                         width, rounding_mode="floor").clamp(0, T).to(torch.int16)

    features = q.shape[-1]
    width = GROUP if share64 else 1
    groups = (features + width - 1) // width
    tokens = math.prod(q.shape[:-1])
    if features == 0 or tokens == 0:
        return q.to(torch.int16).clone()
    flat = q.reshape(tokens, features)
    if features % width:
        flat = torch.nn.functional.pad(flat, (0, groups * width - features))
    grouped_q = flat.reshape(tokens * groups, width)
    output = torch.empty_like(grouped_q, dtype=torch.int16)
    for start in range(0, grouped_q.shape[0], _RNG_BATCH_GROUPS):
        end = min(start + _RNG_BATCH_GROUPS, grouped_q.shape[0])
        n = end - start
        if method == "iid":
            # 64 thresholds divide the [0,256) integer-word domain into 65
            # intervals. The multinomial count vector is the exact sufficient
            # statistic for fixed-weight linear accumulation. Seven conditional
            # binomial splits replace a [token,group,T] draw buffer, preserving
            # the shared-lane joint law. Based on the prior shared_counts.py
            # algorithm; probabilities here are formed from integer q masses.
            sorted_q, order = grouped_q[start:end].long().sort(-1)
            mass = torch.cat((sorted_q[:, :1], sorted_q[:, 1:] - sorted_q[:, :-1],
                              256 - sorted_q[:, -1:]), -1).double()
            leaves = 1 << width.bit_length()
            mass = torch.nn.functional.pad(mass, (0, leaves - (width + 1)))
            cumulative = torch.nn.functional.pad(mass.cumsum(-1), (1, 0))
            counts = torch.full((n, 1), float(T), dtype=torch.float64, device=q.device)
            nodes = 1
            while nodes < leaves:
                span = leaves // nodes
                total = cumulative[:, span::span] - cumulative[:, :-1:span]
                left_mass = cumulative[:, span//2::span] - cumulative[:, :-1:span]
                conditional = (left_mass / total.clamp_min(1)).clamp(0, 1)
                left = torch.binomial(counts, conditional, generator=generator)
                counts = torch.stack((left, counts - left), -1).reshape(n, nodes * 2)
                nodes *= 2
            prefix = counts.cumsum(-1)[:, :width]
            result = torch.empty_like(prefix).scatter_(-1, order, prefix).to(torch.int16)
            output[start:end] = result
            continue
        stratum = 256 // T
        jitter = torch.randint(stratum, (n, T), device=q.device, generator=generator)
        for local in range(0, n, chunk_groups):
            stop = min(local + chunk_groups, n)
            codes = grouped_q[start + local:start + stop].long()
            complete = torch.div(codes, stratum, rounding_mode="floor")
            remainder = torch.remainder(codes, stratum)
            # Every earlier stratum is surely below q; only q's own stratum
            # can be random. One jitter per stratum is shared by all 64 lanes.
            event = jitter[local:stop].gather(1, complete) < remainder
            output[start + local:start + stop] = (complete + event).to(torch.int16)
    return output.reshape(tokens, groups * width)[:, :features].reshape(q.shape)


def exact_integer_linear(input_signed_integer, weight_int8):
    """Return exact INT64 raw dot products (no scale restoration or rounding).

    Input shape [..., K], range [-4096,4096]; weight [out,K], INT8. CUDA uses
    torch._int_mm twice: input=low+128*high, low in [0,127], high in [-32,32].
    Each INT32 digit dot is range-checked from K, and is converted to INT64
    *before* combining. E.g. K=11008, T=4096 can overflow a final INT32 dot.
    Padding makes dimensions satisfy Tensor Core INT8 constraints. CPU is an
    INT64 reference. Multiply the returned integer by appropriate scales/T
    afterwards; per-tile scales require separately restoring each tile sum.
    """
    _require_torch()
    if input_signed_integer.ndim < 1 or weight_int8.ndim != 2:
        raise ValueError("expected [...,K] inputs and [out,K] weight")
    if input_signed_integer.shape[-1] != weight_int8.shape[1]:
        raise ValueError("linear dimensions disagree")
    if input_signed_integer.device != weight_int8.device:
        raise ValueError("input and weight must be on the same device")
    if input_signed_integer.dtype not in (torch.int8, torch.int16, torch.int32, torch.int64):
        raise ValueError("inputs must be signed integers")
    if weight_int8.dtype != torch.int8:
        raise ValueError("weight must have dtype int8")
    if bool(((input_signed_integer < -4096) | (input_signed_integer > 4096)).any()):
        raise ValueError("input outside supported [-4096,4096] range")
    if bool((weight_int8 == -128).any()):
        raise ValueError("symmetric quantized weights exclude -128")
    K = weight_int8.shape[1]
    if K * 127 * 127 > torch.iinfo(torch.int32).max:
        raise ValueError("INT32 digit dot could overflow; partition K first")
    flat = input_signed_integer.reshape(math.prod(input_signed_integer.shape[:-1]), K).to(torch.int64)
    if flat.shape[0] == 0 or weight_int8.shape[0] == 0 or K == 0:
        return torch.zeros((*input_signed_integer.shape[:-1], weight_int8.shape[0]),
                           dtype=torch.int64, device=input_signed_integer.device)
    if not flat.is_cuda:
        result = flat @ weight_int8.to(torch.int64).t()
    else:
        if not hasattr(torch, "_int_mm"):
            raise RuntimeError("CUDA exact path requires torch._int_mm")
        M, O = flat.shape[0], weight_int8.shape[0]
        mp, op, kp = ((v + 31) // 32 * 32 for v in (M, O, K))
        low = torch.remainder(flat, 128).to(torch.int8)
        high = torch.div(flat, 128, rounding_mode="floor").to(torch.int8)
        low = torch.nn.functional.pad(low, (0, kp - K, 0, mp - M)).contiguous()
        high = torch.nn.functional.pad(high, (0, kp - K, 0, mp - M)).contiguous()
        padded_weight = torch.nn.functional.pad(weight_int8, (0, kp - K, 0, op - O)).contiguous()
        right = padded_weight.t()
        lo_dot = torch._int_mm(low, right).to(torch.int64)
        hi_dot = torch._int_mm(high, right).to(torch.int64)
        result = (lo_dot + hi_dot * 128)[:M, :O]
    return result.reshape(*input_signed_integer.shape[:-1], weight_int8.shape[0])


def q10_swiglu_scalar(g, u, out_w=24):
    """Scalar integer oracle: raw signed Q10 inputs -> raw signed Q10 output."""
    if not (-32768 <= g <= 32767 and -32768 <= u <= 32767):
        raise ValueError("Q10 raw inputs must fit signed 16 bits")
    if not 2 <= out_w <= 32:
        raise ValueError("out_w must be in [2,32]")
    positive = 65536 if abs(g) >= 8192 else _LUT_VALUES[abs(g) // 32]
    sigmoid = 65536 - positive if g < 0 else positive
    product = g * u * sigmoid
    magnitude, remainder = divmod(abs(product), 1 << 26)
    magnitude += int(remainder > (1 << 25) or (remainder == (1 << 25) and magnitude % 2))
    rounded = -magnitude if product < 0 else magnitude
    lo, hi = -(1 << (out_w - 1)), (1 << (out_w - 1)) - 1
    saturated = rounded < lo or rounded > hi
    return max(lo, min(hi, rounded)), int(saturated), int(bool(remainder) or saturated)


def q10_swiglu(g, u, return_stats=False, out_w=24):
    """Vectorized Issue-7 RTL arithmetic with FP32 -> Q10 RNE/saturating inputs.

    Inputs round to signed 16-bit Q10. LUT is the original 256-entry positive
    Q16 table; negative sigmoid uses exact complement and |g|>=8 saturates.
    Form g_raw*u_raw (signed 32-bit), then its 50-bit Q36 product with sigmoid;
    use INT64 storage, divide by 2**26 with symmetric ties-even, saturate OUT_W.
    Return FP32 raw/1024. Optional stats are device tensors (no forced CPU sync).
    This validates the arithmetic contract, not model quality or conversion PPA.
    """
    _require_torch()
    if g.shape != u.shape or g.device != u.device or not 2 <= out_w <= 32:
        raise ValueError("g/u shapes/devices or output width disagree")
    if not bool(torch.isfinite(g).all()) or not bool(torch.isfinite(u).all()):
        raise ValueError("g and u must be finite")
    gr = (g.float() * 1024).round()
    ur = (u.float() * 1024).round()
    gi = gr.clamp(-32768, 32767).to(torch.int64)
    ui = ur.clamp(-32768, 32767).to(torch.int64)
    lut = torch.tensor(_LUT_VALUES, dtype=torch.int64, device=g.device)
    mag_g = gi.abs()
    positive = lut[(mag_g // 32).clamp_max(255)]
    positive = torch.where(mag_g >= 8192, 65536, positive)
    sigma = torch.where(gi < 0, 65536 - positive, positive)
    product = (gi * ui) * sigma
    magnitude = product.abs()
    quotient = torch.div(magnitude, 1 << 26, rounding_mode="floor")
    remainder = torch.remainder(magnitude, 1 << 26)
    increment = (remainder > (1 << 25)) | ((remainder == (1 << 25)) & ((quotient & 1) != 0))
    rounded_mag = quotient + increment.to(torch.int64)
    rounded = torch.where(product < 0, -rounded_mag, rounded_mag)
    lo, hi = -(1 << (out_w - 1)), (1 << (out_w - 1)) - 1
    raw = rounded.clamp(lo, hi)
    value = raw.float() / 1024
    if not return_stats:
        return value
    saturated = (rounded < lo) | (rounded > hi)
    return value, {
        "values": torch.tensor(g.numel(), dtype=torch.int64, device=g.device),
        "g_input_clipped": ((gr < -32768) | (gr > 32767)).sum(),
        "u_input_clipped": ((ur < -32768) | (ur > 32767)).sum(),
        "output_saturated": saturated.sum(),
        "output_inexact": ((remainder != 0) | saturated).sum(),
    }
