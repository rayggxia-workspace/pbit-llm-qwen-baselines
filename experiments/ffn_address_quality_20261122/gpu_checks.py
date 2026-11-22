"""GPU-vs-independent CPU integer and masked-weight oracles."""
import torch
from sparse_gu import pack_bank, project, multiply_checked
from sparse_sampling import compact, sample


def run():
    torch.manual_seed(7001)
    n, m, rows = 128, 128, 3
    w = torch.randint(-127, 128, (2 * m, n), dtype=torch.int16)
    count = torch.randint(0, 8, (rows, n), dtype=torch.int64)
    count[0, 1::2] = 0
    count[1] = 0
    sign = torch.randint(0, 2, (rows, n)) * 2 - 1
    shift = torch.randint(0, 4, (rows, n)) * 2
    coefficients = (torch.ones(2 * m // 64, n // 64, dtype=torch.int64)
                    << torch.randint(0, 7, (2 * m // 64, n // 64)))
    expected = torch.zeros(rows, 2 * m, dtype=torch.int64)
    for group in range(n // 64):
        x = (count[:, group * 64:(group + 1) * 64]
             << (6 - shift[:, group * 64:(group + 1) * 64])) * sign[:, group * 64:(group + 1) * 64]
        expected += (x @ w[:, group * 64:(group + 1) * 64].long().T
                     * coefficients[:, group].repeat_interleave(64)[None, :])
    records, pointer, lengths = compact(count.cuda(), sign.cuda(), shift.cuda())
    bank = pack_bank(w.cuda(), 64)
    observed = project(bank, records, pointer, coefficients.cuda(), 6).cpu()
    assert torch.equal(observed, expected), 'sparse GPU != independent CPU integer oracle'
    assert int(lengths[1]) == 0 and bool((observed[1] == 0).all())
    # Perturb every input direction not selected by row0. Its output must not
    # change. This catches accidental full/dense weight participation.
    poisoned = w.clone()
    unused = count[0] == 0
    poisoned[:, unused] = 127 - (poisoned[:, unused].abs() % 127)
    changed = project(pack_bank(poisoned.cuda(), 64), records, pointer, coefficients.cuda(), 6).cpu()
    assert torch.equal(changed[0], expected[0]), 'unselected weights influenced output'
    assert torch.equal(multiply_checked(observed.cuda(), 16).cpu(), expected * 16)

    from sampling import shared_input_counts
    from types import SimpleNamespace
    module = SimpleNamespace(x_scales=torch.tensor([[16., 4., 1., .25], [8., 2., .5, .125]], device='cuda'))
    q = torch.randint(0, 257, (rows, n), device='cuda')
    q[0] = 0
    enc = {'bin_id': torch.randint(0, 4, (rows, n), device='cuda')}
    one = sample(q, enc, module, {'kind': 'pot', 'divisor': 1, 'samples': 64},
                 torch.Generator(device='cuda').manual_seed(41), shared_input_counts)
    original = shared_input_counts(q, 64, torch.Generator(device='cuda').manual_seed(41))
    assert torch.equal(one['counts'], original), 'L1 changed shared64 stratified law'
    checks = ['independent_CPU_integer_dot', 'zero_CSR_row', 'unselected_weight_poison',
              'integer_compensation', 'shared64_L1_bitwise']
    for kind, budget in [('normalized_bernoulli', 64), ('categorical', 64), ('categorical', 1024)]:
        result = sample(q, enc, module, {'kind': kind, 'samples': budget},
                        torch.Generator(device='cuda').manual_seed(42), shared_input_counts)
        assert bool((result['counts'][0] == 0).all()), 'zero input sampled a weight'
        assert bool(((result['counts'] >= 0) & (result['counts'] <= budget)).all())
        checks.append(kind + '_' + str(budget) + '_integer_mass_zero_and_budget')
    return {'status': 'PASS', 'checks': checks, 'tests': len(checks),
            'framework': 'Triton selected W8 bank vs independent CPU signed64 oracle'}
