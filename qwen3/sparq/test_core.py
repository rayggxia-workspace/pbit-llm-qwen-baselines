"""CPU numerical contracts plus executable, pinned Graphcore-source oracle.

Run: python -m unittest qwen3.sparq.test_core -v
No network or Transformers import is needed. AST selection removes only model
adapters/import dependencies; the selected official algorithm bodies are intact.
"""
import ast
from dataclasses import dataclass
from functools import partial
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Optional, Tuple, Union, cast
import unittest

import torch
from torch import Tensor, nn

from .core import SparQConfig, sparq_attention


EXPECTED_SOURCE_HASHES = {
    "llminference/methods/ann_attention.py": "2b07afe06ff1dd6627f1a255be585c82a632f7bbdb7bf606f4ff2f8b260b6b74",
    "llminference/methods/sparse_attention.py": "dc24fa18ca67b58dc0b28e8a18deb4728c7d7fdac020a61dd1238d24b5c0e4b1",
    "LICENSE": "8508742df2cfdf7f65d279a8456358d84a5c4269e1b376de87104fdee021beda",
}


def official_oracle():
    """Execute original MIT source nodes, not a rewritten reference function."""
    manifest = json.loads(Path(__file__).with_name("SOURCES.json").read_text(encoding="utf-8"))
    assert manifest["official_commit"] == "554ea6db219405becbdc0a126984a19f181bdc69"
    files = {}
    for item in manifest["files"]:
        payload = item["utf8"].encode("utf-8")
        assert hashlib.sha256(payload).hexdigest() == item["sha256"] == EXPECTED_SOURCE_HASHES[item["path"]]
        assert len(payload) == item["bytes"]
        assert hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest() == item["git_blob_sha1"]
        files[item["path"]] = item["utf8"]

    def extract(path, names, namespace):
        tree = ast.parse(files[path], filename=path)
        selected = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
                selected.append(node)
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
                selected.append(node)
        assert len(selected) == len(names), (path, names)
        exec(compile(ast.Module(body=selected, type_ignores=[]), path, "exec"), namespace)

    sparse = dict(torch=torch, Tensor=Tensor)
    extract("llminference/methods/sparse_attention.py", {"score_to_mask", "causal_index"}, sparse)
    ann = dict(torch=torch, Tensor=Tensor, nn=nn, dataclass=dataclass, partial=partial,
               Any=Any, List=List, Optional=Optional, Tuple=Tuple, Union=Union, cast=cast,
               sparse_attention=SimpleNamespace(**sparse))
    extract("llminference/methods/ann_attention.py",
            {"gather", "LowRank", "SparseQ", "ScoreSettings", "Settings", "AnnAttention"}, ann)
    return SimpleNamespace(**ann)


def dense_reference(q, k, v, valid=None):
    # Independent PyTorch SDPA path, not core's own dense implementation.
    g = q.shape[1] // k.shape[1]
    dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    k, v = k.to(dtype), v.to(dtype)
    if valid is not None:
        k = k.masked_fill(~valid[:, None, :, None], 0)
        v = v.masked_fill(~valid[:, None, :, None], 0)
    mask = None if valid is None else valid[:, None, None, :]
    return torch.nn.functional.scaled_dot_product_attention(
        q.to(dtype), k.repeat_interleave(g, 1), v.repeat_interleave(g, 1),
        attn_mask=mask, dropout_p=0).to(q.dtype)


def fixture(seed=17, b=2, hkv=2, g=4, n=17, d=8, dtype=torch.float32):
    rng = torch.Generator().manual_seed(seed)
    return tuple(torch.randn(shape, generator=rng, dtype=dtype) for shape in
                 [(b, hkv*g, 1, d), (b, hkv, n, d), (b, hkv, n, d)])


class SparQCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.official = official_oracle()

    def test_official_tag_source_oracle_output_and_indices(self):
        """4 seeds x MHA/GQA x mean enabled/disabled, with masked left padding."""
        for seed in range(4):
            for g in (1, 4):
                for mean in (False, True):
                    with self.subTest(seed=seed, g=g, mean=mean):
                        q, k, v = fixture(seed=seed, g=g)
                        valid = torch.ones(2, 17, dtype=torch.bool)
                        valid[0, :3] = False
                        logmask = torch.zeros(2, 2*g, 1, 17).masked_fill(~valid[:, None, None, :], -torch.inf)
                        oracle = self.official.AnnAttention(self.official.Settings(
                            k=5, local_k=1, reallocate_to_mean_value=mean, score="sparse_q", rank=3), 2, 8)
                        oracle.debug_indices = []
                        expected, _ = oracle(q, k, v, logmask)
                        actual, diag = sparq_attention(q, k, v, valid_mask=valid, return_diagnostics=True,
                            config=SparQConfig(r=3, k_total=6, local_total=2, reallocation=mean, selection="raw_score_sum"))
                        torch.testing.assert_close(actual, expected, rtol=2e-5, atol=3e-6)
                        original_ids = oracle.debug_indices[0].squeeze(2).squeeze(2)
                        torch.testing.assert_close(diag["candidate_ids"].sort(-1).values, original_ids.sort(-1).values)

    def test_paper_probability_route_uses_official_projection(self):
        """Reuse official SparseQ projection; only paper's documented reduction changes."""
        for seed in range(6):
            q, k, v = fixture(seed=seed, dtype=torch.float32)
            projection = self.official.SparseQ(self.official.SparseQ.Settings(rank=3))
            approx = projection(q.unflatten(1, (2, 4)), k.unsqueeze(2)).squeeze(-2)
            probabilities = approx.softmax(-1)
            group_score = probabilities.sum(2)
            group_score[:, :, -2:] = torch.inf
            selected = group_score.topk(6, -1).indices
            ki = selected[:, :, :, None].expand(2, 2, 6, 8)
            expected = dense_reference(q, k.gather(2, ki), v.gather(2, ki))
            actual, diag = sparq_attention(q, k, v, config=SparQConfig(r=3, k_total=6, local_total=2), return_diagnostics=True)
            torch.testing.assert_close(actual, expected, rtol=2e-5, atol=3e-6)
            torch.testing.assert_close(diag["candidate_ids"].sort(-1).values, selected.sort(-1).values)

    def test_probability_sum_is_not_raw_score_sum(self):
        q = torch.tensor([[[[math.sqrt(2), 0]], [[0, math.sqrt(2)]]]])
        k = torch.tensor([[[[10., 0], [9, 9], [0, 10]]]])
        v = k.clone()
        _, paper = sparq_attention(q, k, v, config=SparQConfig(r=2, k_total=1, local_total=0), return_diagnostics=True)
        _, tag = sparq_attention(q, k, v, config=SparQConfig(r=2, k_total=1, local_total=0, selection="raw_score_sum"), return_diagnostics=True)
        self.assertIn(paper["candidate_ids"].item(), (0, 2))
        self.assertEqual(tag["candidate_ids"].item(), 1)

    def test_local_force_survives_group_probability_greater_than_one(self):
        q = torch.ones(1, 4, 1, 2)
        k = torch.tensor([[[[100., 100], [90, 90], [80, 80], [-20, -20], [-30, -30]]]])
        _, diag = sparq_attention(q, k, k, config=SparQConfig(r=2, k_total=3, local_total=2), return_diagnostics=True)
        self.assertEqual(set(diag["candidate_ids"].flatten().tolist()), {0, 3, 4})

    def test_local_window_counts_visible_rows_not_padding(self):
        q, k, v = fixture(b=1, n=12)
        valid = torch.tensor([[False, True, True, False, True, True, True, True, True, False, True, False]])
        _, diag = sparq_attention(q, k, v, valid_mask=valid, config=SparQConfig(r=3, k_total=4, local_total=2), return_diagnostics=True)
        for candidates in diag["candidate_ids"][0]:
            ids = set(candidates.tolist())
            self.assertTrue({8, 10}.issubset(ids))
            self.assertTrue(all(valid[0, i] for i in ids))

    def test_full_budget_dense_matches_sdpa(self):
        for dtype in (torch.float32, torch.float64, torch.bfloat16):
            q, k, v = fixture(n=6, dtype=dtype)
            actual, diag = sparq_attention(q, k, v, config=SparQConfig(r=3, k_total=6, local_total=2), return_diagnostics=True)
            torch.testing.assert_close(actual, dense_reference(q, k, v), rtol=3e-5 if dtype != torch.bfloat16 else .01, atol=1e-6 if dtype != torch.bfloat16 else .008)
            self.assertTrue(diag["all_groups_full_budget"])
            self.assertTrue((diag["candidate_ids"] == -1).all())
            self.assertEqual(diag["logical_counts"]["routing_key_elements"].item(), 0)

    def test_mixed_padding_budget_fallback_and_masked_nonfinite(self):
        q, k, v = fixture(n=17)
        valid = torch.ones(2, 17, dtype=torch.bool)
        valid[0, :13] = False
        k[0, :, :13] = torch.nan
        v[0, :, :13] = torch.inf
        actual, diag = sparq_attention(q, k, v, valid_mask=valid, config=SparQConfig(r=3, k_total=6, local_total=2), return_diagnostics=True)
        expected = dense_reference(q, k, v, valid)
        torch.testing.assert_close(actual[0], expected[0], rtol=3e-5, atol=2e-6)
        torch.testing.assert_close(diag["group_fallback_reason"], torch.tensor([[1, 1], [0, 0]]))
        self.assertTrue(torch.isfinite(actual).all())
        self.assertTrue((diag["candidate_ids"][1] >= 0).all())

    def test_zero_selected_l1_falls_back_entire_group(self):
        q = torch.tensor([[[[10., 0]], [[0, 1]], [[2., 0]], [[1., 0]]]])
        _, k, v = fixture(b=1, hkv=2, g=2, n=7, d=2)
        actual, diag = sparq_attention(q, k, v, config=SparQConfig(r=1, k_total=2, local_total=1), return_diagnostics=True)
        torch.testing.assert_close(actual[:, :2], dense_reference(q, k, v)[:, :2], rtol=3e-5, atol=2e-6)
        torch.testing.assert_close(diag["group_fallback_reason"], torch.tensor([[2, 0]]))
        self.assertEqual(diag["logical_counts"]["zero_coverage_groups"].item(), 1)

    def test_zero_query_is_uniform_dense(self):
        q, k, v = fixture(b=1)
        q.zero_()
        actual, diag = sparq_attention(q, k, v, config=SparQConfig(r=3, k_total=4, local_total=1), return_diagnostics=True)
        expected = v.mean(2, keepdim=True).repeat_interleave(4, 1)
        torch.testing.assert_close(actual, expected)
        self.assertTrue((diag["group_fallback_reason"] == 2).all())

    def test_full_rank_still_sparse_if_budget_is_smaller(self):
        q, k, v = fixture()
        _, diag = sparq_attention(q, k, v, config=SparQConfig(r=8, k_total=4, local_total=1), return_diagnostics=True)
        self.assertTrue((diag["group_fallback_reason"] == 0).all())
        self.assertTrue((diag["selected_counts"] == 4).all())
        torch.testing.assert_close(diag["temperature"], torch.full_like(diag["temperature"], math.sqrt(8)))

    def test_cost_counts_are_group_shared_but_macs_are_per_query(self):
        q, k, v = fixture()
        _, diag = sparq_attention(q, k, v, config=SparQConfig(r=3, k_total=6, local_total=2), return_diagnostics=True)
        counts = diag["logical_counts"]
        expected = {"query_groups": 4, "routing_key_elements": 4*17*3,
                    "selected_key_elements": 4*6*8, "selected_value_elements": 4*6*8,
                    "routing_qk_macs": 4*17*4*3, "selected_qk_macs": 4*6*4*8,
                    "selected_pv_macs": 4*6*4*8, "approx_softmax_elements": 4*17*4,
                    "exact_softmax_elements": 4*6*4, "mean_value_elements": 0,
                    "validation_kv_elements": 2*4*17*8}
        for name, value in expected.items():
            self.assertEqual(counts[name].item(), value, name)
        self.assertTrue(all(isinstance(x, Tensor) and x.ndim == 0 and x.dtype == torch.int64 for x in counts.values()))

    def test_input_contract_errors(self):
        q, k, v = fixture()
        cfg = SparQConfig(r=3, k_total=6, local_total=2)
        for call in (
            lambda: sparq_attention(q.expand(-1, -1, 2, -1), k, v, config=cfg),
            lambda: sparq_attention(q[:, :7], k, v, config=cfg),
            lambda: sparq_attention(q, k, v, config=SparQConfig(r=9)),
            lambda: sparq_attention(q, k, v.double(), config=cfg),
            lambda: sparq_attention(q, k, v, valid_mask=torch.zeros(2, 17, dtype=torch.bool), config=cfg),
            lambda: sparq_attention(q, k, v, valid_mask=torch.ones(2, 17), config=cfg),
            lambda: SparQConfig(r=0), lambda: SparQConfig(k_total=1, local_total=2),
            lambda: SparQConfig(r=True), lambda: SparQConfig(selection="max4"),
            lambda: SparQConfig(reallocation="false"),
            lambda: SparQConfig(validate_finite=1),
        ):
            with self.assertRaises(ValueError):
                call()
        for pos in range(3):
            args = [x.clone() for x in (q, k, v)]
            args[pos].flatten()[0] = torch.nan
            with self.assertRaises(ValueError):
                sparq_attention(*args, config=cfg)

    def test_visible_arithmetic_overflow_rejected(self):
        q, k, v = fixture()
        q.fill_(1e38)
        k.fill_(1e38)
        with self.assertRaisesRegex(ValueError, "arithmetic"):
            sparq_attention(q, k, v, config=SparQConfig(r=3, k_total=6, local_total=2))

    def test_subnormal_l1_ratio_not_clamped_to_normal_range(self):
        q = torch.tensor([[[[1e-40, 0.]]]])
        k = torch.zeros(1, 1, 3, 2)
        _, diag = sparq_attention(q, k, k, config=SparQConfig(r=1, k_total=1, local_total=1), return_diagnostics=True)
        torch.testing.assert_close(diag["temperature"], torch.tensor([[[[math.sqrt(2)]]]]))

    def test_bfloat16_sparse_dtype_and_determinism(self):
        q, k, v = fixture(dtype=torch.bfloat16)
        cfg = SparQConfig(r=3, k_total=6, local_total=2)
        first, diag = sparq_attention(q, k, v, config=cfg, return_diagnostics=True)
        second = sparq_attention(q, k, v, config=cfg)
        self.assertEqual(first.dtype, torch.bfloat16)
        torch.testing.assert_close(first, second, rtol=0, atol=0)
        self.assertEqual(diag["compute_dtype"], "torch.float32")


if __name__ == "__main__":
    unittest.main()
