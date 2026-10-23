"""CPU-only preparation contract tests; no claim of real-model execution."""
import ast
import json
from pathlib import Path
import unittest

HERE = Path(__file__).parent
OLD = HERE.parent / 'stochastic'


class ContractTests(unittest.TestCase):
    def test_exact_model(self):
        config = json.loads((HERE / 'baseline/config.json').read_bytes())
        self.assertEqual(len(config['models']), 1)
        self.assertEqual(config['models'][0]['id'], 'Qwen/Qwen3-4B')
        self.assertEqual(config['models'][0]['revision'], '1cfa9a7208912126459214e8b04321603b3df60c')
        self.assertEqual(config['endpoint'], 'https://hf-mirror.com')

    def test_same_scoring_algorithm(self):
        for name in ['evaluate.py', 'support.py', 'test_baseline.py']:
            self.assertEqual((HERE / 'baseline' / name).read_bytes(), (HERE.parent / 'baselines' / name).read_bytes())

    def test_same_architecture_parameters(self):
        old = json.loads((OLD / 'config.json').read_bytes())
        new = json.loads((HERE / 'config.json').read_bytes())
        for key in ['context', 'decode', 'examples', 'batch', 'stride', 'seeds', 'ffn', 'attention', 'calibration', 'protocol']:
            self.assertEqual(new[key], old[key], key)
        self.assertFalse(new['full_corpus_candidate_submitted'])
        self.assertFalse(new['chat_template_used_for_ppl'])
        self.assertFalse(new['thinking_generation'])

    def test_same_case_matrix(self):
        def case_loop(path):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            return [ast.dump(n) for n in ast.walk(tree) if isinstance(n, ast.For)
                    and isinstance(n.target, ast.Tuple) and ast.unparse(n.target) == '(label, mode, sampler, samples)']
        a, b = case_loop(OLD / 'run.py'), case_loop(HERE / 'run.py')
        self.assertEqual(len(a), 1)
        self.assertEqual(a, b)

    def test_no_base_calibration_or_token_inheritance(self):
        source = (HERE / 'run.py').read_text(encoding='utf-8')
        self.assertNotIn("config['expected_test_token_sha256']", source)
        self.assertIn("prepared['test_token_ids_sha256_le_int64']", source)
        self.assertIn("anchor['nll_sum'] == original_anchor['nll_sum']", source)
        self.assertIn("calibration = calibrate(model, tokenize('wiki.train.raw')", source)


if __name__ == '__main__':
    unittest.main()
