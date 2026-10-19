"""Stage-boundary tests for the actual PPL FFN wrapper, including CUDA if present."""
import unittest
try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'PyTorch is unavailable locally; execute via Slurm')
class PipelineTest(unittest.TestCase):
    @unittest.skipUnless(torch is not None and torch.cuda.is_available(), 'CUDA is required')
    def test_cuda_iid_under_actual_deterministic_flags(self):
        from experiments.llama2_ffn_precision.numeric import sample_counts
        torch.use_deterministic_algorithms(True)
        q = torch.zeros(8192, 64, device='cuda', dtype=torch.int16)
        q[:, 1:32], q[:, 32:] = 64, 128
        def gen():
            return torch.Generator(device='cuda').manual_seed(19)
        a = sample_counts(q, 4096, 'iid', generator=gen(), chunk_groups=1)
        b = sample_counts(q, 4096, 'iid', generator=gen(), chunk_groups=8192)
        self.assertTrue(torch.equal(a, b))
        self.assertTrue((a[:, 0] == 0).all())
        self.assertTrue((a[:, 1] <= a[:, 32]).all())
        self.assertTrue(torch.equal(a[:, 1:32], a[:, 1:2].expand(-1, 31)))
        self.assertLess(abs(a[:, 1].float().mean().item() - 1024), 2.)
        self.assertLess(abs(a[:, 32].float().mean().item() - 2048), 2.)

    @unittest.skipUnless(torch is not None and torch.cuda.is_available(), 'CUDA is required by the actual wrapper')
    def test_enumeration_matches_deterministic_whole_ffn(self):
        from experiments.llama2_ffn_precision.run import make_mlp_class
        from types import SimpleNamespace
        torch.manual_seed(11)
        torch.backends.cuda.matmul.allow_tf32 = False
        original = SimpleNamespace(
            gate_proj=torch.nn.Linear(64, 64, bias=False, device='cuda', dtype=torch.bfloat16),
            up_proj=torch.nn.Linear(64, 64, bias=False, device='cuda', dtype=torch.bfloat16),
            down_proj=torch.nn.Linear(64, 64, bias=False, device='cuda', dtype=torch.bfloat16))
        cls = make_mlp_class(torch)
        scales = {'sx': [8.], 'sz': [16.]}
        x = torch.randn(1, 16, 64, device='cuda', dtype=torch.bfloat16)
        for post in ('exact', 'q10'):
            det = cls(original, scales, {'seed': 0, 'mode': 'deterministic', 'post': post}, 0)
            enum = cls(original, scales, {'seed': 0, 'mode': 'counts', 'post': post,
                                          'method': 'enumerate256', 'T': 256}, 0)
            with torch.inference_mode():
                a, b = det(x), enum(x)
            self.assertTrue(torch.equal(a, b), post)
            self.assertEqual(a.dtype, torch.bfloat16)
            self.assertEqual(list(a.shape), list(x.shape))
            self.assertTrue(torch.isfinite(a).all())


if __name__ == '__main__':
    unittest.main()
