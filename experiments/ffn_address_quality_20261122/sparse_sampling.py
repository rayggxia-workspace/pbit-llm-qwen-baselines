"""Integer input samplers. No floating-point categorical probability oracle.

All GU columns share a token's address/count list. Original64 sharing is kept
for comparator laws; categorical tickets choose one address over the vector.
"""
import math


def uniform_tickets(totals, shape, generator):
    """Uniform integer [0,total), via per-row power-of-two rejection.

    A zero total emits dummy zeros (caller masks that row). Python/Torch's
    generator is an explicit ideal uniform-bit interface, not physical p-bit
    validation. frexp only finds the bit width of exact integers <2**53.
    """
    import torch
    totals = totals.long()
    if bool(((totals < 0) | (totals >= 1 << 53)).any()):
        raise ValueError('integer mass outside exact bit-width contract')
    safe = totals.clamp_min(1)
    bits = torch.frexp((safe - 1).double())[1].long()
    while bits.ndim < len(shape):
        bits = bits.unsqueeze(-1)
        safe = safe.unsqueeze(-1)
    bits, safe = bits.expand(shape), safe.expand(shape)
    max_bits = int(bits.max())
    masks = (torch.ones_like(bits) << bits) - 1
    r = torch.randint(1 << max_bits, shape, device=totals.device,
                      generator=generator, dtype=torch.int64) & masks
    proposals, random_bits, loops = r.numel(), int(bits.sum()), 0
    bad = r >= safe
    while bool(bad.any()):
        loops += 1
        if loops > 128:
            raise RuntimeError('uniform-ticket entropy/rejection failure; no modulo fallback')
        bad_index = bad.flatten().nonzero().flatten()
        replacement = torch.randint(1 << max_bits, (bad_index.numel(),),
                                    device=r.device, generator=generator,
                                    dtype=torch.int64)
        r.flatten()[bad_index] = replacement & masks.flatten()[bad_index]
        proposals += bad_index.numel()
        random_bits += int(bits.flatten()[bad_index].sum())
        bad = r >= safe
    return r, dict(ticket_proposals=proposals, ticket_random_bits=random_bits,
                   rejection_rounds=loops)


def input_mass(codes, bin_ids, top_scales):
    """|x_i| = mass_i * 2**unit_exponent, from frozen P8/PoT only."""
    import torch
    tops = top_scales[:, 0]
    mantissa, exponents = torch.frexp(tops.double())
    if not bool((mantissa == .5).all()):
        raise ValueError('frozen input top scales must be exact PoT')
    top_exp = exponents.long() - 1
    unit = int(top_exp.min()) - 6 - 8
    delta = top_exp.repeat_interleave(64)[None, :] - bin_ids.long() * 2 - 8 - unit
    if bool(((delta < 0) | (delta >= 40)).any()):
        raise ValueError('input mass requires a wider declared integer format')
    mass = codes.long() << delta
    # Worst-case sum bound before integer cumsum; never silently overflow.
    if codes.shape[-1] * 256 * (1 << int(delta.max())) >= 1 << 53:
        raise ValueError('input mass sum outside declared exact range')
    return mass, mass.sum(-1), unit


def sample(codes, enc, module, case, generator, original_sampler):
    import torch
    codes = codes.reshape(-1, codes.shape[-1]).long()
    rows, n = codes.shape
    if n % 64 or n > 4096 or bool(((codes < 0) | (codes > 256)).any()):
        raise ValueError('original64 groups and P8 code0..256 required')
    t = int(case['samples'])
    result = dict(kind=case['kind'], denominator=t, compensation=1,
                  mass=None, unit=None)
    if case['kind'] == 'original':
        result['counts'] = original_sampler(codes, t, generator)
    elif case['kind'] == 'pot':
        divisor = int(case['divisor'])
        if divisor < 1 or divisor & (divisor - 1) or 256 % t:
            raise ValueError('PoT divisor and full R8 strata required')
        grouped = codes.reshape(rows, n // 64, 64).contiguous()
        shape = (rows, n // 64, t)
        width = 256 // t
        # Same low-bit draw layout as the original stratified shared64 law.
        lo = torch.randint(width, shape, device=codes.device, generator=generator)
        lo += torch.arange(t, device=codes.device)[None, None, :] * width
        hi = torch.randint(divisor, shape, device=codes.device, generator=generator)
        surviving = torch.where(hi == 0, lo, 256).sort(-1).values.contiguous()
        result['counts'] = torch.searchsorted(surviving, grouped, right=False).reshape(rows, n)
        result['compensation'] = divisor
        result['extra_gate_bits'] = int(math.log2(divisor)) * rows * (n // 64) * t
    else:
        bins = enc['bin_id'].reshape(rows, n)
        mass, total, unit = input_mass(codes, bins, module.x_scales)
        result.update(mass=total, unit=unit)
        if case['kind'] == 'categorical':
            tickets, audit = uniform_tickets(total, (rows, t), generator)
            cdf = mass.cumsum(-1).contiguous()
            indices = torch.searchsorted(cdf, tickets, right=True).clamp_max(n - 1)
            counts = torch.zeros_like(codes)
            counts.scatter_add_(1, indices, (total > 0).long()[:, None].expand_as(indices))
            if not torch.equal(counts.sum(-1), (total > 0).long() * t):
                raise AssertionError('categorical address budget changed')
        elif case['kind'] == 'normalized_bernoulli':
            # IID integer tickets, shared across each original64 group.
            # Sum probabilities is1, but a round may hit zero or many inputs.
            tickets, audit = uniform_tickets(total, (rows, n // 64, t), generator)
            ordered = tickets.sort(-1).values.contiguous()
            counts = torch.searchsorted(ordered, mass.reshape(rows, n // 64, 64).contiguous(), right=False).reshape(rows, n)
            counts = torch.where(total[:, None] > 0, counts, 0)
        else:
            raise ValueError('unknown input sampler')
        result.update(audit)
        result['counts'] = counts
    if bool(((result['counts'] < 0) | (result['counts'] > t)).any()):
        raise AssertionError('raw counts outside actual sampling budget')
    return result


def compact(counts, signs, shifts):
    """CSR with one packed32 record per unique input; count is not a re-draw.

    input12 | count11 | shift3 | negative1. Only Qwen GU N<=4096, S<=1024.
    """
    import torch
    counts = counts.reshape(-1, counts.shape[-1]).long()
    signs, shifts = signs.reshape_as(counts).long(), shifts.reshape_as(counts).long()
    if bool(((counts < 0) | (counts > 1024) | (shifts < 0) | (shifts > 6)).any()):
        raise ValueError('record field overflow')
    locations = (counts > 0).nonzero()
    row, index = locations[:, 0], locations[:, 1]
    if bool((signs[row, index].abs() != 1).any()):
        raise ValueError('selected input must have a sign')
    records = (index | (counts[row, index] << 12) | (shifts[row, index] << 23)
               | ((signs[row, index] < 0).long() << 26)).to(torch.int32).contiguous()
    lengths = (counts > 0).sum(-1)
    pointer = torch.cat((torch.zeros(1, dtype=torch.int64, device=counts.device), lengths.cumsum(0)))
    assert int(pointer[-1]) == records.numel()
    return records, pointer.contiguous(), lengths
