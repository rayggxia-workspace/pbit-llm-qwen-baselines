"""Independent probability enumeration and GPU vs CPU integer projection."""
import torch
from prune_sweep import apply_rule, mask_random_values


def run():
    from sparse_sampling import compact
    from sparse_gu import pack_bank, project
    checks = []
    thresholds = {'20': 10, '30': 20, '40': 30}
    counts = torch.tensor([[0, 1, 32, 64, 64]], dtype=torch.int64)
    mass = torch.tensor([[0, 10, 11, 30, 31]])
    case = {'kind': 'boundary_half'}
    a = apply_rule(counts, mass, case, thresholds, torch.zeros_like(counts))[0]
    b = apply_rule(counts, mass, case, thresholds, torch.ones_like(counts))[0]
    anchor = counts * (mass > thresholds['20'])
    assert torch.equal(a + b, 2 * anchor)
    assert int(b.max()) == 128
    checks.append('enumerated_half_probability_expectation_equals_hard20')
    assert torch.equal(apply_rule(counts, mass, {'kind': 'original'}, thresholds)[0], counts)
    checks.append('original_count_noop')
    for p in [20, 30, 40]:
        got = apply_rule(counts, mass, {'kind': 'hard', 'percent': p}, thresholds)[0]
        expected = torch.tensor([[int(c) if int(v) > thresholds[str(p)] else 0
                                  for c, v in zip(counts[0], mass[0])]])
        assert torch.equal(got, expected)
    checks.append('hard_threshold_integer_boundaries')
    r8 = torch.arange(256)[None, :]
    c = torch.ones_like(r8)
    got = apply_rule(c, c, {'kind': 'random18'}, thresholds, r8)[0]
    assert int((got == 0).sum()) == 46 and int(got.sum()) == 210
    checks.append('random18_R8_exact46_of256_no_compensation')
    parent = torch.Generator(device='cuda').manual_seed(91)
    state = parent.get_state().clone()
    first = mask_random_values((8, 128), 'cuda', parent.initial_seed(), 3, 'boundary_half')
    second = mask_random_values((8, 128), 'cuda', parent.initial_seed(), 3, 'boundary_half')
    assert torch.equal(first, second) and torch.equal(state, parent.get_state())
    checks.append('mask_generator_reproducible_no_parent_RNG_consumption')
    g = torch.Generator(device='cuda').manual_seed(1123)
    w = torch.randint(-127, 128, (128, 128), generator=g, device='cuda', dtype=torch.int16)
    counts = torch.randint(0, 65, (4, 128), generator=g, device='cuda', dtype=torch.int64)
    counts[0, :] = 64
    mass = torch.randint(0, 50, counts.shape, generator=g, device='cuda')
    mass[0, :] = 15
    shifts = torch.randint(0, 4, counts.shape, generator=g, device='cuda') * 2
    signs = torch.randint(0, 2, counts.shape, generator=g, device='cuda') * 2 - 1
    coeff = torch.tensor([[1, 2], [4, 8]], device='cuda', dtype=torch.int64)
    weighted = apply_rule(counts, mass, case, thresholds, torch.ones_like(counts))[0]
    records, pointer, lengths = compact(weighted, signs, shifts)
    assert int(weighted.max()) == 128 and int(lengths.sum()) == records.numel()
    actual = project(pack_bank(w, 64), records, pointer, coeff, 6).cpu()
    scaled_w = w.cpu().long() * coeff.cpu().repeat_interleave(64, 0).repeat_interleave(64, 1)
    values = ((weighted << (6 - shifts)) * signs).cpu()
    expected = values @ scaled_w.T
    assert torch.equal(actual, expected)
    checks.append('GPU_selected_W8_count128_vs_independent_CPU_int64_dot')
    return {'status': 'PASS', 'tests': len(checks), 'checks': checks,
            'count_max128_is_weighted_not128_physical_draws': True}
