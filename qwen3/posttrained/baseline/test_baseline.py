import argparse
import tempfile
import unittest
from pathlib import Path

from support import windows


class CoverageTests(unittest.TestCase):
    def test_exact_coverage(self):
        for length in (2, 3, 1024, 2047, 2048, 2049, 3072, 3073, 10001):
            for stride in (1, 512, 1024, 2047):
                positions = [p for _, end, first in windows(length, 2048, stride) for p in range(first, end)]
                self.assertEqual(positions, list(range(1, length)))

    def test_invalid(self):
        for values in ((1, 2048, 1024), (10, 8, 8), (10, 8, 0)):
            with self.assertRaises(ValueError):
                list(windows(*values))


def model_preflight(project):
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, Qwen3Config
    assert transformers.__version__ == "4.51.3"
    torch.manual_seed(0)
    # Like 4B, the attention inner width differs from hidden_size; GQA and QK-Norm stay native.
    config = Qwen3Config(vocab_size=97, hidden_size=32, intermediate_size=64,
                        num_hidden_layers=2, num_attention_heads=4,
                        num_key_value_heads=2, head_dim=16, tie_word_embeddings=True)
    model = AutoModelForCausalLM.from_config(config, attn_implementation="sdpa").eval()
    ids = torch.tensor([[1, 4, 5, 6, 7]])
    with torch.inference_mode():
        output = model(ids).logits
    assert output.shape == (1, 5, 97) and torch.isfinite(output).all()
    assert hasattr(model.model.layers[0].self_attn, "q_norm")
    assert model.model.rotary_emb.inv_freq.dtype == torch.float32
    with tempfile.TemporaryDirectory(prefix="cpu-preflight-", dir=project) as temporary:
        model.save_pretrained(temporary)
        reloaded = AutoModelForCausalLM.from_pretrained(temporary, torch_dtype=torch.float32,
                                                     attn_implementation="sdpa", local_files_only=True).eval()
        for a, b in ((dict(model.named_parameters()), dict(reloaded.named_parameters())),
                     (dict(model.named_buffers()), dict(reloaded.named_buffers()))):
            assert a.keys() == b.keys()
            for key in a:
                assert a[key].dtype == b[key].dtype and torch.equal(a[key], b[key]), key
        with torch.inference_mode():
            torch.testing.assert_close(reloaded(ids).logits, output, rtol=0, atol=0)
    print("CPU_QWEN3_PREFLIGHT_PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CoverageTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.project:
        model_preflight(str(Path(args.project).resolve()))
