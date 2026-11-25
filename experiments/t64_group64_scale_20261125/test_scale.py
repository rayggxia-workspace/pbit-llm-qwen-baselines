import itertools
import unittest
import torch
from scale_patch import encode_group64, encode_group_p8
from sampling import shared_input_counts, joint_counts


class TestGroupScale(unittest.TestCase):
    def test_choose_common_cover(self):
        v = torch.full((2, 128), .001)
        v[0, 0] = .3
        v[1, 64] = 1.1
        table = torch.tensor([[4., 1., .25, .0625], [2., .5, .125, .03125]])
        e = encode_group64(v, table)
        for row in range(2):
            for group in range(2):
                values = v[row, group*64:(group+1)*64]
                candidates = [float(s) for s in table[group] if s >= values.abs().max()]
                expected = min(candidates) if candidates else float(table[group, 0])
                self.assertTrue(torch.equal(e['scale'][row, group*64:(group+1)*64],
                                           torch.full((64,), expected)))

    def test_endpoints_and_rne(self):
        v = torch.zeros(64); v[:5] = torch.tensor([1., -2., 0., 2.5/256, 3.5/256])
        e = encode_group64(v, torch.tensor([[1., .25, .0625, .015625]]))
        self.assertEqual(e['full_one'][:3].tolist(), [True, True, False])
        self.assertEqual(e['q'][3:5].tolist(), [2, 4])
        self.assertEqual(e['decoded'][:3].tolist(), [1., -1., 0.])

    def test_g_u_choose_independently(self):
        g, u = torch.full((2, 64), .1), torch.full((2, 64), 3.)
        qg, _, eg, sg = encode_group_p8(g, torch.tensor([4.]))
        qu, _, eu, su = encode_group_p8(u, torch.tensor([4.]))
        self.assertTrue((sg == 4).all() and (su == 0).all())
        self.assertTrue((eg == -2).all() and (eu == 2).all())

    def test_input_literal_strata(self):
        for t in [16, 64]:
            codes = torch.arange(256).reshape(4, 64).long()
            gen = torch.Generator().manual_seed(123)
            got = shared_input_counts(codes, t, gen)
            gen.manual_seed(123)
            r = torch.randint(256//t, (4, t), generator=gen) + torch.arange(t)[None, :] * (256//t)
            expected = (r[:, :, None] < codes[:, None, :]).sum(1)
            self.assertTrue(torch.equal(got, expected))

    def test_joint_deterministic_cell_boundaries(self):
        for grid in [(4,2,4), (8,2,8)]:
            t = grid[0]*grid[1]*grid[2]
            qs = [torch.tensor([0, 256//axis, 256], dtype=torch.long) for axis in grid]
            got = joint_counts(qs, t, grid, torch.Generator().manual_seed(9))
            self.assertTrue(torch.equal(got, torch.tensor([0, 1, t])))

    def test_joint_unbiased_rare_and_common(self):
        n = 12000
        qs = [torch.full((n,), v, dtype=torch.long) for v in [19, 149, 230]]
        for grid in [(4,2,4), (8,2,8)]:
            t = grid[0]*grid[1]*grid[2]
            v = joint_counts(qs, t, grid, torch.Generator().manual_seed(17)).double()
            expected = t * 19*149*230/256**3
            self.assertLess(abs(v.mean().item()-expected), 5*v.std().item()/n**.5 + .002)


if __name__ == '__main__':
    unittest.main()
