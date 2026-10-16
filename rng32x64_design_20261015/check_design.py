"""Independent rank, field, and emitted-equation checks; no HDL simulator required.

This checks the generated straight-line RTL equations against mathematical maps.
It does NOT claim an HDL compile, timing check or cell-level synthesis.
"""
from itertools import combinations
import json
from pathlib import Path
import re

import numpy as np

import design as d


def parse_signal(name, masks):
    if name == "1'b0":
        return 0
    match = re.fullmatch(r"state\[(\d+)\]", name)
    return (1 << int(match[1])) if match else masks[name]


def check_rtl(path, expected_rows, stride):
    text = path.read_text(encoding="utf-8")
    masks = {}
    for target, left, right in re.findall(r"assign ([gt]\d+) = (\S+) \^ (\S+);", text):
        masks[target] = parse_signal(left, masks) ^ parse_signal(right, masks)
    rows = []
    for port, expression in re.findall(r"assign random_word\[(\d+)\] = \{([^}]+)\};", text):
        assert int(port) == len(rows)
        rows.append([parse_signal(name.strip(), masks) for name in expression.split(",")][::-1])
    assert rows == expected_rows
    actual_transition = [None] * 32
    for bit, name in re.findall(r"assign next_state\[(\d+)\] = (\S+);", text):
        actual_transition[int(bit)] = parse_signal(name, masks)
    assert actual_transition == d.columns_to_rows(d.transition_power(stride))
    comparisons = re.findall(r"assign stochastic_bit\[(\d+)\] = random_word\[(\d+)\] < threshold\[(\d+)\];", text)
    assert len(comparisons) == 64 and all(a == b == c for a, b, c in comparisons)
    assert "else if (seed_load)" in text and "else if (enable)" in text
    return {"word_equations": sum(map(len, expected_rows)), "next_state_equations": 32, "comparators": 64}


def main():
    manifest = json.loads((d.ROOT / "manifest.json").read_text())
    stride = manifest["jump_stride"]
    permutation = manifest["state_bit_permutation"]
    fast, area = d.gf4_grid(permutation), d.gf4_grid_area(permutation)
    rows = d.row_masks(*fast)
    assert rows == d.row_masks(*area)
    assert len(set(row for word in rows for row in word)) == 512
    direct = sum(mask.bit_count() == 1 for word in rows for mask in word)
    assert direct == 8
    assert area[0].cost(area[1])["xor2"] == 512 - direct == 504
    assert d.pair_certificate(rows)["all_2016_pair_rank_histogram"] == {16: 2016}
    assert all(hist == {16: 4096} for hist in d.cross_port_lag_certificate(rows, stride).values())
    # GF(256) inverse existence proves the configured AES polynomial is a field.
    for a in range(1, 256):
        assert any(d.gf_multiply(a, b) == 1 for b in range(1, 256))
    three = d.gf256_quadratic_shared()
    three_rows = d.row_masks(*three)
    assert three_rows == d.row_masks(*d.gf256_polynomial(2))
    assert all(d.rank(three_rows[i] + three_rows[j] + three_rows[k]) == 24
               for i, j, k in combinations(range(64), 3))
    # Reduced-width exhaustive analog of the polynomial independence theorem.
    histogram = np.zeros(64, dtype=np.int64)
    for a in range(4):
        for b in range(4):
            for c in range(4):
                out = [a ^ d.gf_multiply(x, b, 2, 7) ^ d.gf_multiply(d.gf_multiply(x, x, 2, 7), c, 2, 7)
                       for x in (0, 1, 2)]
                histogram[out[0] | out[1] << 2 | out[2] << 4] += 1
    assert np.all(histogram == 1)
    collinear_joint_zero = sum((a == 0 and (a ^ b) == 0
                              and (a ^ d.gf_multiply(2, b, 2, 7)) == 0)
                             for a in range(4) for b in range(4)) / 16
    assert collinear_joint_zero == 1 / 16
    # Rabin irreducibility test for x^12+x^6+x^4+x+1.
    def polynomial_remainder(a, b):
        while a and a.bit_length() >= b.bit_length():
            a ^= b << (a.bit_length() - b.bit_length())
        return a
    def polynomial_gcd(a, b):
        while b:
            a, b = b, polynomial_remainder(a, b)
        return a
    power = 2
    for step in range(1, 13):
        power = d.gf_multiply(power, power, 12, 0x1053)
        if step in (4, 6):
            assert polynomial_gcd(power ^ 2, 0x1053) == 1
    assert power == 2
    twelve = d.gf4096_pairwise()
    assert all(d.rank(left + right) == 24 for left, right in combinations(d.row_masks(*twelve), 2))
    checks = {}
    for name, candidate in (("rng32x64", fast), ("rng32x64_area", area),
                             ("rng32x64_threewise", three), ("rng32x64_twelve", twelve)):
        checks[name] = check_rtl(d.ROOT / f"{name}.sv", d.row_masks(*candidate), stride)
    result = {"status": "passed", "algebraic_and_emitted_equation_checks": checks,
              "pairwise_only_collinear_three_AND": {
                  "three_marginals": [0.25, 0.25, 0.25],
                  "joint_probability": collinear_joint_zero,
                  "desired_product": 1 / 64},
              "scope": "Not HDL compilation, synthesis, physical PPA or Qwen quality evaluation."}
    (d.ROOT / "checks.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
