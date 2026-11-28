"""Dynamic group64 PoT base, one exact S/S4 flag per GU element.

P8, frozen W8, scale-aware S8/F3 sigmoid address, finite AND events and
integer Wd reduction are retained. No continuous z is requantized/resampled.
"""
from contextlib import AbstractContextManager
import math
import torch

MIN_EXP = -6
CAPS = {'x': 512., 'g': 256., 'u': 512.}


def encode(value, cap, correction=True):
    if value.shape[-1] % 64 or cap not in (256., 512.):
        raise ValueError('Complete groups64 and validated PoT caps required')
    v = value.float()
    if not bool(torch.isfinite(v).all()):
        raise ValueError('Finite GU values required')
    a = v.abs().reshape(*v.shape[:-1], -1, 64)
    maximum = a.amax(-1, keepdim=True)
    mantissa, exp = torch.frexp(maximum)
    base = torch.where(maximum == 0, MIN_EXP, exp-(mantissa == .5).int())
    base = base.clamp(MIN_EXP, int(math.log2(cap))).long()
    base_lane = base.expand_as(a).reshape_as(v)
    # Strictly two possible scales. At the exponent floor, disable the small
    # scale instead of silently introducing a third S/2 boundary case.
    eligible = base_lane >= MIN_EXP+2
    small = (v.abs() <= torch.ldexp(torch.ones_like(v), base_lane-2)) & eligible
    if not correction:
        small = torch.zeros_like(small)
    exponent = base_lane-2*small.long()
    selected = torch.ldexp(torch.ones_like(v), exponent)
    q = torch.ldexp(v.abs(), 8-exponent).round().clamp(0, 255).long()
    q = torch.where((v.abs() >= selected) & (v != 0), 256, q)
    return dict(q=q, sign=v.sign().long(), exponent=exponent,
                shift=int(math.log2(cap))-exponent, scale=selected,
                base_exponent=base_lane, small=small, floor_limited=~eligible)


class OnebitOverride(AbstractContextManager):
    def __init__(self, policy):
        if policy not in ('equivalent_four', 'gu_max64', 'gu_onebit64', 'all64_onebit'):
            raise ValueError(policy)
        import seven_forward as sf
        self.sf, self.policy = sf, policy
        self.old = sf.upstream.hard_forward
        self.statistics = {}

    def observe(self, name, value, enc):
        q = enc['q']
        row = torch.stack([q.new_tensor(q.numel()), q.sum(), (q == 0).sum(),
                           (q == 256).sum(), (value.abs() > enc['scale']).sum(),
                           enc['small'].sum(), enc['floor_limited'].sum()])
        self.statistics[name] = self.statistics.get(name, torch.zeros_like(row))+row

    def __enter__(self):
        sf = self.sf
        from wide_wd import shifted_output

        def hard(x, wg, wu, wd, module, key):
            cfg = module.config
            if not isinstance(cfg, sf.Config):
                return self.old(x, wg, wu, wd, module, key)
            with torch.no_grad(), torch.autocast(device_type=x.device.type, enabled=False):
                assert cfg.mode == 'sampled' and cfg.backend == 'exact_int8' and cfg.weight_bits == 8
                gu_codes, gu, gl, dc, dd, dl = sf.projection_state(module, wg, wu, wd)
                if self.policy == 'all64_onebit':
                    from dynamic import encode as encode_dynamic
                    xc, xs, xe, xshift, xscale = encode_dynamic(x, 64, CAPS['x'])
                    topx = torch.full_like(module.x_scales[:, 0], CAPS['x'])
                    cf, ex = sf.exact_coefficients(gl, topx, torch.ones_like(topx))
                    counts = sf.iid_shared64_counts(xc, cfg.input_samples, key.generator(x.device, module.layer, 'input_iid'))
                    rx = int(xshift.max())
                    acc = shifted_output(counts.contiguous(), xs.contiguous(), xshift.contiguous(), gu_codes, cf, cfg.input_samples, rx, 127)
                    g, u = sf.finish_fp32(acc, ex, cfg.input_samples, rx).chunk(2, -1)
                else:
                    # This is the frozen original GU arithmetic, not a digital
                    # approximation or a change to x's four-bin encoding.
                    enc = sf._encode_static_validated(x.float(), module.x_scales)
                    xc = torch.where(enc['full_one'], 256, enc['q']).long()
                    counts = sf.iid_shared64_counts(xc, cfg.input_samples, key.generator(x.device, module.layer, 'input_iid'))
                    xs, xshift = enc['sign'].long(), enc['bin_id'].long()*2
                    cf, ex = sf.exact_coefficients(gl, module.x_scales[:, 0], torch.ones_like(module.x_scales[:, 0]))
                    sf.integer_bound(x.shape[-1], cfg.input_samples, 127, 6, cf)
                    acc = sf.shifted_integer(counts, xs, xshift, gu_codes, cf, cfg.input_samples, 6, 127, cfg.backend)
                    g, u = sf.finish_fp32(acc, ex, cfg.input_samples, 6).chunk(2, -1)
                    rx = 6
                if self.policy == 'equivalent_four':
                    gq, gs, ge, gh = sf.encode_p8(g, module.g_top)
                    uq, us, ue, uh = sf.encode_p8(u, module.u_top)
                    cf, ex = sf.exact_coefficients(dl, module.g_top, module.u_top)
                    shift, rr = gh+uh, 12
                else:
                    correction = self.policy != 'gu_max64'
                    gc, uc = encode(g, CAPS['g'], correction), encode(u, CAPS['u'], correction)
                    self.observe('g', g, gc)
                    self.observe('u', u, uc)
                    gq, gs, ge = gc['q'], gc['sign'], gc['exponent']
                    uq, us, ue = uc['q'], uc['sign'], uc['exponent']
                    tg, tu = torch.full_like(module.g_top, CAPS['g']), torch.full_like(module.u_top, CAPS['u'])
                    cf, ex = sf.exact_coefficients(dl, tg, tu)
                    shift = gc['shift']+uc['shift']
                    rr = int(shift.max())
                field = sf.sigmoid_field(gq, gs, ge)
                hq = module.lut[field+128].long()
                events, _ = sf.count_events((gq, hq, uq), cfg.nonlinear_samples, key.generator(x.device, module.layer, 'and_iid'))
                acc = shifted_output(events.contiguous(), (gs*us).contiguous(), shift.contiguous(), dc, cf, cfg.nonlinear_samples, rr, 127)
                y = sf.finish_bf16(acc, ex-rr, cfg.nonlinear_samples).to(x.dtype)
                module.last_arithmetic = dict(mode='sampled', T_x=cfg.input_samples, T_AND=cfg.nonlinear_samples,
                    scale_policy=self.policy, x_policy='dynamic64' if self.policy == 'all64_onebit' else 'original_four',
                    gu_alignment_bits=rx, wd_alignment_bits=rr, exact_integer_W8=True,
                    direct_AND_to_Wd=True, and_events=int(events.sum()), and_zero=int((events == 0).sum()))
                return y, ()
        sf.upstream.hard_forward = hard
        return self

    def __exit__(self, *exc):
        self.sf.upstream.hard_forward = self.old
        return False

    def report(self):
        result = {}
        for name, row in self.statistics.items():
            n, total, zero, full, clip, small, floor = row.cpu().tolist()
            result[name] = dict(elements=n, mean_probability=total/(256*n), zero_code_fraction=zero/n,
                full_one_fraction=full/n, clipped_fraction=clip/n, small_scale_fraction=small/n,
                floor_limited_fraction=floor/n)
        return result
