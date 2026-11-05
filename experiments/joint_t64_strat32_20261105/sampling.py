"""Finite P8 count samplers, independent of model/quantization/loading code.

New inference candidates only. The reference IID64 runner must stay unchanged.
Input counts preserve one shared R8 per 64-lane group. Nonlinear counts preserve
the same AND event/count for all Wd columns, with no z re-encoding. Independent
within-cell jitter is assumed; this is not an RTL GF64 or physical-pbit replay.
"""
import itertools
import math


def validate(samples, grid=None):
    if type(samples) is not int or samples <= 0:
        raise ValueError('positive integer sample count required')
    if grid is None:
        if 256 % samples:
            raise ValueError('input strata must partition the R8 domain')
    elif len(grid) != 3 or any(type(x) is not int or x <= 0 or 256 % x for x in grid) or samples % math.prod(grid):
        raise ValueError('three full-domain grid axes must divide R8 and sample count')


def shared_input_counts(codes, samples, generator=None, group=64):
    """T strata, one independent offset/stratum/group; codes are integers 0..256."""
    import torch
    validate(samples)
    if codes.shape[-1] % group:
        raise ValueError('incomplete input group')
    shape = codes.shape
    q = codes.to(torch.int64).reshape(-1, group)
    width = 256 // samples
    boundary, remainder = q // width, q % width
    offsets = torch.randint(width, (q.shape[0], samples), device=q.device, generator=generator)
    chosen = offsets.gather(1, boundary.clamp_max(samples - 1))
    return (boundary + (chosen < remainder).long()).reshape(shape)


def joint_counts(codes, samples, grid=(4, 4, 2), generator=None):
    """Exact joint-cell count law via seven disjoint boundary-cell binomials.

    Every cell has samples/product(grid) independent draws. Different channels
    and cells are independent. Inputs are P8 probability codes, not signed g/u
    or already rounded probability products. Returns integer counts in 0..T.
    """
    import torch
    validate(samples, grid)
    if len(codes) != 3 or any(q.shape != codes[0].shape for q in codes):
        raise ValueError('three equal-shaped probability codes required')
    q = [x.to(torch.int64) for x in codes]
    full = [x // (256 // n) for x, n in zip(q, grid)]
    fraction = [(x % (256 // n)).double() / (256 // n) for x, n in zip(q, grid)]
    per_cell = samples // math.prod(grid)
    count = full[0] * full[1] * full[2] * per_cell
    for partial in itertools.product((False, True), repeat=3):
        if not any(partial):
            continue
        trials = torch.full_like(count, per_cell)
        probability = torch.ones_like(count, dtype=torch.float64)
        for i in range(3):
            if partial[i]:
                probability = probability * fraction[i]
            else:
                trials = trials * full[i]
        count = count + torch.binomial(trials.double(), probability, generator=generator).long()
    return count
