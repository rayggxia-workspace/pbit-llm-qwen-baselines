"""32-state-bit / 64-word SNG candidates with exact GF(2) rank certificates.

Area numbers are explicit two-input XOR DAG counts, not synthesis/PPA.
No input data, neural weights or model quality results are used for tuning.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import time

import numpy as np

ROOT = Path(__file__).resolve().parent
MASK32 = 0xFFFFFFFF
GALOIS = 0x80200003
PERIOD = (1 << 32) - 1
FACTORS = (3, 5, 17, 257, 65537)


def rank(rows):
    pivots = {}
    for row in rows:
        value = int(row)
        while value:
            pivot = value.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = value
                break
            value ^= pivots[pivot]
    return len(pivots)


def transition(value):
    return (value >> 1) ^ (GALOIS if value & 1 else 0)


def apply_columns(columns, value):
    out = 0
    while value:
        low = value & -value
        out ^= columns[low.bit_length() - 1]
        value ^= low
    return out


def compose_columns(left, right):
    return [apply_columns(left, value) for value in right]


def transition_power(exponent):
    result = [1 << bit for bit in range(32)]
    base = [transition(1 << bit) for bit in range(32)]
    while exponent:
        if exponent & 1:
            result = compose_columns(base, result)
        base = compose_columns(base, base)
        exponent >>= 1
    return result


def period_certificate():
    full = apply_columns(transition_power(PERIOD), 1)
    shorter = {str(p): apply_columns(transition_power(PERIOD // p), 1) for p in FACTORS}
    assert full == 1 and all(value != 1 for value in shorter.values())
    return {"galois_mask": hex(GALOIS), "period": PERIOD,
            "full_power_seed1": full, "proper_factor_power_seed1": shorter}


def columns_to_rows(columns):
    return [sum(((int(columns[col]) >> row) & 1) << col for col in range(32))
            for row in range(32)]


class XorNetwork:
    """Interned linear expressions; each generated node is exactly one XOR2."""
    def __init__(self):
        self.masks = [0] + [1 << bit for bit in range(32)]
        self.lookup = {mask: i for i, mask in enumerate(self.masks)}
        self.nodes = {}

    def xor(self, a, b):
        mask = self.masks[a] ^ self.masks[b]
        if mask in self.lookup:
            return self.lookup[mask]
        node = len(self.masks)
        self.masks.append(mask)
        self.lookup[mask] = node
        self.nodes[node] = (a, b)
        return node

    def vector_xor(self, a, b):
        return [self.xor(x, y) for x, y in zip(a, b)]

    def fold(self, signals):
        values = list(signals)
        if not values:
            return 0
        while len(values) > 1:
            values = [self.xor(values[i], values[i + 1]) if i + 1 < len(values)
                      else values[i] for i in range(0, len(values), 2)]
        return values[0]

    def vector_fold(self, vectors):
        return [self.fold(v[bit] for v in vectors) for bit in range(len(vectors[0]))]

    def reachable(self, outputs):
        found = set()
        def visit(node):
            if node in found or node not in self.nodes:
                return
            found.add(node)
            for parent in self.nodes[node]:
                visit(parent)
        for output in outputs:
            for node in output:
                visit(node)
        return sorted(found)

    def cost(self, outputs):
        used = self.reachable(outputs)
        depth = {i: 0 for i in range(33)}
        fanout = Counter()
        for node in used:
            a, b = self.nodes[node]
            depth[node] = 1 + max(depth[a], depth[b])
            fanout[a] += 1
            fanout[b] += 1
        for output in outputs:
            fanout.update(output)
        return {"xor2": len(used), "xor_depth": max(depth[node] for out in outputs for node in out),
                "max_logical_fanout": max(fanout.values())}


def gf4_multiply(network, word, coefficient):
    # Every adjacent pair encodes GF(4) using z^2+z+1.
    result = []
    for bit in range(0, len(word), 2):
        low, high = word[bit:bit + 2]
        if coefficient == 0:
            result.extend([0, 0])
        elif coefficient == 1:
            result.extend([low, high])
        elif coefficient == 2:
            result.extend([high, network.xor(low, high)])
        else:
            result.extend([network.xor(low, high), low])
    return result


def gf_multiply(a, b, width=8, polynomial=0x11B):
    value = 0
    while b:
        if b & 1:
            value ^= a
        b >>= 1
        a <<= 1
        if a & (1 << width):
            a ^= polynomial
    return value


def gf_constant(network, word, coefficient, polynomial=0x11B):
    width = len(word)
    masks = [gf_multiply(1 << bit, coefficient, width, polynomial) for bit in range(width)]
    return [network.fold(word[bit] for bit in range(width) if (masks[bit] >> out) & 1)
            for out in range(width)]


def gf4_grid(permutation=None):
    network = XorNetwork()
    permutation = list(range(32)) if permutation is None else list(permutation)
    words = [[permutation[byte * 8 + bit] + 1 for bit in range(8)] for byte in range(4)]
    a, b, c, d = words
    outputs = []
    for i in range(4):
        first = network.vector_xor(a, gf4_multiply(network, b, i))
        for j in range(4):
            second = network.vector_xor(first, gf4_multiply(network, c, j))
            for k in range(4):
                outputs.append(network.vector_xor(second, gf4_multiply(network, d, k)))
    return network, outputs


def gf4_grid_area(permutation=None):
    """Same linear map, exactly 504 XOR2 gates by subset expansion.

    Only eight output functions are input wires for this fixed map; its other
    504 distinct output functions each require a non-input gate output. Hence
    504 is optimal for this fixed input basis/map in the XOR2+wire model.
    """
    network = XorNetwork()
    permutation = list(range(32)) if permutation is None else list(permutation)
    source = [int(bit) + 1 for bit in permutation]
    outputs = [[None] * 8 for _ in range(64)]
    for lane in range(4):
        variables = [source[byte * 8 + 2 * lane + bit] for byte in (1, 2, 3) for bit in (0, 1)]
        for bit in (0, 1):
            subset = [source[2 * lane + bit]]
            for variable in variables:
                subset += [network.xor(value, variable) for value in subset]
            for i in range(4):
                for j in range(4):
                    for k in range(4):
                        coefficients = (i, j, k) if bit == 0 else tuple(
                            ((x >> 1) & 1) | (((x & 1) ^ (x >> 1)) << 1) for x in (i, j, k))
                        index = coefficients[0] | (coefficients[1] << 2) | (coefficients[2] << 4)
                        outputs[16 * i + 4 * j + k][2 * lane + bit] = subset[index]
    assert network.cost(outputs)["xor2"] == 504
    return network, outputs


def gf256_polynomial(degree, points=None):
    network = XorNetwork()
    words = [[byte * 8 + bit + 1 for bit in range(8)] for byte in range(4)]
    if degree == 1:
        # Use all 32 state bits without increasing the number of coefficients.
        coeffs = [network.vector_xor(words[0], words[2]), network.vector_xor(words[1], words[3])]
    elif degree == 2:
        coeffs = [network.vector_xor(words[0], words[3]), words[1], words[2]]
    else:
        coeffs = words
    points = range(64) if points is None else points
    outputs = []
    for x in points:
        power = 1
        terms = []
        for coefficient in coeffs:
            terms.append(gf_constant(network, coefficient, power))
            power = gf_multiply(power, x)
        outputs.append(network.vector_fold(terms))
    return network, outputs


def gf256_quadratic_shared(grouped=False):
    """Share linearized a*B+a^2*C for a in the six-bit point subspace.

    Squaring in characteristic two is linear. Six 8-bit basis vectors replace
    64 separate field evaluations, preserving three-wise word independence.
    """
    network = XorNetwork()
    words = [[byte * 8 + bit + 1 for bit in range(8)] for byte in range(4)]
    a = network.vector_xor(words[0], words[3])
    if grouped:
        basis = [network.vector_xor(gf_constant(network, words[1], 1 << j),
                                   gf_constant(network, words[2], gf_multiply(1 << j, 1 << j)))
                 for j in range(6)]
    else:
        b_powers, c_powers = [words[1]], [words[2]]
        for _ in range(5):
            b_powers.append(gf_constant(network, b_powers[-1], 2))
        for _ in range(10):
            c_powers.append(gf_constant(network, c_powers[-1], 2))
        basis = [network.vector_xor(b_powers[j], c_powers[2*j]) for j in range(6)]
    if grouped:
        outputs = [a]
        for j in range(0, 6, 2):
            additions = [[0] * 8, basis[j], basis[j+1], network.vector_xor(basis[j], basis[j+1])]
            previous = outputs
            outputs = [network.vector_xor(value, increment) for increment in additions for value in previous]
    else:
        outputs = [a]
        for vector in basis:
            outputs += [network.vector_xor(value, vector) for value in outputs]
    return network, outputs


def gf4096_pairwise():
    network = XorNetwork()
    a, b = list(range(1, 13)), list(range(13, 25))
    for bit in range(4):
        a[bit] = network.xor(a[bit], 25 + bit)
        b[bit] = network.xor(b[bit], 29 + bit)
    basis = [b]
    for _ in range(5):
        basis.append(gf_constant(network, basis[-1], 2, 0x1053))
    outputs = [a]
    for vector in basis:
        outputs += [network.vector_xor(value, vector) for value in outputs]
    return network, outputs


def wire_baseline(seed=7401):
    # Baseline is our reproducible random wiring, not a reproduction of Salehi.
    rng = np.random.default_rng(seed)
    network = XorNetwork()
    outputs = [(rng.choice(32, size=8, replace=False) + 1).tolist() for _ in range(64)]
    return network, outputs


def row_masks(network, outputs):
    return [[network.masks[node] for node in out] for out in outputs]


def pair_certificate(masks):
    marginal = Counter(rank(word) for word in masks)
    pairs = Counter(rank(masks[i] + masks[j]) for i, j in combinations(range(64), 2))
    return {"marginal_rank_histogram": dict(sorted(marginal.items())),
            "all_2016_pair_rank_histogram": dict(sorted(pairs.items()))}


def lag_certificate(masks, stride, lags=(1, 2, 4, 8)):
    answer = {}
    for lag in lags:
        columns = transition_power(stride * lag)
        counts = Counter()
        for word in masks:
            future = [sum(((int(mask) & col).bit_count() & 1) << bit
                          for bit, col in enumerate(columns)) for mask in word]
            counts[rank(word + future)] += 1
        answer[str(lag)] = dict(sorted(counts.items()))
    return answer


def cross_port_lag_certificate(masks, stride, lags=(1, 2, 4, 8)):
    answer = {}
    for lag in lags:
        columns = transition_power(stride * lag)
        future = [[sum(((int(mask) & col).bit_count() & 1) << bit
                       for bit, col in enumerate(columns)) for mask in word] for word in masks]
        counts = Counter(rank(left + right) for left in masks for right in future)
        answer[str(lag)] = dict(sorted(counts.items()))
    return answer


def trajectories(seeds, length, stride):
    """Jump-ahead transition evaluated through four 256-entry software tables.

    Tables accelerate software only. RTL uses the derived XOR equations.
    """
    columns = transition_power(stride)
    lookup = np.array([[apply_columns(columns, value << (8 * byte)) for value in range(256)]
                       for byte in range(4)], dtype=np.uint32)
    state = np.array(seeds, dtype=np.uint32)
    result = np.empty((len(seeds), length), dtype=np.uint32)
    for t in range(length):
        result[:, t] = state
        state = (lookup[0, state & 255] ^ lookup[1, (state >> 8) & 255]
                 ^ lookup[2, (state >> 16) & 255] ^ lookup[3, state >> 24])
    return result


def evaluate_network(network, outputs, states):
    values = [np.zeros(states.shape, dtype=np.uint8)]
    values += [((states >> bit) & 1).astype(np.uint8) for bit in range(32)]
    used = set(network.reachable(outputs))
    for node in range(33, len(network.masks)):
        if node in used:
            a, b = network.nodes[node]
            values.append(values[a] ^ values[b])
        else:
            values.append(None)
    result = np.empty(states.shape + (len(outputs),), dtype=np.uint8)
    for port, word in enumerate(outputs):
        value = np.zeros(states.shape, dtype=np.uint8)
        for bit, node in enumerate(word):
            value ^= values[node] << bit
        result[..., port] = value
    return result


GF4_TABLE = np.array([[sum(gf_multiply((x >> bit) & 3, a, 2, 7) << bit
                                for bit in range(0, 8, 2)) for x in range(256)]
                     for a in range(4)], dtype=np.uint8)


def fast_grid(states, permutation):
    words = np.zeros(states.shape + (4,), dtype=np.uint8)
    for byte in range(4):
        for bit in range(8):
            words[..., byte] |= (((states >> int(permutation[byte * 8 + bit])) & 1) << bit).astype(np.uint8)
    a, b, c, d = [words[..., byte] for byte in range(4)]
    output = np.empty(states.shape + (64,), dtype=np.uint8)
    for i in range(4):
        first = a ^ GF4_TABLE[i, b]
        for j in range(4):
            second = first ^ GF4_TABLE[j, c]
            for k in range(4):
                output[..., 16 * i + 4 * j + k] = second ^ GF4_TABLE[k, d]
    return output


def cdf_summary(words, lengths=(256, 512, 1024, 1280, 2048, 4096)):
    answer = {}
    p = np.arange(257) / 256
    for length in lengths:
        offsets = np.arange(words.shape[0] * 64).reshape(words.shape[0], 1, 64) * 256
        counts = np.bincount((words[:, :length].astype(np.int64) + offsets).ravel(),
                             minlength=words.shape[0] * 64 * 256).reshape(words.shape[0], 64, 256)
        cdf = np.concatenate([np.zeros(counts.shape[:-1] + (1,)), counts.cumsum(axis=-1) / length], axis=-1)
        errors = cdf - p
        per_stream = np.max(np.abs(errors), axis=-1)
        answer[str(length)] = {"cdf_mae": float(np.mean(np.abs(errors))),
                               "cdf_rmse": float(np.sqrt(np.mean(errors**2))),
                               "ks_mean": float(per_stream.mean()),
                               "ks_max": float(per_stream.max())}
    return answer


def optimization_score(words):
    # Quantiles emphasize finite-prefix balance. No neural tensors involved.
    score = 0.0
    thresholds = np.array([16, 32, 64, 96, 128, 160, 192, 224, 240])
    expected = thresholds / 256
    for length in (256, 512, 1024):
        means = (words[:, :length, :, None] < thresholds).mean(axis=1)
        error = means - expected
        score += float(np.mean(error**2)) * length
        score += float(np.quantile(np.abs(error), .98)**2) * length * 0.15
    return score


def optimize_grid(train_states, trials=96):
    rng = np.random.default_rng(7413)
    permutation = np.arange(32)
    best = optimization_score(fast_grid(train_states[:, :1024], permutation))
    initial = best
    log = [{"trial": 0, "score": best}]
    for trial in range(1, trials + 1):
        if trial % 8 == 0:
            candidate = rng.permutation(32)
        else:
            candidate = permutation.copy()
            swaps = 1 if trial % 3 else 3
            for _ in range(swaps):
                a, b = rng.choice(32, 2, replace=False)
                candidate[a], candidate[b] = candidate[b], candidate[a]
        value = optimization_score(fast_grid(train_states[:, :1024], candidate))
        if value < best:
            best, permutation = value, candidate
            log.append({"trial": trial, "score": best})
    return permutation, {"trials": trials, "initial_train_score": initial,
                         "final_train_score": best, "improvements": log}


def constrain_temporal(permutation, train_states, stride, trials=128):
    rng = np.random.default_rng(7501)
    best = float("inf")
    chosen = None
    checks = []
    for trial in range(trials + 1):
        candidate = permutation.copy()
        if trial:
            a, b = rng.choice(32, 2, replace=False)
            candidate[a], candidate[b] = candidate[b], candidate[a]
        value = optimization_score(fast_grid(train_states[:, :1024], candidate))
        if value >= best:
            continue
        network, outputs = gf4_grid(candidate)
        certificate = cross_port_lag_certificate(row_masks(network, outputs), stride)
        valid = all(histogram == {16: 4096} for histogram in certificate.values())
        checks.append({"trial": trial, "score": value, "passed": valid})
        if valid:
            best, chosen = value, candidate
    if chosen is None:
        raise RuntimeError("No wiring met the selected finite lag rank constraints")
    return chosen, {"trials": trials, "rank_checks": checks, "train_score": best,
                    "constraints": "all ordered port pairs at word lags 1,2,4,8 have rank16"}


def statistical_summary(words, seed=101):
    rng = np.random.default_rng(seed)
    n = words.shape[1]
    # Every pair, at five common threshold codes; empirical covariance not SCC.
    covariance = []
    for q in (16, 64, 128, 192, 240):
        bits = (words < q).astype(np.float64)
        for values in bits:
            cov = values.T @ values / n - np.outer(values.mean(0), values.mean(0))
            covariance.extend(cov[np.triu_indices(64, 1)].tolist())
    # Random fixed threshold assignments, exact sum across 64 synthetic lanes.
    cases = []
    for _ in range(48):
        codes = rng.integers(1, 256, size=64)
        weights = rng.integers(-127, 128, size=64).astype(np.float64)
        error = (words < codes).mean(axis=1) - codes / 256
        denom = np.sqrt(np.sum(weights**2))
        cases.extend(((error @ weights) / denom).tolist())
    return {"scope": "synthetic only; empirical fixed-prefix errors, not Qwen quality",
            "pair_covariance_abs_mean": float(np.mean(np.abs(covariance))),
            "pair_covariance_abs_max": float(np.max(np.abs(covariance))),
            "signed_dot_normalized_rmse": float(np.sqrt(np.mean(np.square(cases))))}


def synthesize_masks(masks):
    """Shared-pair greedy XOR CSE for a small list of linear forms."""
    expressions = [set(bit + 1 for bit in range(32) if mask >> bit & 1) for mask in masks]
    network = XorNetwork()
    while True:
        counts = Counter(pair for expression in expressions for pair in combinations(sorted(expression), 2))
        if not counts:
            break
        (a, b), count = counts.most_common(1)[0]
        if count < 2:
            break
        node = network.xor(a, b)
        for expression in expressions:
            if a in expression and b in expression:
                expression.remove(a)
                expression.remove(b)
                if node in expression:
                    expression.remove(node)
                else:
                    expression.add(node)
    outputs = [[network.fold(sorted(expression))] for expression in expressions]
    return network, outputs


def emit_rtl(network, outputs, stride, module_name="rng32x64"):
    width = len(outputs[0])
    rows = columns_to_rows(transition_power(stride))
    transition_net, transition_out = synthesize_masks(rows)
    lines = ["// Generated by design.py. XOR counts are structural, not cell-mapped PPA.",
             "// Seeds must be nonzero. State sampled before jump-ahead update.",
             f"module {module_name}(input logic clk, input logic rst_n, input logic enable,",
             "  input logic seed_load, input logic [31:0] seed,",
             f"  input logic [63:0][{width-1}:0] threshold,",
             f"  output logic [63:0][{width-1}:0] random_word,",
             "  output logic [63:0] stochastic_bit);",
             "  logic [31:0] state, next_state;"]
    def declare(prefix, net, outs):
        used = net.reachable(outs)
        if used:
            lines.append("  wire " + ", ".join(f"{prefix}{node}" for node in used) + ";")
        def signal(node):
            return "1'b0" if node == 0 else (f"state[{node-1}]" if node <= 32 else f"{prefix}{node}")
        for node in used:
            a, b = net.nodes[node]
            lines.append(f"  assign {prefix}{node} = {signal(a)} ^ {signal(b)};")
        return signal
    sig = declare("g", network, outputs)
    for port, word in enumerate(outputs):
        lines.append(f"  assign random_word[{port}] = {{" + ", ".join(sig(node) for node in reversed(word)) + "};")
        lines.append(f"  assign stochastic_bit[{port}] = random_word[{port}] < threshold[{port}];")
    trsig = declare("t", transition_net, transition_out)
    for bit, word in enumerate(transition_out):
        lines.append(f"  assign next_state[{bit}] = {trsig(word[0])};")
    lines += ["  always_ff @(posedge clk or negedge rst_n) begin",
              "    if (!rst_n) state <= 32'h00000001;",
              "    else if (seed_load) state <= (seed == 0) ? 32'h00000001 : seed;",
              "    else if (enable) state <= next_state;", "  end", "endmodule"]
    (ROOT / f"{module_name}.sv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return transition_net.cost(transition_out)


def main():
    started = time.time()
    rng = np.random.default_rng(20261015)
    seeds = [int(x) for x in rng.integers(1, 1 << 32, size=24, dtype=np.uint32)]
    training, validation = seeds[:8], seeds[8:]
    result = {"period_certificate": period_certificate(), "width": 8, "ports": 64,
              "training_seeds": training, "held_out_seeds": validation,
              "scope": "Synthetic numerical and algebraic checks only. No Qwen PPL, no RTL synthesis."}
    grid_net, grid_out = gf4_grid()
    grid_masks = row_masks(grid_net, grid_out)
    result["stride_scan"] = {}
    best_stride, best_score = None, float("inf")
    for stride in (1, 8, 16, 32, 64):
        states = trajectories(training, 1024, stride)
        score = optimization_score(fast_grid(states, np.arange(32)))
        transition_net, transition_out = synthesize_masks(columns_to_rows(transition_power(stride)))
        result["stride_scan"][str(stride)] = {"score": score,
            "transition_logic": transition_net.cost(transition_out),
            "same_port_lag_rank": lag_certificate(grid_masks, stride)}
        # Explicit small cost regularizer, structural gate count only.
        objective = score + 0.0004 * result["stride_scan"][str(stride)]["transition_logic"]["xor2"]
        if objective < best_score:
            best_score, best_stride = objective, stride
    result["selected_stride"] = best_stride
    print("selected stride", best_stride, flush=True)
    train_states = trajectories(training, 4096, best_stride)
    permutation, optimization = optimize_grid(train_states)
    unconstrained = permutation.copy()
    permutation, temporal_optimization = constrain_temporal(permutation, train_states, best_stride)
    result["state_bit_permutation"] = permutation.tolist()
    result["unconstrained_state_bit_permutation"] = unconstrained.tolist()
    result["optimization"] = optimization
    result["temporal_constrained_optimization"] = temporal_optimization
    print("optimized wiring", optimization["initial_train_score"], optimization["final_train_score"], flush=True)
    valid_states = trajectories(validation, 4096, best_stride)
    candidates = {"wire_random_baseline": wire_baseline(),
                  "gf4_grid_identity": gf4_grid(),
                  "gf4_grid_optimized": gf4_grid(permutation),
                  "gf4_grid_area_optimized": gf4_grid_area(permutation),
                  "gf256_degree1": gf256_polynomial(1),
                  "gf256_degree2": gf256_polynomial(2),
                  "gf256_degree2_shared_area": gf256_quadratic_shared(),
                  "gf256_degree2_shared_fast": gf256_quadratic_shared(grouped=True),
                  "gf256_degree3": gf256_polynomial(3)}
    result["candidates"] = {}
    for name, (network, outputs) in candidates.items():
        masks = row_masks(network, outputs)
        words = evaluate_network(network, outputs, valid_states)
        if name == "gf4_grid_optimized":
            assert np.array_equal(words, fast_grid(valid_states, permutation))
        if name == "gf4_grid_area_optimized":
            assert row_masks(network, outputs) == row_masks(*candidates["gf4_grid_optimized"])
        if name.startswith("gf256_degree2_shared"):
            assert row_masks(network, outputs) == row_masks(*candidates["gf256_degree2"])
        certificate = pair_certificate(masks)
        if name != "wire_random_baseline":
            assert certificate["all_2016_pair_rank_histogram"] == {16: 2016}
        result["candidates"][name] = {
            "logic": network.cost(outputs), "certificate": certificate,
            "held_out_cdf": cdf_summary(words),
            "held_out_statistics_4096": statistical_summary(words),
            "same_port_lag_rank": lag_certificate(masks, best_stride)}
        print(name, network.cost(outputs), flush=True)
    # Monte Carlo reference is software IID, not 64 short same-polynomial LFSRs.
    iid = rng.integers(0, 256, size=(len(validation), 4096, 64), dtype=np.uint8)
    result["iid_reference"] = {"held_out_cdf": cdf_summary(iid),
                                "held_out_statistics_4096": statistical_summary(iid)}
    # Verify high-order rank properties without pretending exhaustive quads were checked.
    result["higher_order_checks"] = {}
    for name in ("gf4_grid_optimized", "gf256_degree2", "gf256_degree3"):
        network, outputs = candidates[name]
        masks = row_masks(network, outputs)
        triples = Counter(rank(masks[i] + masks[j] + masks[k])
                          for i, j, k in combinations(range(64), 3))
        quadruples = Counter()
        for _ in range(4096):
            indices = rng.choice(64, 4, replace=False)
            quadruples[rank([row for i in indices for row in masks[i]])] += 1
        result["higher_order_checks"][name] = {"all_41664_triple_rank_histogram": dict(sorted(triples.items())),
            "sampled_4096_quad_rank_histogram": dict(sorted(quadruples.items()))}
        if name in ("gf256_degree2", "gf256_degree3"):
            assert triples == {24: 41664}
        if name == "gf256_degree3":
            assert quadruples == {32: 4096}
    network, outputs = candidates["gf4_grid_optimized"]
    result["selected_cross_port_lag_rank"] = cross_port_lag_certificate(row_masks(network, outputs), best_stride)
    result["rtl_transition_logic"] = emit_rtl(network, outputs, best_stride)
    emit_rtl(*candidates["gf4_grid_area_optimized"], best_stride, "rng32x64_area")
    emit_rtl(*candidates["gf256_degree2_shared_area"], best_stride, "rng32x64_threewise")
    twelve = gf4096_pairwise()
    twelve_masks = row_masks(*twelve)
    assert all(rank(left + right) == 24 for left, right in combinations(twelve_masks, 2))
    result["twelve_bit_pairwise"] = {"logic": twelve[0].cost(twelve[1]),
         "all_2016_pair_rank_histogram": {24: 2016}, "polynomial": "0x1053",
         "scope": "algebra and structural count only; no 12-bit short-stream quality scan"}
    emit_rtl(*twelve, best_stride, "rng32x64_twelve")
    manifest = {"generator": "GF4 affine grid over four interleaved GF4 lanes",
                "state_bits": 32, "ports": 64, "word_bits": 8,
                "galois_mask": hex(GALOIS), "jump_stride": best_stride,
                "state_bit_permutation": permutation.tolist(),
                "output_rows_lsb_first": [[hex(mask) for mask in word] for word in row_masks(network, outputs)],
                "zero_seed_handling": "replace with 1", "comparator": "unsigned random_word < threshold; Q/256",
                "port_index": "16*i + 4*j + k, i,j,k in GF4={0,1,z,z+1}",
                "formula": "r_ijk = A XOR i*B XOR j*C XOR k*D; GF4 z^2+z+1=0"}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    vector_states = trajectories([1, seeds[0]], 8, best_stride)
    vector_words = evaluate_network(network, outputs, vector_states)
    (ROOT / "reference_vectors.json").write_text(json.dumps({"states": vector_states.tolist(),
        "words": vector_words.tolist()}, indent=2) + "\n", encoding="utf-8")
    result["elapsed_seconds"] = time.time() - started
    (ROOT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("saved results in", ROOT, "elapsed", result["elapsed_seconds"], flush=True)


if __name__ == "__main__":
    main()
