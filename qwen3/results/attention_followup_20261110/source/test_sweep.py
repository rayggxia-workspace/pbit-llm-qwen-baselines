import unittest
import torch
from .methods import GROUPS, configuration, draw, inverse_cdf, Patch
from experiments.sparq_ising_20261028 import core
from experiments.sparq_ising_20261028.vendor.plans import full_window_plan, plan_batches


class FollowupTests(unittest.TestCase):
    def test_cases_and_plans(self):
        self.assertEqual(len(GROUPS["2k"]), 9)
        self.assertEqual(len(GROUPS["8k"]), 5)
        self.assertEqual([c["seed"] for c in GROUPS["2k"][1:3]], [1, 2])
        for context, size, count in [(2048, 32, 292), (8192, 8, 286)]:
            plan = full_window_plan(299078, context, 1024)
            self.assertEqual(len(plan), count)
            self.assertEqual(sum(r["scored_tokens"] for r in plan), 299077)
            self.assertEqual(sum(len(b) for b in plan_batches(plan, size)), count)
        for group in GROUPS.values():
            for c in group[1:]:
                cfg = configuration(c)
                self.assertEqual(cfg.samples, 64)
                self.assertEqual(cfg.local, 32)

    def test_cdf_boundary_oracle(self):
        logits = torch.tensor([[0., float("-inf"), 0., float("-inf")]])
        u = torch.tensor([[0., .125, .49999, .5, .75, .99999, 1.]])
        self.assertEqual(inverse_cdf(logits, u).tolist(), [[0, 0, 0, 2, 2, 2, 2]])
        for n in [1, 3, 64, 127, 128, 256]:
            z = torch.arange(n).float()[None, :] / max(n, 1)
            p = z.softmax(-1)[0].double().tolist()
            values = [i/1000 for i in range(1000)]
            expected = []
            for x in values:
                total = 0.
                for j, weight in enumerate(p):
                    total += weight
                    if x < total:
                        expected.append(j)
                        break
            got = inverse_cdf(z, torch.tensor([values]))[0].tolist()
            self.assertEqual(got, expected)

    def test_systematic_counts(self):
        z = torch.tensor([[.1, -.5, 1.1, -2.], [1., 1., 1., 1.]])
        for seed in (0, 1, 2):
            ids = draw(z, 64, "systematic", seed)
            counts = torch.zeros_like(z).scatter_add_(1, ids, torch.ones_like(ids, dtype=z.dtype))
            self.assertTrue(bool(((counts - z.softmax(-1)*64).abs() < 1.0001).all()))
            self.assertTrue(bool((counts[1] == 16).all()))

    def test_iid_frequency_and_replay(self):
        z = torch.tensor([[0., .5, -1.]])
        ids = draw(z, 100000, "categorical", 1981110)
        self.assertTrue(torch.equal(ids, draw(z, 100000, "categorical", 1981110)))
        count = torch.bincount(ids[0], minlength=3).float()/100000
        self.assertTrue(bool(((count - z.softmax(-1)[0]).abs() < .008).all()))

    def test_readout_and_restore(self):
        old_readout, old_select = core.readout, core.select
        for method in ("categorical", "systematic"):
            c = next(c for c in GROUPS["2k"] if c["method"] == method)
            cfg = configuration(c)
            z = torch.randn((2, 2, 4, 7), generator=torch.Generator().manual_seed(7))
            v = torch.randn((2, 2, 7, 5), generator=torch.Generator().manual_seed(8))
            with Patch(c):
                out, ids, stats = core.readout(z, v, cfg, 5)
                expected = torch.stack([torch.stack([torch.stack([v[b,h,ids[b,h,g]].mean(0)
                    for g in range(4)]) for h in range(2)]) for b in range(2)])
                self.assertTrue(torch.equal(out, expected))
                self.assertEqual(tuple(ids.shape), (2, 2, 4, 64))
                self.assertTrue(bool((stats[:, 1] == 64).all()))
            self.assertIs(core.readout, old_readout)
            self.assertIs(core.select, old_select)


def gpu_oracle():
    checked = []
    for n in (1, 3, 64, 127, 128, 256):
        z = torch.linspace(-3, 3, n)[None, :].repeat(2, 1)
        uniforms = torch.tensor([[.001, .11, .49, .501, .89, .999]]).repeat(2, 1)
        expected = inverse_cdf(z, uniforms)
        actual = inverse_cdf(z.cuda(), uniforms.cuda()).cpu()
        assert torch.equal(expected, actual), n
        for method in ("categorical", "systematic"):
            a = draw(z.cuda(), 64, method, 7)
            assert torch.equal(a, draw(z.cuda(), 64, method, 7))
            assert a.shape == (2, 64) and bool(((a >= 0) & (a < n)).all())
        checked.append(n)
    return checked
