"""Independent A/W range ablation; exact IID shared-input/independent-W law.

All weight policies start from the SAME historical 64x64 W8 decoded matrix.
``row64_ideal`` changes only the stochastic event amplitude; ``row64`` also
rounds to an 8-bit q/256 probability. It is not a second BF16 quantizer.
Dynamic activation ranges are online per token/per 64 inputs, an accuracy
diagnostic with an explicit range-reduction cost, not a free hardware change.
"""
from dataclasses import dataclass
from pathlib import Path
import sys

import torch
from torch import nn
from torch.nn import functional as F

from .core import encode_fixed, quantize_int8
from .shared_counts import shared_counts


@dataclass
class MatrixSpec:
    decoded: torch.Tensor
    probability: torch.Tensor
    amplitude: torch.Tensor  # Signed coefficient of one asserted weight bit.
    reference_decoded: torch.Tensor
    policy: str


def encode_input(value, fixed_scale, policy, bits=8):
    """Return (probability, signed decoded value, positive expanded scale)."""
    if bits != 8:
        raise ValueError('This range study requires 8-bit probabilities')
    value = value.float()
    if value.shape[-1] % 64:
        raise ValueError('Input width must be divisible by 64')
    if policy == 'legacy':
        scale = torch.as_tensor(fixed_scale, device=value.device, dtype=torch.float32)
        if not bool(torch.isfinite(scale).all() and (scale > 0).all()):
            raise ValueError('Fixed scales must be finite and positive')
    elif policy == 'dynamic64':
        grouped = value.reshape(*value.shape[:-1], value.shape[-1] // 64, 64)
        maximum = grouped.abs().amax(-1, keepdim=True).clamp_min(1e-20)
        # q(max)=255; decoded max is exact rather than inadvertently saturated.
        scale = (maximum * (256. / 255.)).expand_as(grouped).reshape_as(value)
    else:
        raise ValueError(policy)
    probability, decoded = encode_fixed(value, scale, bits)
    return probability, decoded, scale


def make_matrix_spec(weight, policy='legacy', group=64):
    if group != 64:
        raise ValueError('Only group=64 is supported in this controlled study')
    codes, reference, lsb = quantize_int8(weight.detach(), group)
    if policy == 'legacy':
        probability = codes.abs().float() / 127.
        magnitude = lsb.repeat_interleave(group, 0).repeat_interleave(group, 1) * 127.
    elif policy in ('row64', 'row64_ideal'):
        grouped = reference.reshape(reference.shape[0], -1, group)
        maximum = grouped.abs().amax(-1, keepdim=True).clamp_min(1e-20)
        if policy == 'row64':
            magnitude = (maximum * (256. / 255.)).expand_as(grouped).reshape_as(reference)
            probability = (reference.abs() * (256. / magnitude)).round().clamp(0, 255) / 256.
        else:
            magnitude = maximum.expand_as(grouped).reshape_as(reference)
            probability = reference.abs() / magnitude
    else:
        raise ValueError(policy)
    amplitude = magnitude * reference.sign()
    # Preserve the identical W8 expectation for legacy/ideal controls rather
    # than introducing a second floating-point divide/multiply round trip.
    decoded = probability * amplitude if policy == 'row64' else reference
    return MatrixSpec(decoded.contiguous(), probability.contiguous(),
                      amplitude.contiguous(), reference.contiguous(), policy)


def project_counts(counts, sign, scale, spec, kind, cycles, generator,
                   token_chunk=16, output_chunk=32):
    """Project input-stream counts; exact conditional W Bernoulli counts.

    Same input counts feed all output rows. W streams remain independent for
    each connection and independent of A. Temporal order may be discarded only
    under this declared independence and exact spatial/time accumulation.
    """
    if kind not in ('fixed', 'dual') or cycles <= 0:
        raise ValueError('Expected fixed/dual and positive cycles')
    if kind == 'fixed':
        return F.linear(sign * scale * counts, spec.decoded) / cycles
    shape = counts.shape
    n = counts.reshape(-1, shape[-1])
    coefficient = (sign * scale).expand_as(counts).reshape_as(n)
    out = torch.empty((n.shape[0], spec.decoded.shape[0]), device=n.device, dtype=torch.float32)
    for start in range(0, n.shape[0], token_chunk):
        for row in range(0, out.shape[-1], output_chunk):
            p = spec.probability[row:row+output_chunk]
            count = n[start:start+token_chunk, None, :].expand(-1, p.shape[0], -1)
            events = torch.binomial(count, p[None].expand_as(count), generator=generator)
            contribution = (events * coefficient[start:start+token_chunk, None, :]
                            * spec.amplitude[row:row+output_chunk][None])
            out[start:start+token_chunk, row:row+output_chunk] = contribution.sum(-1) / cycles
    return out.reshape(*shape[:-1], out.shape[-1])


def project_probability(probability, sign, scale, spec, kind, cycles,
                        input_generator=None, weight_generator=None, **kwargs):
    if kind == 'mean':
        return F.linear(sign * scale * probability, spec.decoded)
    if kind not in ('fixed', 'dual'):
        raise ValueError(kind)
    counts = shared_counts(probability, cycles, input_generator, 64)
    return project_counts(counts, sign, scale, spec, kind, cycles, weight_generator, **kwargs)


class RangeFFN(nn.Module):
    def __init__(self, original, old_scales, sz, activation_policy='legacy',
                 weight_policy='legacy', kind='dual', cycles=256, seed=0,
                 layer=0, scope='all'):
        super().__init__()
        if kind not in ('dual', 'fixed', 'mean') or scope not in ('all', 'gu', 'down'):
            raise ValueError('Invalid kind/scope')
        if cycles <= 0:
            raise ValueError('cycles must be positive')
        if any(p.bias is not None for p in (original.gate_proj, original.up_proj, original.down_proj)):
            raise ValueError('Qwen reference expects bias-free FFN')
        self.activation_policy, self.weight_policy = activation_policy, weight_policy
        self.kind, self.cycles, self.scope, self.calls = kind, cycles, scope, 0
        self.width = original.gate_proj.weight.shape[0]
        weights = {'gu': torch.cat((original.gate_proj.weight, original.up_proj.weight), 0),
                   'down': original.down_proj.weight}
        for name, weight in weights.items():
            spec = make_matrix_spec(weight, weight_policy)
            for field in ('decoded', 'probability', 'amplitude', 'reference_decoded'):
                self.register_buffer(name + '_' + field, getattr(spec, field))
        for name, values, width in (('x', old_scales['x'], weights['gu'].shape[-1]),
                                     ('z', sz, self.width)):
            scale = torch.as_tensor(values, device=weights['gu'].device, dtype=torch.float32)
            if scale.numel() == 1:
                scale = scale.expand(width)
            elif scale.numel() == width // 64:
                scale = scale.repeat_interleave(64)
            if scale.shape != (width,) or not bool(torch.isfinite(scale).all() and (scale > 0).all()):
                raise ValueError('Invalid ' + name + ' scale')
            self.register_buffer('scale_' + name, scale.clone())
            # n, zero, p_sum, encoding SSE, value power, clipped, scale_sum
            self.register_buffer(name + '_stats', torch.zeros(7, device=scale.device, dtype=torch.float64))
        for offset, name in enumerate(('input', 'product', 'weight_gu', 'weight_down'), 1):
            setattr(self, 'rng_' + name, torch.Generator(device=weights['gu'].device)
                    .manual_seed(700000 + offset + seed * 1000 + layer * 7))

    def matrix_spec(self, name):
        if name not in ('gu', 'down'):
            raise ValueError(name)
        return MatrixSpec(*(getattr(self, name + '_' + field) for field in
                            ('decoded', 'probability', 'amplitude', 'reference_decoded')),
                          self.weight_policy)

    def stage_kind(self, stage):
        return self.kind if self.scope in ('all', stage) else 'mean'

    def _stage(self, value, name, matrix, input_generator, weight_generator):
        p, decoded, scale = encode_input(value, getattr(self, 'scale_' + name), self.activation_policy)
        s = getattr(self, name + '_stats')
        with torch.no_grad():
            s[0] += value.numel()
            s[1] += (p == 0).sum()
            s[2] += p.sum(dtype=torch.float64)
            s[3] += (decoded-value).square().sum(dtype=torch.float64)
            s[4] += value.square().sum(dtype=torch.float64)
            s[5] += (value.abs() >= scale).sum()
            s[6] += scale.expand_as(value).sum(dtype=torch.float64)
        return project_probability(p, value.sign(), scale, self.matrix_spec(matrix),
                                   self.stage_kind(matrix), self.cycles,
                                   input_generator, weight_generator)

    def forward(self, x):
        self.calls += 1
        gu = self._stage(x.float(), 'x', 'gu', self.rng_input, self.rng_weight_gu)
        g, u = gu.chunk(2, -1)
        z = F.silu(g) * u
        return self._stage(z, 'z', 'down', self.rng_product, self.rng_weight_down).to(x.dtype)

    def diagnostics(self):
        result = dict(calls=self.calls, activation_policy=self.activation_policy,
                      weight_policy=self.weight_policy, kind=self.kind, scope=self.scope,
                      cycles=self.cycles, gu_kind=self.stage_kind('gu'),
                      down_kind=self.stage_kind('down'), backend='exact conditional Binomial')
        for name in ('x', 'z'):
            n, zeros, psum, err, power, clipped, scale_sum = getattr(self, name + '_stats').tolist()
            result.update({name + '_values': int(n), name + '_zero_fraction': zeros / max(n, 1),
                           name + '_mean_probability': psum / max(n, 1),
                           name + '_encoding_nmse': err / max(power, 1e-30),
                           name + '_clip_fraction': clipped / max(n, 1),
                           name + '_mean_scale': scale_sum / max(n, 1)})
        for name in ('gu', 'down'):
            spec = self.matrix_spec(name)
            result[name + '_weight_mean_probability'] = spec.probability.mean().item()
            result[name + '_weight_reencode_nmse'] = ((spec.decoded-spec.reference_decoded).square().sum()
                / spec.reference_decoded.square().sum().clamp_min(1e-30)).item()
        return result
