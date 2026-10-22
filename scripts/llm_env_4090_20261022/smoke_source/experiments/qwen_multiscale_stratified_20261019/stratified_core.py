"""Fixed historical W8: multiscale activations and exact random strata.

Weights are quantized exactly once with the historical symmetric 64x64 INT8
quantizer; neither their integer codes nor their decoded values are recoded as
probabilities.  Activation lanes retain their original channel positions.  The
PoT policies attach a per-element scale-bin index within each 64-input group.
All scale bins in a group share the SAME random R8 word at each clock.

K equal strata partition 0..255. Each stratum receives T/K independent draws,
uniform within its own range; groups, tokens, and different strata are mutually
independent. K=1 is unchanged natural IID. K=T has one random offset per stratum
and is deliberately NOT IID. No deterministic low-discrepancy or selected seed
is substituted. Counts preserve the shared-lane joint distribution, permitting
FP32 linear reduction without explicitly expanding T by every lane. This is
a numerical distribution reference, not finite-width/cycle-accurate hardware.
"""
from pathlib import Path
import sys

import torch
from torch import nn
from torch.nn import functional as F


EXPERIMENTS = Path(__file__).resolve().parents[1]
FROZEN = EXPERIMENTS / 'qwen_dual_iid_exact_20261018/vendor/frozen'
RANGE = EXPERIMENTS / 'qwen_dual_range_20261018'
for path in (FROZEN, RANGE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
from core import quantize_int8
from range_core import encode_input as encode_dynamic_reference
from shared_counts import shared_counts


GROUP = 64
POLICY_BINS = {'dynamic64': 1, **{'pot' + str(k): k for k in (1, 2, 3, 4, 6, 8)}}


def _validate_sampling(cycles, strata):
    for name, value in (('cycles', cycles), ('strata', strata)):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(name + ' must be a positive integer')
    if 256 % strata or cycles % strata:
        raise ValueError('strata must divide both 256 and cycles')


def stratified_counts(probability, cycles, strata, generator=None, group=64):
    """Exact joint counts for shared R8, optionally stratified over its range.

    A threshold q in 0..256 has deterministic n*floor(q/w) successes plus
    successes from its single boundary stratum, where w=256/K and n=T/K.
    Lanes with boundaries in different strata must use independent draws;
    using one common offset in *all* strata would change the covariance.

    K=1 delegates to the frozen IID implementation, including RNG consumption.
    For n=1 draw one independent offset per group/stratum and gather the boundary
    offset. For n>1 a conditional binomial tree draws each stratum's exact
    multinomial histogram over its w integer offsets. Roots are independent
    and each has n counts; all child splits have probability .5. Cumulative
    histogram lookup gives all thresholds' counts. At most 256 histogram bins
    are materialized per group, independent of T (no T*64 bitstream expansion).

    Input must be the A8 grid q/256, including an explicit probability-one
    bypass. CPU calls validate this contract; the GPU hot path relies on the
    encoder invariant rather than synchronizing for a redundant host check.
    """
    _validate_sampling(cycles, strata)
    if not isinstance(group, int) or isinstance(group, bool) or group <= 0:
        raise ValueError('group must be a positive integer')
    if probability.ndim < 1 or probability.shape[-1] == 0 or probability.shape[-1] % group:
        raise ValueError('last dimension must be a positive multiple of group')
    if strata == 1:
        return shared_counts(probability, cycles, generator, group)
    shape = probability.shape
    p = probability.reshape(-1, group)
    # All producer encodings are exact multiples of 1/256. Do not add a device
    # synchronization for redundant hot-path checks; enforce this public input
    # contract on CPU fixtures and in encoding boundary tests.
    q = (p * 256).to(torch.int64)
    if probability.device.type == 'cpu':
        if not bool(torch.isfinite(p).all()) or not bool(((p * 256) == q).all()) or \
                not bool(((q >= 0) & (q <= 256)).all()):
            raise ValueError('probability must lie on the exact A8 q/256 grid in [0,1]')
    n, width = cycles // strata, 256 // strata
    if width == 1:
        # Full coverage is deterministic, even if the temporal order is shuffled.
        return (q * n).to(p.dtype).reshape(shape)
    if n == 1:
        offsets = torch.randint(width, (p.shape[0], strata), device=p.device,
                                generator=generator)
        boundary = q // width
        remainder = q % width
        chosen = offsets.gather(-1, boundary.clamp_max(strata - 1))
        result = boundary + (chosen < remainder).to(boundary.dtype)
        return result.to(p.dtype).reshape(shape)

    counts = p.new_full((p.shape[0], strata), float(n))
    remaining = width
    while remaining > 1:
        left = torch.binomial(counts, torch.full_like(counts, .5), generator=generator)
        counts = torch.stack((left, counts - left), -1).flatten(1)
        remaining //= 2
    # Entry q is the number of sampled integer words strictly less than q.
    cumulative = F.pad(counts.cumsum(-1), (1, 0))
    return cumulative.gather(-1, q).reshape(shape)


def encode_input(value, policy='pot4'):
    """Return an A8 magnitude encoding, separate sign, scale, and bin metadata.

    ``dynamic64`` calls the previous reference without changing its q=255,
    p=255/256 endpoint.  For PoT policies, the largest bin is ceilPow2(absmax)
    for each token/64 inputs.  Further bins divide that scale by 4.  Each lane
    selects the smallest bin that contains its magnitude, without clipping.
    Positive magnitude exactly at its scale uses an explicit full-one bypass;
    ordinary q=255 always means 255/256, never one.  An all-zero group uses top
    scale one and produces only zero probabilities.

    Expected inputs are finite FP32/BF16 model activations.  PoT scales must be
    representable in FP32; this reference does not implement exceptional BF16
    saturation or a wider exponent datapath.
    """
    if policy not in POLICY_BINS:
        raise ValueError('Unknown activation policy: ' + str(policy))
    value = value.float()
    if value.ndim < 1 or value.shape[-1] == 0 or value.shape[-1] % GROUP:
        raise ValueError('Input width must be a positive multiple of 64')
    if policy == 'dynamic64':
        probability, decoded, scale = encode_dynamic_reference(value, None, policy)
        return dict(q=(probability * 256).to(torch.int16), sign=value.sign(),
                    scale=scale, probability=probability, decoded=decoded,
                    full_one=torch.zeros_like(value, dtype=torch.bool),
                    bin_id=torch.zeros_like(value, dtype=torch.int64))

    grouped = value.reshape(*value.shape[:-1], value.shape[-1] // GROUP, GROUP)
    magnitude = grouped.abs()
    maximum = magnitude.amax(-1, keepdim=True)
    # frexp avoids log2 rounding near a power-of-two boundary.  For m*2**e,
    # m=.5 already denotes a power of two and therefore needs exponent e-1.
    mantissa, exponent = torch.frexp(maximum)
    exponent = exponent - (mantissa == .5).to(exponent.dtype)
    exponent = torch.where(maximum == 0, torch.zeros_like(exponent), exponent)
    top = torch.ldexp(torch.ones_like(maximum), exponent)
    scale = top.expand_as(grouped).clone()
    bin_id = torch.zeros_like(grouped, dtype=torch.int64)
    # Normal Qwen activations are far above the FP32 subnormal region.  A clamp
    # still prevents a lower bin from becoming zero for tiny fixture values.
    minimum = torch.finfo(torch.float32).tiny
    for index in range(1, POLICY_BINS[policy]):
        candidate = (top * (4. ** -index)).clamp_min(minimum)
        eligible = magnitude <= candidate
        scale = torch.where(eligible, candidate, scale)
        bin_id = torch.where(eligible, index, bin_id)
    scale = scale.reshape_as(value)
    q = (value.abs() * (256. / scale)).round().clamp(0, 255)
    full_one = (value.abs() >= scale) & (value != 0)
    probability = torch.where(full_one, torch.ones_like(q), q / 256.)
    return dict(q=q.to(torch.int16), sign=value.sign(), scale=scale,
                probability=probability, decoded=value.sign() * scale * probability,
                full_one=full_one, bin_id=bin_id.reshape_as(value))


def project_counts(counts, sign, scale, decoded_weight, cycles):
    """Exact linear reduction for fixed W and the supplied shared A counts.

    Per-lane scales are restored BEFORE summation, so counts from different
    scale bins or weight tiles are never incorrectly merged without alignment.
    F.linear operates on the identical historical W8 decoded matrix throughout.
    """
    if cycles <= 0:
        raise ValueError('cycles must be positive')
    return F.linear(sign * scale * counts, decoded_weight) / cycles


def project_encoded(encoded, decoded_weight, mode, cycles, generator=None, strata=1):
    """One encoded projection; ``mean`` is a no-sampling encoding control.

    The complete nonlinear FFN in this mode is not the mathematical expectation
    of the complete sampled FFN, because SiLU and multiplication intervene.
    """
    if mode == 'mean':
        return F.linear(encoded['decoded'], decoded_weight)
    if mode != 'sampled':
        raise ValueError('Encoded projection mode must be mean or sampled')
    counts = stratified_counts(encoded['probability'], cycles, strata, generator, GROUP)
    return project_counts(counts, encoded['sign'], encoded['scale'], decoded_weight, cycles)


class StratifiedFFN(nn.Module):
    def __init__(self, original, policy='pot4', mode='sampled', cycles=128,
                 seed=0, layer=0, strata=1):
        super().__init__()
        if policy not in POLICY_BINS or mode not in ('w8_only', 'mean', 'sampled'):
            raise ValueError('Invalid policy/mode')
        _validate_sampling(cycles, strata)
        if any(p.bias is not None for p in
               (original.gate_proj, original.up_proj, original.down_proj)):
            raise ValueError('This reference expects bias-free FFN projections')
        self.policy, self.mode, self.cycles = policy, mode, cycles
        self.strata = strata
        self.seed, self.layer, self.calls = seed, layer, 0
        self.width = original.gate_proj.weight.shape[0]
        weights = {'gu': torch.cat((original.gate_proj.weight.detach(),
                                    original.up_proj.weight.detach()), 0),
                   'down': original.down_proj.weight.detach()}
        for name, weight in weights.items():
            codes, decoded, lsb = quantize_int8(weight, GROUP)
            self.register_buffer(name + '_codes', codes)
            self.register_buffer(name + '_decoded', decoded)
            self.register_buffer(name + '_tile_lsb', lsb)
        device = weights['gu'].device
        for name in ('x', 'z'):
            # n, probability-zero, p sum, encoding SSE, value power, actual
            # magnitude clipping, selected-scale sum, full-one bypass count.
            self.register_buffer(name + '_stats', torch.zeros(8, device=device,
                                                              dtype=torch.float64))
            self.register_buffer(name + '_bins', torch.zeros(POLICY_BINS[policy],
                                                             device=device, dtype=torch.float64))
        self.rng_input = torch.Generator(device=device).manual_seed(
            700001 + seed * 1000 + layer * 7)
        self.rng_product = torch.Generator(device=device).manual_seed(
            700002 + seed * 1000 + layer * 7)

    def _stage(self, value, signal, matrix, generator):
        stats = getattr(self, signal + '_stats')
        with torch.no_grad():
            stats[0] += value.numel()
            stats[4] += value.square().sum(dtype=torch.float64)
        weight = getattr(self, matrix + '_decoded')
        if self.mode == 'w8_only':
            return F.linear(value, weight)
        encoded = encode_input(value, self.policy)
        with torch.no_grad():
            probability = encoded['probability']
            stats[1] += (probability == 0).sum()
            stats[2] += probability.sum(dtype=torch.float64)
            stats[3] += (encoded['decoded'] - value).square().sum(dtype=torch.float64)
            stats[5] += (value.abs() > encoded['scale']).sum()
            stats[6] += encoded['scale'].sum(dtype=torch.float64)
            stats[7] += encoded['full_one'].sum()
            occupancy = torch.bincount(encoded['bin_id'].reshape(-1),
                                       minlength=POLICY_BINS[self.policy])
            getattr(self, signal + '_bins').add_(occupancy)
        return project_encoded(encoded, weight, self.mode, self.cycles, generator, self.strata)

    def forward(self, x):
        self.calls += 1
        # Exactly the same input draw feeds gate and up.  Only after restoring
        # g/u do we apply continuous FP32 SiLU(g)*u; z gets an independent draw.
        g, u = self._stage(x.float(), 'x', 'gu', self.rng_input).chunk(2, -1)
        z = F.silu(g) * u
        return self._stage(z, 'z', 'down', self.rng_product).to(x.dtype)

    def diagnostics(self):
        result = dict(calls=self.calls, layer=self.layer, policy=self.policy,
                      mode=self.mode, cycles=self.cycles, probability_bits=8,
                      sampler='IID' if self.strata == 1 else 'random equal-range stratification',
                      strata=self.strata, samples_per_stratum=self.cycles // self.strata,
                      stratum_width=256 // self.strata,
                      sharing=64, scale_bin_count=POLICY_BINS[self.policy],
                      scale_bin_exponent_step=0 if self.policy == 'dynamic64' else 2,
                      weight_encoding='fixed symmetric INT8, historical 64x64 tile',
                      weight_stochastic=False, weight_probability_reencoded=False,
                      gu_weight_reencode_nmse=0., down_weight_reencode_nmse=0.,
                      backend='exact joint shared-R8 counts; FP32 linear reduction',
                      activation_encoding_applied=self.mode != 'w8_only',
                      p1_bypass=self.policy != 'dynamic64' and self.mode != 'w8_only',
                      nonlinear='continuous FP32 SiLU(g)*u, independently reencoded z',
                      finite_width_bittrue=False)
        for name in ('x', 'z'):
            n, zeros, psum, err, power, clipped, scale_sum, p1 = getattr(
                self, name + '_stats').tolist()
            bins = getattr(self, name + '_bins').tolist()
            result.update({name + '_values': int(n),
                           name + '_zero_fraction': zeros / max(n, 1),
                           name + '_mean_probability': psum / max(n, 1),
                           name + '_encoding_nmse': err / max(power, 1e-30),
                           name + '_clip_fraction': clipped / max(n, 1),
                           name + '_mean_scale': scale_sum / max(n, 1),
                           name + '_p1_fraction': p1 / max(n, 1),
                           name + '_bin_counts': [int(v) for v in bins],
                           name + '_bin_occupancy': [v / max(n, 1) for v in bins]})
        return result
