"""Stage-boundary tests for the actual PPL FFN wrapper, including CUDA if present."""
import unittest
try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'PyTorch is unavailable locally; execute via Slurm')
class PipelineTest(unittest.TestCase):
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
