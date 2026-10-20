"""Run all frozen upstream tests with package aliases, without modifying them."""
import importlib
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
PACKAGE = 'experiments.qwen_joint_stratified_attention_20261019.upstream_attention'
ALIAS = 'experiments.attention_joint_ising'
sys.modules[ALIAS] = importlib.import_module(PACKAGE)
for name in ('ctmc', 'scoring', 'attention', 'evaluate'):
    sys.modules[ALIAS + '.' + name] = importlib.import_module(PACKAGE + '.' + name)


def load_tests(loader, tests, pattern):
    import torch  # A missing Torch must fail, never silently skip model tests.
    suite = unittest.TestSuite()
    for name in ('test_ctmc', 'test_scoring', 'test_attention'):
        suite.addTests(loader.loadTestsFromModule(importlib.import_module(PACKAGE + '.' + name)))
    if suite.countTestCases() != 38:
        raise AssertionError('expected all 38 frozen upstream regression tests')
    return suite


if __name__ == '__main__':
    unittest.main()
