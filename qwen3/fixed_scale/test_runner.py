import unittest
import torch
from torch.nn import functional as F
from transformers import Qwen3Config, Qwen3ForCausalLM
from .run import score, configure
from .static_core import StaticFFN


class PilotTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(15)
        config = Qwen3Config(vocab_size=128, hidden_size=64, intermediate_size=128,
            num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
            head_dim=32, tie_word_embeddings=True)
        config._attn_implementation = 'sdpa'
        self.model = Qwen3ForCausalLM(config).eval()
        self.ids = torch.randint(128, (80,))

    def test_suffix_matches_independent_prefix_score(self):
        result = score(self.model, self.ids, dict(context=16, decode=4, examples=2))
        total = 0.
        with torch.no_grad():
            for start in [0, 60]:
                for target in range(16, 20):
                    logits = self.model(input_ids=self.ids[start:start + target].unsqueeze(0)).logits[:, -1]
                    total += F.cross_entropy(logits, self.ids[start + target].reshape(1)).item()
        self.assertAlmostEqual(total, result['nll_sum'], places=4)
        self.assertEqual(result['all_layer_calls'], [2, 2])
        self.assertEqual(result['all_layer_input_tokens'], [38, 38])
        self.assertEqual(result['scored_tokens'], 8)

    def test_case_reset_replays_and_freezes_tables(self):
        tables = {}
        for i, layer in enumerate(self.model.model.layers):
            layer.mlp = StaticFFN(layer.mlp).eval()
            tables[str(i)] = dict(x=[[8., 2., .5, .125]], z=[[8., 2., .5, .125]] * 2)
        config = dict(context=16, decode=4, examples=2)
        configure(self.model, 'sampled', 32, 2, tables, True, True)
        first = score(self.model, self.ids, config)
        configure(self.model, 'sampled', 64, 0)
        score(self.model, self.ids, config)
        configure(self.model, 'sampled', 32, 2, tables, True, True)
        again = score(self.model, self.ids, config)
        self.assertEqual(first['nll_sum'], again['nll_sum'])
        for layer in self.model.model.layers:
            self.assertEqual(layer.mlp.diagnostics()['online_absmax_signals'], [])
            self.assertEqual(layer.mlp.calls, 2)


if __name__ == '__main__':
    unittest.main()
