"""Offline four-scale activation encoding with the frozen shared-R8 FFN law.

Static scale tables are per layer, signal (x/z), and original group of 64
channels. Inference selects a scale per lane; it does NOT estimate a group
maximum or alter the configured scale table. Explicit clipping above the top
scale is intentional. Diagnostic reductions do not feed the encoding and are
software measurements, not claims of free hardware instrumentation.

The reference keeps historical W8 matrices and FP32 count restoration/SiLU.
It is not a finite-width RTL simulation. Random equal-range stratification is
not IID. ``mean`` is an encoding control, not the nonlinear network expectation.
"""
import hashlib
from pathlib import Path
import sys

import torch
from torch.nn import functional as F


from qwen3.stochastic.vendor.stratified_core import GROUP, StratifiedFFN, encode_input, project_encoded


def _validated_scales(scales, groups, device):
    """Validate once at setup and retain detached FP32 powers of two.

The setup synchronization is deliberate. StaticFFN never repeats this check
in its GPU hot path. Scales may be passed as a CPU list or a tensor.
"""
    source = torch.as_tensor(scales)
    if source.is_complex() or source.dtype == torch.bool:
        raise ValueError('Scales must be real positive powers of two')
    # Preserve Python float precision until validation; default as_tensor on a
    # list would otherwise round a non-PoT number to FP32 before checking it.
    if not isinstance(scales, torch.Tensor):
        source = torch.as_tensor(scales, dtype=torch.float64)
    raw = source.detach().to(device='cpu', dtype=torch.float64)
    if raw.ndim != 2 or tuple(raw.shape) != (groups, 4):
        raise ValueError('Static scale shape must be (input_width // 64, 4)')
    if not bool(torch.isfinite(raw).all()) or not bool((raw > 0).all()):
        raise ValueError('Scales must be finite and strictly positive')
    if not bool((raw[:, :-1] > raw[:, 1:]).all()):
        raise ValueError('Four scales must be strictly descending in each group')
    mantissa, _ = torch.frexp(raw)
    if not bool((mantissa == .5).all()):
        raise ValueError('Every static scale must be exactly a power of two')
    cast = raw.to(dtype=torch.float32)
    if not bool(torch.isfinite(cast).all()) or not bool((cast > 0).all()) or \
            not torch.equal(cast.to(dtype=torch.float64), raw):
        raise ValueError('Every static scale must be exactly representable in FP32')
    return cast.to(device=device).contiguous().clone()


def _check_value_shape(value):
    if not isinstance(value, torch.Tensor) or value.ndim < 1 or \
            value.shape[-1] == 0 or value.shape[-1] % GROUP:
        raise ValueError('Input width must be a positive multiple of 64')
    if value.is_complex() or value.dtype == torch.bool:
        raise ValueError('Activation values must be real')


