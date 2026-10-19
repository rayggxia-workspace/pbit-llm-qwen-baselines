"""Run with ``python -m unittest experiments.llama2_ffn_precision.test_numeric``.

The source/oracle tests run without PyTorch. Tensor tests skip explicitly when
the current environment lacks PyTorch; CUDA precision tests additionally require
a CUDA device and never silently replace integer arithmetic with floating GEMM.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import unittest

from . import numeric as n

torch = n.torch
VENDOR = Path(__file__).parent / "vendor_q10"
spec = importlib.util.spec_from_file_location("issue7_q10_golden", VENDOR / "golden_model.py")
golden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(golden)


class ScalarOracleTests(unittest.TestCase):
    def test_original_bytes(self):
        manifest = json.loads((VENDOR / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_issue"], 7)
        self.assertEqual(len(manifest["files"]), 5)
        for item in manifest["files"]:
            data = (VENDOR / item["path"]).read_bytes()
            self.assertEqual(len(data), item["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])

    def test_scalar_matches_original_all_gate_codes(self):
        for g in range(-32768, 32768):
            self.assertEqual(n.q10_swiglu_scalar(g, 12345), golden.evaluate(g, 12345))

    def test_scalar_boundaries_random_and_ties(self):
        rng = random.Random(19)
        pairs = [(rng.randrange(-32768, 32768), rng.randrange(-32768, 32768)) for _ in range(3000)]
        pairs += [(g, u) for g in (-32768, -8192, -8191, -1, 0, 1, 4096, 8191, 8192, 32767)
                  for u in (-32768, -24576, -8192, -1, 0, 1, 8192, 24576, 32767)]
        for width in (16, 24, 32):
            for g, u in pairs:
                self.assertEqual(n.q10_swiglu_scalar(g, u, width), golden.evaluate(g, u, width))
        with self.assertRaises(ValueError):
            n.q10_swiglu_scalar(32768, 0)

    def test_256_enumeration_identity_and_short_strata_unbiased(self):
        # Exhaust every possible integer jitter for each stratum: its exact
        # expected contribution is fraction of thresholds below q in that bin.
        for q in range(256):
            self.assertEqual(sum(r < q for r in range(256)), q)
            for T in (16, 32, 64, 128):
                width = 256 // T
                event_total = sum(sum(s * width + j < q for j in range(width)) for s in range(T))
                self.assertEqual(event_total / width, T * q / 256)

    def test_integer_bounds(self):
        self.assertLess(11008 * 127 * 127, 2**31)
        self.assertGreater(11008 * 4096 * 127, 2**31)
        for value in (-4096, -4095, -129, -128, -127, -1, 0, 1, 127, 128, 4095, 4096):
            low, high = value % 128, value // 128
            self.assertTrue(0 <= low <= 127 and -32 <= high <= 32)
            self.assertEqual(low + 128 * high, value)


@unittest.skipIf(torch is None, "PyTorch unavailable: tensor tests must run in experiment environment")
class TensorTests(unittest.TestCase):
    def gen(self, seed=19, device="cpu"):
        return torch.Generator(device=device).manual_seed(seed)

    def test_weight_tiles_and_decode(self):
        weight = torch.zeros((128, 128))
        weight[:64, :64] = torch.linspace(-1, 1, 4096).reshape(64, 64)
        weight[:64, 64:] = 2
        weight[64:, :64] = -4
        code, scales = n.quantize_weight(weight)
        self.assertEqual(code.dtype, torch.int8)
        self.assertTrue(torch.equal(scales[:1, :], torch.tensor([[1/127, 2/127]], dtype=torch.float32)))
        self.assertEqual(scales[1, 0].item(), torch.tensor(4/127, dtype=torch.float32).item())
        self.assertTrue((code[:64, 64:] == 127).all())
        self.assertTrue((code[64:, :64] == -127).all())
        decoded = n.dequantize_weight(code, scales)
        self.assertTrue(torch.equal(decoded[:64, 64:], weight[:64, 64:]))
        self.assertTrue(torch.equal(decoded[64:, :64], weight[64:, :64]))
        self.assertTrue((decoded[64:, 64:] == 0).all())

    def test_fixed_encoding_sign_endpoints_and_rne(self):
        value = torch.tensor([-2., -1., -0.5, -0., 0., 1/512, 3/512, 0.5, 1., 2.])
        q, sign, decoded = n.encode_fixed(value, 1.)
        self.assertEqual(q.tolist(), [255, 255, 128, 0, 0, 0, 2, 128, 255, 255])
        self.assertEqual(sign.tolist(), [-1, -1, -1, 0, 0, 1, 1, 1, 1, 1])
        self.assertTrue(torch.equal(decoded, sign.float() * q.float() / 256))
        grouped = n.encode_fixed(torch.ones(2, 128), torch.tensor([1., 2.]))[0]
        self.assertTrue((grouped[:, :64] == 255).all())
        self.assertTrue((grouped[:, 64:] == 128).all())

    def test_256_counts_exact_without_rng(self):
        q = torch.arange(256, dtype=torch.int16).repeat(2, 1)
        gen = self.gen()
        state = gen.get_state().clone()
        for method in ("enumerate256", "stratified"):
            self.assertTrue(torch.equal(n.sample_counts(q, 256, method, generator=gen), q))
        self.assertTrue(torch.equal(state, gen.get_state()))
        signed = torch.tensor([1, -1], dtype=torch.int64)[:, None] * q
        weights = ((torch.arange(256).reshape(1, -1) % 255) - 127).to(torch.int8)
        self.assertTrue(torch.equal(n.exact_integer_linear(signed, weights), signed.long() @ weights.long().t()))

    def test_shared64_and_independent_tokens(self):
        q = torch.full((64, 130), 129, dtype=torch.int16)
        count = n.sample_counts(q, 64, "iid", generator=self.gen())
        for a, b in ((0, 64), (64, 128), (128, 130)):
            self.assertTrue(torch.equal(count[:, a:b], count[:, a:a+1].expand(-1, b-a)))
        self.assertGreater(torch.unique(count[:, 0]).numel(), 1)
        independent = n.sample_counts(q, 64, "iid", share64=False, generator=self.gen())
        self.assertFalse(torch.equal(independent[:, :64], independent[:, :1].expand(-1, 64)))

    def test_histogram_chunk_and_higher_dim_shape(self):
        q = (torch.arange(2 * 3 * 137).reshape(2, 3, 137) % 256).to(torch.int16)
        for method, T in (("iid", 4096), ("stratified", 16), ("stratified", 128)):
            a = n.sample_counts(q, T, method, generator=self.gen(), chunk_groups=1)
            b = n.sample_counts(q, T, method, generator=self.gen(), chunk_groups=257)
            self.assertTrue(torch.equal(a, b))
            self.assertEqual(a.shape, q.shape)

    def test_iid_joint_moments_monotonicity_and_endpoints(self):
        q = torch.zeros((8192, 64), dtype=torch.int16)
        q[:, 1:32], q[:, 32:] = 64, 128
        actual = n.sample_counts(q, 31, "iid", generator=self.gen()).float()
        self.assertTrue((actual[:, 0] == 0).all())
        self.assertTrue((actual[:, 1] <= actual[:, 32]).all())
        self.assertLess(abs(actual[:, 1].mean().item() - 31/4), .1)
        self.assertLess(abs(actual[:, 32].mean().item() - 31/2), .1)
        cov = ((actual[:, 1] - actual[:, 1].mean()) * (actual[:, 32] - actual[:, 32].mean())).mean()
        self.assertLess(abs(cov.item() - 31 * (.25 - .25*.5)), .25)
        endpoint = n.sample_counts(torch.tensor([[0, 255]], dtype=torch.int16), 4096,
                                   "iid", generator=self.gen())
        self.assertEqual(endpoint[0, 0].item(), 0)
        self.assertLessEqual(endpoint[0, 1].item(), 4096)

    def test_stratified_literal_draws_and_midpoint(self):
        q = torch.arange(256, dtype=torch.int16).reshape(1, 256)
        for T in (16, 32, 64, 128):
            width = 256 // T
            jitter = torch.randint(width, (4, T), generator=self.gen())
            thresholds = jitter + torch.arange(T)[None, :] * width
            expected = (thresholds[:, None, :] < q.reshape(4, 64)[:, :, None]).sum(-1).reshape(1, 256)
            actual = n.sample_counts(q, T, "stratified", generator=self.gen())
            self.assertTrue(torch.equal(actual, expected.to(torch.int16)))
            midpoint = n.sample_counts(q, T, "midpoint")
            mid_threshold = torch.arange(T) * width + width//2
            mid_expected = (mid_threshold[None, :] < q.reshape(-1, 1)).sum(-1).reshape(1, 256)
            self.assertTrue(torch.equal(midpoint, mid_expected.to(torch.int16)))

    def test_strata_error_bound_and_unbiased_mean(self):
        q = torch.arange(256, dtype=torch.int16).repeat(512, 1)
        for T in (16, 32, 64, 128):
            count = n.sample_counts(q, T, "stratified", generator=self.gen(T))
            expected = q.float() * T / 256
            self.assertTrue(((count.float() - expected).abs() < 1).all())
            self.assertLess((count.float().mean(0) - expected[0]).abs().max().item(), .09)

    def test_integer_linear_signed_overflow_and_validation(self):
        inp = torch.tensor([[-4096, -129, -128, -1, 0, 1, 127, 128, 4096]], dtype=torch.int16)
        w = torch.tensor([[-127, -2, 3, 5, 7, -9, 13, 17, 127]], dtype=torch.int8)
        self.assertTrue(torch.equal(n.exact_integer_linear(inp, w), inp.long() @ w.long().t()))
        large = n.exact_integer_linear(torch.full((1, 11008), 4096, dtype=torch.int16),
                                       torch.full((1, 11008), 127, dtype=torch.int8))
        self.assertEqual(large.item(), 11008 * 4096 * 127)
        with self.assertRaises(ValueError):
            n.exact_integer_linear(torch.tensor([[-32768]], dtype=torch.int16), torch.tensor([[1]], dtype=torch.int8))

    def test_tensor_q10_matches_original_and_clipping_stats(self):
        gen = self.gen()
        gi = torch.randint(-32768, 32768, (4096,), generator=gen)
        ui = torch.randint(-32768, 32768, (4096,), generator=gen)
        gi[:8] = torch.tensor([-32768, 32767, 8192, -8192, 4096, 4096, 4096, 4096])
        ui[:8] = torch.tensor([32767, -32768, 1024, 1024, 8192, 24576, -8192, -24576])
        for width in (16, 24, 32):
            actual, stats = n.q10_swiglu(gi.float()/1024, ui.float()/1024, True, width)
            expected = torch.tensor([golden.evaluate(g, u, width)[0] for g, u in zip(gi.tolist(), ui.tolist())])
            self.assertTrue(torch.equal(actual, expected.float()/1024))
            self.assertEqual(stats["g_input_clipped"].item(), 0)
        _, stats = n.q10_swiglu(torch.tensor([-40., 32., 0.]), torch.tensor([32., -40., 0.]), True)
        self.assertEqual(stats["g_input_clipped"].item(), 2)
        self.assertEqual(stats["u_input_clipped"].item(), 2)

    @unittest.skipIf(torch is None or not torch.cuda.is_available(), "CUDA unavailable")
    def test_cuda_integer_exact_and_q10(self):
        gen = self.gen()
        x = torch.randint(-4096, 4097, (19, 173), generator=gen, dtype=torch.int16)
        w = torch.randint(-127, 128, (37, 173), generator=gen, dtype=torch.int8)
        expected = n.exact_integer_linear(x, w)
        actual = n.exact_integer_linear(x.cuda(), w.cuda()).cpu()
        self.assertTrue(torch.equal(actual, expected))
        large = n.exact_integer_linear(torch.full((1, 11008), 4096, dtype=torch.int16, device="cuda"),
                                       torch.full((1, 11008), 127, dtype=torch.int8, device="cuda"))
        self.assertEqual(large.item(), 11008 * 4096 * 127)
        g, u = x.float()/1024, x.flip(0).float()/1024
        self.assertTrue(torch.equal(n.q10_swiglu(g.cuda(), u.cuda()).cpu(), n.q10_swiglu(g, u)))
        q = torch.arange(256, dtype=torch.int16, device="cuda").repeat(3, 1)
        a = n.sample_counts(q, 64, "stratified", generator=self.gen(device="cuda"), chunk_groups=1)
        b = n.sample_counts(q, 64, "stratified", generator=self.gen(device="cuda"), chunk_groups=256)
        self.assertTrue(torch.equal(a, b))


if __name__ == "__main__":
    unittest.main()
