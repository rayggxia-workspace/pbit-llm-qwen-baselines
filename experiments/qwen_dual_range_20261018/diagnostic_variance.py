"""Conditional per-projection IID variances with shared-uniform input lanes.

This module does not sample a stream or run a model. Inputs are flattened
``tokens x input_features`` tensors; weights are ``output_features x inputs``.
For each token and group, all input lanes compare against the same IID U.
Distinct groups, time steps and individual weight connections are independent.

``spec.decoded`` is the deterministic mean weight. ``spec.amplitude`` is the
signed amplitude of an asserted weight bit, and ``spec.probability`` its r.
The caller must ensure decoded == amplitude * probability. The default
computation uses FP32 and clamps tiny negative variances caused by rounding.

Run ``python diagnostic_variance.py`` for CPU-only mathematical checks.
"""

from types import SimpleNamespace

import torch
from torch.nn import functional as F


# Keep the largest intermediate token/output/group/lane tensor below 2^20
# elements with the default group size. These are computational chunks only;
# changing them must not change the model's sharing or range groups.
_OUTPUT_CHUNK = 32
_TOKEN_CHUNK = 32
_GROUP_CHUNK = 8


@torch.no_grad()
def projection_variances(p, sign, scale, spec, cycles, group=64):
    """Return (shared_input_variance, extra_weight_variance), each tokens x out.

    The two terms sum to the unconditional variance at *fixed current inputs*.
    The second is E[Var(output | all input streams)], rather than the variance
    conditional on one realized input count. Means/quantization errors must be
    reported separately. No independence assumption is made within an input
    sharing group, and signs are retained in the input covariance.
    """
    if p.ndim != 2:
        raise ValueError("p must have shape tokens x input_features")
    if cycles <= 0 or group <= 0 or p.shape[1] % group:
        raise ValueError("positive cycles/group and divisible input width required")
    p = p.detach().to(dtype=torch.float32)
    sign = torch.broadcast_to(torch.as_tensor(sign, device=p.device,
                                             dtype=torch.float32), p.shape)
    scale = torch.broadcast_to(torch.as_tensor(scale, device=p.device,
                                              dtype=torch.float32), p.shape)
    decoded = torch.as_tensor(spec.decoded, device=p.device, dtype=torch.float32)
    if decoded.ndim != 2 or decoded.shape[1] != p.shape[1]:
        raise ValueError("spec.decoded must have shape output_features x inputs")
    amplitude = torch.broadcast_to(torch.as_tensor(spec.amplitude, device=p.device,
                                                  dtype=torch.float32), decoded.shape)
    probability = torch.broadcast_to(torch.as_tensor(spec.probability,
                                                    device=p.device,
                                                    dtype=torch.float32), decoded.shape)
    if not bool(((p >= 0) & (p <= 1)).all()):
        raise ValueError("input probabilities must be finite and in [0, 1]")
    if not bool(((probability >= 0) & (probability <= 1)).all()):
        raise ValueError("weight probabilities must be finite and in [0, 1]")
    if not bool((torch.isfinite(scale) & (scale >= 0)).all()):
        raise ValueError("input scales must be finite and nonnegative")

    ntokens, ninputs = p.shape
    noutputs = decoded.shape[0]
    ngroups = ninputs // group
    var_input = torch.zeros((ntokens, noutputs), device=p.device,
                            dtype=torch.float32)
    var_weight = torch.empty_like(var_input)
    signed_scale = sign * scale
    input_second_factor = p * scale.square()

    # Sorted thresholds partition U in [0, 1]. On [p[k-1], p[k]),
    # only coefficients k..last remain asserted. Equal thresholds create
    # zero-length intervals and require no special tie handling.
    for token_start in range(0, ntokens, _TOKEN_CHUNK):
        token_stop = min(token_start + _TOKEN_CHUNK, ntokens)
        token_count = token_stop - token_start
        pg = p[token_start:token_stop].reshape(token_count, ngroups, group)
        sorted_p, order = pg.sort(dim=-1)
        delta = torch.cat((sorted_p[..., :1],
                           sorted_p[..., 1:] - sorted_p[..., :-1]), dim=-1)
        sg = signed_scale[token_start:token_stop].reshape(
            token_count, ngroups, group)
        for output_start in range(0, noutputs, _OUTPUT_CHUNK):
            output_stop = min(output_start + _OUTPUT_CHUNK, noutputs)
            output_count = output_stop - output_start
            wg = decoded[output_start:output_stop].reshape(
                output_count, ngroups, group)
            accumulator = torch.zeros((token_count, output_count),
                                      device=p.device, dtype=torch.float32)
            for group_start in range(0, ngroups, _GROUP_CHUNK):
                group_stop = min(group_start + _GROUP_CHUNK, ngroups)
                coefficients = (sg[:, None, group_start:group_stop, :]
                                * wg[None, :, group_start:group_stop, :])
                index = order[:, None, group_start:group_stop, :].expand_as(
                    coefficients)
                sorted_coefficients = coefficients.gather(-1, index)
                tails = sorted_coefficients.flip((-1,)).cumsum(-1).flip((-1,))
                mean = (sorted_coefficients
                        * sorted_p[:, None, group_start:group_stop, :]).sum(-1)
                second = (tails.square()
                          * delta[:, None, group_start:group_stop, :]).sum(-1)
                accumulator += (second - mean.square()).clamp_min_(0).sum(-1)
            var_input[token_start:token_stop,
                      output_start:output_stop] = accumulator / float(cycles)

    # W connections are conditionally independent, even when A lanes share U.
    # Average over the random A counts: E[C_i] = T*p_i.
    for output_start in range(0, noutputs, _OUTPUT_CHUNK):
        output_stop = min(output_start + _OUTPUT_CHUNK, noutputs)
        r = probability[output_start:output_stop]
        coefficient = (amplitude[output_start:output_stop].square()
                       * r * (1.0 - r))
        var_weight[:, output_start:output_stop] = F.linear(
            input_second_factor, coefficient).clamp_min_(0) / float(cycles)
    return var_input, var_weight


