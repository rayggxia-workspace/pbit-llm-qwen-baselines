"""GU-only adapter around the immutable T64 hard forward.

P8 g/u, sigmoid LUT, three-way AND counts, Wd integer projection and BF16
finish all execute their ORIGINAL functions. No training/backward is supported.
"""
from contextlib import AbstractContextManager
import torch
from sparse_sampling import sample, compact
from sparse_gu import pack_bank, project, multiply_checked


class GUOverride(AbstractContextManager):
    def __init__(self, case, banks, verify_dense=False):
        import seven_forward as sf
        self.sf, self.case, self.banks = sf, case, banks
        self.verify_dense = verify_dense
        self.active = None
        self.stats = {}
        self.dense_checks = 0
        self.wd_calls = 0

    def __enter__(self):
        sf = self.sf
        self.old_hard = sf.upstream.hard_forward
        self.old_encode = sf._encode_static_validated
        self.old_input = sf.iid_shared64_counts
        self.old_project = sf.shifted_integer
        self.old_finish = sf.finish_fp32

        def encode(x, scales):
            value = self.old_encode(x, scales)
            if self.active is not None:
                self.active['enc'] = value
            return value

        def input_counts(codes, samples, generator=None, thresholds=None):
            if self.active is None or thresholds is not None:
                raise RuntimeError('GU sampler outside the declared forward')
            a = self.active
            assert samples == 64 and a['module'].config.nonlinear_samples == 64
            a['sample'] = sample(codes, a['enc'], a['module'], self.case, generator, self.old_input)
            return a['sample']['counts'].reshape_as(codes)

        def projection(counts, sign, shifts, weights, coeff, samples, max_shift, qmax, backend):
            a = self.active
            if a is None or weights is not a['module'].frozen_gu_codes:
                # Wd reaches this ORIGINAL path, with unchanged AND counts.
                if a is not None:
                    assert weights is a['module'].frozen_down_codes
                    self.wd_calls += 1
                return self.old_project(counts, sign, shifts, weights, coeff,
                                        samples, max_shift, qmax, backend)
            module, s = a['module'], a['sample']
            n, leading = counts.shape[-1], counts.shape[:-1]
            assert n == 2560 and qmax == 127 and samples == 64 and max_shift == 6
            assert weights.shape == (19456, 2560)
            if module.layer not in self.banks:
                self.banks[module.layer] = pack_bank(weights, 512)
            bank = self.banks[module.layer]
            normalized = s['mass'] is not None
            if normalized:
                top = sf.pow2_exact(torch.full((n // 64,), s['unit'], device=counts.device, dtype=torch.int64))
                coeff, exponent = sf.exact_coefficients(module.frozen_gu_lsb, top, torch.ones_like(top))
                use_shifts, use_max_shift = torch.zeros_like(shifts), 0
                multiplier = s['mass']
            else:
                _, exponent = sf.exact_coefficients(module.frozen_gu_lsb, module.x_scales[:, 0],
                                                    torch.ones_like(module.x_scales[:, 0]))
                use_shifts, use_max_shift = shifts, 6
                multiplier = s['compensation']
            flat = counts.reshape(-1, n)
            shifted_abs_sum = (flat << (use_max_shift - use_shifts.reshape(-1, n))).sum(-1)
            bound = int(shifted_abs_sum.max()) * qmax * int(coeff.max())
            if bound >= 1 << 63:
                raise OverflowError('selected dot requires wider than signed64')
            records, pointer, lengths = compact(flat, sign, use_shifts)
            acc = project(bank, records, pointer, coeff, use_max_shift)
            acc = multiply_checked(acc, multiplier).reshape(*leading, weights.shape[0])
            if self.verify_dense:
                if self.case['kind'] != 'original':
                    raise ValueError('dense no-op witness is baseline only')
                oracle = self.old_project(counts, sign, shifts, weights, coeff,
                                          samples, max_shift, qmax, backend)
                if not torch.equal(oracle, acc):
                    raise AssertionError('selected-row integer projection differs from original')
                self.dense_checks += 1
            a['finish'] = (exponent, s['denominator'], use_max_shift)
            a['projection_calls'] += 1
            self.record(module, s, lengths, flat, records, bank, bound)
            return acc

        def finish(acc, exponents, samples, max_shift):
            if self.active is None or 'finish' not in self.active:
                raise RuntimeError('missing selected-GU restore contract')
            exponent, denominator, shift = self.active.pop('finish')
            return self.old_finish(acc, exponent, denominator, shift)

        def hard(x, wg, wu, wd, module, key):
            if torch.is_grad_enabled():
                raise RuntimeError('inference-only quality adapter')
            if self.active is not None:
                raise RuntimeError('nested GU forward')
            self.active = dict(module=module, projection_calls=0)
            try:
                value, cache = self.old_hard(x, wg, wu, wd, module, key)
                a = self.active
                assert a['projection_calls'] == 1 and 'finish' not in a
                s = a['sample']
                module.last_arithmetic['address_GU'] = dict(case=self.case, raw_count_events=int(s['counts'].sum()),
                    denominator=s['denominator'], compensation_kind='integer_mass' if s['mass'] is not None else 'PoT',
                    downstream='original_P8_LUT_AND_Wd', dense_witness=self.verify_dense)
                # Keep the diagnostic cache honest; downstream y was already
                # computed by the original hard forward from the new exact GU.
                shape = x.shape
                if s['mass'] is None:
                    xhat = cache[0] * s['compensation']
                else:
                    scale = sf.pow2_exact(torch.tensor(s['unit'], device=x.device))
                    xhat = (s['counts'].double() * a['enc']['sign'].reshape_as(s['counts'])
                            * s['mass'][:, None] * scale / s['denominator']).float().reshape(shape)
                cache = (xhat,) + cache[1:]
                return value, cache
            finally:
                self.active = None

        sf._encode_static_validated = encode
        sf.iid_shared64_counts = input_counts
        sf.shifted_integer = projection
        sf.finish_fp32 = finish
        sf.upstream.hard_forward = hard
        return self

    def record(self, module, sample_info, lengths, counts, records, bank, bound):
        row = self.stats.setdefault(str(module.layer), dict(calls=0, tokens=0, possible_addresses=0,
            unique_addresses=0, events=0, max_count=0, selected_weight_bytes=0,
            full_weight_bytes=0, csr_bytes=0, input_groups_touched=0, ticket_proposals=0,
            ticket_random_bits=0, extra_gate_bits=0, accumulator_bound_max=0))
        tokens, n = counts.shape
        unique = int(lengths.sum())
        row['calls'] += 1
        row['tokens'] += tokens
        row['possible_addresses'] += tokens * n
        row['unique_addresses'] += unique
        row['events'] += int(counts.sum())
        row['max_count'] = max(row['max_count'], int(counts.max()))
        # Each input supplies both GU branches, all9728 outputs, one W8 byte.
        row['selected_weight_bytes'] += unique * 19456
        row['full_weight_bytes'] += tokens * n * 19456
        row['csr_bytes'] += records.numel() * 4
        row['input_groups_touched'] += int((counts.reshape(tokens, n // 64, 64).sum(-1) > 0).sum())
        for name in ['ticket_proposals', 'ticket_random_bits', 'extra_gate_bits']:
            row[name] += sample_info.get(name, 0)
        row['accumulator_bound_max'] = max(row['accumulator_bound_max'], bound)

    def __exit__(self, *args):
        sf = self.sf
        sf._encode_static_validated = self.old_encode
        sf.iid_shared64_counts = self.old_input
        sf.shifted_integer = self.old_project
        sf.finish_fp32 = self.old_finish
        sf.upstream.hard_forward = self.old_hard

    def summary(self):
        total = {k: sum(r[k] for r in self.stats.values()) for k in
                 ['tokens', 'possible_addresses', 'unique_addresses', 'events',
                  'selected_weight_bytes', 'full_weight_bytes', 'csr_bytes',
                  'input_groups_touched', 'ticket_proposals', 'ticket_random_bits', 'extra_gate_bits']}
        total['unique_address_ratio'] = total['unique_addresses'] / total['possible_addresses'] if total['possible_addresses'] else 0.
        total['per_layer'] = self.stats
        total['dense_witness_checks'] = self.dense_checks
        total['original_wd_calls'] = self.wd_calls
        total['read_scope'] = 'selected W8 payload from GPU-global packed bank;no LPDDR burst/timing/PPA claim'
        return total
