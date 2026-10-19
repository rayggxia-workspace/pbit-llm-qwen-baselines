"""Clipped amplitude ranges with exact shared-input/independent-weight sampling.

``scale`` denotes the magnitude represented by a probability of exactly one.
The ordinary 8-bit threshold still represents q/256 (q <= 255); values at or
above the range use an explicit constant-one bypass.  This extra endpoint is
not secretly an eight-bit threshold of 256.  Signs remain separate.

All weight variants begin with the unchanged historical decoded W8 matrix.
SiLU(g)*u is continuous FP32, and its result is re-encoded before Wd.  There is
no claim that intermediate nonlinear computation stays in a stochastic stream.
"""
import math
from pathlib import Path
import sys

import torch
from torch.nn import functional as F

RANGE = Path(__file__).resolve().parents[1] / 'qwen_dual_range_20261018'
if str(RANGE) not in sys.path:
    sys.path.insert(0, str(RANGE))
from range_core import (MatrixSpec, RangeFFN, encode_input, project_probability)


def _expanded_scale(value, scale):
    scale = torch.as_tensor(scale, device=value.device, dtype=torch.float32)
    if value.shape[-1] % 64:
        raise ValueError('Input width must be divisible by 64')
    if scale.ndim and scale.shape[-1] == value.shape[-1] // 64:
        scale = scale.repeat_interleave(64, -1)
    if not bool(torch.isfinite(scale).all() and (scale > 0).all()):
        raise ValueError('Scales must be finite and positive')
    try:
        return scale.expand_as(value)
    except RuntimeError as exc:
        raise ValueError('Scale must broadcast to the input or contain one value per 64 lanes') from exc


def round_up_pow2(scale):
    """Positive FP32 powers of two, rounded upward; zero is safely bounded.

    Values larger than the greatest finite FP32 power of two are rejected
    instead of silently rounding down or manufacturing an infinite scale.
    """
    scale = torch.as_tensor(scale, dtype=torch.float32)
    if not bool(torch.isfinite(scale).all() and (scale >= 0).all()):
        raise ValueError('PoT scales must be finite and nonnegative')
    if bool((scale > 2. ** 127).any()):
        raise ValueError('Scale exceeds the greatest finite FP32 power of two')
    bounded = scale.clamp_min(torch.finfo(torch.float32).tiny)
    exponent = bounded.log2().ceil().clamp(-126, 127)
    rounded = torch.pow(torch.full_like(exponent, 2.), exponent)
    # log2 can round a value just above a power of two down to that power.
    return torch.where(rounded < bounded, rounded * 2., rounded)


def encode_clipped(value, scale, endpoint='one'):
    """Return (probability, signed decoded value, expanded positive scale).

    ``one`` sets p=1 exactly when |value| >= scale; otherwise q/256 applies.
    ``legacy`` has no constant-one bypass and always saturates at 255/256.
    The caller is responsible for distinguishing a clipped value from a
    range maximum: equality produces p=1 without numerical clipping.
    """
    if endpoint not in ('one', 'legacy'):
        raise ValueError('endpoint must be one or legacy')
    value = value.float()
    if not bool(torch.isfinite(value).all()):
        raise ValueError('Inputs must be finite')
    scale = _expanded_scale(value, scale)
    probability = (value.abs() * (256. / scale)).round().clamp(0, 255) / 256.
    if endpoint == 'one':
        probability = torch.where(value.abs() >= scale, torch.ones_like(probability), probability)
    decoded = value.sign() * scale * probability
    return probability, decoded, scale


def _weight_pow2_spec(reference):
    grouped = reference.reshape(reference.shape[0], -1, 64)
    scale = round_up_pow2(grouped.abs().amax(-1, keepdim=True).clamp_min(1e-20))
    scale = scale.expand_as(grouped).reshape_as(reference)
    p, decoded, scale = encode_clipped(reference, scale, 'one')
    return MatrixSpec(decoded.contiguous(), p.contiguous(),
                      (reference.sign() * scale).contiguous(),
                      reference.contiguous(), 'row64_pow2')


