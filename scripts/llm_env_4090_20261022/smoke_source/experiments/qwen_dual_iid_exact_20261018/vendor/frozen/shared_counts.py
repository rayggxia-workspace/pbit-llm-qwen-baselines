"""Exact joint count law for IID random words shared across input lanes.

For each token and contiguous group of lanes, draw the SAME uniform word at
each clock, independently of other groups/tokens/stages. With exact spatial
addition, the temporal order can be compressed to multinomial interval counts.
This is not independent binomial sampling of each lane.
"""
import torch


def shared_counts(probability, cycles, generator, group=64):
    if probability.shape[-1] % group or group <= 0:
        raise ValueError('last dimension must be a multiple of a positive group')
    if cycles <= 0:
        raise ValueError('cycles must be positive')
    shape = probability.shape
    p = probability.reshape(-1, group)
    sorted_p, order = p.sort(-1)
    # group thresholds partition the uniform [0,1) interval into group+1 bins.
    mass = torch.cat((sorted_p[:, :1], sorted_p[:, 1:] - sorted_p[:, :-1],
                      1. - sorted_p[:, -1:]), -1)
    leaves = 1 << group.bit_length()
    mass = torch.nn.functional.pad(mass, (0, leaves - (group + 1)))
    cumulative = torch.nn.functional.pad(mass.cumsum(-1), (1, 0))
    counts = torch.full_like(p[:, :1], float(cycles))
    nodes = 1
    while nodes < leaves:
        width = leaves // nodes
        # Each conditional binomial splits the parent multinomial category.
        total = cumulative[:, width::width] - cumulative[:, :-1:width]
        left_mass = cumulative[:, width//2::width] - cumulative[:, :-1:width]
        conditional = (left_mass / total.clamp_min(1e-30)).clamp(0., 1.)
        left = torch.binomial(counts, conditional, generator=generator)
        counts = torch.stack((left, counts - left), -1).reshape(p.shape[0], nodes * 2)
        nodes *= 2
    prefix = counts.cumsum(-1)[:, :group]
    result = torch.empty_like(prefix).scatter_(-1, order, prefix)
    return result.reshape(shape)
