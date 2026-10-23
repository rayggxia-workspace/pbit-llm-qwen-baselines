"""Exact arithmetic illustrations; no model, sampling simulation, or theorem checker."""
from fractions import Fraction
import json


def show(value):
    return {"exact": str(value), "decimal": float(value)}


def examples():
    heads, teams, budget = 4, 64, 8
    independent_union = teams * (1 - (1 - Fraction(budget, teams)) ** heads)
    shared_union = Fraction(budget)
    p = Fraction(1, 2)
    return {
        "scope": "Exact analytic examples only; not Qwen measurements or proof by testing",
        "identical_uniform_heads": {
            "heads": heads, "teams": teams, "per_head_budget": budget,
            "independent_expected_union": show(independent_union),
            "shared_expected_union": show(shared_union),
        },
        "output_covariance_counterexample": {
            "heads": 4, "teams": 2, "per_head_budget": 1,
            "team_outputs": [0, 1], "projection": "mean of four head outputs",
            "independent_expected_union": show(2 * (1 - (1-p) ** 4)),
            "shared_expected_union": show(Fraction(1)),
            "both_output_means": show(p),
            "independent_projection_variance": show(p * (1-p) / 4),
            "shared_projection_variance": show(p * (1-p)),
        },
    }


if __name__ == '__main__':
    print(json.dumps(examples(), ensure_ascii=False, indent=2))
