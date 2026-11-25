"""T64 inference ablation: share the selected PoT scale across 64 lanes.

Only selection changes; frozen tables, W8 codes, integer reduction, scale-aware
sigmoid field/LUT, and direct AND-to-Wd arithmetic stay in seven_forward.
"""
from contextlib import AbstractContextManager
import torch


def encode_group64(value, scales):
    if value.shape[-1] % 64 or tuple(scales.shape) != (value.shape[-1] // 64, 4):
        raise ValueError('complete groups64 and four immutable scales required')
    value = value.float()
    grouped = value.reshape(*value.shape[:-1], -1, 64)
    maximum = grouped.abs().amax(-1, keepdim=True)
    chosen = scales[:, 0, None].expand_as(maximum).clone()
    index = torch.zeros_like(maximum, dtype=torch.int64)
    for i in range(1, 4):
        candidate = scales[:, i, None]
        eligible = maximum <= candidate
        chosen = torch.where(eligible, candidate, chosen)
        index = torch.where(eligible, i, index)
    scale = chosen.expand_as(grouped).reshape_as(value)
    bins = index.expand_as(grouped).reshape_as(value)
    q = (value.abs() / scale * 256).round().clamp(0, 255).to(torch.int16)
    full = (value.abs() >= scale) & (value != 0)
    probability = torch.where(full, torch.ones_like(value), q.float() / 256)
    return dict(q=q, full_one=full, bin_id=bins, scale=scale,
                sign=value.sign(), probability=probability,
                decoded=value.sign() * scale * probability)


def encode_group_p8(value, top):
    scales = top[:, None] * top.new_tensor([1., .25, .0625, .015625])[None, :]
    enc = encode_group64(value, scales)
    q = torch.where(enc['full_one'], 256, enc['q']).long()
    shift = enc['bin_id'].long() * 2
    _, exponent = torch.frexp(top.repeat_interleave(64))
    return q, enc['sign'].long(), exponent.long() - 1 - shift, shift


class ScaleOverride(AbstractContextManager):
    def __init__(self, policy):
        if policy not in ('lane', 'group64', 'x64', 'gu64'):
            raise ValueError(policy)
        import seven_forward as sf
        self.sf, self.policy = sf, policy
        self.original_x = sf._encode_static_validated
        self.original_gu = sf.encode_p8
        self.statistics = {}
        self.gu_calls = 0

    def observe(self, name, value, enc):
        q = torch.where(enc['full_one'], 256, enc['q']).long()
        row = torch.stack([q.new_tensor(q.numel()), q.sum(), (q == 0).sum(),
                           (q == 256).sum(), (value.abs() > enc['scale']).sum(),
                           *[(enc['bin_id'] == i).sum() for i in range(4)]])
        if name not in self.statistics:
            self.statistics[name] = row
        else:
            self.statistics[name] += row

    def __enter__(self):
        if self.policy in ('group64', 'x64'):
            def x(value, scales):
                enc = encode_group64(value, scales)
                self.observe('x', value, enc)
                return enc
            self.sf._encode_static_validated = x
        if self.policy in ('group64', 'gu64'):
            def gu(value, top):
                result = encode_group_p8(value, top)
                q, sign, exponent, shift = result
                scale = top.repeat_interleave(64) * (2. ** -shift)
                self.observe('g' if self.gu_calls % 2 == 0 else 'u', value,
                             dict(q=q.clamp_max(255), full_one=q == 256,
                                  bin_id=shift // 2, scale=scale))
                self.gu_calls += 1
                return result
            self.sf.encode_p8 = gu
        return self

    def __exit__(self, *exc):
        self.sf._encode_static_validated = self.original_x
        self.sf.encode_p8 = self.original_gu
        return False

    def report(self):
        result = {}
        for name, tensor in self.statistics.items():
            n, total, zeros, ones, clipped, *bins = tensor.cpu().tolist()
            result[name] = dict(elements=n, mean_probability=total / (n * 256),
                                zero_code_fraction=zeros / n, full_one_fraction=ones / n,
                                clipped_fraction=clipped / n, bin_hist=bins)
        return result