def _encode_static_validated(value, scales):
    """Hot path: validated immutable table, shape checks without GPU reads."""
    _check_value_shape(value)
    if tuple(scales.shape) != (value.shape[-1] // GROUP, 4):
        raise ValueError('Scale table does not match activation width')
    value = value.float()
    grouped = value.reshape(*value.shape[:-1], value.shape[-1] // GROUP, GROUP)
    magnitude = grouped.abs()
    scale = scales[:, 0].unsqueeze(-1).expand_as(grouped).clone()
    bin_id = torch.zeros_like(grouped, dtype=torch.int64)
    for index in range(1, 4):
        candidate = scales[:, index].unsqueeze(-1)
        eligible = magnitude <= candidate
        scale = torch.where(eligible, candidate, scale)
        bin_id = torch.where(eligible, index, bin_id)
    scale = scale.reshape_as(value)
    # Divide before multiplying by 256 so valid subnormal PoT fixtures do not
    # create 0 * inf at zero. No general runtime scale estimation occurs.
    q = ((value.abs() / scale) * 256.).round().clamp(0, 255)
    full_one = (value.abs() >= scale) & (value != 0)
    probability = torch.where(full_one, torch.ones_like(q), q / 256.)
    return dict(q=q.to(torch.int16), sign=value.sign(), scale=scale,
                probability=probability, decoded=value.sign() * scale * probability,
                full_one=full_one, bin_id=bin_id.reshape_as(value))


def encode_static(value, scales):
    """Encode with a fixed [groups, 4] table; return the legacy encoding keys.

Each lane chooses the smallest configured scale containing its magnitude.
Above the largest scale, the decoded magnitude clips to that largest scale
with probability exactly one. q=255 alone still means probability 255/256;
an explicit full_one bit distinguishes equality/saturation. Public calls
validate the supplied table. StaticFFN validates only during construction.
"""
    _check_value_shape(value)
    if not bool(torch.isfinite(value).all()):
        raise ValueError('Activation values must be finite')
    table = _validated_scales(scales, value.shape[-1] // GROUP, value.device)
    return _encode_static_validated(value, table)


def _scale_metadata(scales):
    if scales is None:
        return dict(policy='dynamic_pot4', sha256=None, shape=None,
                    exponent_spacing=2)
    cpu = scales.detach().to(device='cpu').contiguous()
    # Canonical little-endian contiguous float32 bytes, independent of JSON
    # whitespace. The calibration manifest separately hashes its JSON bytes.
    payload = cpu.numpy().astype('<f4', copy=False).tobytes(order='C')
    _, exponent = torch.frexp(cpu)
    exponent = exponent - 1
    spacing = exponent[:, :-1] - exponent[:, 1:]
    flat = spacing.reshape(-1)
    uniform = int(flat[0]) if bool((flat == flat[0]).all()) else None
    return dict(policy='static_four_pot', sha256=hashlib.sha256(payload).hexdigest(),
                shape=list(cpu.shape), dtype='little-endian float32',
                exponent_spacing=uniform, exponents=exponent.tolist())


class StaticFFN(StratifiedFFN):
    """Fixed scale x and/or z with unchanged W8 weights and random streams.

None for either table means the original dynamic pot4 encoding for that
signal. Set ``observer`` after construction to a callable
``observer(layer, signal, value)``; it sees each pre-encoding x/z tensor. An
observer must not mutate the value or random generators. ``w8_only`` bypasses
both encoders but still calls the observer, for offline train calibration.
"""
    def __init__(self, original, x_scales=None, z_scales=None, mode='sampled',
                 cycles=32, strata=32, seed=0, layer=0):
        super().__init__(original, policy='pot4', mode=mode, cycles=cycles,
                         seed=seed, layer=layer, strata=strata)
        self.observer = None
        self.scale_metadata = {}
        for name, scales, matrix in (('x', x_scales, 'gu'),
                                     ('z', z_scales, 'down')):
            weight = getattr(self, matrix + '_decoded')
            table = None if scales is None else _validated_scales(
                scales, weight.shape[1] // GROUP, weight.device)
            self.register_buffer(name + '_scales', table)
            self.scale_metadata[name] = _scale_metadata(table)
            # actual clipping SSE; original power of clipped values; maximum
            # |value| / selected_scale among overflow values (zero if none).
            self.register_buffer(name + '_clip_stats', torch.zeros(
                3, device=weight.device, dtype=torch.float64))

    def _stage(self, value, signal, matrix, generator):
        if self.observer is not None:
            with torch.no_grad():
                self.observer(self.layer, signal, value.detach())
        stats = getattr(self, signal + '_stats')
        with torch.no_grad():
            stats[0] += value.numel()
            stats[4] += value.square().sum(dtype=torch.float64)
        weight = getattr(self, matrix + '_decoded')
        if self.mode == 'w8_only':
            return F.linear(value, weight)
        table = getattr(self, signal + '_scales')
        encoded = encode_input(value, 'pot4') if table is None else \
            _encode_static_validated(value, table)
        with torch.no_grad():
            probability = encoded['probability']
            stats[1] += (probability == 0).sum()
            stats[2] += probability.sum(dtype=torch.float64)
            stats[3] += (encoded['decoded'] - value).square().sum(dtype=torch.float64)
            magnitude = value.abs()
            clipped = magnitude > encoded['scale']
            stats[5] += clipped.sum()
            stats[6] += encoded['scale'].sum(dtype=torch.float64)
            stats[7] += encoded['full_one'].sum()
            occupancy = torch.bincount(encoded['bin_id'].reshape(-1), minlength=4)
            getattr(self, signal + '_bins').add_(occupancy)
            extra = getattr(self, signal + '_clip_stats')
            extra[0] += (magnitude - encoded['scale']).clamp_min(0).square().sum(
                dtype=torch.float64)
            extra[1] += torch.where(clipped, value.square(), torch.zeros_like(value)).sum(
                dtype=torch.float64)
            ratio = torch.where(clipped, magnitude / encoded['scale'],
                                torch.zeros_like(magnitude))
            extra[2].copy_(torch.maximum(extra[2], ratio.amax().to(dtype=torch.float64)))
        return project_encoded(encoded, weight, self.mode, self.cycles,
                               generator, self.strata)

    def diagnostics(self):
        result = super().diagnostics()
        result['scale_tables'] = self.scale_metadata
        result['scales_sha256'] = {key: value['sha256']
                                  for key, value in self.scale_metadata.items()}
        result['encoding_policy'] = {key: value['policy']
                                     for key, value in self.scale_metadata.items()}
        result['policy'] = 'pot4' if self.x_scales is None and self.z_scales is None \
            else 'static_multiscale'
        result['scale_bin_exponent_step'] = None
        result['scale_bin_exponent_steps'] = {
            key: value['exponent_spacing'] for key, value in self.scale_metadata.items()}
        result['online_absmax_signals'] = [] if self.mode == 'w8_only' else [
            name for name in ('x', 'z') if getattr(self, name + '_scales') is None]
        result['diagnostic_reductions_drive_scales'] = False
        for name in ('x', 'z'):
            sse, clipped_power, maximum = getattr(self, name + '_clip_stats').tolist()
            power = float(getattr(self, name + '_stats')[4])
            result.update({name + '_clip_sse': sse,
                           name + '_clip_sse_over_power': sse / max(power, 1e-30),
                           name + '_clipped_value_power': clipped_power,
                           name + '_clipped_value_power_over_power':
                               clipped_power / max(power, 1e-30),
                           name + '_max_overflow_ratio': maximum,
                           name + '_max_overflow_excess': max(maximum - 1., 0.),
                           name + '_scales_sha256': self.scale_metadata[name]['sha256']})
        return result
