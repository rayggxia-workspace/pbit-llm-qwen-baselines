"""Fixed GU input masks. Compensation is exact integer count weighting."""
import hashlib
import torch
import gu_adapter as original_gu
from sparse_sampling import input_mass


def apply_rule(counts, mass, case, thresholds, random_values=None):
    kind = case['kind']
    band = torch.zeros_like(counts, dtype=torch.bool)
    if kind == 'original':
        keep = torch.ones_like(counts, dtype=torch.bool)
    elif kind == 'hard':
        keep = mass > thresholds[str(case['percent'])]
    elif kind == 'boundary_half':
        above = mass > thresholds['20']
        band = above & (mass <= thresholds['40'])
        assert random_values is not None
        keep = above & (~band | random_values.bool())
    elif kind == 'random18':
        assert random_values is not None
        keep = random_values >= 46  # 46/256 = 17.96875%, explicit P8 contract.
    else:
        raise ValueError(kind)
    physical = counts * keep.long()
    weighted = physical << band.long()
    assert not bool((weighted < 0).any()) and int(weighted.max()) <= 128
    return weighted, physical, keep, band


def mask_random_values(shape, device, parent_seed, layer, kind):
    """Separate PRNG state; never advances the matrix/nonlinearity generator."""
    if kind not in ['boundary_half', 'random18']:
        return None
    key = ('GU-pruning-mask-v1|%s|%s|%s' % (parent_seed, layer, kind)).encode()
    seed = int.from_bytes(hashlib.sha256(key).digest()[:8], 'little') & ((1 << 63) - 1)
    generator = torch.Generator(device=device).manual_seed(seed)
    return torch.randint(2 if kind == 'boundary_half' else 256, shape,
                         device=device, generator=generator, dtype=torch.int64)


class SweepGU(original_gu.GUOverride):
    def __init__(self, case, banks, calibration, verify_dense=False):
        super().__init__(case, banks, verify_dense)
        self.calibration = calibration
        self.prune_stats = {}
        self.last_counts = {}

    def sampled(self, codes, enc, module, case, generator, original_sampler):
        s = self.saved_sample(codes, enc, module, {'kind': 'original', 'samples': 64},
                              generator, original_sampler)
        counts = s['counts'].reshape(-1, codes.shape[-1])
        mass, _, unit = input_mass(codes.reshape_as(counts), enc['bin_id'].reshape_as(counts), module.x_scales)
        thresholds = self.calibration['thresholds'][str(module.layer)]
        rnd = mask_random_values(counts.shape, counts.device, generator.initial_seed(), module.layer, case['kind'])
        weighted, physical, keep, band = apply_rule(counts, mass, case, thresholds, rnd)
        raw_events, physical_events = int(counts.sum()), int(physical.sum())
        effective_events = int(weighted.sum())
        s['counts'] = weighted.reshape_as(s['counts'])
        gate_bits = int(band.sum()) if case['kind'] == 'boundary_half' else counts.numel() * 8 if case['kind'] == 'random18' else 0
        s['extra_gate_bits'] = gate_bits
        s['sweep_audit'] = {'possible': counts.numel(), 'mask_pruned': int((~keep).sum()),
            'baseline_nonzero': int((counts > 0).sum()),
            'removed_nonzero': int(((counts > 0) & ~keep).sum()),
            'raw_base_events': raw_events, 'physical_retained_events': physical_events,
            'effective_weighted_events': effective_events, 'boundary_directions': int(band.sum()),
            'amplified_directions': int((band & keep).sum()), 'logical_random_bits': gate_bits,
            'software_random_bits': 0 if rnd is None else rnd.numel() * (1 if case['kind'] == 'boundary_half' else 8),
            'physical_max_count': int(physical.max()), 'effective_max_count': int(weighted.max()),
            'input_absolute_mass': float(mass.double().sum()),
            'removed_input_absolute_mass': float((mass.double() * ~keep).sum()),
            'input_square_mass': float(mass.double().square().sum()),
            'removed_input_square_mass': float((mass.double().square() * ~keep).sum()),
            'unit_exponent': unit}
        self.last_counts[module.layer] = dict(raw_count_events=physical_events,
            effective_weighted_count_events=effective_events, physical_samples=64,
            maximum_compensation_shift=1 if case['kind'] == 'boundary_half' else 0)
        return s

    def record(self, module, s, lengths, counts, records, bank, bound):
        super().record(module, s, lengths, counts, records, bank, bound)
        self.last_counts[module.layer]['actual_weighted_absolute_bound'] = bound
        audit = s['sweep_audit']
        # The parent counts weighted arithmetic events. Expose physical events
        # separately so the 2x contribution is never called extra sampling.
        self.stats[str(module.layer)]['events'] += audit['physical_retained_events'] - audit['effective_weighted_events']
        row = self.prune_stats.setdefault(str(module.layer), {})
        for key, value in audit.items():
            if key in ['physical_max_count', 'effective_max_count']:
                row[key] = max(row.get(key, 0), value)
            elif key == 'unit_exponent':
                if key in row:
                    assert row[key] == value
                row[key] = value
            else:
                row[key] = row.get(key, 0) + value

    def __enter__(self):
        self.saved_sample = original_gu.sample
        original_gu.sample = self.sampled
        try:
            super().__enter__()
            inner = self.sf.upstream.hard_forward

            def audited_hard(x, wg, wu, wd, module, key):
                value, cache = inner(x, wg, wu, wd, module, key)
                module.last_arithmetic['address_GU'].update(self.last_counts[module.layer])
                return value, cache

            self.sf.upstream.hard_forward = audited_hard
            return self
        except BaseException:
            original_gu.sample = self.saved_sample
            raise

    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            original_gu.sample = self.saved_sample

    def summary(self):
        out = super().summary()
        total = {}
        for row in self.prune_stats.values():
            for key, value in row.items():
                if key in ['unit_exponent', 'input_absolute_mass', 'removed_input_absolute_mass',
                           'input_square_mass', 'removed_input_square_mass']:
                    continue  # Physical scales can differ across layers.
                if key in ['physical_max_count', 'effective_max_count']:
                    total[key] = max(total.get(key, 0), value)
                else:
                    total[key] = total.get(key, 0) + value
        total['actual_mask_pruned_fraction'] = total.get('mask_pruned', 0) / max(1, total.get('possible', 0))
        out['pruning_sweep'] = {'total': total, 'per_layer': self.prune_stats,
            'mask_scope': 'one_per_token_layer_input_shared_all64ticks_bothGU_all_output_stripes',
            'mask_RNG': 'separate_hash_domain_and_generator;IID_mask_bits;not_physical_entropy_validation',
            'compensation': 'boundary_kept_count_shift_left_1;no_P8_reencoding;physical_samples64'}
        return out
