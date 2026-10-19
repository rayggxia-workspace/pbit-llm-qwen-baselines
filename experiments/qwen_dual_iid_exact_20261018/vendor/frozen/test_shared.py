"""Independent invariants and statistical tests for the correlated sampler."""
import torch
from shared_counts import shared_counts


def main():
    torch.set_num_threads(4)
    generator = torch.Generator().manual_seed(918)
    p = torch.tensor([0., .25, .25, .5, 1., .125, .875, .5]).repeat(10000, 1)
    counts = shared_counts(p, 64, generator, 8)
    assert (counts[:, 0] == 0).all() and (counts[:, 4] == 64).all()
    assert (counts[:, 1] == counts[:, 2]).all() and (counts[:, 3] == counts[:, 7]).all()
    assert (counts[:, 1] <= counts[:, 3]).all()
    assert (counts[:, 5] <= counts[:, 1]).all()
    expected = p[0] * 64
    assert (counts.mean(0) - expected).abs().max() < .18
    covariance = torch.cov(counts.T)
    analytic = 64 * (torch.minimum(p[0, :, None], p[0, None, :]) - p[0, :, None]*p[0, None, :])
    assert (covariance - analytic).abs().max() < .6, (covariance, analytic)
    # Compare with literal IID 8-bit comparator clocks, not another count sampler.
    r = torch.randint(256, (10000, 64, 1), generator=generator)
    literal = (r < (p[0] * 256).long()).sum(1).float()
    assert (literal.mean(0) - counts.mean(0)).abs().max() < .25
    coeff = torch.tensor([0., 1., -.7, .2, .1, -.3, .4, .05])
    y = counts @ coeff / 64
    yl = literal @ coeff / 64
    assert abs(y.mean().item()-yl.mean().item()) < .006
    assert abs(y.var().item()-yl.var().item()) < .00025
    # Separate input groups must NOT share the same source.
    pp = torch.full((10000, 128), .5)
    cc = shared_counts(pp, 64, generator, 64)
    assert (cc[:, :64] == cc[:, :1]).all()
    assert (cc[:, 64:] == cc[:, 64:65]).all()
    cov = torch.cov(cc[:, [0,64]].T)
    assert abs(cov[0,1].item()) < .6
    a = shared_counts(p[:5], 4096, torch.Generator().manual_seed(33), 8)
    b = shared_counts(p[:5], 4096, torch.Generator().manual_seed(33), 8)
    assert torch.equal(a,b)
    if torch.cuda.is_available():
        a = shared_counts(p[:500].cuda(), 4096, torch.Generator(device='cuda').manual_seed(33), 8)
        assert (a[:, 1] == a[:, 2]).all() and torch.isfinite(a).all()
    print('PASS: nested thresholds, exact boundaries, analytic mean/covariance, literal comparator projection, group independence, reproducibility', flush=True)


if __name__ == '__main__': main()
