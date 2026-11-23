"""Small exact-enumeration checks; no model, dataset, GPU, or PPA is used."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path


def norm2(v):
    return sum(x * x for x in v)


def close(a, b, tol=2e-10):
    assert abs(a - b) <= tol * max(1.0, abs(a), abs(b)), (a, b)


def optimal_inclusion(magnitudes, costs, budget):
    """Independent HT masks, minimum trace covariance at expected read cost."""
    assert 0 < budget < sum(costs)
    score = [a / math.sqrt(c) for a, c in zip(magnitudes, costs)]
    low, high = 0.0, max(score) * sum(costs) / budget + 1.0
    for _ in range(120):
        tau = (low + high) / 2
        total = sum(c * min(1.0, s / tau) for c, s in zip(costs, score))
        if total > budget:
            low = tau
        else:
            high = tau
    return [min(1.0, s / high) for s in score]


def enumerate_masks(vectors, probs):
    target = [sum(v[j] for v in vectors) for j in range(len(vectors[0]))]
    mean = [0.0] * len(target)
    mse = total_prob = reads = 0.0
    for mask in itertools.product((0, 1), repeat=len(vectors)):
        p = math.prod(q if m else 1 - q for m, q in zip(mask, probs))
        y = [sum(m * v[j] / q for m, v, q in zip(mask, vectors, probs))
             for j in range(len(target))]
        total_prob += p
        reads += p * sum(mask)
        for j in range(len(target)):
            mean[j] += p * y[j]
        mse += p * norm2([a - b for a, b in zip(y, target)])
    close(total_prob, 1)
    for a, b in zip(mean, target):
        close(a, b)
    analytic = sum((1 / q - 1) * norm2(v) for v, q in zip(vectors, probs))
    close(mse, analytic)
    close(reads, sum(probs))
    return {"expected_rows": reads, "mse": mse, "analytic_mse": analytic}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    counts = [1, 2, 3, 5, 8, 13, 21, 34]
    rows = [[16, 0], [0, 1], [1, 0], [1, 1], [-1, 2], [1, -1], [0, 1], [-1, 0]]
    vectors = [[c * w for w in row] for c, row in zip(counts, rows)]
    magnitudes = [math.sqrt(norm2(v)) for v in vectors]
    budget = 6.0
    q_amp = optimal_inclusion(counts, [1] * len(counts), budget)
    q_norm = optimal_inclusion(magnitudes, [1] * len(counts), budget)
    methods = {
        'constant_075': enumerate_masks(vectors, [0.75] * len(counts)),
        'amplitude_capped': enumerate_masks(vectors, q_amp),
        'contribution_capped': enumerate_masks(vectors, q_norm),
    }
    assert methods['contribution_capped']['mse'] <= methods['amplitude_capped']['mse'] + 1e-9
    assert methods['contribution_capped']['mse'] <= methods['constant_075']['mse'] + 1e-9
    # Cost-weighted KKT stationarity, including saturated coordinates.
    costs = [1, 2, 1, 3, 1, 2, 1, 2]
    q_cost = optimal_inclusion(magnitudes, costs, sum(costs) * 0.7)
    ratios = [a * a / (q * q * c) for a, q, c in zip(magnitudes, q_cost, costs) if q < 1 - 1e-12]
    for r in ratios:
        close(r, ratios[0])
    close(sum(q * c for q, c in zip(q_cost, costs)), sum(costs) * 0.7)
    # Exact integer comparison: U is uniform 0..K-1; no probability LUT.
    integer_cases = 0
    for k in range(1, 9):
        threshold = 1 << k
        for count in range(threshold + 1):
            values = [threshold if u < count else 0 for u in range(threshold)]
            close(sum(values) / threshold, count)
            close(sum((v - count) ** 2 for v in values) / threshold,
                  count * (threshold - count))
            integer_cases += 1
    # Original counts may be correlated: conditional zero-mean outer error
    # still yields a decomposition into original MSE plus added variance.
    states = [(0.5, [[0.0, 0.0], [0.0, 0.0]]),
              (0.5, [[1.0, 2.0], [-0.5, 0.25]])]
    target = [0.25, 1.125]
    base_mse = added = total_mse = 0.0
    for state_p, vv in states:
        qq = [0.5, 0.5]
        zz = [sum(v[j] for v in vv) for j in range(2)]
        base_mse += state_p * norm2([a - b for a, b in zip(zz, target)])
        added += state_p * sum((1 / q - 1) * norm2(v) for q, v in zip(qq, vv))
        for mask in itertools.product((0, 1), repeat=2):
            yy = [sum(m * v[j] / q for m, v, q in zip(mask, vv, qq)) for j in range(2)]
            total_mse += state_p * 0.25 * norm2([a - b for a, b in zip(yy, target)])
    close(total_mse, base_mse + added)
    # Unbiased (g,u) does not imply unbiased SiLU(g)*u.
    vv = [[1.0, 2.0], [-0.7, 0.5]]
    g, u = [sum(v[j] for v in vv) for j in range(2)]
    silu = lambda x: x / (1 + math.exp(-x))
    nonlinear_reference = silu(g) * u
    nonlinear_mean = sum(0.25 * silu(sum(m * v[0] * 2 for m, v in zip(mask, vv)))
                         * sum(m * v[1] * 2 for m, v in zip(mask, vv))
                         for mask in itertools.product((0, 1), repeat=2))
    assert abs(nonlinear_mean - nonlinear_reference) > 1e-3
    result = {
        'status': 'passed',
        'scope': 'synthetic exact-enumeration and algebra checks only; no LLM/PPL/PPA',
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'toy_dimensions': {'input_rows': 8, 'output_dimensions': 2, 'expected_rows': budget},
        'independent_mask_mse': methods,
        'cost_weighted_kkt': 'passed',
        'power_of_two_integer_rounding_cases': integer_cases,
        'conditional_original_mse': base_mse,
        'conditional_added_mse': added,
        'conditional_total_mse': total_mse,
        'nonlinear_reference': nonlinear_reference,
        'nonlinear_sample_mean': nonlinear_mean,
    }
    text = json.dumps(result, ensure_ascii=True, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(text.encode('utf-8'))
    print(text, end='')


if __name__ == '__main__':
    main()