def _direct_covariance_variance(p, sign, scale, decoded, cycles, group):
    """Slow FP64 CPU oracle used only by tests; materializes group covariances."""
    p, sign, scale, decoded = (v.double() for v in (p, sign, scale, decoded))
    sign = torch.broadcast_to(sign, p.shape)
    scale = torch.broadcast_to(scale, p.shape)
    result = torch.zeros((p.shape[0], decoded.shape[0]), dtype=torch.float64)
    for start in range(0, p.shape[1], group):
        pg = p[:, start:start + group]
        covariance = (torch.minimum(pg[:, :, None], pg[:, None, :])
                      - pg[:, :, None] * pg[:, None, :])
        coefficient = (sign[:, None, start:start + group]
                       * scale[:, None, start:start + group]
                       * decoded[None, :, start:start + group])
        result += torch.einsum("toi,tij,toj->to", coefficient,
                               covariance, coefficient)
    return result.clamp_min(0) / cycles


def test_cpu():
    """Exercise endpoint/tie/signed/broadcast/chunk cases against two oracles."""
    generator = torch.Generator(device="cpu").manual_seed(812735)
    for group, ntokens, noutputs, scale_shape in (
            (1, 3, 5, ()), (4, 5, 7, (12,)),
            (64, 35, 35, (35, 192))):
        ninputs = group * 3
        p = torch.rand((ntokens, ninputs), generator=generator)
        p[:, 0] = 0
        p[:, 1 if ninputs > 1 else 0] = 1
        if group > 2:
            p[:, 2:4] = 0.5  # Equal-probability lanes, possibly opposite signs.
        sign = torch.randint(0, 2, p.shape, generator=generator).float() * 2 - 1
        scale = torch.rand(scale_shape, generator=generator) + 0.2
        amplitude = torch.randn((noutputs, ninputs), generator=generator)
        r = torch.rand((noutputs, ninputs), generator=generator)
        r[0, :2] = torch.tensor([0., 1.])
        spec = SimpleNamespace(decoded=amplitude * r,
                               amplitude=amplitude, probability=r)
        for cycles in (1, 256):
            vi, vw = projection_variances(p, sign, scale, spec, cycles, group)
            vi_ref = _direct_covariance_variance(p, sign, scale,
                                                spec.decoded, cycles, group)
            vw_ref = F.linear(p.double() * scale.double().square(),
                              amplitude.double().square() * r.double()
                              * (1 - r.double())) / cycles
            torch.testing.assert_close(vi.double(), vi_ref, rtol=2e-5, atol=2e-5)
            torch.testing.assert_close(vw.double(), vw_ref, rtol=2e-5, atol=2e-5)
            assert vi.shape == vw.shape == (ntokens, noutputs)
            assert bool((vi >= 0).all()) and bool((vw >= 0).all())

    # Complete cancellation must survive shared input covariance: identical
    # probabilities and opposite mean weights give identically zero A noise.
    p = torch.tensor([[0.2, 0.2]])
    spec = SimpleNamespace(decoded=torch.tensor([[1., -1.]]),
                           amplitude=torch.tensor([[2., -2.]]),
                           probability=torch.tensor([[0.5, 0.5]]))
    vi, vw = projection_variances(p, 1., 1., spec, 256, group=2)
    torch.testing.assert_close(vi, torch.zeros_like(vi), atol=1e-8, rtol=0)
    torch.testing.assert_close(vw, torch.tensor([[0.4 / 256]]))

    # Explicit scalar product Bernoulli variance, including fixed-W endpoint.
    for pa, rw in ((0., 0.4), (0.05, 0.1), (1., 0.4), (0.3, 1.)):
        spec = SimpleNamespace(decoded=torch.tensor([[rw * 3.]]),
                               amplitude=torch.tensor([[3.]]),
                               probability=torch.tensor([[rw]]))
        vi, vw = projection_variances(torch.tensor([[pa]]), -1., 2.,
                                      spec, 256, group=1)
        expected = (6. ** 2) * pa * rw * (1 - pa * rw) / 256
        torch.testing.assert_close(vi + vw, torch.tensor([[expected]]),
                                   rtol=2e-6, atol=1e-8)
    print("PASS: shared-threshold integration matches direct covariance; "
          "weight variance, endpoints, ties, signs, broadcasting and chunks")


if __name__ == "__main__":
    test_cpu()