class ClipFFN(RangeFFN):
    """Independent x/z clipping; optional frozen per-group and PoT ranges.

    Fixed ranges are calibration amplitudes, not observed test maxima.  A
    scalar, one amplitude per 64 input lanes, or a per-lane vector is accepted.
    Without explicit fixed_x/fixed_z, the historical x/Sz vectors are used.
    Setting ``endpoint='legacy'``, dynamic ranges, factors=1 and pow2=False
    exactly reproduces RangeFFN(dynamic64,row64), including random draws.
    ``weight_pow2=False`` retains that same row64 W8-derived encoding.
    """
    def __init__(self, original, old_scales, sz, range_policy='dynamic',
                 x_factor=1., z_factor=1., fixed_x=None, fixed_z=None,
                 pow2=False, weight_pow2=False, endpoint='one', kind='dual',
                 cycles=256, seed=0, layer=0):
        if range_policy not in ('dynamic', 'fixed'):
            raise ValueError('range_policy must be dynamic or fixed')
        if endpoint not in ('one', 'legacy'):
            raise ValueError('endpoint must be one or legacy')
        if any(not math.isfinite(float(f)) or float(f) <= 0 for f in (x_factor, z_factor)):
            raise ValueError('Range factors must be finite and positive')
        super().__init__(original, old_scales, sz,
                         activation_policy='dynamic64' if range_policy == 'dynamic' else 'legacy',
                         weight_policy='row64', kind=kind, cycles=cycles,
                         seed=seed, layer=layer)
        self.range_policy, self.endpoint = range_policy, endpoint
        self.x_factor, self.z_factor = float(x_factor), float(z_factor)
        self.pow2, self.weight_pow2 = bool(pow2), bool(weight_pow2)
        for name, explicit in (('x', fixed_x), ('z', fixed_z)):
            scale = getattr(self, 'scale_' + name)
            if explicit is not None:
                replacement = _expanded_scale(scale, explicit).clone()
                setattr(self, 'scale_' + name, replacement)
            # n, zero, p_sum, SSE, value power, clipped, scale_sum, p_one
            setattr(self, name + '_stats', torch.zeros(8, device=scale.device, dtype=torch.float64))
        if self.weight_pow2:
            for name in ('gu', 'down'):
                spec = _weight_pow2_spec(getattr(self, name + '_reference_decoded'))
                for field in ('decoded', 'probability', 'amplitude', 'reference_decoded'):
                    setattr(self, name + '_' + field, getattr(spec, field))
            self.weight_policy = 'row64_pow2'

    def encode_stage(self, value, name):
        if name not in ('x', 'z'):
            raise ValueError(name)
        factor = getattr(self, name + '_factor')
        # Keep old arithmetic, scaling endpoint and generator consumption
        # byte-for-byte for the requested regression control.
        if (self.endpoint == 'legacy' and self.range_policy == 'dynamic'
                and factor == 1. and not self.pow2):
            return encode_input(value, getattr(self, 'scale_' + name), 'dynamic64')
        if self.range_policy == 'dynamic':
            grouped = value.reshape(*value.shape[:-1], value.shape[-1] // 64, 64)
            scale = grouped.abs().amax(-1, keepdim=True).clamp_min(1e-20) * factor
            scale = scale.expand_as(grouped).reshape_as(value)
        else:
            scale = getattr(self, 'scale_' + name) * factor
        if self.pow2:
            scale = round_up_pow2(scale)
        return encode_clipped(value, scale, self.endpoint)

    def _stage(self, value, name, matrix, input_generator, weight_generator):
        p, decoded, scale = self.encode_stage(value, name)
        s = getattr(self, name + '_stats')
        # Legacy q=255 has a representable endpoint below its event amplitude.
        limit = scale if self.endpoint == 'one' else scale * (255. / 256.)
        tolerance = 8. * torch.finfo(torch.float32).eps
        with torch.no_grad():
            s[0] += value.numel()
            s[1] += (p == 0).sum()
            s[2] += p.sum(dtype=torch.float64)
            s[3] += (decoded-value).square().sum(dtype=torch.float64)
            s[4] += value.square().sum(dtype=torch.float64)
            s[5] += (value.abs() > limit * (1. + tolerance)).sum()
            s[6] += scale.expand_as(value).sum(dtype=torch.float64)
            s[7] += (p == 1).sum()
        return project_probability(p, value.sign(), scale, self.matrix_spec(matrix),
                                   self.stage_kind(matrix), self.cycles,
                                   input_generator, weight_generator)

    def diagnostics(self):
        result = dict(calls=self.calls, range_policy=self.range_policy,
                      x_factor=self.x_factor, z_factor=self.z_factor,
                      pow2=self.pow2, weight_pow2=self.weight_pow2,
                      endpoint=self.endpoint, weight_policy=self.weight_policy,
                      kind=self.kind, cycles=self.cycles,
                      backend='exact conditional Binomial', sharing=64,
                      nonlinear='continuous FP32 SiLU(g)*u')
        for name in ('x', 'z'):
            n, zeros, psum, err, power, clipped, scale_sum, ones = getattr(self, name + '_stats').tolist()
            result.update({name + '_values': int(n), name + '_zero_fraction': zeros / max(n, 1),
                           name + '_mean_probability': psum / max(n, 1),
                           name + '_encoding_nmse': err / max(power, 1e-30),
                           name + '_clip_fraction': clipped / max(n, 1),
                           name + '_mean_scale': scale_sum / max(n, 1),
                           name + '_p_one_fraction': ones / max(n, 1)})
        for name in ('gu', 'down'):
            spec = self.matrix_spec(name)
            result[name + '_weight_mean_probability'] = spec.probability.mean().item()
            result[name + '_weight_p_one_fraction'] = (spec.probability == 1).float().mean().item()
            result[name + '_weight_zero_fraction'] = (spec.probability == 0).float().mean().item()
            result[name + '_weight_reencode_nmse'] = ((spec.decoded-spec.reference_decoded).square().sum()
                / spec.reference_decoded.square().sum().clamp_min(1e-30)).item()
        return result
