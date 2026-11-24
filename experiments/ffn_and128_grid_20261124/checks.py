"""Analytic and sampled checks for equal-budget nested joint stratification."""
import itertools
import math


def moments(codes, grid, samples=128):
    first = second = 1.0
    for code, bins in zip(codes, grid):
        width = 256 // bins
        full, remainder = divmod(code, width)
        frac = remainder / width
        first *= full + frac
        second *= full + frac * frac
    repeats = samples // math.prod(grid)
    return repeats * first, repeats * (first - second)


def analytic_checks():
    codes = [0, 1, 31, 32, 33, 63, 64, 65, 127, 128, 129, 191, 192, 193, 255, 256]
    count = 0
    for triple in itertools.product(codes, repeat=3):
        mean0, v0 = moments(triple, (4, 2, 4))
        mean1, v1 = moments(triple, (8, 2, 8))
        expected = 128 * math.prod(c / 256 for c in triple)
        assert mean0 == mean1 == expected
        assert v1 <= v0 + 1e-12
        count += 1
    return {'analytic_triples': count, 'same_mean': True, 'nested_variance_nonincrease': True}


def device_checks(device):
    import torch
    from sampling import joint_counts, shared_input_counts
    result = analytic_checks()
    g = torch.Generator(device=device).manual_seed(101)
    x = torch.tensor([[0, 128, 256] + [83] * 61], device=device)
    a = shared_input_counts(x, 64, g)
    assert a[0, :3].tolist() == [0, 32, 64]
    for grid in [(4, 2, 4), (8, 2, 8)]:
        for triple, expected in [((256, 256, 256), 128), ((0, 128, 256), 0)]:
            q = [torch.full((64,), z, device=device) for z in triple]
            assert joint_counts(q, 128, grid, g).tolist() == [expected] * 64
    tests = []
    repeats = 16384
    for triple in [(73, 149, 211), (111, 91, 179), (128, 128, 128)]:
        for grid in [(4, 2, 4), (8, 2, 8)]:
            exact_mean, exact_var = moments(triple, grid)
            q = [torch.full((repeats,), z, device=device) for z in triple]
            draws = joint_counts(q, 128, grid, g).double()
            assert int(draws.min()) >= 0 and int(draws.max()) <= 128
            mean, var = float(draws.mean()), float(draws.var(unbiased=True))
            assert abs(mean - exact_mean) <= 8 * math.sqrt(exact_var / repeats) + 1e-12
            assert abs(var - exact_var) <= 0.08 * exact_var + 1e-10
            # Independently form every stratum's three comparator bits.
            cells = torch.tensor(list(itertools.product(*(range(n) for n in grid))), device=device)
            cells = cells.repeat_interleave(128 // math.prod(grid), dim=0)
            events = torch.ones((repeats, 128), device=device, dtype=torch.bool)
            for axis, bins in enumerate(grid):
                width = 256 // bins
                u = torch.randint(width, events.shape, device=device, generator=g) + cells[:, axis] * width
                events &= u < triple[axis]
            literal = events.sum(-1).double()
            assert abs(float(literal.mean()) - exact_mean) <= 8 * math.sqrt(exact_var / repeats) + 1e-12
            assert abs(float(literal.var(unbiased=True)) - exact_var) <= 0.08 * exact_var + 1e-10
            tests.append({'codes': triple, 'grid': grid, 'mean': mean, 'variance': var,
                          'analytic_mean': exact_mean, 'analytic_variance': exact_var})
    result.update(device=str(device), sample_moments=tests, literal_comparators=True, samples=128)
    return result
